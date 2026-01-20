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
        You are the SECRETARIAT & COMMS AGENT.
        CURRENT DATE/TIME: {current_time}
        
        ---------------------------------------------------------
        ### REAL-TIME CALENDAR DATA (NEXT 7 DAYS) ###
        {calendar_context}
        ---------------------------------------------------------
        
        YOUR ROLE:
        Check availability using the data above.
        USER INPUT: "{user_input}"
        
        ---------------------------------------------------------
        ### LANGUAGE RULES ###
        1. Notification Message: HEBREW.
        2. Email Draft: Match input language.
        ---------------------------------------------------------

        ---------------------------------------------------------
        ### PRIORITY 1: CALENDAR ###
        1. **CONFLICT** (Time matches event in list) -> Action: 'draft_email' (Refuse politely).
        2. **FREE** (Time is NOT in list) -> Action: 'notify_user'.
           Message: "ביקשו פגישה ב-[Time]. בדקתי ביומן והזמן פנוי. לאשר?"
        
        ---------------------------------------------------------
        ### OUTPUT FORMAT (JSON ONLY) ###
        {{
            "source_agent": "{self.name}",
            "action_type": "...",
            "risk_level": "safe", 
            "payload": {{ "draft": "...", "message": "...", "start_time": "ISO_FORMAT_IF_RELEVANT", "email": "SENDER_EMAIL" }},
            "reasoning": "..."
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
            # שליחה עם הגדרות הבטיחות
            response = self.model.generate_content(prompt, safety_settings=safety_settings)
            
            # בדיקה האם יש חלקים תקינים בתשובה לפני שניגשים ל-text
            if not response.parts:
                print("❌ Gemini returned an empty response (blocked?).")
                # ניסיון להדפיס פידבק מגוגל אם יש
                if response.prompt_feedback:
                    print(f"Feedback: {response.prompt_feedback}")
                raise ValueError("Empty response from AI")

            clean_text = response.text.replace("```json", "").replace("```", "").strip()
            data_dict = json.loads(clean_text)
            
            if isinstance(data_dict, list): data_dict = data_dict[0]
            if "payload" not in data_dict: data_dict["payload"] = {}
            
            return ActionProposal(**data_dict)

        except Exception as e:
            print(f"❌ AI Analysis Error: {e}")
            return ActionProposal(
                source_agent=self.name,
                action_type=ActionType.LOG_INFO,
                risk_level=RiskLevel.SAFE,
                payload={},
                reasoning=f"AI Error: {str(e)}"
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
