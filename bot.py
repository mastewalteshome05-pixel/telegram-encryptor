import os
import io
import logging

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
# Your Bot Token
BOT_TOKEN = "8806428515:AAHBCgPKhfxrinBExVTaL-SbMVCXr2jJYzg"

# Your Telegram Channel and Group Usernames (Updated with your links)
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

# In-memory database
user_state = {}     # For file encryption/decryption state
chat_rooms = {}     # room_id -> {"password": str, "users": set}
user_rooms = {}     # user_id -> room_id

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

def decrypt_text(hex_str: str, password: str) -> str:
    try:
        encrypted_bin = bytes.fromhex(hex_str)
        decrypted_bin = decrypt_bytes(encrypted_bin, password)
        return decrypted_bin.decode('utf-8')
    except Exception:
        return "[❌ Decryption Failed: Wrong Password or Corrupted Message]"

# ---------------------------------------------------------------------------
# Membership Guard (Force Join)
# ---------------------------------------------------------------------------
async def is_user_member(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        channel_member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        group_member = await context.bot.get_chat_member(chat_id=GROUP_USERNAME, user_id=user_id)
        
        allowed = ['member', 'administrator', 'creator']
        if channel_member.status in allowed and group_member.status in allowed:
            return True
        return False
    except Exception:
        return False

async def force_join_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    if not await is_user_member(user_id, context):
        msg = (
            "⚠️ Access Denied!\n\n"
            "To use this secure bot, you must join our Channel and Group first:\n"
            f"1️⃣ Join Channel: {CHANNEL_USERNAME}\n"
            f"2️⃣ Join Group: {GROUP_USERNAME}\n\n"
            "After joining, type /start to unlock the bot! 🚀"
        )
        if update.message:
            await update.message.reply_text(msg)
        elif update.callback_query:
            await update.callback_query.answer(text="Please join channel & group first!", show_alert=True)
        return False
    return True

# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_join_check(update, context): return

    await update.message.reply_text(
        "🔐 Welcome to the Military-Grade File & Chat Encryptor Bot!\n\n"
        "📁 FOR FILES:\n"
        "1. Send me any file.\n"
        "2. Choose Encrypt or Decrypt.\n"
        "3. Reply with a password.\n\n"
        "💬 FOR SECURE CHAT ROOMS:\n"
        "• /create_room <password> - Create a secure chat room\n"
        "• /join_room <room_id> <password> - Join a secure chat room\n"
        "• /leave_room - Leave current room\n\n"
        "Every message sent inside a room is fully encrypted before reaching anyone else!"
    )

# --- Secure Chat Features ---
async def create_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_join_check(update, context): return
    user_id = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /create_room <room_password>")
        return
        
    password = context.args[0]
    room_id = os.urandom(4).hex()
    
    chat_rooms[room_id] = {"password": password, "users": {user_id}}
    user_rooms[user_id] = room_id
    
    await update.message.reply_text(
        f"✅ Secure Chat Room Created!\n\n"
        f"🔑 Room ID: {room_id}\n"
        f"🔒 Password: {password}\n\n"
        f"Share the ID and Password with your friend. Any text you type now will be encrypted!"
    )

async def join_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_join_check(update, context): return
    user_id = update.effective_user.id
    
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Usage: /join_room <room_id> <password>")
        return
        
    room_id = context.args[0]
    password = context.args[1]
    
    if room_id not in chat_rooms:
        await update.message.reply_text("❌ Room not found.")
        return
        
    if chat_rooms[room_id]["password"] != password:
        await update.message.reply_text("❌ Wrong password for this room.")
        return
        
    chat_rooms[room_id]["users"].add(user_id)
    user_rooms[user_id] = room_id
    
    await update.message.reply_text("🔒 Connected to the Secure Chat Room! Your chats are now heavily encrypted.")

async def leave_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_rooms:
        await update.message.reply_text("You are not in any room.")
        return
        
    room_id = user_rooms.pop(user_id)
    if room_id in chat_rooms:
        chat_rooms[room_id]["users"].discard(user_id)
        if not chat_rooms[room_id]["users"]:
            chat_rooms.pop(room_id)
            
    await update.message.reply_text("🚪 Left the secure chat room.")

# --- Text Messaging ---
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
        decrypted_preview = text
        
        for peer_id in chat_rooms[room_id]["users"]:
            if peer_id != user_id:
                try:
                    await context.bot.send_message(
                        chat_id=peer_id,
                        text=f"💬 **New Secure Message:**\n`{cipher_text}`\n\n🔓 **Decrypted automatically:**\n{decrypted_preview}"
                    )
                except: pass
        return

    state = user_state.get(user_id)
    if not state or not state.get("action"):
        return

    try: await update.message.delete()
    except: pass

    action = state["action"]
    file_bytes = state["file_bytes"]
    file_name = state["file_name"]

    try:
        if action == "encrypt":
            result = encrypt_bytes(file_bytes, text)
            out_name = file_name + ".enc"
        else:
            result = decrypt_bytes(file_bytes, text)
            out_name = file_name[:-4] if file_name.endswith(".enc") else file_name + ".dec"

        await update.message.reply_document(
            document=io.BytesIO(result),
            filename=out_name,
            caption=f"✅ {action.capitalize()}ion complete.",
        )
    except Exception as e:
        logger.exception("Processing failed")
        if action == "decrypt":
            await update.message.reply_text("❌ Decryption failed. Wrong password.")
        else:
            await update.message.reply_text(f"❌ Something went wrong: {e}")
    finally:
        user_state.pop(user_id, None)

# --- File Operations ---
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_join_check(update, context): return
    user_id = update.effective_user.id
    document = update.message.document

    if document.file_size > 19 * 1024 * 1024:
        await update.message.reply_text("⚠️ File too large (max 20MB).")
        return

    file = await document.get_file()
    file_bytes = await file.download_as_bytearray()

    user_state[user_id] = {
        "file_bytes": bytes(file_bytes),
        "file_name": document.file_name or "file",
        "action": None,
    }

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔒 Encrypt File", callback_data="encrypt"),
            InlineKeyboardButton("🔓 Decrypt File", callback_data="decrypt"),
        ]
    ])
    await update.message.reply_text("What would you like to do with this file?", reply_markup=keyboard)

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    if not await force_join_check(update, context): return
    await query.answer()

    if user_id not in user_state:
        await query.edit_message_text("Session expired. Please send the file again.")
        return

    user_state[user_id]["action"] = query.data
    await query.edit_message_text(f"Selected: {query.data.capitalize()}\n\n🔑 Now reply with a password for the file:")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("create_room", create_room))
    app.add_handler(CommandHandler("join_room", join_room))
    app.add_handler(CommandHandler("leave_room", leave_room))
    
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(CallbackQueryHandler(handle_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Bot starting...")
    app.run_polling()

if __name__ == "__main__":
    main()