from pyrogram import Client

api_id = 33452389
api_hash = "c8308b0b3f34fe7350416004751485f8"

app = Client("my_account", api_id=api_id, api_hash=api_hash)

with app:
    for dialog in app.get_dialogs():
        print(dialog.chat.id, "—", dialog.chat.title)