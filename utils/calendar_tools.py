from datetime import datetime, timedelta, timezone
import dateutil.parser
import re
from utils.gmail_connector import get_calendar_service

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

TZ_IL = ZoneInfo("Asia/Jerusalem")
VIRTUAL_LOCATION_RE = re.compile(r"(zoom|meet|teams|webex|online|remote|טלפון|phone|virtual)", re.IGNORECASE)
FIXED_ACTIVITY_RE = re.compile(r"(שיעור|פרטי|gym|מכון|class|lesson|אימון|טיפול|doctor|dentist)", re.IGNORECASE)


def _normalize_whitespace(text):
    return " ".join((text or "").split()).strip()


def _humanize_email_local_part(email):
    local = (email or "").split("@")[0]
    if not local:
        return ""
    local = re.sub(r"[._-]+", " ", local)
    return _normalize_whitespace(local).title()


def _extract_counterparty_name(summary, attendees=None, description=None):
    summary = _normalize_whitespace(summary)
    description = description or ""

    paren_match = re.search(r"\(([^()]{2,})\)\s*$", summary)
    if paren_match:
        return _normalize_whitespace(paren_match.group(1))

    with_match = re.search(r"(?:עם|with)\s+([^-,|()]+)$", summary, re.IGNORECASE)
    if with_match:
        return _normalize_whitespace(with_match.group(1))

    if attendees:
        humanized = _humanize_email_local_part(attendees[0])
        if humanized:
            return humanized

    desc_patterns = [
        r"(?:מאת|שולח)\s*[:\-]\s*([^\n|]+)",
        r"(?:from|sender)\s*[:\-]\s*([^\n|]+)",
    ]
    for pattern in desc_patterns:
        match = re.search(pattern, description, re.IGNORECASE)
        if match:
            candidate = _normalize_whitespace(match.group(1))
            if candidate:
                return re.sub(r"\s*<[^>]+>\s*$", "", candidate).strip()

    return ""


def normalize_event_summary(summary, attendees=None, description=None):
    summary = _normalize_whitespace(summary) or "פגישה"
    if " - " in summary:
        return summary
    if ":" in summary:
        left, right = summary.split(":", 1)
        left = _normalize_whitespace(left)
        right = _normalize_whitespace(right)
        if left and right:
            return f"{left} - {right}"

    counterparty = _extract_counterparty_name(summary, attendees=attendees, description=description)
    purpose = summary
    purpose = re.sub(r"\(([^()]{2,})\)\s*$", "", purpose).strip()
    purpose = re.sub(r"\s*(?:עם|with)\s+[^-,|()]+$", "", purpose, flags=re.IGNORECASE).strip()
    purpose = re.sub(r"\s*[:-]\s*$", "", purpose).strip()

    if counterparty and counterparty.lower() not in purpose.lower():
        return f"{purpose} - {counterparty}"
    return summary


def _looks_virtual(location, summary):
    haystack = f"{location or ''} {summary or ''}"
    return bool(VIRTUAL_LOCATION_RE.search(haystack))


def _event_buffers(event):
    summary = event.get("summary", "")
    location = event.get("location", "")

    if _looks_virtual(location, summary):
        return 10, 15

    if location:
        return 30, 45

    if FIXED_ACTIVITY_RE.search(summary):
        return 30, 45

    return 15, 30


def _now_il():
    """Returns current datetime in Israel timezone."""
    return datetime.now(TZ_IL)


def escape_md(text):
    """ניקוי תווים מיוחדים עבור Markdown (טלגרם)"""
    if not text:
        return ""
    special_chars = r"_*[]()~`>#+-=|{}.!"
    for char in special_chars:
        text = text.replace(char, f"\\{char}")
    return text


def _format_event_line(event):
    """Helper - formats a single event into a readable line including its ID."""
    start_raw = event['start'].get('dateTime', event['start'].get('date'))
    try:
        dt = dateutil.parser.parse(start_raw)
        start_fmt = dt.strftime("%H:%M")
    except Exception:
        start_fmt = start_raw

    end_raw = event['end'].get('dateTime', event['end'].get('date'))
    try:
        end_dt = dateutil.parser.parse(end_raw)
        end_fmt = end_dt.strftime("%H:%M")
    except Exception:
        end_fmt = ""

    summary = event.get('summary', 'Busy')
    event_id = event.get('id', '')
    return {
        "id": event_id,
        "start": start_fmt,
        "end": end_fmt,
        "summary": summary,
        "line": f"• {start_fmt}-{end_fmt} | {summary} (ID: {event_id})"
    }


def get_upcoming_events(days=7):
    """
    מושך את האירועים מהיומן עבור X הימים הקרובים.
    FIXED: Uses Israel timezone, not UTC.
    """
    service = get_calendar_service()

    now = _now_il()
    time_min = now.isoformat()
    time_max = (now + timedelta(days=days)).isoformat()

    print(f"📅 Scanning calendar for the next {days} days (IL time)...")

    try:
        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            maxResults=30,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])

        if not events:
            return "No upcoming events. The calendar is free."

        agenda = []
        for event in events:
            start_raw = event['start'].get('dateTime', event['start'].get('date'))
            try:
                dt = dateutil.parser.parse(start_raw)
                start_fmt = dt.strftime("%d.%m.%Y %H:%M")
            except Exception:
                start_fmt = start_raw

            summary = event.get('summary', 'Busy')
            event_id = event.get('id')
            agenda.append(f"[{start_fmt}] {summary} (ID: {event_id})")

        return "\n".join(agenda)

    except Exception as e:
        print(f"❌ Calendar Error: {e}")
        return "Could not fetch calendar data."


def get_events_for_date(target_date_iso):
    """
    מחזיר את רשימת האירועים עבור תאריך ספציפי.
    IMPROVED: Returns event IDs and end times for full context.
    """
    service = get_calendar_service()
    try:
        dt = dateutil.parser.parse(target_date_iso)
        # Use Israel timezone
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ_IL)

        start_of_day = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        events_result = service.events().list(
            calendarId='primary',
            timeMin=start_of_day.isoformat(),
            timeMax=end_of_day.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])
        if not events:
            return "No events on this date."

        lines = []
        for event in events:
            entry = _format_event_line(event)
            lines.append(entry["line"])

        return "\n".join(lines)

    except Exception as e:
        return f"Error fetching daily agenda: {e}"


def get_free_slots(date_iso, work_start_hour=9, work_end_hour=19, min_duration_min=30):
    """
    מחשב ומחזיר חלונות זמן פנויים ביום נתון.
    REAL IMPLEMENTATION: Calculates actual gaps between events.
    """
    service = get_calendar_service()
    try:
        dt = dateutil.parser.parse(date_iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ_IL)

        start_of_window = dt.replace(hour=work_start_hour, minute=0, second=0, microsecond=0)
        end_of_window = dt.replace(hour=work_end_hour, minute=0, second=0, microsecond=0)

        events_result = service.events().list(
            calendarId='primary',
            timeMin=start_of_window.isoformat(),
            timeMax=end_of_window.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])

        # Build occupied intervals with realistic transition buffers
        occupied = []
        for event in events:
            s_raw = event['start'].get('dateTime', event['start'].get('date'))
            e_raw = event['end'].get('dateTime', event['end'].get('date'))
            try:
                s = dateutil.parser.parse(s_raw)
                e = dateutil.parser.parse(e_raw)
                if s.tzinfo is None: s = s.replace(tzinfo=TZ_IL)
                if e.tzinfo is None: e = e.replace(tzinfo=TZ_IL)
                before_buffer_min, after_buffer_min = _event_buffers(event)
                buffered_start = max(start_of_window, s - timedelta(minutes=before_buffer_min))
                buffered_end = min(end_of_window, e + timedelta(minutes=after_buffer_min))
                occupied.append((buffered_start, buffered_end, event.get('summary', 'Busy')))
            except Exception:
                continue

        # Sort occupied
        occupied.sort(key=lambda x: x[0])

        merged_occupied = []
        for start_dt, end_dt, summary in occupied:
            if not merged_occupied or start_dt > merged_occupied[-1][1]:
                merged_occupied.append([start_dt, end_dt, summary])
            else:
                merged_occupied[-1][1] = max(merged_occupied[-1][1], end_dt)

        # Find gaps
        free_slots = []
        cursor = start_of_window
        for (s, e, _) in merged_occupied:
            if cursor < s:
                gap_minutes = int((s - cursor).total_seconds() / 60)
                if gap_minutes >= min_duration_min:
                    free_slots.append(f"• {cursor.strftime('%H:%M')} - {s.strftime('%H:%M')} ({gap_minutes} min free)")
            cursor = max(cursor, e)

        # Gap at the end
        if cursor < end_of_window:
            gap_minutes = int((end_of_window - cursor).total_seconds() / 60)
            if gap_minutes >= min_duration_min:
                free_slots.append(f"• {cursor.strftime('%H:%M')} - {end_of_window.strftime('%H:%M')} ({gap_minutes} min free)")

        date_str = dt.strftime("%d.%m.%Y")
        if not free_slots:
            return f"No free slots on {date_str} between {work_start_hour}:00 and {work_end_hour}:00."

        return f"Free slots on {date_str}:\n" + "\n".join(free_slots)

    except Exception as e:
        return f"Error calculating free slots: {e}"


def search_event_by_title(keyword, days_back=30, days_forward=60):
    """
    מחפש אירועים לפי מילת מפתח בכותרת.
    """
    service = get_calendar_service()
    try:
        now = _now_il()
        time_min = (now - timedelta(days=days_back)).isoformat()
        time_max = (now + timedelta(days=days_forward)).isoformat()

        events_result = service.events().list(
            calendarId='primary',
            q=keyword,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime',
            maxResults=10
        ).execute()

        events = events_result.get('items', [])
        if not events:
            return f"No events found matching '{keyword}'."

        lines = []
        for event in events:
            entry = _format_event_line(event)
            start_raw = event['start'].get('dateTime', event['start'].get('date', ''))
            try:
                dt = dateutil.parser.parse(start_raw)
                date_str = dt.strftime("%d.%m.%Y %H:%M")
            except Exception:
                date_str = start_raw
            lines.append(f"• {date_str} | {entry['summary']} (ID: {entry['id']})")

        return f"Events matching '{keyword}':\n" + "\n".join(lines)

    except Exception as e:
        return f"Error searching events: {e}"


def get_event_details(event_id):
    """
    מחזיר את כל הפרטים של אירוע לפי ID (משתתפים, תיאור, מיקום).
    """
    service = get_calendar_service()
    try:
        event = service.events().get(calendarId='primary', eventId=event_id).execute()

        start_raw = event['start'].get('dateTime', event['start'].get('date'))
        end_raw = event['end'].get('dateTime', event['end'].get('date'))
        try:
            start_fmt = dateutil.parser.parse(start_raw).strftime("%d.%m.%Y %H:%M")
            end_fmt = dateutil.parser.parse(end_raw).strftime("%d.%m.%Y %H:%M")
        except Exception:
            start_fmt = start_raw
            end_fmt = end_raw

        attendees = event.get('attendees', [])
        attendee_list = ", ".join([a.get('email', '') for a in attendees]) if attendees else "None"

        return (
            f"Event: {event.get('summary', 'N/A')}\n"
            f"ID: {event.get('id')}\n"
            f"Start: {start_fmt} | End: {end_fmt}\n"
            f"Location: {event.get('location', 'N/A')}\n"
            f"Attendees: {attendee_list}\n"
            f"Description: {event.get('description', 'N/A')}\n"
            f"Status: {event.get('status', 'N/A')}\n"
            f"Link: {event.get('htmlLink', 'N/A')}"
        )
    except Exception as e:
        return f"Error fetching event details: {e}"


def update_event_details(event_id, new_summary=None, new_location=None, new_description=None, new_attendees=None):
    """
    מעדכן את פרטי האירוע (כותרת, מיקום, תיאור, משתתפים) ללא שינוי זמן.
    """
    service = get_calendar_service()
    try:
        event = service.events().get(calendarId='primary', eventId=event_id).execute()

        if new_summary:
            event['summary'] = normalize_event_summary(
                new_summary,
                attendees=[a.get('email') for a in event.get('attendees', []) if a.get('email')],
                description=new_description or event.get('description', ''),
            )
        if new_location:
            event['location'] = new_location
        if new_description:
            event['description'] = new_description
        if new_attendees is not None:
            existing = [a for a in event.get('attendees', []) if a.get('self')]
            new_entries = [{'email': e} for e in new_attendees]
            event['attendees'] = existing + new_entries

        updated = service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
        print(f"✅ Event details updated: {updated.get('htmlLink')}")
        return updated

    except Exception as e:
        print(f"❌ Error updating event details: {e}")
        return None


def create_event(summary, start_time, end_time=None, attendees=None, location=None, description=None):
    """
    יוצר אירוע חדש ביומן.
    """
    service = get_calendar_service()
    if not service:
        return None

    try:
        summary = normalize_event_summary(summary, attendees=attendees, description=description)
        print(f"📅 Creating event: {summary} at {start_time}")

        start_dt = dateutil.parser.parse(start_time)
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=TZ_IL)

        if end_time:
            end_dt = dateutil.parser.parse(end_time)
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=TZ_IL)
        else:
            end_dt = start_dt + timedelta(hours=1)

        event = {
            'summary': summary,
            'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'Asia/Jerusalem'},
            'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'Asia/Jerusalem'},
        }

        if location:
            event['location'] = location
        if description:
            event['description'] = description
        if attendees:
            event['attendees'] = [{'email': email} for email in attendees]

        created_event = service.events().insert(
            calendarId='primary', body=event, sendUpdates='all'
        ).execute()
        print(f"📅 Event created: {created_event.get('htmlLink')}")
        return created_event

    except Exception as e:
        print(f"❌ Error creating event: {e}")
        return None


def update_event_time(event_id, new_start_time, new_summary=None):
    """
    מעדכן אירוע קיים (דחייה/שינוי זמן).
    FIXED: Preserves Israel timezone on updated times.
    """
    print(f"🔄 Updating event {event_id} to new time: {new_start_time}")
    service = get_calendar_service()

    try:
        event = service.events().get(calendarId='primary', eventId=event_id).execute()

        start_dt = dateutil.parser.parse(new_start_time)
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=TZ_IL)

        try:
            orig_start = dateutil.parser.parse(event['start'].get('dateTime', event['start'].get('date')))
            orig_end = dateutil.parser.parse(event['end'].get('dateTime', event['end'].get('date')))
            duration = orig_end - orig_start
            end_dt = start_dt + duration
        except Exception:
            end_dt = start_dt + timedelta(hours=1)

        event['start'] = {'dateTime': start_dt.isoformat(), 'timeZone': 'Asia/Jerusalem'}
        event['end'] = {'dateTime': end_dt.isoformat(), 'timeZone': 'Asia/Jerusalem'}

        if new_summary:
            event['summary'] = normalize_event_summary(new_summary, description=event.get('description', ''))

        updated_event = service.events().update(
            calendarId='primary', eventId=event_id, body=event, sendUpdates='all'
        ).execute()
        print(f"✅ Event updated: {updated_event.get('htmlLink')}")
        return updated_event

    except Exception as e:
        print(f"❌ Error updating event: {e}")
        return None


def delete_event(event_id):
    """
    מוחק אירוע מהיומן לפי ה-ID שלו.
    """
    print(f"🗑️ Deleting event {event_id}...")
    service = get_calendar_service()
    try:
        service.events().delete(
            calendarId='primary', eventId=event_id, sendUpdates='all'
        ).execute()
        print(f"✅ Event {event_id} deleted successfully.")
        return True
    except Exception as e:
        print(f"❌ Error deleting event: {e}")
        return False
