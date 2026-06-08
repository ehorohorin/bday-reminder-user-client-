from pyrogram import Client, raw
from datetime import datetime, timezone
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os
import pickle

api_id = 33452389
api_hash = "c8308b0b3f34fe7350416004751485f8"
CHANNEL_ID = -1003979232316

SCOPES = ['https://www.googleapis.com/auth/contacts.readonly']

MONTHS_RU = {
    1: "январе", 2: "феврале", 3: "марте", 4: "апреле",
    5: "мае", 6: "июне", 7: "июле", 8: "августе",
    9: "сентябре", 10: "октябре", 11: "ноябре", 12: "декабре"
}

MONTHS_RU_GEN = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
}

def get_google_contacts():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('people', 'v1', credentials=creds)
    results = service.people().connections().list(
        resourceName='people/me',
        pageSize=1000,
        personFields='names,birthdays'
    ).execute()

    contacts = []
    for person in results.get('connections', []):
        names = person.get('names', [])
        birthdays = person.get('birthdays', [])
        if names and birthdays:
            name = names[0].get('displayName', '')
            bday = birthdays[0].get('date', {})
            month = bday.get('month')
            day = bday.get('day')
            if month and day:
                contacts.append({'name': name, 'month': month, 'day': day})

    return contacts

def schedule_birthdays():
    app = Client("my_account", api_id=api_id, api_hash=api_hash)

    with app:
        # Удаляем старые отложенные сообщения
        scheduled = app.invoke(
            raw.functions.messages.GetScheduledHistory(
                peer=app.resolve_peer(CHANNEL_ID),
                hash=0
            )
        )
        if scheduled.messages:
            ids = [msg.id for msg in scheduled.messages]
            app.invoke(
                raw.functions.messages.DeleteScheduledMessages(
                    peer=app.resolve_peer(CHANNEL_ID),
                    id=ids
                )
            )
            print(f"🗑 Удалено старых сообщений: {len(ids)}")
        else:
            print("📭 Старых сообщений нет")

        contacts = get_google_contacts()
        print(f"👥 Найдено контактов с ДР: {len(contacts)}")

        now = datetime.now(timezone.utc)
        year = now.year
        max_date = datetime(now.year + 1, now.month, now.day + 2, tzinfo=timezone.utc)
        total = 0

        for month in range(1, 13):
            # Именинники этого месяца
            this_month = sorted(
                [p for p in contacts if p['month'] == month],
                key=lambda x: x['day']
            )
            if not this_month:
                continue

            # Определяем год для этого месяца
            summary_date = datetime(year, month, 1, 3, 0, 0, tzinfo=timezone.utc)
            if summary_date < now:
                summary_date = datetime(year + 1, month, 1, 3, 0, 0, tzinfo=timezone.utc)
                bday_year = year + 1
            else:
                bday_year = year

            # Пропускаем если дата больше чем через 1 год
            if summary_date > max_date:
                print(f"⏩ Пропускаем {MONTHS_RU_GEN[month]} — слишком далеко")
                continue

            # Сводное сообщение на 1-е число месяца
            lines = [f"📅 День рождения в {MONTHS_RU[month]}:\n"]
            for p in this_month:
                lines.append(f"🎂 {p['day']} {MONTHS_RU_GEN[month]} — {p['name']}")
            summary_text = "\n".join(lines)

            app.send_message(
                chat_id=CHANNEL_ID,
                text=summary_text,
                schedule_date=summary_date
            )
            print(f"📅 Сводка за {MONTHS_RU_GEN[month]} запланирована на 1-е число")
            total += 1

            # Отдельное сообщение на каждый ДР
            for p in this_month:
                bday_date = datetime(year, p['month'], p['day'], 7, 0, 0, tzinfo=timezone.utc)
                if bday_date < now:
                    bday_date = datetime(year + 1, p['month'], p['day'], 7, 0, 0, tzinfo=timezone.utc)

                app.send_message(
                    chat_id=CHANNEL_ID,
                    text=f"🎉 Сегодня день рождения у {p['name']}! Поздравляем! 🎂",
                    schedule_date=bday_date
                )
                print(f"  ✅ {p['name']} — {p['day']}/{p['month']}")
                total += 1

        print(f"\n🎯 Всего запланировано: {total} сообщений")

if __name__ == "__main__":
    schedule_birthdays()