from pyrogram import Client
from config import API_ID, API_HASH, SESSION_NAME

app = Client(SESSION_NAME, api_id=API_ID, api_hash=API_HASH)

with app:
    for dialog in app.get_dialogs():
        print(dialog.chat.id, "—", dialog.chat.title)
