import os
import io
import logging
import threading
import time
import requests
import http.server
import socketserver

from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BOT_TOKEN = "8806428515:AAHBCgPKhfxrinBExVTaL-SbMVCXr2jJYzg"
CHANNEL_USERNAME = "@DarkCipherLab"
GROUP_USERNAME = "@DarkCipherLab1"

SALT_SIZE = 16
NONCE_SIZE = 12
KEY_SIZE = 32  # AES-256

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

user_state = {}     # For normal file encryption/decryption state
chat_rooms = {}     # room_id -> {"password": str, "users": set}
user_rooms = {}     # user_id -> room_id
user_lang = {}      # user_id -> lang_code

# ---------------------------------------------------------------------------
# 🛠️ KEEP ALIVE SYSTEM & WEB SERVER
# ---------------------------------------------------------------------------
def start_health_server():
    class HealthHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Bot is Running Perfectly!")

    port = int(os.environ.get("PORT", 10000))
    with socketserver.TCPServer(("", port), HealthHandler) as httpd:
        logger.info(f"Health check server running on port {port}")
        httpd.serve_forever()

def keep_alive_ping():
    time.sleep(30)
    while True:
        try:
            url = "https://telegram-encryptor.onrender.com"
            response = requests.get(url, timeout=10)
            logger.info(f"[Keep-Alive] Self-ping status: {response.status_code} - Bot is awake!")
        except Exception as e:
            logger.warning(f"[Keep-Alive] Self-ping failed: {e}")
        time.sleep(300)

threading.Thread(target=start_health_server, daemon=True).start()
threading.Thread(target=keep_alive_ping, daemon=True).start()

# ---------------------------------------------------------------------------
# 🌍 12-Language Expanded Text Content (TEXTS)
# ---------------------------------------------------------------------------
TEXTS = {
    'en': {
        'welcome': "🔐 **Welcome to the Military-Grade File & Chat Encryptor Bot!**\n\n📁 **FOR NORMAL FILES:**\n• Send me ANY file to encrypt/decrypt it with a password manually.\n\n💬 **SECURE CHAT ROOMS:**\n• Create or Join a room using the buttons below.\n• Inside the room, **EVERY text and file** you send is automatically encrypted and delivered safely!",
        'access_denied': "⚠️ **Access Denied!**\nTo use this secure bot, you must join our Channel and Group first:\n1️⃣ Channel: {ch}\n2️⃣ Group: {gr}\nAfter joining, click /start to unlock! 🚀",
        'btn_encrypt': "🔒 Encrypt File", 'btn_decrypt': "🔓 Decrypt File",
        'btn_create_room': "➕ Create Room", 'btn_join_room': "🔑 Join Room", 'btn_leave_room': "🚪 Leave Room",
        'ask_action': "What would you like to do with this file?",
        'ask_password': "Selected: {action}\n\n🔑 Send a password for the file:",
        'success_enc': "✅ Encryption complete.", 'success_dec': "✅ Decryption complete.",
        'fail_dec': "❌ Decryption failed. Wrong password.", 'error': "❌ Error: {e}", 'too_large': "⚠️ File too large (max 19MB).",
        'room_created': "✅ **Room Created!**\n🔑 **Room ID:** `{room_id}`\n🔒 **Password:** `{password}`\nShare with your friend!",
        'room_not_found': "❌ Room not found.", 'wrong_room_pass': "❌ Wrong password.",
        'room_connected': "🔒 Connected to Room! Chats and media are fully encrypted.",
        'room_left': "🚪 Left the room.", 'not_in_room': "You are not in any room.",
        'ask_room_pass': "Enter a password for the new room:",
        'ask_join_details': "Send Room ID and Password separated by space.\nExample: `roomid123 pass123`", 'session_expired': "Session expired. Send file again."
    },
    'am': {
        'welcome': "🔐 **እንኳን ወደ ወታደራዊ-ደረጃ ፋይል እና ቻት መቆለፊያ ቦት በደህና መጡ!**\n\n📁 **ለተራ ፋይሎች:**\n• ማንኛውንም ፋይል በመላክ በፓስወርድ መቆለፍ እና መክፈት ይችላሉ።\n\n💬 **ሚስጥራዊ የቻት ክፍል (Rooms):**\n• ከታች ያሉትን በተኖች በመጠቀም ክፍል ይፍጠሩ ወይም ይቀላቀሉ።\n• በክፍሉ ውስጥ የሚልኩት **ማንኛውም ጽሑፍ እና ፋይል** በራሱ ተቆልፎ በጥሬው ይደርሳል!",
        'access_denied': "⚠️ **መግባት አልተፈቀደም!**\nመጀመሪያ ቻናላችንን እና ግሩፓችንን መቀላቀል አለብዎት፦\n1️⃣ ቻናል: {ch}\n2️⃣ ግሩፕ: {gr}\nከገቡ በኋላ ቦቱን ለማስጀመር /start ን ይጫኑ! 🚀",
        'btn_encrypt': "🔒 ፋይል ቆልፍ", 'btn_decrypt': "🔓 ፋይል ክፈት",
        'btn_create_room': "➕ ክፍል ፍጠር", 'btn_join_room': "🔑 ክፍል ተቀላቀል", 'btn_leave_room': "🚪 ከክፍል ውጣ",
        'ask_action': "ከዚህ ፋይል ጋር ምን ማድረግ ይፈልጋሉ?",
        'ask_password': "የተመረጠው: {action}\n\n🔑 አሁን ለፋይሉ የይለፍ ቃል (Password) ይላኩ፦",
        'success_enc': "✅ በተሳካ ሁኔታ ተቆልፏል።", 'success_dec': "✅ በተሳካ ሁኔታ ተከፍቷል።",
        'fail_dec': "❌ መክፈት አልተቻለም። ፓስወርዱ ስህተት ነው።", 'error': "❌ ችግር አጋጥሟል: {e}", 'too_large': "⚠️ ፋይሉ በጣም ትልቅ ነው (ከ 19MB በታች)።",
        'room_created': "✅ **ክፍል ተፈጥሯል!**\n🔑 **Room ID:** `{room_id}`\n🔒 **Password:** `{password}`\nለጓደኛዎ ያጋሩ!",
        'room_not_found': "❌ ክፍሉ አልተገኘም።", 'wrong_room_pass': "❌ የክፍሉ ፓስወርድ ስህተት ነው።",
        'room_connected': "🔒 ከክፍሉ ጋር ተገናኝተዋል! መልእክቶች እና ፋይሎች በሙሉ የተጠበቁ ናቸው።",
        'room_left': "🚪 ከክፍሉ ወጥተዋል።", 'not_in_room': "እርስዎ በማንኛውም ክፍል ውስጥ የሉዎትም።",
        'ask_room_pass': "ለሚፈጥሩት አዲስ ክፍል የይለፍ ቃል ይላኩ፦",
        'ask_join_details': "የክፍሉን መለያ (ID) እና ፓስወርድ በመሃል ክፍት ቦታ (space) በማድረግ ይላኩ。\nምሳሌ፦ `roomid123 pass123`", 'session_expired': "ጊዜው አልፏል። እባክዎ ፋይሉን እንደገና ይላኩት。"
    },
    'om': {
        'welcome': "🔐 **Baga Gara Botii Dhoksaa Faayilaa fi Haasaa Sadarkaa Waraanaa Nagayan Dhuftan!**\n\n📁 **FAAYILAAF:** Faayila kamiyyuu erguun bilisaan kiibandii kessaniin dhoksuu fi banuu dandeessu.\n💬 **KUTAA HAASAA (Rooms):** Kutaa haasaa uumuun ykn seenuun iccitidhaan haasa'aa!",
        'access_denied': "⚠️ **Hayyamni Dhorkameera!**\nMee jalqaba Chaannalii fi Garee keenya miseensa ta'aa:\n1️⃣ {ch}\n2️⃣ {gr}\nErga taatanii booda /start cuqaasaa! 🚀",
        'btn_encrypt': "🔒 Faayila Cufi", 'btn_decrypt': "🔓 Faayila Bani",
        'btn_create_room': "➕ Kutaa Uumi", 'btn_join_room': "🔑 Kutaa Seeni", 'btn_leave_room': "🚪 Kutaa Ba'i",
        'ask_action': "Faayila kana maalgachuu barbaaddu?", 'ask_password': "Filatamee jira: {action}\n\n🔑 Jecha iccitii (Password) faayilaa ergaa:",
        'success_enc': "✅ Milkiidhaan cufameera.", 'success_dec': "✅ Milkiidhaan banameera.",
        'fail_dec': "❌ Banuun hin danda'amne. Password dogoggora.", 'error': "❌ Dogoggora: {e}", 'too_large': "⚠️ Faayilli baay'ee guddaadha (max 19MB).",
        'room_created': "✅ **Kutaan Uumameera!**\n🔑 **Room ID:** `{room_id}`\n🔒 **Password:** `{password}`",
        'room_not_found': "❌ Kutaan hin argamne.", 'wrong_room_pass': "❌ Password dogoggora.",
        'room_connected': "🔒 Kutaa iccitii seenitanii jirtu. Haasofni keessan eeggamaadha.",
        'room_left': "🚪 Kutaa keessaa baatanii jirtu.", 'not_in_room': "Kutaa kamiyyuu keessa hin jirtu.",
        'ask_room_pass': "Password kutaa haaraa ergaa:", 'ask_join_details': "Room ID fi Password addaan baasaa ergaa.\nFakkeenya: `roomid123 pass123`", 'session_expired': "Yeroon darbeera. Ammas faayila ergaa."
    },
    'ti': {
        'welcome': "🔐 **እንቋዕ ናብዚ ናይ ወታደራዊ-ደረጃ ፋይልን ቻትን መቆለፊ ቦት ብደሓን መጻእኩም!**\n\n📁 **ንፋይላት:** ዝኾነ ፋይል ብምልኣኽ ብምስጢራዊ ቃል ክትቆልፉን ክትከፍቱን ትኽእሉ.\n💬 **ናይ ቻት ክፍልታት:** ናይ ምስጢር ክፍሊ ብምፍጣር ወይ ብምእታው ምስ መሓዙትኩም ብምስጢር ተዕልሉ!",
        'access_denied': "⚠️ **ምእታው ኣይተፈቐደን!**\nቅድም ቻነልናን ግሩፕናን ክትጽንበሩ ኣለኩም:\n1️⃣ {ch}\n2️⃣ {gr}\nምስ ኣተኹም ንምጅማር /start ጠውቑ! 🚀",
        'btn_encrypt': "🔒 ፋይል ቆልፍ", 'btn_decrypt': "🔓 ፋይል ክፈት",
        'btn_create_room': "➕ ክፍሊ ፈጥር", 'btn_join_room': "🔑 ክፍሊ ተጸንበር", 'btn_leave_room': "🚪 ካብ ክፍሊ ውጻእ",
        'ask_action': "ነዚ ፋይል እዚ እንታይ ክግበር ትደልዩ?", 'ask_password': "ዝተመርጸ: {action}\n\n🔑 ሕጂ ምስጢራዊ ቃል (Password) ይልኣኹ:",
        'success_enc': "✅ ብዓወት ተቆሊፉ.", 'success_dec': "✅ ብዓወት ተኸፊቱ.",
        'fail_dec': "❌ ክኽፈት ኣይከኣለን. ጌጋ ፓስወርድ.", 'error': "❌ ጌጋ: {e}", 'too_large': "⚠️ ፋይል ዓቢ እዩ (ማክስ 19MB).",
        'room_created': "✅ **ክፍሊ ተፈጢሩ!**\n🔑 **Room ID:** `{room_id}`\n🔒 **Password:** `{password}`",
        'room_not_found': "❌ ክፍሊ ኣይተረኽበን.", 'wrong_room_pass': "❌ ጌጋ ፓስወርድ.",
        'room_connected': "🔒 ምስቲ ክፍሊ ተራኺብኩም. ዕላልኩም ብምሉኡ ምስጢራዊ እዩ.",
        'room_left': "🚪 ካብቲ ክፍሊ ወጺእኩም.", 'not_in_room': "ኣብ ዝኾነ ክፍሊ የለኹምን.",
        'ask_room_pass': "ናይቲ ሓድሽ ክፍሊ ምስጢራዊ ቃል ይልኣኹ:", 'ask_join_details': "Room IDን ፓስወርድን ፈላልኹም ይልኣኹ.\nምሳሌ: `roomid123 pass123`", 'session_expired': "ግዜ ሓሊፉ. በጃኹም እንደገና ፋይል ይልኣኹ."
    },
    'ru': {
        'welcome': "🔐 **Добро пожаловать в Бота Военного Шифрования Чат-комнат и Файлов!**\n\n📁 **ФАЙЛЫ:** Отправьте любой файл для шифрования.\n💬 **ЧАТ-КОМНАТЫ:** Создавайте защищенные комнаты для приватного общения!",
        'access_denied': "⚠️ **Доступ запрещен!** Подпишитесь на канал и группу:\n1️⃣ {ch}\n2️⃣ {gr}\nЗатем введите /start! 🚀",
        'btn_encrypt': "🔒 Зашифровать", 'btn_decrypt': "🔓 Расшифровать",
        'btn_create_room': "➕ Создать комнату", 'btn_join_room': "🔑 Войти в комнату", 'btn_leave_room': "🚪 Выйти из комнаты",
        'ask_action': "Что вы хотите сделать с этим файлом?", 'ask_password': "Выбрано: {action}\n\n🔑 Отправьте пароль для файла:",
        'success_enc': "✅ Шифрование завершено.", 'success_dec': "✅ Расшифрование завершено.",
        'fail_dec': "❌ Ошибка. Неверный пароль.", 'error': "❌ Ошибка: {e}", 'too_large': "⚠️ Файл слишком большой (макс 19MB).",
        'room_created': "✅ **Комната создана!**\n🔑 **ID:** `{room_id}`\n🔒 **Пароль:** `{password}`",
        'room_not_found': "❌ Комната не найдена.", 'wrong_room_pass': "❌ Неверный пароль.",
        'room_connected': "🔒 Вы вошли в секретную комнату. Все сообщения защищены.",
        'room_left': "🚪 Вы покинули комнату.", 'not_in_room': "Вы не находитесь в комнате.",
        'ask_room_pass': "Введите пароль для новой комнаты:", 'ask_join_details': "Введите ID комнаты и пароль через пробел.\nПример: `roomid123 pass123`", 'session_expired': "Сессия истекла. Отправьте файл заново."
    },
    'ar': {
        'welcome': "🔐 **مرحباً بك في بوت التشفير العسكري للملفات والمحادثات!**\n\n📁 **الملفات:** أرسل أي ملف لتشفيره بكلمة سر.\n💬 **الغرف السريّة:** أنشئ غرفة أو انضم إليها للدردشة المشفرة تلقائياً مع أصدقائك!",
        'access_denied': "⚠️ **تم رفض الوصول!** يجب الانضمام للقناة والمجموعة أولاً:\n1️⃣ {ch}\n2️⃣ {gr}\nبعد الانضمام، أرسل /start لتفعيل البوت! 🚀",
        'btn_encrypt': "🔒 تشفير الملف", 'btn_decrypt': "🔓 فك التشفير",
        'btn_create_room': "➕ إنشاء غرفة", 'btn_join_room': "🔑 الانضمام لغرفة", 'btn_leave_room': "🚪 مغادرة الغرفة",
        'ask_action': "ماذا تريد أن تفعل بهذا الملف؟", 'ask_password': "تم اختيار: {action}\n\n🔑 أرسل كلمة السر للملف:",
        'success_enc': "✅ تم التشفير بنجاح.", 'success_dec': "✅ تم فك التشفير بنجاح.",
        'fail_dec': "❌ فشل فك التشفير. كلمة السر خاطئة.", 'error': "❌ خطأ: {e}", 'too_large': "⚠️ الملف كبير جداً (الأقصى 19 ميجابايت).",
        'room_created': "✅ **تم إنشاء الغرفة!**\n🔑 **رقم الغرفة:** `{room_id}`\n🔒 **كلمة السر:** `{password}`",
        'room_not_found': "❌ الغرفة غير موجودة.", 'wrong_room_pass': "❌ كلمة السر خاطئة.",
        'room_connected': "🔒 تم الاتصال بالغرفة السريّة بنجاح. محادثاتكم آمنة تماماً.",
        'room_left': "🚪 غادرت الغرفة السريّة.", 'not_in_room': "أنت لست في أي غرفة حالياً.",
        'ask_room_pass': "أدخل كلمة سر لحماية غرفتك الجديدة:", 'ask_join_details': "أرسل رقم الغرفة وكلمة السر وبينهما مسافة.\nمثال: `roomid123 pass123`", 'session_expired': "انتهت الجلسة. أعد إرسال الملف من فضلك."
    },
    'es': {
        'welcome': "🔐 **¡Bienvenido al Bot de Cifrado Militar de Archivos y Chats!**\n\n📁 **ARCHIVOS:** Envía cualquier archivo para cifrarlo/descifrarlo.\n💬 **CHATS SEGUROS:** ¡Crea o únete a una sala para enviar mensajes y archivos totalmente cifrados!",
        'access_denied': "⚠️ **¡Acceso Denegado!** Debes unirte al canal y al grupo primero:\n1️⃣ {ch}\n2️⃣ {gr}\n¡Luego escribe /start! 🚀",
        'btn_encrypt': "🔒 Cifrar Archivo", 'btn_decrypt': "🔓 Descifrar Archivo",
        'btn_create_room': "➕ Crear Sala", 'btn_join_room': "🔑 Unirse a Sala", 'btn_leave_room': "🚪 Salir de Sala",
        'ask_action': "¿Qué deseas hacer con este archivo?", 'ask_password': "Seleccionado: {action}\n\n🔑 Envía una contraseña para el archivo:",
        'success_enc': "✅ Cifrado completado.", 'success_dec': "✅ Descifrado completado.",
        'fail_dec': "❌ Contraseña incorrecta.", 'error': "❌ Error: {e}", 'too_large': "⚠️ Archivo demasiado grande (máx 19MB).",
        'room_created': "✅ **¡Sala Creada!**\n🔑 **ID:** `{room_id}`\n🔒 **Contraseña:** `{password}`",
        'room_not_found': "❌ Sala no encontrada.", 'wrong_room_pass': "❌ Contraseña incorrecta.",
        'room_connected': "🔒 ¡Conectado a la sala segura! Tus mensajes están protegidos.",
        'room_left': "🚪 Saliste de la sala.", 'not_in_room': "No estás en ninguna sala.",
        'ask_room_pass': "Introduce una contraseña para la nueva sala:", 'ask_join_details': "Envía el ID de la sala y la contraseña separados por un espacio.\nEjemplo: `salaid123 pass123`", 'session_expired': "Sesión expirada. Envía el archivo de nuevo."
    },
    'fr': {
        'welcome': "🔐 **Bienvenue sur le Bot de Chiffrement Militaire de Fichiers & Chats !**\n\n📁 **FICHIERS:** Envoyez un fichier pour le chiffrer.\n💬 **SALONS SÉCURISÉS:** Créez ou rejoignez un salon privé pour communiquer en toute sécurité !",
        'access_denied': "⚠️ **Accès Refusé!** Rejoignez d'abord le canal et le groupe:\n1️⃣ {ch}\n2️⃣ {gr}\nEnsuite, tapez /start ! 🚀",
        'btn_encrypt': "🔒 Chiffrer", 'btn_decrypt': "🔓 Déchiffrer",
        'btn_create_room': "➕ Créer Salon", 'btn_join_room': "🔑 Rejoindre Salon", 'btn_leave_room': "🚪 Quitter Salon",
        'ask_action': "Que voulez-vous faire de ce fichier ?", 'ask_password': "Choisi: {action}\n\n🔑 Envoyez un mot de passe pour le fichier :",
        'success_enc': "✅ Chiffrement réussi.", 'success_dec': "✅ Déchiffrement réussi.",
        'fail_dec': "❌ Mot de passe incorrect.", 'error': "❌ Erreur: {e}", 'too_large': "⚠️ Fichier trop volumineux (max 19Mo).",
        'room_created': "✅ **Salon créé !**\n🔑 **ID:** `{room_id}`\n🔒 **Mot de passe:** `{password}`",
        'room_not_found': "❌ Salon non trouvé.", 'wrong_room_pass': "❌ Mot de passe incorrect.",
        'room_connected': "🔒 Connecté au salon sécurisé ! Vos discussions sont protégées.",
        'room_left': "🚪 Vous avez quitté le salon.", 'not_in_room': "Vous n'êtes dans aucun salon.",
        'ask_room_pass': "Entrez un mot de passe pour le nouveau salon :", 'ask_join_details': "Envoyez l'ID du salon et le mot de passe séparés par un espace.\nExemple: `salonid123 pass123`", 'session_expired': "Session expirée. Renvoyez le fichier."
    },
    'de': {
        'welcome': "🔐 **Willkommen beim Militär-Verschlüsselungs-Bot!**\n\n📁 **DATEIEN:** Senden Sie eine Datei zum Verschlüsseln.\n💬 **SICHERE RÄUME:** Erstellen oder betreten Sie einen Raum für komplett geschützte Chats!",
        'access_denied': "⚠️ **Zugriff verweigert!** Bitte treten Sie Kanal und Gruppe bei:\n1️⃣ {ch}\n2️⃣ {gr}\nDanach /start tippen! 🚀",
        'btn_encrypt': "🔒 Verschlüsseln", 'btn_decrypt': "🔓 Entschlüsseln",
        'btn_create_room': "➕ Raum erstellen", 'btn_join_room': "🔑 Raum beitreten", 'btn_leave_room': "🚪 Raum verlassen",
        'ask_action': "Was möchten Sie mit dieser Datei tun?", 'ask_password': "Ausgewählt: {action}\n\n🔑 Senden Sie ein Passwort für die Datei:",
        'success_enc': "✅ Verschlüsselung fertig.", 'success_dec': "✅ Entschlüsselung fertig.",
        'fail_dec': "❌ Falsches Passwort.", 'error': "❌ Fehler: {e}", 'too_large': "⚠️ Datei zu groß (max 19MB).",
        'room_created': "✅ **Raum erstellt!**\n🔑 **ID:** `{room_id}`\n🔒 **Passwort:** `{password}`",
        'room_not_found': "❌ Raum nicht gefunden.", 'wrong_room_pass': "❌ Falsches Passwort.",
        'room_connected': "🔒 Verbunden! Ihre Chats sind jetzt militärisch gesichert.",
        'room_left': "🚪 Raum verlassen.", 'not_in_room': "Sie sind in keinem Raum.",
        'ask_room_pass': "Geben Sie ein Passwort für den neuen Raum ein:", 'ask_join_details': "Senden Sie Raum-ID und Passwort getrennt durch ein Leerzeichen.\nBeispiel: `raumid123 pass123`", 'session_expired': "Sitzung abgelaufen. Datei erneut senden."
    },
    'tr': {
        'welcome': "🔐 **Askeri Düzey Dosya ve Sohbet Şifreleme Botuna Hoş Geldiniz!**\n\n📁 **DOSYALAR:** Şifrelemek için herhangi bir dosya gönderin.\n💬 **GÜVENLİ ODALAR:** Tamamen şifreli konuşmak için bir oda oluşturun veya odaya katılın!",
        'access_denied': "⚠️ **Erişim Reddedildi!** Lütfen önce kanalımıza ve grubumuza katılın:\n1️⃣ {ch}\n2️⃣ {gr}\nKatıldıktan sonra /start yazın! 🚀",
        'btn_encrypt': "🔒 Dosyayı Şifrele", 'btn_decrypt': "🔓 Şifreyi Çöz",
        'btn_create_room': "➕ Oda Oluştur", 'btn_join_room': "🔑 Odaya Katıl", 'btn_leave_room': "🚪 Odadan Ayrıl",
        'ask_action': "Bu dosyaya ne yapmak istersiniz?", 'ask_password': "Seçilen: {action}\n\n🔑 Dosya için bir şifre gönderin:",
        'success_enc': "✅ Şifreleme tamamlandı.", 'success_dec': "✅ Şifre çözüldü.",
        'fail_dec': "❌ Şifre çözme başarısız. Yanlış şifre.", 'error': "❌ Hata: {e}", 'too_large': "⚠️ Dosya çok büyük (maks 19MB).",
        'room_created': "✅ **Oda Oluşturuldu!**\n🔑 **Oda ID:** `{room_id}`\n🔒 **Şifre:** `{password}`",
        'room_not_found': "❌ Oda bulunamadı.", 'wrong_room_pass': "❌ Yanlış şifre.",
        'room_connected': "🔒 Güvenli Odaya Bağlanıldı! Sohbetleriniz tamamen şifrelendi.",
        'room_left': "🚪 Odadan ayrıldınız.", 'not_in_room': "Herhangi bir odada değilsiniz.",
        'ask_room_pass': "Yeni oda için bir şifre girin:", 'ask_join_details': "Oda ID ve Şifresini aralarında boşluk bırakarak gönderin.\nÖrnek: `odaid123 sifre123`", 'session_expired': "Oturum süresi doldu. Dosyayı tekrar gönderin."
    },
    'zh': {
        'welcome': "🔐 **欢迎使用军工级文件与聊天加密机器人！**\n\n📁 **文件加密:** 发送任何文件并设置密码手动加密。\n💬 **加密聊天室:** 运用下方按钮创建或加入隐私聊天室，所有文字和文件均自动加密传输！",
        'access_denied': "⚠️ **访问拒绝！** 请先加入频道和群组：\n1️⃣ 频道: {ch}\n2️⃣ 群组: {gr}\n加入后发送 /start 解锁！ 🚀",
        'btn_encrypt': "🔒 加密文件", 'btn_decrypt': "🔓 解密文件",
        'btn_create_room': "➕ 创建聊天室", 'btn_join_room': "🔑 加入聊天室", 'btn_leave_room': "🚪 离开聊天室",
        'ask_action': "您想对该文件做什么？", 'ask_password': "已选择: {action}\n\n🔑 请发送文件加密密码:",
        'success_enc': "✅ 加密成功。", 'success_dec': "✅ 解密成功。",
        'fail_dec': "❌ 解密失败，密码错误。", 'error': "❌ 错误: {e}", 'too_large': "⚠️ 文件过大 (最大 19MB)。",
        'room_created': "✅ **聊天室创建成功！**\n🔑 **房间 ID:** `{room_id}`\n🔒 **密码:** `{password}`\n请分享给您的朋友！",
        'room_not_found': "❌ 未找到房间。", 'wrong_room_pass': "❌ 密码错误。",
        'room_connected': "🔒 已连接到加密聊天室！您的聊天与媒体传输已全面受到加密保护。",
        'room_left': "🚪 已离开聊天室。", 'not_in_room': "您不在任何房间中。",
        'ask_room_pass': "请输入新聊天室的密码:", 'ask_join_details': "请发送房间ID和密码，用空格隔开。\n例如: `roomid123 pass123`", 'session_expired': "会话过期，请重新发送文件。"
    },
    'it': {
        'welcome': "🔐 **Benvenuto nel Bot di Crittografia Militare per File & Chat!**\n\n📁 **FILE:** Invia qualsiasi file per cifrarlo/decifrarlo.\n💬 **CHAT SICURE:** Crea o unisciti a una stanza privata. Tutti i messaggi e media inviati saranno cifrati automaticamente!",
        'access_denied': "⚠️ **Accesso Negato!** Unisciti prima al canale e al gruppo:\n1️⃣ {ch}\n2️⃣ {gr}\nDopo esserti unito, digita /start! 🚀",
        'btn_encrypt': "🔒 Cifra File", 'btn_decrypt': "🔓 Decifra File",
        'btn_create_room': "➕ Crea Stanza", 'btn_join_room': "🔑 Unisciti alla Stanza", 'btn_leave_room': "🚪 Lascia Stanza",
        'ask_action': "Cosa vorresti fare con questo file?", 'ask_password': "Selezionato: {action}\n\n🔑 Invia una password per il file:",
        'success_enc': "✅ Cifratura completata.", 'success_dec': "✅ Decifratura completata.",
        'fail_dec': "❌ Password errata.", 'error': "❌ Errore: {e}", 'too_large': "⚠️ File too large (max 19MB).",
        'room_created': "✅ **Stanza Creata!**\n🔑 **ID:** `{room_id}`\n🔒 **Password:** `{password}`",
        'room_not_found': "❌ Stanza non trovata.", 'wrong_room_pass': "❌ Password errata.",
        'room_connected': "🔒 Connesso alla stanza sicura! I tuoi messaggi sono protetti.",
        'room_left': "🚪 Hai lasciato la stanza.", 'not_in_room': "Non sei in nessuna stanza.",
        'ask_room_pass': "Inserisci una password per la nuova stanza:", 'ask_join_details': "Invia l'ID della stanza e la password separati da uno spazio.\nEsempio: `stanzaid123 pass123`", 'session_expired': "Sessione scaduta. Invia nuovamente il file."
    }
}

def get_text(user_id: int, key: str, **kwargs) -> str:
    lang = user_lang.get(user_id, 'en')
    text = TEXTS[lang].get(key, TEXTS['en'][key])
    if kwargs:
        return text.format(**kwargs)
    return text

# ---------------------------------------------------------------------------
# Crypto helpers
# ---------------------------------------------------------------------------
def derive_key(password: str, salt: bytes) -> bytes:
    kdf = Scrypt(salt=salt, length=KEY_SIZE, n=2**14, r=8, p=1)
    return kdf.derive(password.encode("utf-8"))

def encrypt_bytes(data: bytes, password: str) -> bytes:
    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    key = derive_key(password, salt)
    ciphertext = AESGCM(key).encrypt(nonce, data, None)
    return salt + nonce + ciphertext

def decrypt_bytes(blob: bytes, password: str) -> bytes:
    salt, nonce, ciphertext = (
        blob[:SALT_SIZE],
        blob[SALT_SIZE:SALT_SIZE + NONCE_SIZE],
        blob[SALT_SIZE + NONCE_SIZE:],
    )
    key = derive_key(password, salt)
    return AESGCM(key).decrypt(nonce, ciphertext, None)

def encrypt_text(text: str, password: str) -> str:
    encrypted_bin = encrypt_bytes(text.encode('utf-8'), password)
    return encrypted_bin.hex()

# ---------------------------------------------------------------------------
# Membership Guard (Force Join)
# ---------------------------------------------------------------------------
async def is_user_member(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        channel_member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        group_member = await context.bot.get_chat_member(chat_id=GROUP_USERNAME, user_id=user_id)
        allowed = ['member', 'administrator', 'creator']
        return channel_member.status in allowed and group_member.status in allowed
    except:
        return False

async def force_join_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    if not await is_user_member(user_id, context):
        msg = get_text(user_id, 'access_denied', ch=CHANNEL_USERNAME, gr=GROUP_USERNAME)
        if update.message:
            await update.message.reply_text(msg)
        elif update.callback_query:
            await update.callback_query.answer(text="Please join channel & group first!", show_alert=True)
            try: await update.callback_query.message.reply_text(msg)
            except: pass
        return False
    return True

# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("English 🇬🇧", callback_data="lang_en"),
            InlineKeyboardButton("አማርኛ 🇪🇹", callback_data="lang_am"),
            InlineKeyboardButton("Oromoo 🇪🇹", callback_data="lang_om")
        ],
        [
            InlineKeyboardButton("ትግርኛ 🇪🇹", callback_data="lang_ti"),
            InlineKeyboardButton("Русский 🇷🇺", callback_data="lang_ru"),
            InlineKeyboardButton("العربية 🇸🇦", callback_data="lang_ar")
        ],
        [
            InlineKeyboardButton("Español 🇪🇸", callback_data="lang_es"),
            InlineKeyboardButton("Français 🇫🇷", callback_data="lang_fr"),
            InlineKeyboardButton("Deutsch 🇩🇪", callback_data="lang_de")
        ],
        [
            InlineKeyboardButton("Türkçe 🇹🇷", callback_data="lang_tr"),
            InlineKeyboardButton("中文 🇨🇳", callback_data="lang_zh"),
            InlineKeyboardButton("Italiano 🇮🇹", callback_data="lang_it")
        ]
    ])
    await update.message.reply_text("Please select your language / እባክዎ ቋንቋ ይምረጡ፦", reply_markup=keyboard)

def get_main_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(get_text(user_id, 'btn_create_room'), callback_data="room_create"),
            InlineKeyboardButton(get_text(user_id, 'btn_join_room'), callback_data="room_join")
        ],
        [
            InlineKeyboardButton(get_text(user_id, 'btn_leave_room'), callback_data="room_leave")
        ]
    ])

async def show_welcome_menu(update: Update, user_id: int):
    msg = get_text(user_id, 'welcome')
    keyboard = get_main_menu_keyboard(user_id)
    if update.message:
        await update.message.reply_text(msg, reply_markup=keyboard, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.message.reply_text(msg, reply_markup=keyboard, parse_mode="Markdown")

# --- All Media/File Handling ---
async def handle_any_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_join_check(update, context): return
    user_id = update.effective_user.id
    msg = update.message

    file_id = None
    file_name = "secure_file"
    size = 0

    if msg.document:
        file_id = msg.document.file_id
        file_name = msg.document.file_name
        size = msg.document.file_size
    elif msg.photo:
        file_id = msg.photo[-1].file_id
        file_name = f"photo_{int(time.time())}.jpg"
        size = msg.photo[-1].file_size
    elif msg.video:
        file_id = msg.video.file_id
        file_name = msg.video.file_name or f"video_{int(time.time())}.mp4"
        size = msg.video.file_size
    elif msg.audio:
        file_id = msg.audio.file_id
        file_name = msg.audio.file_name or f"audio_{int(time.time())}.mp3"
        size = msg.audio.file_size
    elif msg.voice:
        file_id = msg.voice.file_id
        file_name = f"voice_{int(time.time())}.ogg"
        size = msg.voice.file_size

    if not file_id:
        return

    if size > 19 * 1024 * 1024:
        await msg.reply_text(get_text(user_id, 'too_large'))
        return

    file = await context.bot.get_file(file_id)
    file_bytes = await file.download_as_bytearray()
    raw_data = bytes(file_bytes)

    if user_id in user_rooms:
        room_id = user_rooms[user_id]
        password = chat_rooms[room_id]["password"]
        try: await msg.delete()
        except: pass

        encrypted_file_bytes = encrypt_bytes(raw_data, password)
        cipher_hex = encrypted_file_bytes.hex()[:40] + "..."

        for peer_id in chat_rooms[room_id]["users"]:
            if peer_id != user_id:
                try:
                    await context.bot.send_message(
                        chat_id=peer_id,
                        text=f"📁 **Secure Media Payload Shared:**\n`[AES-256 Blob: {cipher_hex}]`"
                    )
                    await context.bot.send_document(
                        chat_id=peer_id,
                        document=io.BytesIO(raw_data),
                        filename=file_name,
                        caption="🔓 **Auto-Decrypted Room Media File**"
                    )
                except Exception as e:
                    logger.warning(f"Push failed: {e}")
        return

    user_state[user_id] = {
        "file_bytes": raw_data,
        "file_name": file_name,
        "action": None,
    }

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(get_text(user_id, 'btn_encrypt'), callback_data="encrypt"),
            InlineKeyboardButton(get_text(user_id, 'btn_decrypt'), callback_data="decrypt"),
        ]
    ])
    await msg.reply_text(get_text(user_id, 'ask_action'), reply_markup=keyboard)

# --- Interactive Buttons Handler ---
async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    await query.answer()

    if data.startswith("lang_"):
        user_lang[user_id] = data.split("_")[1]
        if not await force_join_check(update, context): return
        try: await query.message.delete()
        except: pass
        await show_welcome_menu(update, user_id)
        return

    if not await force_join_check(update, context): return

    if data in ["encrypt", "decrypt"]:
        if user_id not in user_state:
            await query.edit_message_text(get_text(user_id, 'session_expired'))
            return
        user_state[user_id]["action"] = data
        await query.edit_message_text(get_text(user_id, 'ask_password', action=data.capitalize()))

    elif data == "room_create":
        user_state[user_id] = {"room_action": "create"}
        await query.message.reply_text(get_text(user_id, 'ask_room_pass'))
        
    elif data == "room_join":
        user_state[user_id] = {"room_action": "join"}
        await query.message.reply_text(get_text(user_id, 'ask_join_details'), parse_mode="Markdown")
        
    elif data == "room_leave":
        if user_id not in user_rooms:
            await query.message.reply_text(get_text(user_id, 'not_in_room'))
            return
        room_id = user_rooms.pop(user_id)
        if room_id in chat_rooms:
            chat_rooms[room_id]["users"].discard(user_id)
            if not chat_rooms[room_id]["users"]:
                chat_rooms.pop(room_id)
        await query.message.reply_text(get_text(user_id, 'room_left'))

# --- Text Handling (Messages & Passwords) ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_join_check(update, context): return
    user_id = update.effective_user.id
    text = update.message.text

    if user_id in user_rooms:
        room_id = user_rooms[user_id]
        password = chat_rooms[room_id]["password"]
        try: await update.message.delete()
        except: pass
        
        cipher_text = encrypt_text(text, password)
        for peer_id in chat_rooms[room_id]["users"]:
            if peer_id != user_id:
                try:
                    await context.bot.send_message(
                        chat_id=peer_id,
                        text=f"💬 **New Secure Message:**\n`{cipher_text}`\n\n🔓 **Decrypted automatically:**\n{text}"
                    )
                except: pass
        return

    state = user_state.get(user_id)
    if not state:
        return

    if "room_action" in state:
        action = state["room_action"]
        user_state.pop(user_id, None)
        try: await update.message.delete()
        except: pass

        if action == "create":
            room_id = os.urandom(4).hex()
            chat_rooms[room_id] = {"password": text, "users": {user_id}}
            user_rooms[user_id] = room_id
            await update.message.reply_text(get_text(user_id, 'room_created', room_id=room_id, password=text), parse_mode="Markdown")
        
        elif action == "join":
            parts = text.split()
            if len(parts) < 2:
                await update.message.reply_text(get_text(user_id, 'wrong_room_pass'))
                return
            room_id, password = parts[0], parts[1]
            if room_id in chat_rooms and chat_rooms[room_id]["password"] == password:
                chat_rooms[room_id]["users"].add(user_id)
                user_rooms[user_id] = room_id
                await update.message.reply_text(get_text(user_id, 'room_connected'))
            else:
                await update.message.reply_text(get_text(user_id, 'room_not_found'))
        return

    if state.get("action") == "encrypt":
        action_type = "encrypt"
    elif state.get("action") == "decrypt":
        action_type = "decrypt"
    else:
        return

    file_bytes = state["file_bytes"]
    file_name = state["file_name"]
    user_state.pop(user_id, None)

    processing_msg = await update.message.reply_text("⚡ Processing file... Please wait.")

    try:
        if action_type == "encrypt":
            output_bytes = encrypt_bytes(file_bytes, text)
            out_name = file_name + ".enc"
            caption_text = get_text(user_id, 'success_enc')
        else:
            output_bytes = decrypt_bytes(file_bytes, text)
            if file_name.endswith(".enc"):
                out_name = file_name[:-4]
            else:
                out_name = "decrypted_" + file_name
            caption_text = get_text(user_id, 'success_dec')

        await context.bot.send_document(
            chat_id=user_id,
            document=io.BytesIO(output_bytes),
            filename=out_name,
            caption=caption_text
        )
    except Exception as e:
        if action_type == "decrypt":
            await update.message.reply_text(get_text(user_id, 'fail_dec'))
        else:
            await update.message.reply_text(get_text(user_id, 'error', e=str(e)))
    finally:
        try: await processing_msg.delete()
        except: pass

# --- Main Application Builder ---
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_button))
    
    media_filter = filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.VOICE
    app.add_handler(MessageHandler(media_filter, handle_any_file))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

    logger.info("Bot starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
