<div align="center">

# 🧠 myOS — Personal Agent Orchestration System

![Views](https://komarev.com/ghpvc/?username=GolanLevi-myOS&label=Project%20Views&color=0e75b6&style=flat)

**הבעיה:** ניהול זמן ותכתובות דיגיטליות גוזל משאבים קוגניטיביים יקרים.  
**הפתרון:** שכבת ניהול (Orchestration) מבוססת LangGraph, שמרכזת את כל הפעולות (Gmail, Calendar, Telegram) תחת תשתית אחת חכמה, תוך שמירה על פרטיות מקסימלית ובקרת אנוש.

[🇬🇧 Read in English](README.md)

</div>

---

### 🛠️ My Tech Stack

**Generative AI & Tech:**  
![LangGraph](https://img.shields.io/badge/LangGraph-1C1C1C?style=for-the-badge) ![Gemini Flash](https://img.shields.io/badge/Gemini_Flash-4285F4?style=for-the-badge&logo=google&logoColor=white) ![ChromaDB](https://img.shields.io/badge/ChromaDB-FF6C37?style=for-the-badge)

**Backend & Database:**  
![Python](https://img.shields.io/badge/Python_3.11-3776AB?style=for-the-badge&logo=python&logoColor=white) ![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white) ![MongoDB](https://img.shields.io/badge/MongoDB-4EA94B?style=for-the-badge&logo=mongodb&logoColor=white)

**Automation & Interface:**  
![n8n](https://img.shields.io/badge/n8n-FF6D5A?style=for-the-badge&logo=n8n&logoColor=white) ![Telegram Bot API](https://img.shields.io/badge/Telegram_Bot_API-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)

**Tools & Environment:**  
![Codex](https://img.shields.io/badge/Codex-000000?style=for-the-badge&logo=openai&logoColor=white) ![Antigravity](https://img.shields.io/badge/Antigravity-8A2BE2?style=for-the-badge)

---

## 📌 למה פיתחתי את זה?
נמאס לי לבזבז זמן על ניהול ידני של המיילים שלי ועל קפיצות בין אפליקציות כדי לתאם פגישה. רציתי תאום דיגיטלי שעושה את העבודה השחורה:

*   **סיווג:** מה לא רלוונטי ומה דחוף.
*   **הכנה:** בדיקת היומן וניסוח טיוטה מראש.
*   **בטיחות:** שום דבר לא יוצא לעולם (שליחת מייל/קביעת פגישה) בלי לחיצת כפתור שלי בטלגרם (Human in the loop).

---

## 🏗️ ארכיטקטורת המערכת (End-to-End Flow)
ככה המידע זורם מרגע שמגיע מייל ועד שהפעולה מבוצעת:

```mermaid
graph TD
    A["📧 n8n Webhook\n(זיהוי מייל חדש)"] -->|POST /analyze_email| B["⚡ FastAPI Manager\n(שרת הניהול)"]
    B --> C["🧠 Secretariat Graph\n(LangGraph)"]
    C --> D["🤖 LLM Node\n(Gemini Flash)"]
    D --> E{"🛠️ Router\n(ניתוב כלים)"}
    
    E -->|כלים 'בטוחים'| F["🔍 קריאת נתונים\n(חיפוש מיילים, צפייה ביומן)"]
    F --> D
    
    E -->|כלים 'רגישים'| G["⛔ BREAKPOINT\n(עצירה לאישור)"]
    G --> H["💬 בוט טלגרם\n(כרטיסייה עם כפתורי אישור)"]
    
    H -->|לחיצה על 'אשר'| I["⚡ FastAPI /ask\n(פקודת המשך)"]
    I -->|טעינת מצב| C
    
    C --> J["✅ ביצוע סופי\n(שליחת מייל, קביעת פגישה)"]
    
    M[("🗄️ MongoDB")] -. "Persistence\n(זיכרון מצב)" .- C
    N[("🧠 ChromaDB")] -. "RAG Context\n(זיכרון וקטורי)" .- D
```

---

## 💡 יכולות ליבה הנדסיות

### 1. ניהול מצב (State Persistence)
השתמשתי ב-`MongoDBSaver` כדי שהמערכת תוכל "ללכת לישון" אחרי שהיא שולחת לך הודעה בטלגרם. כשאתה לוחץ על "אשר" (אפילו שעתיים אחרי), המערכת טוענת את המצב המדויק שבו היא עצרה וממשיכה את הביצוע כאילו לא עבר זמן.

### 2. עצירה לאישור אנושי (Human-in-the-Loop)
המערכת מתוכנתת עם "בלם יד" טופולוגי. כל כלי שמשנה מידע בעולם האמיתי מוגדר כ-Sensitive Tool. הגרף קופא אוטומטית לפני הביצוע, מה שמונע טעויות או "הזיות" של ה-AI.

### 3. זיכרון ארוך טווח (RAG)
כל מידע חשוב נשמר ב-ChromaDB. כשאתה שואל שאלה על העבר, הסוכן מבצע חיפוש וקטורי ומקבל את העובדות הרלוונטיות לפני שהוא עונה.

---

## 💻 מבט לקוד: הגדרת הגרף והעצירות

```python
# הגדרת הכלים שדורשים אישור אנושי מפורש
sensitive_tool_names = ["create_event", "send_email", "trash_email", "delete_event"]

# בניית הגרף עם Breakpoint מובנה
def build_secretariat_graph(checkpointer):
    return workflow.compile(
        checkpointer=checkpointer, # שמירת המצב ב-MongoDB
        interrupt_before=["sensitive_tools"] # עצירה פיזית לפני פעולות רגישות
    )
```


