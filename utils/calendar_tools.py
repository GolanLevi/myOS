from datetime import datetime, timedelta
import dateutil.parser
from utils.gmail_connector import get_calendar_service


def escape_md(text):
    """ניקוי תווים מיוחדים עבור Markdown (טלגרם)"""
    if not text:
        return ""
    special_chars = r"_*[]()~`>#+-=|{}.!"
    for char in special_chars:
        text = text.replace(char, f"\\{char}")
    return text

def get_upcoming_events(days=7):
    """
    מושך את האירועים מהיומן עבור X הימים הקרובים.
    """
    service = get_calendar_service()
   
    # חישוב זמנים בפורמט שגוגל דורש (ISO Format)
    now = datetime.utcnow()
    time_min = now.isoformat() + 'Z'
    time_max = (now + timedelta(days=days)).isoformat() + 'Z'
   
    print(f"📅 Scanning calendar for the next {days} days...")
   
    try:
        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            maxResults=20,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
       
        events = events_result.get('items', [])
       
        if not events:
            return "No upcoming events. The calendar is free."

        agenda = []
        for event in events:
            # טיפול בפורמט הזמן
            start_raw = event['start'].get('dateTime', event['start'].get('date'))
            try:
                dt = dateutil.parser.parse(start_raw)
                start_fmt = dt.strftime("%Y-%m-%d %H:%M")
            except:
                start_fmt = start_raw
               
            summary = event.get('summary', 'Busy')
            event_id = event.get('id')

            safe_summary = escape_md(summary)
            safe_id = escape_md(event_id)
            
            agenda.append(f"[Occupied] {start_fmt} - {safe_summary} (ID: {safe_id})")
           
        return "\n".join(agenda)

    except Exception as e:
        print(f"❌ Calendar Error: {e}")
        return "Could not fetch calendar data."

def get_events_for_date(target_date_iso):
    """
    מחזיר את רשימת האירועים עבור תאריך ספציפי (Target Date).
    מקבל: 2026-02-02T15:00:00 או סתם date string
    """
    service = get_calendar_service()
    try:
        dt = dateutil.parser.parse(target_date_iso)
        # תחילת היום
        start_of_day = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        
        time_min = start_of_day.isoformat() + 'Z'
        time_max = end_of_day.isoformat() + 'Z'
        
        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])
        if not events: return "אין אירועים נוספים ביום זה."

        agenda = []
        for event in events:
            start_raw = event['start'].get('dateTime', event['start'].get('date'))
            try:
                evt_dt = dateutil.parser.parse(start_raw)
                start_fmt = evt_dt.strftime("%H:%M")
            except:
                start_fmt = start_raw
            
            summary = event.get('summary', 'Busy')

            safe_sum = escape_md(summary)
            agenda.append(f"• {start_fmt} - {safe_sum}")
            
        return "\n".join(agenda)
    except Exception as e:
        return f"Error fetching daily agenda: {e}"

def create_event(summary, start_time, end_time=None, attendees=None, location=None, description=None):
    """
    יוצר אירוע חדש ביומן.
    start_time: מחרוזת ISO 8601
    end_time: מחרוזת ISO 8601 (אופציונלי)
    attendees: רשימת כתובות אימייל (אופציונלי)
    """
    service = get_calendar_service()
    if not service:
        return None

    try:
        print(f"📅 Creating event: {summary} at {start_time}")
       
        # המרת מחרוזת זמן לאובייקט datetime
        start_dt = dateutil.parser.parse(start_time)
       
        
        # חישוב זמן סיום: אם יש end_time נשתמש בו, אחרת ברירת מחדל שעה 1
        if end_time:
             end_dt = dateutil.parser.parse(end_time)
        else:
             end_dt = start_dt + timedelta(hours=1)
        
        event = {
            'summary': summary,
            'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'Asia/Jerusalem'},
            'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'Asia/Jerusalem'},
        }

        # הוספת מיקום ותיאור אם סופקו
        if location:
            event['location'] = location
        if description:
            event['description'] = description

        # הוספת משתתפים אם יש
        if attendees:
            event['attendees'] = [{'email': email} for email in attendees]

        created_event = service.events().insert(calendarId='primary', body=event).execute()
        print(f"📅 Event created successfully: {created_event.get('htmlLink')}")
        return created_event

    except Exception as e:
        print(f"❌ Error creating event: {e}")
        return None

def update_event_time(event_id, new_start_time, new_summary=None):
    """
    מעדכן אירוע קיים (דחייה/שינוי זמן)
    """
    print(f"🔄 Updating event {event_id} to new time: {new_start_time}")
    service = get_calendar_service()

    try:
        # שליפת האירוע המקורי כדי לשמור על פרטים קיימים
        event = service.events().get(calendarId='primary', eventId=event_id).execute()
       
        # עדכון הזמנים
        start_dt = dateutil.parser.parse(new_start_time)
        
        # חישוב משך האירוע המקורי (אם רוצים לשמור עליו)
        try:
            orig_start = dateutil.parser.parse(event['start'].get('dateTime', event['start'].get('date')))
            orig_end = dateutil.parser.parse(event['end'].get('dateTime', event['end'].get('date')))
            duration = orig_end - orig_start
            end_dt = start_dt + duration
        except:
            # Fallback to 1 hour if parsing fails
            end_dt = start_dt + timedelta(hours=1) 
           
        event['start']['dateTime'] = start_dt.isoformat()
        event['end']['dateTime'] = end_dt.isoformat()
       
        if new_summary:
            event['summary'] = new_summary
           
        updated_event = service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
        print(f"✅ Event updated: {updated_event.get('htmlLink')}")
        return updated_event
       
    except Exception as e:
        print(f"❌ Error updating event: {e}")
        return None