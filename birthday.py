from pyrogram import Client, raw
from datetime import datetime, timezone, timedelta
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os
import pickle

api_id = #ваше значение
api_hash = "ваше значние"
CHANNEL_ID = ваше значние

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

TELEGRAM_SCHEDULE_LIMIT = 100

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


def get_next_mondays(from_date: datetime, count: int):
    mondays = []
    days_ahead = (7 - from_date.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    first_monday = from_date + timedelta(days=days_ahead)
    first_monday = first_monday.replace(hour=6, minute=0, second=0, microsecond=0)
    for i in range(count):
        mondays.append(first_monday + timedelta(weeks=i))
    return mondays


def get_birthdays_in_week(contacts, week_start: datetime):
    result = []
    for p in contacts:
        for year_offset in [0, 1]:
            try:
                bday = datetime(
                    week_start.year + year_offset,
                    p['month'], p['day'],
                    tzinfo=timezone.utc
                )
                if week_start <= bday < week_start + timedelta(days=7):
                    result.append({
                        'name': p['name'],
                        'day': p['day'],
                        'month': p['month'],
                        'date': bday
                    })
                    break
            except ValueError:
                pass
    result.sort(key=lambda x: x['date'])
    return result


def schedule_birthdays():
    app = Client("my_account", api_id=api_id, api_hash=api_hash)

    with app:
        # удаление старых
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

        
        priority_1 = []  
        priority_2 = []  
        priority_3 = []  
        priority_4 = [] 

#год
        for year_offset in [0, 1]:
            jan_first = datetime(year + year_offset, 1, 1, 1, 0, 0, tzinfo=timezone.utc)
            if jan_first > now:
                sorted_contacts = sorted(contacts, key=lambda x: (x['month'], x['day']))
                lines = ["🎊 Все дни рождения в этом году:\n"]
                for p in sorted_contacts:
                    lines.append(f"🎂 {p['day']} {MONTHS_RU_GEN[p['month']]} — {p['name']}")
                priority_1.append((jan_first, "\n".join(lines)))
                break  

#day
        for p in contacts:
            for year_offset in [0, 1]:
                try:
                    bday_date = datetime(year + year_offset, p['month'], p['day'], 7, 0, 0, tzinfo=timezone.utc)
                    if bday_date >= now:
                        priority_2.append((
                            bday_date,
                            f"🎉 Сегодня день рождения у {p['name']}! Поздравляем! 🎂"
                        ))
                        break
                except ValueError:
                    pass  

        priority_2.sort(key=lambda x: x[0])

#month
        for month in range(1, 13):
            this_month = sorted(
                [p for p in contacts if p['month'] == month],
                key=lambda x: x['day']
            )
            if not this_month:
                continue
            for year_offset in [0, 1]:
                summary_date = datetime(year + year_offset, month, 1, 3, 0, 0, tzinfo=timezone.utc)
                if summary_date >= now:
                    lines = [f"📅 Дни рождения в {MONTHS_RU[month]}:\n"]
                    for p in this_month:
                        lines.append(f"🎂 {p['day']} {MONTHS_RU_GEN[month]} — {p['name']}")
                    priority_3.append((summary_date, "\n".join(lines)))
                    break

        priority_3.sort(key=lambda x: x[0])

#week
        mondays = get_next_mondays(now, count=54)
        for monday in mondays:
            week_birthdays = get_birthdays_in_week(contacts, monday)
            if not week_birthdays:
                continue
            lines = ["🗓 Дни рождения на этой неделе:\n"]
            for p in week_birthdays:
                lines.append(f"🎂 {p['day']} {MONTHS_RU_GEN[p['month']]} — {p['name']}")
            priority_4.append((monday, "\n".join(lines)))

        final_messages = []
        remaining = TELEGRAM_SCHEDULE_LIMIT

        for bucket_name, bucket in [
            ("Годовые",    priority_1),
            ("Личные ДР",  priority_2),
            ("Месячные",   priority_3),
            ("Недельные",  priority_4),
        ]:
            added = 0
            for msg in bucket:
                if remaining <= 0:
                    break
                final_messages.append(msg)
                remaining -= 1
                added += 1
            print(f"{bucket_name}: запланировано {added} / {len(bucket)}")

        # oтправляем
        final_messages.sort(key=lambda x: x[0])
        for schedule_date, text in final_messages:
            app.send_message(
                chat_id=CHANNEL_ID,
                text=text,
                schedule_date=schedule_date
            )

        print(f"\n Итого запланировано: {len(final_messages)} сообщений")
        total_skipped = (len(priority_1) + len(priority_2) + len(priority_3) + len(priority_4)) - len(final_messages)
        if total_skipped > 0:
            print(f"⚠️  Не вошло в лимит: {total_skipped} сообщений (в основном недельные сводки)")


if __name__ == "__main__":
    schedule_birthdays()
