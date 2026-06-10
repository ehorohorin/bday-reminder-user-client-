from pyrogram import Client, raw
from datetime import datetime, timezone, timedelta
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os
import pickle

from config import (
    API_ID, API_HASH, CHANNEL_ID, SESSION_NAME,
    GOOGLE_CREDENTIALS_FILE, GOOGLE_TOKEN_FILE,
    HASHTAG, TELEGRAM_SCHEDULE_LIMIT,
)

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
    if os.path.exists(GOOGLE_TOKEN_FILE):
        with open(GOOGLE_TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(GOOGLE_CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(GOOGLE_TOKEN_FILE, 'wb') as token:
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


def iter_days_from(start: datetime, count: int):
    
    day = start.replace(hour=0, minute=0, second=0, microsecond=0)
    for _ in range(count):
        yield day
        day += timedelta(days=1)


def birthdays_on_day(contacts, day: datetime):
    
    return [p for p in contacts if p['month'] == day.month and p['day'] == day.day]


def birthdays_in_week(contacts, week_start: datetime):
    
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
                    result.append({'name': p['name'], 'day': p['day'], 'month': p['month']})
                    break
            except ValueError:
                pass
    result.sort(key=lambda x: (x['month'], x['day']))
    return result


def birthdays_in_month(contacts, month: int):
  
    return sorted([p for p in contacts if p['month'] == month], key=lambda x: x['day'])


def build_daily_message(contacts, day: datetime):
 
    blocks = []

    
    if day.month == 1 and day.day == 1:
        sorted_contacts = sorted(contacts, key=lambda x: (x['month'], x['day']))
        lines = ["🎊 Все дни рождения в этом году:\n"]
        for p in sorted_contacts:
            lines.append(f"  🎂 {p['day']} {MONTHS_RU_GEN[p['month']]} — {p['name']}")
        blocks.append("\n".join(lines))

 
    if day.day == 1:
        month_bdays = birthdays_in_month(contacts, day.month)
        if month_bdays:
            lines = [f"📅 Дни рождения в {MONTHS_RU[day.month]}:\n"]
            for p in month_bdays:
                lines.append(f"  🎂 {p['day']} {MONTHS_RU_GEN[day.month]} — {p['name']}")
            blocks.append("\n".join(lines))

   
    if day.weekday() == 0:
        week_bdays = birthdays_in_week(contacts, day)
        if week_bdays:
            lines = ["🗓 Дни рождения на этой неделе:\n"]
            for p in week_bdays:
                lines.append(f"  🎂 {p['day']} {MONTHS_RU_GEN[p['month']]} — {p['name']}")
            blocks.append("\n".join(lines))


    today_bdays = birthdays_on_day(contacts, day)
    if today_bdays:
        if len(today_bdays) == 1:
            blocks.append(f"🎉 Сегодня день рождения у {today_bdays[0]['name']}! Поздравляем! 🎂")
        else:
            names = ", ".join(p['name'] for p in today_bdays)
            blocks.append(f"🎉 Сегодня дни рождения у: {names}! Поздравляем! 🎂")

    if not blocks:
        return None

    return "\n\n".join(blocks) + f"\n\n{HASHTAG}"


def schedule_birthdays():
    app = Client(SESSION_NAME, api_id=API_ID, api_hash=API_HASH)

    with app:
        
        scheduled = app.invoke(
            raw.functions.messages.GetScheduledHistory(
                peer=app.resolve_peer(CHANNEL_ID),
                hash=0
            )
        )

        our_ids = []
        foreign_count = 0
        for msg in scheduled.messages:
            text = getattr(msg, 'message', '') or ''
            if HASHTAG in text:
                our_ids.append(msg.id)
            else:
                foreign_count += 1

        if our_ids:
            app.invoke(
                raw.functions.messages.DeleteScheduledMessages(
                    peer=app.resolve_peer(CHANNEL_ID),
                    id=our_ids
                )
            )
            print(f"🗑 Удалено наших сообщений: {len(our_ids)}")
        else:
            print("📭 Наших старых сообщений нет")

        if foreign_count:
            print(f"⚠️  Чужих сообщений (не трогаем): {foreign_count}")

        # Доступный лимит с учётом чужих сообщений
        available_slots = TELEGRAM_SCHEDULE_LIMIT - foreign_count
        if available_slots <= 0:
            print(f"🚫 Лимит исчерпан чужими сообщениями ({foreign_count}/{TELEGRAM_SCHEDULE_LIMIT}), выходим")
            return

        contacts = get_google_contacts()
        print(f"👥 Найдено контактов с ДР: {len(contacts)}")

        now = datetime.now(timezone.utc)
        final_messages = []
        MAX_DAYS = 366  

        for day in iter_days_from(now, MAX_DAYS):
            if len(final_messages) >= available_slots:
                break

            
            if day.month == 1 and day.day == 1:
                send_hour = 1
            elif day.day == 1:
                send_hour = 3
            elif day.weekday() == 0:
                send_hour = 6
            else:
                send_hour = 7

            send_time = day.replace(hour=send_hour, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)

            if send_time <= now:
                continue

            text = build_daily_message(contacts, day)
            if text:
                final_messages.append((send_time, text))

        
        for schedule_date, text in final_messages:
            app.send_message(
                chat_id=CHANNEL_ID,
                text=text,
                schedule_date=schedule_date
            )

        print(f"\n🎯 Итого запланировано: {len(final_messages)} сообщений")
        print(f"📊 Слотов использовано: {len(final_messages) + foreign_count}/{TELEGRAM_SCHEDULE_LIMIT}")

        if len(final_messages) == available_slots:
            last_date = final_messages[-1][0].strftime("%d.%m.%Y")
            print(f"⚠️  Достигнут лимит. Последнее сообщение: {last_date}")
        else:
            print("✅")


if __name__ == "__main__":
    schedule_birthdays()
