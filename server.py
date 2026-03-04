from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import os
import re

# ייבוא הסוכנים והכלים
from agents.secretariat_agent import SecretariatAgent
from agents.information_agent import InformationAgent
from core.state_manager import StateManager
from core.protocols import ActionType
from utils.calendar_tools import get_upcoming_events, get_events_for_date
from utils.gmail_tools import fetch_email_by_id

app = FastAPI()


print("👔 Manager: Initializing MyOS Team...")
secretary = SecretariatAgent() # אתחול הסוכן
librarian = InformationAgent()
state_manager = StateManager()
print("✅ Manager: Team is ready & Scalable!")

# --- מודלים ---
class RequestModel(BaseModel):
    text: str
    source: str = "telegram"
    user_id: str = "admin"
    email_id: str = None 
    images: list[str] = None
    reply_to_message_id: int = None # New: For Context Awareness

class RegisterMessageRequest(BaseModel):
    internal_id: str
    telegram_message_id: int

class ExecutionRequest(BaseModel):
    action: str
    params: dict

@app.get("/")
def home():
    return {"status": "online", "message": "MyOS Manager is running (Stateful Mode)"}

# --- 1. זיכרון (RAG) ---
@app.post("/memorize")
def memorize_info(payload: RequestModel):
    print(f"📥 Archiving: {payload.text[:30]}...")
    librarian.memorize(payload.text, source=payload.source)
    return {"status": "success", "message": "Saved to memory"}

# --- 1.5 רישום הקשר (Context Registration) ---
@app.post("/register_message")
def register_message_map(payload: RegisterMessageRequest):
    """מקבל מ-N8N את המזהה הפנימי + מזהה ההודעה שנוצרה בטלגרם"""
    success = state_manager.map_telegram_id(payload.internal_id, payload.telegram_message_id)
    if success:
        return {"status": "mapped", "internal": payload.internal_id, "telegram": payload.telegram_message_id}
    return {"status": "error", "message": "Internal ID not found"}

# --- 2. המוח המרכזי (שיחה + ניהול אישורים) ---
@app.post("/ask")
def ask_brain(payload: RequestModel):
    user_text = payload.text.strip().lower()
    user_id = payload.user_id 
    
    # 1. ניסיון שליפה לפי הקשר (Reply)
    pending_state = None
    if payload.reply_to_message_id:
        print(f"🔍 Searching context for Reply To ID: {payload.reply_to_message_id}")
        pending_state = state_manager.get_action_by_message(payload.reply_to_message_id)
        if pending_state:
             print("✅ Context Found: Linked to pending action.")
        else:
             print("⚠️ Context Not Found (Maybe expired or unmapped).")

    # 2. Fallback: אם אין הקשר, ננסה לשלוף את האחרון (כמו קודם)
    if not pending_state:
         pending_state = state_manager.get_pending_action(user_id)

    print(f"❓ User ({user_id}) asks: {user_text}")
    print(f"🔍 Pending state found: {pending_state is not None}")

    if pending_state:
        action_type = pending_state.get('action')
        print(f"🚦 Pending Action Detected: {action_type}")
        print(f"🚦 Pending State params: {list(pending_state.get('params', {}).keys())}")

        # --- טיפול מיוחד: המשתמש שלח כתובת מייל (השלמת איש קשר) ---
        if action_type == 'awaiting_email':
            original_text = payload.text.strip()
            # בדיקה אם המשתמש שלח כתובת מייל
            if '@' in original_text:
                email_addr = original_text.strip()
                params = pending_state.get('params', {})
                recipient_name = params.get('recipient_name', '')
                
                # שמירת איש קשר חדש!
                if recipient_name:
                    state_manager.save_contact(user_id, recipient_name, email_addr)
                
                # השלמת הכתובת בהצעה הקיימת
                proposal_params = params.get('original_proposal', {})
                proposal_params['email'] = email_addr
                proposal_action = params.get('original_action', 'send_email')
                
                # ננקה את ה-awaiting ונשמור את ההצעה המושלמת
                state_manager.clear_state(user_id)
                
                has_draft = bool(proposal_params.get('draft'))
                state_manager.set_pending_action(
                    user_id=user_id,
                    agent_name="secretariat_agent",
                    action_type=proposal_action,
                    params={
                        "summary": proposal_params.get('summary'),
                        "start_time": proposal_params.get('start_time'),
                        "end_time": proposal_params.get('end_time'),
                        "email": email_addr,
                        "event_id": proposal_params.get('event_id'),
                        "invite_attendees": proposal_params.get('invite_attendees', False),
                        "send_email": has_draft,
                        "email_payload": {
                            "to_email": email_addr,
                            "subject": proposal_params.get('summary', 'הודעה'),
                            "body": proposal_params.get('draft', '')
                        } if has_draft else {},
                        "draft": proposal_params.get('draft', '')
                    }
                )
                
                formatted_msg = proposal_params.get('message') or proposal_params.get('summary', '')
                if has_draft:
                    formatted_msg += f"\n\n✍️ **טיוטה:**\n_{proposal_params.get('draft')}_"
                
                return {"answer": f"👤 נשמר! \"**{recipient_name}**\" ({email_addr}) נוסף לאנשי הקשר שלך.\n\n{formatted_msg}\n\nהאם לאשר ולבצע?"}
            else:
                # המשתמש לא שלח מייל — אולי התכוון השתנה
                state_manager.clear_state(user_id)
                # ננתב כבקשה חדשה (ימשיך למטה)
       
        # --- סיווג חכם באמצעות AI (במקום מילות מפתח) ---
        classification = secretary.classify_user_response(user_text, pending_state)
        print(f"🚦 AI Classification result: '{user_text}' → {classification}")
       
        if classification == "approve":
            print("🚀 User Approved! Executing...")
            instruction = {
                "action": action_type,
                "params": pending_state.get("params", {})
            }
            print(f"⚙️ Executing: {action_type} with params: {list(instruction['params'].keys())}")
            result_msg = secretary.execute_instruction(instruction)
            
            # שמירת איש קשר חדש לאחר שליחה מוצלחת
            exec_params = pending_state.get("params", {})
            contact_email = exec_params.get("email") or (exec_params.get("email_payload", {}).get("to_email"))
            contact_name = exec_params.get("summary", "").split(" - ")[-1] if exec_params.get("summary") else ""
            if contact_email and "@" in str(contact_email):
                # ננסה לחלץ שם (מה-summary או מה-sender_name)
                if not contact_name:
                    contact_name = contact_email.split("@")[0].replace(".", " ").title()
                state_manager.save_contact(user_id, contact_name, contact_email)
            
            state_manager.clear_state(payload.user_id)
            return {"answer": result_msg}
       
        elif classification == "reject":
            state_manager.clear_state(payload.user_id)
            return {"answer": "❌ הפעולה בוטלה."}
       
        # --- OTHER: ניתוב חכם — בדיקת כוונה לפני refinement ---
        else:
            print(f"🔄 Response classified as 'other'. Checking intent...")
            
            # בדיקה: האם זו בקשה עצמאית חדשה?
            intent_check = secretary.decide_handling(user_text)
            intent = intent_check.get("intent", "general_query")
            print(f"🧠 Sub-intent detected: {intent}")
            
            # אם זו בקשה עצמאית (יומן, מייל, שאלה) — ננקה את ה-state וננתב כרגיל
            if intent in ["schedule", "send_email", "calendar_query", "email_query"]:
                print(f"➡️ Routing as NEW request (clearing pending state)")
                state_manager.clear_state(payload.user_id)
                # ננתב ישר לעיבוד הרגיל (ממשיך למטה, מחוץ ל-if pending_state)
            else:
                # --- REFINEMENT LOGIC (חידוד ההצעה הקיימת) ---
                print(f"🔄 Refining existing proposal with feedback: '{user_text}'")
               
                # שליפת הפרמטרים הקיימים
                current_params = pending_state.get("params", {})
               
                # קריאה לחידוד ההצעה
                refined_proposal = secretary.refine_proposal(current_params, user_text)
                
                # SAFEGUARD: If refinement failed, don't corrupt the state
                if refined_proposal.action_type == "log_info":
                     return {"answer": f"❌ סליחה, לא הבנתי את השינוי המבוקש.\n(שגיאה: {refined_proposal.reasoning})\n\nאנא נסה לנסח שוב או כתוב 'בטל'."}

                # עדכון הטיוטה ב-Gmail בזמן אמת
                new_draft = refined_proposal.payload.get('draft')
                if new_draft:
                    print("📝 Updating draft in Gmail...")
                    secretary.execute_instruction({
                        "action": "draft_email",
                        "params": {
                            "email": refined_proposal.payload.get("email"), 
                            "subject": "עדכון פגישה",
                            "body": new_draft
                        }
                    })

                # **CRITICAL FIX**: Ensure 'send_email' is True ONLY if draft exists
                if new_draft and new_draft.strip():
                    refined_proposal.payload['send_email'] = True
                    refined_proposal.payload['email_payload'] = {
                        "to_email": refined_proposal.payload.get("email"),
                        "subject": "תשובה / עדכון",
                        "body": new_draft
                    }
                else:
                    refined_proposal.payload['send_email'] = False
                    refined_proposal.payload['email_payload'] = {}

                # עדכון המצב בזיכרון
                state_manager.set_pending_action(
                    user_id=payload.user_id,
                    agent_name="secretariat_agent",
                    action_type=action_type, 
                    params=refined_proposal.payload
                )
               
                # יצירת הודעה חדשה למשתמש
                mock_data = {
                    "action_type": action_type, 
                    "payload": refined_proposal.payload
                }
                formatted_msg = secretary._construct_message(mock_data)
                msg = f"📝 **עדכנתי את התוכנית:**\n\n{formatted_msg}"
               
                if new_draft:
                     msg += "\n\n*(הטיוטה ב-Gmail עודכנה)*"
               
                msg += "\n\nהאם לאשר את הגרסה החדשה? (או כתוב הערה נוספת לתיקון)"
                return {"answer": msg}


    # ב. אם אין פעולה ממתינה, נבדוק את כוונת המשתמש
    print("📚 No pending actions. Checking Intent...")
    
    # בדיקת כוונה מפורטת
    intent_result = secretary.decide_handling(user_text)
    intent = intent_result.get("intent", "general_query")
    details = intent_result.get("details", user_text)
    print(f"🧠 Intent detected: {intent} | Details: {details}")

    # --- 1. שאלות על היומן ---
    if intent == "calendar_query":
        print("📅 Routing to Calendar Tools...")
        try:
            # ניסיון לזהות תאריך ספציפי מהבקשה
            import dateutil.parser
            try:
                target_date = dateutil.parser.parse(details, fuzzy=True).isoformat()
                agenda = get_events_for_date(target_date)
            except (ValueError, OverflowError):
                agenda = get_upcoming_events(days=7)
            
            if not agenda or agenda.strip() == "":
                return {"answer": "📅 היומן שלך פנוי! אין אירועים מתוכננים."}
            return {"answer": f"📅 **הלו\"ז שלך:**\n\n{agenda}"}
        except Exception as e:
            print(f"Calendar query error: {e}")
            return {"answer": f"📅 הנה מה שיש:\n\n{get_upcoming_events(days=7)}"}

    # --- 2. פקודות ביצוע (פגישה / מייל) ---
    elif intent in ["schedule", "send_email"]:
        print(f"⚡ Routing to Secretariat for: {intent}...")
        
        # עיבוד הבקשה ע"י הסוכן
        proposal = secretary.process(user_text)
        
        proposed_email = proposal.payload.get("email", "")
        if not proposed_email or "@" not in str(proposed_email):
            # חילוץ שם הנמען מתוך הבקשה
            recipient_name = details if details else user_text
            contacts = state_manager.find_contacts(user_id, recipient_name)
            
            if len(contacts) == 1:
                # תוצאה יחידה — משלימים אוטומטית!
                proposal.payload["email"] = contacts[0]["email"]
                print(f"👤 Auto-filled email: {contacts[0]['name']} <{contacts[0]['email']}>")
            elif len(contacts) > 1:
                # כמה תוצאות — שואלים את המשתמש
                options = "\n".join([f"{i+1}. **{c['name']}** ({c['email']})" for i, c in enumerate(contacts[:5])])
                return {"answer": f"🔍 מצאתי {len(contacts)} אנשי קשר בשם \"{recipient_name}\":\n\n{options}\n\nלמי מביניהם לשלוח?"}
            elif not proposed_email:
                # לא מצאנו — שומרים pending state ומבקשים כתובת
                state_manager.set_pending_action(
                    user_id=user_id,
                    agent_name="secretariat_agent",
                    action_type="awaiting_email",
                    params={
                        "recipient_name": recipient_name,
                        "original_action": proposal.action_type if isinstance(proposal.action_type, str) else proposal.action_type.value,
                        "original_proposal": proposal.payload
                    }
                )
                return {"answer": f"📧 לא מצאתי את \"{recipient_name}\" באנשי הקשר שלך.\n\nאנא כתוב את כתובת המייל."}
        
        # הוספת הקשר ליומן (אם רלוונטי)
        msg_context = ""
        if proposal.action_type in ["schedule_event", "update_event"]:
            try:
                target_date = proposal.payload.get("start_time")
                if target_date:
                    daily_agenda = get_events_for_date(target_date)
                    if not daily_agenda or daily_agenda.strip() == "":
                        msg_context += "\n\n📅 **לו\"ז לאותו יום:** פנוי לגמרי."
                    else:
                        msg_context += f"\n\n📅 **המשך הלו\"ז לאותו יום:**\n{daily_agenda}"
            except Exception as e:
                print(f"Cal Context Error: {e}")

        # הכנת הודעת התשובה
        formatted_msg = (proposal.payload.get('message') or '') + msg_context
        
        # שמירת מצב (State) לאישור
        has_draft = bool(proposal.payload.get('draft'))
        state_manager.set_pending_action(
            user_id=payload.user_id,
            agent_name="secretariat_agent",
            action_type=proposal.action_type,
            params={
                "summary": proposal.payload.get('summary'),
                "start_time": proposal.payload.get("start_time"),
                "end_time": proposal.payload.get("end_time"),
                "email": proposal.payload.get("email"),
                "event_id": proposal.payload.get("event_id"),
                "invite_attendees": proposal.payload.get("invite_attendees", False),
                "send_email": has_draft,
                "email_payload": {
                    "to_email": proposal.payload.get("email"),
                    "subject": proposal.payload.get("summary", "הודעה"),
                    "body": proposal.payload.get("draft", "")
                } if has_draft else {},
                "draft": proposal.payload.get("draft", "")
            }
        )
        
        prompt_q = "\n\nהאם לאשר ולבצע?"
        return {"answer": f"💡 **הבנתי, הנה ההצעה:**\n\n{formatted_msg}{prompt_q}"}

    # --- 3. שאלות על מיילים ---
    elif intent == "email_query":
        print("📧 Routing to RAG (Email context)...")
        answer = librarian.ask_brain(user_text)
        return {"answer": answer}

    # --- 4. שאלות כלליות ---
    else:
        print("📚 Routing to RAG (General).")
        answer = librarian.ask_brain(user_text)
        return {"answer": answer}


# --- 3. ניתוח אירועים (מיילים) והכנת הקרקע לאישור ---
@app.post("/analyze_email")
def analyze_incoming_event(payload: RequestModel):
    print(f"INFO: Analyzing email from source: {payload.source}")
    
    # העשרת הטקסט עם גוף מלא מ-Gmail (אם יש email_id)
    enriched_text = payload.text
    if payload.email_id:
        try:
            full_email = fetch_email_by_id(payload.email_id)
            if full_email and full_email.get("body"):
                enriched_text = full_email["body"]
                print(f"📧 Enriched email body: {len(enriched_text)} chars (was {len(payload.text)} chars)")
                
                # הוספת מידע על קבצים מצורפים
                if full_email.get("has_calendar_invite"):
                    enriched_text += "\n\n[📅 מייל זה מכיל הזמנת יומן (ICS)]"
        except Exception as e:
            print(f"⚠️ Email enrichment failed: {e} — using original text")
    
    # DEBUG: Check image payload
    if payload.images:
        print(f"📸 DEBUG SERVER: Received {len(payload.images)} images.")
    else:
        print("📸 DEBUG SERVER: No images received in payload (None or Empty).")

    # שליחה לסוכן המזכירות לניתוח (כולל תמונות אם יש)
    proposal = secretary.process(enriched_text, images=payload.images)
    
    # Safely get the string value of action_type (whether it's Enum or str)
    action_str = proposal.action_type.value if hasattr(proposal.action_type, 'value') else str(proposal.action_type)

    # 1. שמירת פעולה חדשה (ייחודית) - קודם כל ולפני הכל!
    internal_id = state_manager.save_action(payload.user_id, "secretariat_agent", action_str, proposal.payload)
    print(f"💾 Saved Action {internal_id} for {payload.user_id}")

    # שמירת איש קשר מהמייל הנכנס
    try:
        sender_email = proposal.payload.get("email", "")
        # חילוץ שם מהטקסט המקורי — "From: שם <email>"
        from_match = re.search(r'From:\s*(.+?)[\s<(]', payload.text)
        sender_name = from_match.group(1).strip() if from_match else ""
        # Fallback: אם אין שם, ניקח את החלק לפני ה-@ 
        if not sender_name and sender_email:
            sender_name = sender_email.split("@")[0].replace(".", " ").title()
        if sender_email and sender_name:
            state_manager.save_contact(payload.user_id, sender_name, sender_email)
    except Exception as e:
        print(f"⚠️ Contact extraction failed: {e}")

    # יצירת הודעה למשתמש
    msg = proposal.payload.get("message")
    
    # --- 1. ספאם & זבל (שקט) ---
    if proposal.action_type in ["trash", "mark_as_spam"]:
        if payload.email_id:
            # מחיקה שקטה
            secretary.execute_instruction({"action": "trash_email", "params": {"email_id": payload.email_id}})
        print(f"🗑️ Spam processed silently: {proposal.payload.get('summary')}")
        return {"action_needed": False, "draft": "", "internal_id": internal_id}

    # --- 2. חיבור ליומן והודעות ---   

    # --- 2. יומן (פגישות / שינויים) - דורש הקשר והכנת טיוטה ---
    if proposal.action_type in ["schedule_event", "update_event"]:
        
        # א. הוספת טיוטה אם יש (Interative)
        if proposal.payload.get('draft'):
            secretary.execute_instruction({
                "action": "draft_email",
                "params": {
                    "email": proposal.payload.get("email"),
                    "subject": "תשובה לגבי פגישה",
                    "body": proposal.payload.get("draft")
                }
            })
            msg += "\n\n*(הטיוטה כבר מחכה לך ב-Gmail)*"

        # ב. הוספת הקשר ליומן (אירועים באותו יום ספציפי)
        try:
             target_date = proposal.payload.get("start_time")
             if target_date:
                 daily_agenda = get_events_for_date(target_date)
                 if not daily_agenda or daily_agenda.strip() == "":
                      msg += "\n\n📅 **לו\"ז לאותו יום:** פנוי לגמרי (אין אירועים נוספים)."
                 else:
                      msg += f"\n\n📅 **המשך הלו\"ז לאותו יום:**\n{daily_agenda}"
             else:
                 # אם אין תאריך, נביא את הקרוב
                 upcoming = get_upcoming_events(days=1)
                 msg += f"\n\n📅 **אירועים קרובים:**\n{upcoming}"
        except Exception as e:
             print(f"Server Calendar Context Error: {e}")

        has_draft = bool(proposal.payload.get('draft'))
        
        prompt_q = "האם לאשר ולשלוח?" if has_draft else "האם לאשר את האירוע?"
        msg += f"\n\n{prompt_q} (ענה 'כן' או 'לא')"
        return {"action_needed": True, "draft": msg, "internal_id": internal_id}

    # --- 3. דרושה פעולה (Action Required) ---
    if proposal.action_type == "action_required":
        return {"action_needed": True, "draft": msg, "internal_id": internal_id}

    # --- 4. עדכון חשוב (Critical) ---
    if proposal.action_type == "critical_info":
        return {"action_needed": True, "draft": msg, "internal_id": internal_id}

    # --- 5. עדכונים כלליים (Info / Newsletter) ---
    if proposal.action_type in ["log_info", "update", "info_update"]:
        return {"action_needed": True, "draft": msg, "internal_id": internal_id}

    # --- 6. קריאת יומן (Read Calendar) ---
    if proposal.action_type == "read_calendar":
        target_date = proposal.payload.get("start_time")
        if target_date:
             events_text = get_events_for_date(target_date)
             answer = f"📅 **הלו\"ז שלך ל-{proposal.payload.get('summary') or 'תאריך המבוקש'}:**\n{events_text}"
        else:
             upcoming = get_upcoming_events(days=3)
             answer = f"📅 **הלו\"ז הקרוב שלך (3 ימים):**\n{upcoming}"
        
        # אנחנו לא שומרים Pending Action לקריאת יומן (כי זו תשובה סופית), אלא אם המשתמש ירצה לערוך משהו משם.
        # אבל למען העקביות והיכולת להגיד "תמחק את הפגישה הראשונה", נשמור מצב כללי.
        return {"action_needed": True, "draft": answer, "internal_id": internal_id}

    # ברירת מחדל
    return {"action_needed": True, "draft": msg, "internal_id": internal_id}


@app.post("/execute")
def execute_task(payload: ExecutionRequest):
    print(f"🛠️ Manual Execution: {payload.action}")
    result_message = secretary.execute_instruction({
        "action": payload.action,
        "params": payload.params
    })
    return {"status": "done", "message": result_message}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)