import os
import json
import base64
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from datetime import datetime
from dotenv import load_dotenv
from core.protocols import ActionProposal, ActionType, RiskLevel, HEBREW_DAYS, APPROVAL_KEYWORDS
import dateutil.parser

from utils.calendar_tools import create_event, get_upcoming_events, update_event_time
from utils.gmail_tools import create_draft, send_email, trash_email

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

class SecretariatAgent:
    def __init__(self):
        self.name = "secretariat_agent"
        print("👩💼 Secretariat: Loading 'Human-in-the-Loop' Configuration...")
       
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
                self.model = genai.GenerativeModel('gemini-flash-latest')
                print("✅ Secretariat connected to Gemini (Model: gemini-flash-latest) 🛡️")
            except Exception as e:
                print(f"❌ Connection Error: {e}")
                self.model = None

    def _format_date_il(self, iso_date_str):
        """הופך תאריך ISO למשהו שכיף לקרוא בעברית"""
        if not iso_date_str: return ""
        try:
            dt = dateutil.parser.parse(iso_date_str)
            day_name = HEBREW_DAYS[dt.weekday()]
            return dt.strftime(f"יום {day_name}, %d.%m בשעה %H:%M")
        except:
            return iso_date_str

    def classify_user_response(self, user_text: str, pending_action: dict) -> str:
        """
        מסווג את תגובת המשתמש באמצעות AI לאחת מ-3 קטגוריות:
        - 'approve' — המשתמש מאשר את הפעולה הממתינה
        - 'reject' — המשתמש דוחה/מבטל
        - 'other' — המשתמש רוצה משהו אחר (בקשה חדשה, שאלה, חידוד)
        """
        # Fallback: אם אין מודל AI, נשתמש במילות מפתח
        if not self.model:
            return self._classify_by_keywords(user_text)

        action_type = pending_action.get('action', 'unknown')
        action_summary = pending_action.get('params', {}).get('summary', '')

        prompt = f"""
        You are a smart response classifier for a personal assistant system.

        CONTEXT: The user has a PENDING ACTION waiting for their response:
        - Action Type: {action_type}
        - Summary: {action_summary}

        USER RESPONSE: "{user_text}"

        TASK: Classify the user's response into EXACTLY ONE of these 3 categories:

        1. `approve` — The user CONFIRMS / APPROVES the pending action.
           Examples: "כן", "אשר", "תאשר את הפגישה", "לך על זה", "אישור", 
           "תבצע", "יאללה", "מעולה", "סבבה", "אשר את זה", "שלח", "תקבע",
           "yes", "confirm", "ok", "approve", "send it", "do it"

        2. `reject` — The user REJECTS / CANCELS the pending action.
           Examples: "בטל", "לא", "תבטל", "לא רוצה", "cancel", "no", "stop",
           "אל תשלח", "תמחק", "עזוב", "לא צריך"

        3. `other` — The user wants something DIFFERENT: a new request, a question, 
           a modification, or something unrelated to the pending action.
           Examples: "מה יש לי מחר?", "תקבע לי פגישה עם יוסי", 
           "שנה את השעה ל-15:00", "מה זה RAG?"

        IMPORTANT RULES:
        - If the user mentions the pending action AND expresses approval → `approve`
        - If the user says "change X to Y" → `other` (it's a modification)
        - Short confirmations like "כן", "אוקיי", "👍" → `approve`
        - If unsure, prefer `other` over wrong classification

        OUTPUT: Return ONLY a single JSON object:
        {{"classification": "approve" | "reject" | "other"}}
        """

        try:
            generation_config = {"temperature": 0.0, "response_mime_type": "application/json"}
            response = self.model.generate_content(prompt, generation_config=generation_config)
            raw = response.text.strip()

            # ניקוי markdown אם חזר
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            result = json.loads(raw)
            classification = result.get("classification", "other")

            # ולידציה
            if classification not in ["approve", "reject", "other"]:
                classification = "other"

            print(f"🧠 AI Classification: '{user_text}' → {classification}")
            return classification

        except Exception as e:
            print(f"⚠️ AI Classification failed: {e}. Falling back to keywords.")
            return self._classify_by_keywords(user_text)

    def _classify_by_keywords(self, user_text: str) -> str:
        """Fallback: סיווג לפי מילות מפתח (במקרה שה-AI לא זמין)"""
        from core.protocols import APPROVAL_KEYWORDS, REJECTION_KEYWORDS

        text = user_text.strip().lower()
        words = text.split()
        
        # אישור: רק אם הטקסט קצר (עד 4 מילים) ומכיל מילת אישור
        # משפטים ארוכים כמו "תקבע לי פגישה עם יוסי" — לא ייחשבו אישור
        is_short = len(words) <= 4
        is_exact_match = any(kw == text for kw in APPROVAL_KEYWORDS)
        is_contains_match = is_short and any(kw in text for kw in APPROVAL_KEYWORDS if len(kw) > 1)
        is_approval = is_exact_match or is_contains_match
        
        is_rejection = any(kw == text for kw in REJECTION_KEYWORDS) or \
                       any(kw in text for kw in REJECTION_KEYWORDS if len(kw) > 1)

        if is_approval and not is_rejection:
            return "approve"
        elif is_rejection:
            return "reject"
        else:
            return "other"

    def decide_handling(self, user_input: str) -> dict:
        """Decides the intent of the user input and returns structured routing info."""
        if not self.model:
            return {"intent": "general_query", "details": user_input}
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
        
        prompt = f"""
        You are a smart intent router. Classify the User Input into one of these intents:

        **Intents:**
        1. `schedule` — User wants to CREATE / BOOK a meeting or event.
           Examples: "תקבע לי פגישה עם דני מחר ב-10", "Book a meeting with John at 3pm"
        
        2. `send_email` — User wants to SEND an email or compose a message.
           Examples: "תשלח מייל לדני", "Write an email to john@example.com"
        
        3. `calendar_query` — User ASKS about their schedule / calendar / what's planned.
           Examples: "מה יש לי מחר?", "מה בלוז שלי השבוע?", "האם אני פנוי ביום שלישי?"
        
        4. `email_query` — User ASKS about emails they received or sent.
           Examples: "האם קיבלתי מייל מדני?", "תסכם לי את המיילים מהשבוע", "מי שלח לי מייל?"
        
        5. `general_query` — General knowledge questions or anything else.
           Examples: "מה זה RAG?", "תזכיר לי מה סיכמנו", "מי זה אילון מאסק?"

        **Current Time:** {current_time}
        **User Input:** "{user_input}"

        **Output ONLY valid JSON** (no markdown, no explanation):
        {{"intent": "<one of the 5 intents>", "details": "<brief summary of what the user wants>"}}
        """
        
        try:
            response = self.model.generate_content(prompt)
            raw = response.text.strip()
            
            # ניקוי markdown אם חזר
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            
            result = json.loads(raw)
            
            # ולידציה
            valid_intents = ["schedule", "send_email", "calendar_query", "email_query", "general_query"]
            if result.get("intent") not in valid_intents:
                result["intent"] = "general_query"
            
            return result
        except Exception as e:
            print(f"⚠️ Intent parsing error: {e}")
            return {"intent": "general_query", "details": user_input}

    def _construct_message(self, data_dict):
        """Builds the formatted message (Markdown) based on 4 distinct templates."""
        payload = data_dict.get("payload", {})
        action = data_dict.get("action_type")
        
        # Common Fields
        summary = payload.get("summary", "עדכון חדש")
        sender_email = payload.get("email", "לא ידוע")
        sender_name = payload.get("sender_name", "לא ידוע")
        link = payload.get("link")
        link_desc = payload.get("link_explanation")
        
        # Link formatting
        link_line = ""
        if link:
            link_line = f"\n🔗 **קישור:** [{link_desc or 'לחץ כאן'}]({link})"

        # --- 1. Meeting / Calendar (יצירת פגישה או דחייה) ---
        if action in ["schedule_event", "update_event"]:
            pretty_date = self._format_date_il(payload.get("start_time"))
            conflict_note = payload.get("conflict_note", "")
            draft = payload.get("draft", "")
            
            msg = f"📅 **{summary}**\n"
            # הצגת שולח רק אם יש כתובת אמיתית (לא בפקודות ישירות)
            if sender_email and sender_email != "לא ידוע" and "@" in str(sender_email):
                msg += f"👤 **שולח:** {sender_name} ({sender_email})\n"
            msg += f"⏰ **מועד מבוקש:** {pretty_date}"
            msg += link_line
            
            if conflict_note:
                msg += f"\nℹ️ **הערה:** {conflict_note}"
            
            if draft and draft.strip():
                msg += f"\n\n✍️ **טיוטה שהוכנה עבורך:**\n_\"{draft}\"_"
            
            # Note: The server will append the "Schedule for that day" here
            
            msg += "\n\n❓ **האם לאשר או לשנות משהו?**"
            return msg

        # --- 2. Action Required (דרושה פעולה) ---
        elif action == "action_required":
            deadline = payload.get("deadline", "")
            draft = payload.get("draft", "")
            details = payload.get("message", "")
            
            msg = f"🔴 **{summary}**\n"
            msg += f"👤 **שולח:** {sender_name} ({sender_email})\n"
            if deadline:
                msg += f"⏳ **דד-ליין:** {deadline}\n"
            
            msg += f"\n📌 **פרטים:** {details}"
            msg += link_line
            
            if draft:
                msg += f"\n\n✍️ **הצעת טיוטה / פעולה:**\n_\"{draft}\"_"
            
            msg += "\n\n❓ **האם לאשר, לערוך או להגיב אחרת?**"
            return msg

        # --- 3. Critical Update (עדכון חשוב) ---
        elif action == "critical_info":
            details = payload.get("message", "")
            
            msg = f"📢 **{summary}**\n"
            msg += f"👤 **שולח:** {sender_name} ({sender_email})\n"
            msg += f"\n📌 **עיקרי הדברים:** {details}"
            msg += link_line
            
            if payload.get("suggested_action"):
                msg += f"\n\n💡 **פעולה מוצעת:** {payload.get('suggested_action')}"
            
            return msg

        # --- 4. Spam / Trash (ספאם) ---
        elif action in ["trash", "mark_as_spam"]:
            # If unsubscribe is offered, we might want to show it. 
            # User said: "Ask me if I want to unsubscribe".
            if payload.get("unsubscribe_offered"):
                 msg = f"🗑️ **זוהה ספאם: {summary}**\n"
                 msg += f"👤 **שולח:** {sender_name} ({sender_email})\n"
                 msg += "\n❓ **האם להסיר מרשימת התפוצה (Unsubscribe)?**"
                 return msg
            return None 

        # --- 5. Log Info (Styling Update) ---
        elif action in ["log_info", "update", "info_update"]:
            # Clean Style: Title, Sender, clean content
            msg = f"� **{summary}**\n"
            msg += f"👤 **מאת:** {sender_name}\n"
            msg += f"📄 {payload.get('message')}"
            return msg
        
        # --- 6. Read Calendar ---
        elif action == "read_calendar":
             return f"📅 **בודק את היומן עבורך...**\n(אנא אשר כדי להציג את האירועים)"
            
        else:
            return f"🚨 **עדכון לא מסווג**\nמאת: {sender_email}\n{summary}"

    def process(self, user_input: str, images: list[str] = None) -> ActionProposal:
        if not self.model:
            return ActionProposal(self.name, ActionType.LOG_INFO, RiskLevel.SAFE, {}, "Error: Model not initialized")

        print(f"🕵️ DEBUG - Raw Input to AI: {user_input[:100]}...")
        if images:
             print(f"🕵️ DEBUG - Images attached: {len(images)}")

        short_input = user_input.strip().lower()
        is_approval = short_input in APPROVAL_KEYWORDS
        calendar_context = "SKIPPED (Approval)" if is_approval else "Available in Server context if needed"

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")

        prompt = f"""
        You are the MyOS Executive Secretariat.
        CURRENT DATE: {current_time}
        INCOMING CONTENT: "{user_input}"
        VISUAL CONTEXT: {"Images provided" if images else "None"}
       
        ### GOAL
        Classify the email/request into one of 5 categories and extract structured data for the user.
        If images are provided, USE THEM to extract dates, times, locations, or summary details that might be missing from the text.
        
        ### � IMPORTANT FOR IMAGES
        1. If text is empty/short BUT images are present -> **DO NOT CLASSIFY AS SPAM**.
        2. Analyze the image to see if it's an Invitation, Receipt, or Info.
        3. If it's an invitation image -> `schedule_event`.
        
        ### �🔒 PRIVACY RULES
        1. **NEVER** reveal private calendar details in drafts/notes. Use "Previous commitment".
        2. **LANGUAGE**: All explanations & summaries in **HEBREW**. Drafts in the **Sender's language**.
        3. **ATTENDEES**: Do **NOT** add the sender as a calendar attendee unless explicitly requested ("Invite him", "Send invite"). Default `invite_attendees=false`.

        ### CLASSIFICATION CATEGORIES
        
        1. **MEETING (`schedule_event` / `update_event`)**:
           - **Trigger**: Meeting invites, coordination, rescheduling, "Book this".
           - **Output**: `link` if meeting link exists. `draft` is REQUIRED only when replying to someone's email (there's a sender email). If this is a DIRECT user command (no sender email), do NOT generate a draft — just set `draft` to empty string.
        
        2. **ACTION REQUIRED (`action_required`)**:
           - **Trigger**: Tasks, "Sign this", "Review this", Deadline-driven items, document reviews.
           - **Output**: `deadline` is important. `draft` is REQUIRED — if there's embedded attachment content (marked with 📄 תוכן), you MUST analyze it in detail and include specific findings/feedback in the draft. Do NOT give generic advice — reference actual content from the attachment.
           - **IMPORTANT**: When a document is attached and its content is available, your `message` field should include a brief summary of what you found, and the `draft` should contain detailed, specific feedback.

        3. **CRITICAL INFO (`critical_info`)**:
           - **Trigger**: Important FYI, Flight changes, Security alerts, Status updates.
           - **Output**: `suggested_action` if relevant.
        
        4. **SPAM (`trash`)**:
           - **Trigger**: Marketing, Spam.
           - **Logic**: If it looks like a recurring newsletter/spam, set `unsubscribe_offered=true`.

        5. **INFO (`log_info`)**: Low priority updates, Receipts, Confirmations (where no action is needed).

        6. **READ CALENDAR (`read_calendar`)**:
           - **Trigger**: "What's on my agenda?", "Do I have meetings today?", "Check my calendar".
           - **Output**: `start_time` should be set to the requested date (ISO).

        ### OUTPUT FORMAT (JSON ONLY)
        {{
            "source_agent": "{self.name}",
            "action_type": "schedule_event" | "action_required" | "critical_info" | "trash" | "log_info" | "read_calendar",
            "risk_level": "safe",
            "payload": {{
                "summary": "Hebrew Title: 'Topic - With {{Sender Name}}'",
                "sender_name": "Name extracted",
                "email": "Email address",
                "start_time": "ISO format (for meetings) or empty",
                "end_time": "ISO format (optional)",
                "link": "URL found in email",
                "link_explanation": "Hebrew description of link",
                "message": "Hebrew summary of details/main points (Clean & Concise)",
                "conflict_note": "Any notes/conflicts (Hebrew)",
                "draft": "Reply content (Sender's Language)",
                "deadline": "Deadline if exists",
                "suggested_action": "Hebrew suggestion for critical info",
                "unsubscribe_offered": boolean,
                "invite_attendees": boolean
            }}
        }}
        """
        
        safety_settings = {HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE}

        try:
            # Prepare inputs - List containing prompt and images (if any)
            inputs = [prompt]
            if images:
                for img_b64 in images:
                    # Create the image dict compatible with Gemini API
                    # Note: Gemini SDK often expects 'mime_type' and 'data' (bytes)
                    # We'll assume standard JPEG for simplicity if unknown, or try to detect?
                    # Actually, simple way is using dictionary:
                    try:
                        img_bytes = base64.b64decode(img_b64)
                        inputs.append({"mime_type": "image/jpeg", "data": img_bytes})
                    except Exception as img_err:
                        print(f"⚠️ Error decoding image: {img_err}")

            generation_config = {"temperature": 0.1, "response_mime_type": "application/json"}
            
            # Pass the LIST of inputs (multimodal)
            response = self.model.generate_content(inputs, safety_settings=safety_settings, generation_config=generation_config)
            
            text_resp = response.text if response.parts else (response.candidates[0].content.parts[0].text if response.candidates else "")
            print(f"🤖 DEBUG - AI Decision: {text_resp}")
            data_dict = json.loads(text_resp.replace("```json", "").replace("```", "").strip())
            
            # Formatter Overwrite
            formatted_message = self._construct_message(data_dict)
            data_dict.setdefault("payload", {})["message"] = formatted_message

            if "risk_level" not in data_dict: data_dict["risk_level"] = "safe"
            if "reasoning" not in data_dict: data_dict["reasoning"] = "Auto"
            
            # ENUM Validation
            valid_types = [t.value for t in ActionType]
            if data_dict.get("action_type") not in valid_types:
                 # Map legacy/other types to log_info or keep if valid string
                 if data_dict.get("action_type") not in ["trash", "mark_as_spam"]:
                     data_dict["action_type"] = ActionType.LOG_INFO.value

            return ActionProposal(**data_dict)

        except Exception as e:
            return ActionProposal(
                source_agent=self.name,
                action_type=ActionType.LOG_INFO,
                risk_level=RiskLevel.SAFE,
                payload={},
                reasoning=str(e)
            )

    def refine_proposal(self, previous_state: dict, user_feedback: str) -> ActionProposal:
        if not self.model:
             return ActionProposal(
                 source_agent=self.name, 
                 action_type=ActionType.LOG_INFO, 
                 risk_level=RiskLevel.SAFE, 
                 payload={}, 
                 reasoning="Error: Model not initialized"
             )

        print(f"🔄 Refinement Loop: Feedback='{user_feedback}'")

        prompt = f"""
        You are the MyOS Executive Secretariat.
        GOAL: Refine Plan based on User Feedback.
        
        CONTEXT:
        Original Plan: {json.dumps(previous_state, ensure_ascii=False)}
        User Feedback: "{user_feedback}"
        
        ### PIVOT INSTRUCTIONS (CRITICAL)
        1. **CHANGE ACTION TYPE**: If the user's request implies a different action type, you **MUST** change it.
           - "Add to calendar" / "Book it" / "Set meeting" -> `schedule_event`
           - "Write email to X" / "Reply" -> `draft_email`
           - "What's on my schedule?" -> `read_calendar`
           - "Remind me" -> `action_required`
        
        2. **CALENDAR LOGIC**:
           - If `start_time` is updated or present, prefer `schedule_event`.
           - **SUMMARY FORMAT**: Always ensure `summary` is "Topic - With {{Sender Name}}".
           - If user says "Confirm" or "Approve" regarding a meeting detail -> Ensure `action_type` is `schedule_event`.

        3. **DRAFT LOGIC**:
           - If user wants to **REPLY** or **NOTIFY** the sender -> Rewrite `draft` (Sender's Language).
           - If user only updates **INTERNAL** details (like Title/Notes) -> Set `draft` to `""` (Empty String).
        
        4. Maintain other fields like `sender_name`, `email` unless user asks to change them.
        
        OUTPUT JSON:
        {{
            "source_agent": "{self.name}",
            "action_type": "update_event" | "schedule_event" | "draft_email" | "read_calendar" | "log_info",
            "risk_level": "safe",
            "payload": {{
                "summary": "...", "email": "...", "sender_name": "...",
                "start_time": "ISO", "event_id": "...",
                "draft": "Reply text OR Empty string",
                "message": "Hebrew summary of meeting details ONLY (Do NOT include the draft text here)",
                "invite_attendees": boolean
            }}
        }}
        """
       
        try:
            generation_config = {"temperature": 0.2, "response_mime_type": "application/json"}
            response = self.model.generate_content(prompt, generation_config=generation_config)
            text_resp = response.text if response.parts else (response.candidates[0].content.parts[0].text if response.candidates else "")
            data_dict = json.loads(text_resp.replace("```json", "").replace("```", "").strip())
            
            # Formatter Logic applied to refinement as well
            if "action_type" not in data_dict: data_dict["action_type"] = "update_event"
            formatted_message = self._construct_message(data_dict)
            data_dict.setdefault("payload", {})["message"] = formatted_message

            if "risk_level" not in data_dict: data_dict["risk_level"] = "safe"
            if "reasoning" not in data_dict: data_dict["reasoning"] = "Refinement Update"
            
            return ActionProposal(**data_dict)

        except Exception as e:
            print(f"❌ Error in refinement: {e}")
            return ActionProposal(
                source_agent=self.name, 
                action_type=ActionType.LOG_INFO, 
                risk_level=RiskLevel.SAFE, 
                payload={}, 
                reasoning=f"Refinement Failed: {str(e)}"
            )

    def execute_instruction(self, instruction: dict):
        action = instruction.get("action")
        params = instruction.get("params", {})
        print(f"⚙️ Executing: {action} with params: {params}")

        # עיצוב מחדש של הודעת ההצלחה (הפרדת תאריך ושעה, ללא ID)
        start_time_iso = params.get('start_time')
        pretty_date = "N/A"
        pretty_time = "N/A"
        if start_time_iso:
            try:
                dt = dateutil.parser.parse(start_time_iso)
                day_name = HEBREW_DAYS[dt.weekday()]
                pretty_date = f"יום {day_name}, {dt.strftime('%d.%m.%Y')}"
                pretty_time = dt.strftime("%H:%M")
            except:
                pretty_date = start_time_iso

        if action == "schedule_event":
            clean_msg = ""
            
            # 1. קביעת הפגישה (רק אם יש תאריך)
            start_time_iso = params.get("start_time")
            
            if start_time_iso:
                # לוגיקה מעודכנת: מוסיפים משתתפים רק אם המשתמש ביקש (invite_attendees=True)
                attendees_list = [params.get("email")] if (params.get("email") and params.get("invite_attendees")) else []
                
                try:
                    # שינוי שם הפונקציה מ-schedule_event ל-create_event (השם החדש ב-calendar_tools)
                    # והעברת end_time רק אם קיים
                    result = create_event(
                        summary=params.get("summary", "פגישה"),
                        start_time=start_time_iso,
                        end_time=params.get("end_time"),
                        attendees=attendees_list,
                        description=params.get("message")
                    )
                     # הודעה מעוצבת לפי בקשת המשתמש
                    clean_msg += f"✅ **הפגישה נקבעה בהצלחה!**\n📅 **תאריך:** {pretty_date}\n⏰ **שעה:** {pretty_time}"
                    if attendees_list:
                        clean_msg += f"\n👥 **משתתפים:** {params.get('email')}"
                except Exception as e:
                     clean_msg += f"❌ שגיאה בקביעת הפגישה ביומן: {e}"
            else:
                # אם אין תאריך, אנחנו לא קובעים פגישה, אבל לא זורקים שגיאה אם יש מייל לשלוח
                if not params.get("send_email"):
                     clean_msg += "⚠️ לא צוין תאריך לפגישה ולכן היא לא נקבעה ביומן."

            # 2. שליחת המייל (אם נדרש)
            if params.get("send_email") and params.get("email_payload"):
                email_data = params.get("email_payload")
                print(f"📧 Auto-sending email to {email_data.get('to_email')}...")
               
                send_res = send_email(
                    to_email=email_data.get("to_email"),
                    subject=email_data.get("subject"),
                    body=email_data.get("body")
                )
                if send_res:
                    if clean_msg: clean_msg += "\n"
                    clean_msg += f"✅ המייל נשלח בהצלחה!"
                else:
                    if clean_msg: clean_msg += "\n"
                    clean_msg += f"❌ שגיאה בשליחת המייל."

            return clean_msg if clean_msg else "⚠️ לא בוצעה שום פעולה (חסרים נתונים)."
            
        elif action == "update_event":
            # טיפול בשינוי מועד - עדכון האירוע הקיים (שומר על ה-ID, משמע "מוחק" מהזמן הישן)
            event_id = params.get("event_id")
            new_time = params.get("start_time")
            
            if event_id:
                try:
                    update_event_time(event_id, new_time)
                    clean_msg = f"✅ **הפגישה הוזזה בהצלחה!**\n📅 **תאריך חדש:** {pretty_date}\n⏰ **שעה חדשה:** {pretty_time}"
                    
                    if params.get("send_email") and params.get("email_payload"):
                        email_data = params.get("email_payload")
                        send_email(to_email=email_data.get("to_email"), subject=email_data.get("subject"), body=email_data.get("body"))
                        clean_msg += "\n✅ מייל עדכון נשלח!"
                except Exception as e:
                    clean_msg = f"❌ שגיאה: {e}"
            else:
                 clean_msg = "❌ שגיאה: לא נמצאה פגישה לעדכון."
            
            return clean_msg

        elif action == "draft_email":
            result = create_draft(
                to_email=params.get("email"),
                subject=params.get("subject", "תשובה לפגישה"),
                body=params.get("body")
            )
            return f"✅ הטיוטה נוצרה בהצלחה!"
           
        elif action == "send_email":
            result = send_email(
                to_email=params.get("to_email"),
                subject=params.get("subject"),
                body=params.get("body")
            )
            return "✅ המייל נשלח בהצלחה!" if result else "❌ שגיאה בשליחת המייל."
            
        elif action == "trash_email":
             from utils.gmail_tools import trash_email
             trash_email(params.get("email_id"))
             return "✅ המייל הועבר לאשפה."

        else:
            return f"❌ Unknown action: {action}"