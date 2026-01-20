from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import os

# ייבוא הסוכנים והכלים
from agents.secretariat_agent import SecretariatAgent
from agents.information_agent import InformationAgent
from core.state_manager import StateManager # הרכיב החדש

app = FastAPI()

print("👔 Manager: Initializing MyOS Team...")
secretary = SecretariatAgent() 
librarian = InformationAgent()
state_manager = StateManager() # אתחול מנהל המצבים
print("✅ Manager: Team is ready & Scalable!")

# --- מודלים ---
class RequestModel(BaseModel):
    text: str
    source: str = "telegram"
    user_id: str = "admin"
    email_id: str = None # הוספנו עבור מחיקת ספאם

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

# --- 2. המוח המרכזי (שיחה + ניהול אישורים) ---
@app.post("/ask")
def ask_brain(payload: RequestModel):
    user_text = payload.text.strip().lower()
    user_id = payload.user_id # זיהוי המשתמש (חשוב להרחבות עתידיות)

    print(f"❓ User ({user_id}) asks: {user_text}")

    # א. בדיקה: האם המשתמש מנסה לאשר פעולה שממתינה?
    # מילים שמעידות על אישור
    approval_keywords = ["כן", "מאשר", "תאשר", "סגור", "yes", "approve", "confirm", "לך על זה"]
    
    # שליפת המצב הנוכחי של המשתמש מהזיכרון הניהולי
    pending_state = state_manager.get_pending_action(user_id)

    # התנאי: יש משהו בזיכרון + המשתמש אמר מילת אישור
    if pending_state and any(word in user_text for word in approval_keywords):
        print(f"🚀 Approval detected for action: {pending_state['action']}")
        
        agent_name = pending_state['agent']
        result_msg = ""

        # ניתוב לסוכן הנכון לפי מה שנשמר בזיכרון
        if agent_name == "secretariat_agent":
            result_msg = secretary.execute_instruction({
                "action": pending_state['action'],
                "params": pending_state['params']
            })
        
        # (בעתיד נוסיף כאן: elif agent_name == "finance_agent": ...)

        # ניקוי המצב אחרי ביצוע (כדי שלא יאושר פעמיים)
        state_manager.clear_state(user_id)
        
        return {"answer": f"בוצע! ✅\n{result_msg}"}

    # ב. אם אין פעולה ממתינה, זו סתם שאלה לידע הכללי
    print("📚 No pending actions. Routing to RAG.")
    answer = librarian.ask_brain(payload.text)
    return {"answer": answer}


# --- 3. ניתוח אירועים (מיילים) והכנת הקרקע לאישור ---
@app.post("/analyze_email")
def analyze_incoming_event(payload: RequestModel):
    proposal = secretary.process(payload.text)
    
    # 1. מניעת כפילות: אם זוהה ספאם, מבצעים ושולחים הודעה אחת בלבד
    if proposal.action_type == "trash":
        if payload.email_id:
            secretary.execute_instruction({"action": "trash_email", "params": {"email_id": payload.email_id}})
        return {"action_needed": True, "draft": proposal.payload.get('message')}

    # 2. משימה אקטיבית - כותרת בולטת ועיצוב נקי
    if proposal.action_type == "update":
        return {"action_needed": True, "draft": proposal.payload.get('message')}

    # 3. פגישות - ניקוי הלו"ז והצגת הטיוטה
    if proposal.action_type in ["draft_email", "schedule_event", "notify_user"]:
        msg = proposal.payload.get('message')
        
        # הוספת רשימת האירועים מאותו היום (אם קיים בשדה calendar_preview)
        calendar_preview = proposal.payload.get('calendar_preview')
        if calendar_preview:
            msg += f"\n\n{calendar_preview}"

        # הוספת הטיוטה להודעה בטלגרם בצורה ברורה
        if proposal.payload.get('draft'):
            # יצירת הטיוטה ב-Gmail ברקע
            secretary.execute_instruction({
                "action": "draft_email",
                "params": {
                    "email": proposal.payload.get("email"), 
                    "subject": "תשובה לגבי פגישה",
                    "body": proposal.payload.get("draft")
                }
            })
            msg += f"\n\n✍️ <b>טיוטה שהוכנה עבורך:</b> \n{proposal.payload.get('draft')}"
            msg += "\n\n<i>(הטיוטה כבר מחכה לך ב-Gmail)</i>"

        # שמירת מצב לאישור במידה והזמן פנוי (schedule_event)
        if proposal.action_type == "schedule_event":
            state_manager.set_pending_action(
                user_id=payload.user_id, 
                agent_name="secretariat_agent", 
                action_type="schedule_event", 
                params={
                    "summary": f"פגישה עם {proposal.payload.get('email')}",
                    "start_time": proposal.payload.get("start_time"),
                    "email": proposal.payload.get("email")
                }
            )
            msg += "\n\nהאם לאשר את הפגישה? (ענה 'כן' או 'לא')"

        return {"action_needed": True, "draft": msg}

    return {"action_needed": True, "draft": proposal.payload.get("message")}


# --- 4. WEBHOOK: קבלת הודעות מוואטסאפ (אישורים) ---
@app.post("/webhook/whatsapp")
def whatsapp_webhook(payload: RequestModel):
    user_id = payload.user_id
    user_text = payload.text.strip().lower()
    
    print(f"📩 WhatsApp Incoming: {user_text} (User: {user_id})")

    # 1. בדיקה: האם זו תשובה לפעולה ממתינה?
    approval_keywords = ["כן", "מאשר", "תאשר", "סגור", "yes", "approve", "confirm", "לך על זה"]
    cancel_keywords = ["לא", "בטל", "cancel", "no", "stop"]
    
    pending_state = state_manager.get_pending_action(user_id)
    
    if pending_state:
        # אם המשתמש אישר
        if any(word in user_text for word in approval_keywords):
            print(f"🚀 Approval received! Executing: {pending_state['action']}")
            
            # ביצוע הפעולה שנשמרה
            agent_name = pending_state['agent']
            result_msg = ""
            
            if agent_name == "secretariat_agent":
                result_msg = secretary.execute_instruction({
                    "action": pending_state['action'],
                    "params": pending_state['params']
                })
            
            state_manager.clear_state(user_id)
            return {"answer": f"קיבלתי! הנה הסיכום:\n{result_msg}"}
            
        # אם המשתמש ביטל
        elif any(word in user_text for word in cancel_keywords):
            state_manager.clear_state(user_id)
            return {"answer": "בוטל. 👍"}

    # 2. אם זה לא אישור, מעבירים למנגנון השיחה הרגיל (RAG)
    print("💬 Routing to general chat...")
    answer = librarian.ask_brain(payload.text)
    return {"answer": answer}

# --- 5. ביצוע ישיר (למקרי חירום/בדיקות) ---
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