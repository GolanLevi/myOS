from langchain_core.tools import tool
from typing import List, Optional
from pydantic import BaseModel, Field

import utils.calendar_tools as base_calendar

# --- Input Schemas ---

class GetUpcomingEventsInput(BaseModel):
    days: int = Field(default=7, description="Number of days to look ahead. Default is 7.")

class GetEventsForDateInput(BaseModel):
    target_date_iso: str = Field(..., description="Target date in ISO format, e.g. '2026-03-18'.")

class GetFreeSlotsInput(BaseModel):
    date_iso: str = Field(..., description="The date to check for free slots, e.g. '2026-03-18'.")
    min_duration_min: int = Field(default=30, description="Minimum gap size in minutes to consider as a free slot, after applying transition and travel buffers around existing events.")

class CreateEventInput(BaseModel):
    summary: str = Field(..., description="Title of the new event. For meetings use the format '[purpose] - [person/company]'.")
    start_time: str = Field(..., description="Start time in ISO 8601 format, e.g. '2026-03-18T15:00:00'. Use Israel timezone.")
    end_time: Optional[str] = Field(None, description="End time in ISO 8601 format. If not set, defaults to 1 hour after start.")
    attendees: Optional[List[str]] = Field(None, description="List of attendee email addresses.")
    location: Optional[str] = Field(None, description="Physical or virtual location of the event.")
    description: Optional[str] = Field(None, description="Detailed description for the event body.")

class UpdateEventTimeInput(BaseModel):
    event_id: str = Field(..., description="The unique ID of the event to reschedule.")
    new_start_time: str = Field(..., description="New start time in ISO 8601 format.")
    new_summary: Optional[str] = Field(None, description="Optional new title for the event.")

class UpdateEventDetailsInput(BaseModel):
    event_id: str = Field(..., description="The unique ID of the event to update.")
    new_summary: Optional[str] = Field(None, description="New title for the event.")
    new_location: Optional[str] = Field(None, description="New location for the event.")
    new_description: Optional[str] = Field(None, description="New description/notes for the event.")
    new_attendees: Optional[List[str]] = Field(None, description="List of new attendee emails to ADD (does not replace existing ones).")

class DeleteEventInput(BaseModel):
    event_id: str = Field(..., description="The unique ID of the event to delete.")

class SearchEventInput(BaseModel):
    keyword: str = Field(..., description="Keyword or phrase to search for in event titles (e.g., 'interview', 'meeting with John').")
    days_back: int = Field(default=30, description="How many days back to search.")
    days_forward: int = Field(default=60, description="How many days forward to search.")

class GetEventDetailsInput(BaseModel):
    event_id: str = Field(..., description="The unique ID of the event to retrieve full details for.")

# --- Tools ---

@tool("get_upcoming_events", args_schema=GetUpcomingEventsInput)
def get_upcoming_events(days: int = 7) -> str:
    """Fetch the user's upcoming calendar events for the next N days.
    Returns a list of events with IDs, start times, and titles.
    Use this for a general overview of the schedule.
    """
    return base_calendar.get_upcoming_events(days)

@tool("get_events_for_date", args_schema=GetEventsForDateInput)
def get_events_for_date(target_date_iso: str) -> str:
    """Fetch all events on a specific date.
    Returns an hourly agenda including event IDs (needed for update/delete).
    """
    return base_calendar.get_events_for_date(target_date_iso)

@tool("get_free_slots", args_schema=GetFreeSlotsInput)
def get_free_slots(date_iso: str, min_duration_min: int = 30) -> str:
    """Find available (FREE) time slots on a specific date between 09:00 and 19:00 Israel time.
    IMPORTANT: Use this BEFORE suggesting a meeting time. Do NOT ask the user when they are free — find it yourself.
    The tool already applies realistic transition buffers around existing events, including larger buffers after physical meetings.
    Returns a list of free time windows with their duration in minutes.
    """
    return base_calendar.get_free_slots(date_iso, min_duration_min=min_duration_min)

@tool("search_event_by_title", args_schema=SearchEventInput)
def search_event_by_title(keyword: str, days_back: int = 30, days_forward: int = 60) -> str:
    """Search for calendar events by keyword in their title.
    Use this when the user refers to a specific event by name (e.g., 'the interview with Google', 'the dentist appointment').
    Returns matching events with their IDs, dates, and times.
    """
    return base_calendar.search_event_by_title(keyword, days_back, days_forward)

@tool("get_event_details", args_schema=GetEventDetailsInput)
def get_event_details(event_id: str) -> str:
    """Retrieve full details of a specific calendar event by ID.
    Returns title, start/end time, location, attendees, description, and link.
    Use this before proposing a change or cancellation to the user, so the confirmation message is accurate.
    """
    return base_calendar.get_event_details(event_id)

@tool("create_event", args_schema=CreateEventInput)
def create_event(
    summary: str,
    start_time: str,
    end_time: Optional[str] = None,
    attendees: Optional[List[str]] = None,
    location: Optional[str] = None,
    description: Optional[str] = None
) -> str:
    """Create a new event in the user's primary Google Calendar.
    Automatically sends invites to attendees if provided.
    HITL: Always show draft details and wait for explicit user approval before calling this.
    """
    summary = base_calendar.normalize_event_summary(summary, attendees=attendees, description=description)
    event = base_calendar.create_event(summary, start_time, end_time, attendees, location, description)
    if event:
        return f"Event '{summary}' created successfully: {event.get('htmlLink')}"
    return "Failed to create event."

@tool("update_event_time", args_schema=UpdateEventTimeInput)
def update_event_time(event_id: str, new_start_time: str, new_summary: Optional[str] = None) -> str:
    """Reschedule an existing event to a new start time, preserving its original duration.
    Automatically notifies attendees of the change.
    HITL: Always confirm with user before calling this.
    """
    normalized_summary = base_calendar.normalize_event_summary(new_summary) if new_summary else None
    event = base_calendar.update_event_time(event_id, new_start_time, normalized_summary)
    if event:
        return f"Event rescheduled successfully: {event.get('htmlLink')}"
    return "Failed to update event."

@tool("update_event_details", args_schema=UpdateEventDetailsInput)
def update_event_details(
    event_id: str,
    new_summary: Optional[str] = None,
    new_location: Optional[str] = None,
    new_description: Optional[str] = None,
    new_attendees: Optional[List[str]] = None
) -> str:
    """Update the metadata of an event (title, location, description, or add attendees) WITHOUT changing its time.
    Use this when the user wants to edit event details rather than reschedule.
    """
    event = base_calendar.update_event_details(event_id, new_summary, new_location, new_description, new_attendees)
    if event:
        return f"Event details updated: {event.get('htmlLink')}"
    return "Failed to update event details."

@tool("delete_event", args_schema=DeleteEventInput)
def delete_event(event_id: str) -> str:
    """Delete (cancel) an event from the user's primary calendar.
    Automatically sends cancellation notifications to all attendees.
    HITL: Always confirm with user before calling this.
    """
    success = base_calendar.delete_event(event_id)
    if success:
        return f"Event {event_id} cancelled and deleted successfully."
    return f"Failed to delete event {event_id}."

# --- Final Tools List ---

calendar_tools = [
    get_upcoming_events,
    get_events_for_date,
    get_free_slots,
    search_event_by_title,
    get_event_details,
    create_event,
    update_event_time,
    update_event_details,
    delete_event,
]
