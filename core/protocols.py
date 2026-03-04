from enum import Enum
from typing import Dict, Any
from pydantic import BaseModel, Field

class RiskLevel(str, Enum):
    SAFE = "safe"
    MODERATE = "moderate"
    CRITICAL = "critical"

class ActionType(str, Enum):
 # --- אימייל ויומן ---
    DRAFT_EMAIL = "draft_email"
    SEND_EMAIL = "send_email"
    SCHEDULE_EVENT = "schedule_event"
    UPDATE_EVENT = "update_event"
    
    # --- סיווגים חדשים (חובה!) ---
    ACTION_REQUIRED = "action_required" 
    CRITICAL_INFO = "critical_info"     
    
    # --- כללי ---
    UPDATE = "update"
    LOG_INFO = "log_info"
    NOTIFY_USER = "notify_user"
    READ_CALENDAR = "read_calendar"
    
    # --- תחזוקה ---
    TRASH = "trash"
    TRASH_EMAIL = "trash_email"
    MARK_AS_SPAM = "mark_as_spam"
    EXECUTE_TASK = "execute_task"
    ARCHIVE = "archive"
    ADD_LABEL = "add_label"

class ActionProposal(BaseModel):
    source_agent: str = Field(..., description="Name of the agent creating this proposal")
    action_type: ActionType = Field(..., description="The type of action proposed")
    risk_level: RiskLevel = Field(..., description="Risk level determines execution flow")
    payload: Dict[str, Any] = Field(..., description="The actual data for the action")
    reasoning: str = Field(..., description="Why did the agent suggest this?")

    class Config:
        use_enum_values = True

# --- קבועים משותפים ---
HEBREW_DAYS = {6: 'ראשון', 0: 'שני', 1: 'שלישי', 2: 'רביעי', 3: 'חמישי', 4: 'שישי', 5: 'שבת'}

APPROVAL_KEYWORDS = [
    "כן", "שלח", "אשר", "בצע", "yes", "send", "confirm", "approve",
    "מאשר", "תאשר", "סבבה", "מעולה", "לך על זה", "אוקיי", "ok",
    "שלח את זה", "תשלח", "תבצע", "תעשה", "קדימה", "יאללה", "בסדר",
    "אישור", "אשר את זה", "לבצע", "לשלוח", "הכל טוב", "נשמע טוב",
    "תקבע", "אשר את הגרסה"
]

REJECTION_KEYWORDS = ["בטל", "לא", "cancel", "no", "stop"]
