import os
import json
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold # ייבוא להגדרות בטיחות
from datetime import datetime
from dotenv import load_dotenv
from core.protocols import ActionProposal, ActionType, RiskLevel

# ייבוא כלי היומן והמייל
from utils.calendar_tools import schedule_event, get_upcoming_events
from utils.gmail_tools import create_draft

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

class SecretariatAgent:
    def __init__(self):
        self.name = "secretariat_agent"
        print("👩‍💼 Secretariat: Loading 'Human-in-the-Loop' Configuration...")
        
        try:
            with open("user_config.json", "r", encoding="utf-8") as f:
                self.config = json.load(f)
                print("✅ Config loaded.")
        except FileNotFoundError:
            self.config = {"rules": []}

        if not GOOGLE_API_KEY:
            self.model = None
            print("❌ Error: GOOGLE_API_KEY missing.")
        else:
            try:
                genai.configure(api_key=GOOGLE_API_KEY)
                # נשארים עם המודל שביקשת
                self.model = genai.GenerativeModel('gemini-3-flash-preview')
                print("✅ Secretariat connected to Gemini (Model: gemini-3-flash-preview) 🛡️")
            except Exception as e:
                print(f"❌ Connection Error: {e}")
                self.model = None

    def process(self, user_input: str) -> ActionProposal:
        if not self.model:
            return ActionProposal(
                source_agent=self.name,
                action_type=ActionType.LOG_INFO,
                risk_level=RiskLevel.SAFE,
                payload={},
                reasoning="Error: Model not initialized"
            )

        # 1. שליפת יומן
        print("📅 Secretariat: Peeking at the calendar...")
        try:
            calendar_context = get_upcoming_events(days=7)
        except Exception as e:
            print(f"⚠️ Calendar Error: {e}")
            calendar_context = "Error fetching calendar."

        allowed_actions = ", ".join([f"'{t.value}'" for t in ActionType])
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")

        prompt = f"""
        You are the MyOS Executive Secretariat. 
        CURRENT DATE: {current_time}
        
        ### CONTEXT
        CALENDAR DATA (7 Days): {calendar_context}
        INCOMING EMAIL: "{user_input}"
        
        ### INSTRUCTIONS
        - Use HTML tags for formatting (<b>bold</b>, <i>italic</i>).
        - DO NOT use Markdown stars (*).
        
        ### MESSAGE STRUCTURE (HTML)
        1. **SPAM**: action_type: 'trash'.
           Message: "<b>זוהה ספאם מ:</b> [Name]. האם לבטל רישום?"
           Payload: Must include 'sender' and 'email'.
        
        2. **ACTIVE TASK**: action_type: 'update'.
           Message: "🚨 <b>משימה דחופה לטיפול</b>\n\n<b>מהות:</b> [Details]\n<b>דרישה:</b> [Action]"

        3. **MEETING/CALENDAR**: action_type: 'draft_email' or 'schedule_event'.
           - Extract ONLY events from the same day as the requested meeting.
           - Message: "📅 <b>בקשה לפגישה חדשה</b>\n\n<b>השולח:</b> [Name]\n<b>זמן:</b> [Time]\n\n<b>הלוז שלך להמשך היום:</b>\n[Events]"
           - payload.draft: [Official reply letter]

        ### MANDATORY: NO MIXING LANGUAGES. 
        Hebrew only for messages. English only for reasoning.
        
        ### OUTPUT FORMAT (JSON ONLY)
        {{
            "source_agent": "{self.name}",
            "action_type": "...",
            "risk_level": "safe",
            "payload": {{
                "message": "Hebrew Summary (HTML)",
                "draft": "Email draft (Text)",
                "calendar_preview": "Events on THAT DAY only",
                "start_time": "ISO_TIME",
                "email": "sender@email.com",
                "sender": "Sender Name"
            }},
            "reasoning": "Internal logic"
        }}
        """
        
        # הגדרות בטיחות - מבטלות את החסימה על ה-JSON
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }

        try:
            # הוספת generation_config להבטחת פלט JSON
            generation_config = {
                "temperature": 0.1, # נמוך = עקבי ומדויק יותר
                "top_p": 0.95,
                "response_mime_type": "application/json",
            }

            response = self.model.generate_content(
                prompt, 
                safety_settings=safety_settings,
                generation_config=generation_config
            )
            
            # בדיקה אם התשובה נחסמה עקב בטיחות (Finish Reason 3 או 4)
            if response.candidates[0].finish_reason != 1:
                print(f"⚠️ Warning: Gemini finished with reason {response.candidates[0].finish_reason}")

            data_dict = json.loads(response.text)
            
            # וידוא שה-action_type תואם ל-Enum שלך
            if data_dict.get("action_type") not in [t.value for t in ActionType]:
                data_dict["action_type"] = ActionType.LOG_INFO.value

            return ActionProposal(**data_dict)

        except Exception as e:
            print(f"❌ Critical AI Failure: {e}")
            # החזרת פרומפט "בטוח" במקרה של קריסה
            return ActionProposal(
                source_agent=self.name,
                action_type=ActionType.LOG_INFO,
                risk_level=RiskLevel.SAFE,
                payload={},
                reasoning=f"System error: {str(e)}"
            )

    # --- שאר הפונקציות נשארות ללא שינוי ---
    def generate_response(self, text: str):
        proposal = self.process(text)
        print(f"🤖 Agent Decision: {proposal.action_type} | {proposal.reasoning}")

        if proposal.action_type == ActionType.DRAFT_EMAIL:
            return proposal.payload.get("draft", "Error: No draft")
        elif proposal.action_type == ActionType.NOTIFY_USER:
            return f"🔔 {proposal.payload.get('message', proposal.reasoning)}"
        elif proposal.action_type == ActionType.SCHEDULE_EVENT:
            return f"📅 (Auto-Schedule Blocked) בקשה לפגישה זוהתה. ממתין לאישור ידני."
        elif proposal.action_type == ActionType.TRASH:
            return "NO_ACTION (Trash)"
        else:
            return "NO_ACTION"

    def execute_instruction(self, instruction: dict):
        action = instruction.get("action")
        params = instruction.get("params", {})
        print(f"⚙️ Executing: {action} with params: {params}")

        if action == "schedule_event":
            result = schedule_event(
                summary=params.get("summary", "פגישה"),
                start_time=params.get("start_time"),
                attendees=[params.get("email")] if params.get("email") else []
            )
            return f"✅ הפגישה נקבעה בהצלחה! (Event ID: {result})"

        elif action == "draft_email":
            result = create_draft(
                to_email=params.get("email"),
                subject=params.get("subject", "תשובה לפגישה"),
                body=params.get("body")
            )
            return f"✅ הטיוטה נוצרה בהצלחה! (Draft ID: {result})"
        else:
            return f"❌ Unknown action: {action}"