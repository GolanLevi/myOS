import json
import os
from datetime import datetime
from core.protocols import ActionProposal, RiskLevel, ActionType
from core.state_manager import StateManager  # <-- ייבוא המנהל החדש
from utils.calendar_tools import get_upcoming_events, schedule_event 
from utils.gmail_tools import create_draft, trash_email, archive_email, add_label_to_email

class AgentManager:
    def __init__(self):
        self.agents = []
        self.log_file = "logs/audit_log.json"
        self.state_manager = StateManager() # <-- אתחול ה-State Manager

        # יצירת קובץ לוגים אם לא קיים
        if not os.path.exists("logs"):
            os.makedirs("logs")
        if not os.path.exists(self.log_file):
            with open(self.log_file, "w") as f: json.dump([], f)

    def register_agent(self, agent):
        self.agents.append(agent)

    def process_incoming_request(self, user_input: str, metadata: dict = None):
        """
        metadata: מילון שמכיל מידע טכני כמו email_id
        """
        # 1. ניתוב (Routing) - החלטה איזה סוכן צריך לטפל בבקשה
        selected_agent = self._route_request(user_input)
        
        if not selected_agent: return

        print(f"\n🤖 Agent '{selected_agent.name}' selected for analysis...")
        
        # 2. ה-AI מנתח ומציע פעולה
        proposal = selected_agent.process(user_input)
        
        if not proposal:
            print("❌ No proposal generated.")
            return

        # 3. המנהל מחליט אם לאשר
        self._handle_proposal(proposal, metadata)

    def _route_request(self, user_input: str):
        """Logic to decide which agent to call based on keywords"""
        user_input_lower = user_input.lower()
        
        # Keywords for Finance
        if any(w in user_input_lower for w in ['invoice', 'bill', 'receipt', 'payment', 'salary', 'חשבונית', 'קבלה', 'תשלום']):
            return next((a for a in self.agents if a.name == 'finance_agent'), None)
            
        # Keywords for Secretariat (Scheduling)
        if any(w in user_input_lower for w in ['schedule', 'meeting', 'calendar', 'invite', 'zoom', 'פגישה', 'מפגש', 'יומן']):
            return next((a for a in self.agents if a.name == 'secretariat_agent'), None)

        # Default: Secretariat (for general emails) or Info
        # נבחר במזכירות כברירת מחדל לטיפול במיילים כלליים
        return next((a for a in self.agents if a.name == 'secretariat_agent'), None)

    def _handle_proposal(self, proposal: ActionProposal, metadata: dict):
        print(f"💡 Proposed Action: {proposal.action_type} | Risk: {proposal.risk_level}")
        
        # זיהוי משתמש (כרגע קבוע ל-'admin', בעתיד נוציא מ-metadata)
        user_id = "admin" 

        # 1. פעולות שמחייבות אישור (NOTIFY_USER או סיכון גבוה)
        if proposal.action_type == ActionType.NOTIFY_USER or proposal.risk_level == RiskLevel.CRITICAL:
            print("🛑 Action requires approval. Pausing execution.")
            
            # שמירה ב-State Manager
            self.state_manager.set_pending_action(
                user_id=user_id,
                agent_name=proposal.source_agent,
                action_type=proposal.action_type,
                params=proposal.payload
            )
            
            # שליחת הודעה למשתמש (כרגע הדפסה, בהמשך לוואטסאפ)
            msg = proposal.payload.get('message', proposal.reasoning)
            print(f"🔔 SENDING NOTIFICATION TO USER: {msg}")
            
            # כתיבה ללוג
            self._log_to_file(proposal)

        # 2. סיכון נמוך/בינוני - אישור אוטומטי (למעט אלו שנתפסו למעלה)
        elif proposal.risk_level in [RiskLevel.SAFE, RiskLevel.MODERATE]:
            print("✅ Auto-approving safe action.")
            self._execute_action(proposal, metadata)
        
    def _execute_action(self, proposal: ActionProposal, metadata: dict):
        """כאן קורה הביצוע בפועל בעזרת הכלים"""
        print(f"🚀 EXECUTING: {proposal.action_type}...")
        
        # שליפת ה-ID של המייל (אם קיים)
        email_id = metadata.get('email_id') if metadata else None
        
        try:
            # --- 1. יצירת טיוטה (Draft) ---
            if proposal.action_type == ActionType.DRAFT_EMAIL:
                p = proposal.payload
                create_draft(
                    to_email=p.get("recipient", ""),
                    subject=p.get("subject", "No Subject"),
                    body=p.get("body", "")
                )
            
            # --- 2. זריקה לפח (Trash) ---
            elif proposal.action_type == ActionType.TRASH:
                if email_id:
                    trash_email(email_id)
                else:
                    print("⚠️ Cannot trash: Missing Email ID.")

            # --- 3. העברה לארכיון (Archive) ---
            elif proposal.action_type == ActionType.ARCHIVE:
                if email_id:
                    archive_email(email_id)
                else:
                    print("⚠️ Cannot archive: Missing Email ID.")

            # --- 4. הוספת תווית (Add Label) ---
            elif proposal.action_type == ActionType.ADD_LABEL:
                label = proposal.payload.get("label", "MyOS_Agent")
                if email_id:
                    add_label_to_email(email_id, label)
                else:
                    print("⚠️ Cannot add label: Missing Email ID.")

            # --- 5. סתם התראה (Notify) ---
            elif proposal.action_type == ActionType.NOTIFY_USER:
                print(f"🔔 NOTIFICATION: {proposal.payload.get('summary')}")

            elif proposal.action_type == ActionType.MARK_AS_SPAM:
                print("🗑️ Marked as SPAM (Action pending implementation)")

            elif proposal.action_type == ActionType.EXECUTE_TASK:
                print(f"🏗️ Executing Task: {proposal.payload.get('summary')}")

                # --- טיפול בזימון פגישות ---
            elif proposal.action_type == ActionType.SCHEDULE_EVENT:
                p = proposal.payload
                print(f"📅 Scheduling event: {p.get('summary')} at {p.get('start_time')}")
                
                # אנחנו מושכים את המייל של השולח מה-metadata או מה-payload אם ה-AI היה חכם
                # (לצורך הפשטות נניח שה-AI שם את המייל ב-attendees בתוך ה-payload)
                
                schedule_event(
                    summary=p.get("summary", "Meeting"),
                    start_time=p.get("start_time"),
                    attendees=p.get("attendees", [])
                )

            # תיעוד בלוג
            self._log_to_file(proposal)
            print("✅ Action completed successfully.\n")

        except Exception as e:
            print(f"❌ Execution Failed: {e}")

    def _log_to_file(self, proposal: ActionProposal):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": proposal.source_agent,
            "action": proposal.action_type,
            "risk": proposal.risk_level,
            "payload": proposal.payload,
            "reasoning": proposal.reasoning
        }
        try:
            with open(self.log_file, "r") as f:
                logs = json.load(f)
            logs.append(entry)
            with open(self.log_file, "w") as f:
                json.dump(logs, f, indent=4)
        except Exception as e:
            print(f"Error writing log: {e}")