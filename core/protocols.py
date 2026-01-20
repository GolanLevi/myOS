from enum import Enum
from typing import Dict, Any
from pydantic import BaseModel, Field

class RiskLevel(str, Enum):
    SAFE = "safe"
    MODERATE = "moderate"
    CRITICAL = "critical"

class ActionType(str, Enum):
    DRAFT_EMAIL = "draft_email"
    SCHEDULE_EVENT = "schedule_event"
    LOG_INFO = "log_info"
    NOTIFY_USER = "notify_user"
    UPDATE = "update" # סוג חדש לעדכונים אקטיביים
    MARK_AS_SPAM = "mark_as_spam"    
    EXECUTE_TASK = "execute_task"   
    ARCHIVE = "archive"
    ADD_LABEL = "add_label"
    TRASH = "trash"

class ActionProposal(BaseModel):
    source_agent: str = Field(..., description="Name of the agent creating this proposal")
    action_type: ActionType = Field(..., description="The type of action proposed")
    risk_level: RiskLevel = Field(..., description="Risk level determines execution flow")
    payload: Dict[str, Any] = Field(..., description="The actual data for the action")
    reasoning: str = Field(..., description="Why did the agent suggest this?")

    class Config:
        use_enum_values = True