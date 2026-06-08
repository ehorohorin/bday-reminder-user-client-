from pyrogram import Client

api_id = #ваше значение
api_hash = "ваше значние"

app = Client("my_account", api_id=api_id, api_hash=api_hash)

with app:
    for dialog in app.get_dialogs():
        print(dialog.chat.id, "—", dialog.chat.title)
