from datetime import datetime, timedelta
import dateutil.parser
from utils.gmail_connector import get_calendar_service

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
            agenda.append(f"[Occupied] {start_fmt} - {summary}")
            
        return "\n".join(agenda)

    except Exception as e:
        print(f"❌ Calendar Error: {e}")
        return "Could not fetch calendar data."

def schedule_event(summary, start_time, end_time=None, attendees=None):
    """
    יוצר אירוע חדש ביומן.
    start_time: מחרוזת בפורמט ISO (למשל '2025-05-20T10:00:00')
    """
    service = get_calendar_service()
    
    try:
        # המרת מחרוזת זמן לאובייקט datetime
        start_dt = dateutil.parser.parse(start_time)
        
        if not end_time:
            # ברירת מחדל: פגישה של שעה
            end_dt = start_dt + timedelta(hours=1)
            end_time = end_dt.isoformat()
        
        event = {
            'summary': summary,
            'start': {'dateTime': start_time, 'timeZone': 'Asia/Jerusalem'},
            'end': {'dateTime': end_time, 'timeZone': 'Asia/Jerusalem'},
        }

        # הוספת משתתפים אם יש
        if attendees:
            event['attendees'] = [{'email': email} for email in attendees]

        created_event = service.events().insert(calendarId='primary', body=event).execute()
        print(f"📅 Event created successfully: {created_event.get('htmlLink')}")
        return created_event

    except Exception as e:
        print(f"❌ Error creating event: {e}")
        return None