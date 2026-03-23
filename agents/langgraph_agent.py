from typing import Annotated, Literal
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage, trim_messages, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
import os
from dotenv import load_dotenv
import datetime
import time
load_dotenv()

from utils.calendar_tools_lc import calendar_tools
from utils.gmail_tools_lc import gmail_tools
from agents.information_agent import InformationAgent
from utils.logger import agent_logger

# State Definition
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: str

# Define Tools
sensitive_tool_names = ["create_draft", "create_event", "update_event_time", "delete_event", "send_email", "trash_email"]

all_tools = calendar_tools + gmail_tools
safe_tools = [t for t in all_tools if t.name not in sensitive_tool_names]
sensitive_tools = [t for t in all_tools if t.name in sensitive_tool_names]

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from langchain_groq import ChatGroq

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY_2")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

ACTIVE_PROVIDER: str | None = None


def _quota_like_error(exc: Exception) -> bool:
    message = str(exc).lower()
    quota_markers = [
        "resource_exhausted",
        "spending cap",
        "credit balance is too low",
        "429",
        "rate limit",
        "quota",
        "insufficient credits",
    ]
    return any(marker in message for marker in quota_markers)


def _transient_retry_delay_seconds(exc: Exception) -> float | None:
    message = str(exc).lower()
    if "please try again in" not in message:
        return None

    import re

    wait_ms = re.search(r"try again in\s+([0-9]+)ms", message)
    if wait_ms:
        return max(0.5, min(float(wait_ms.group(1)) / 1000.0, 5.0))

    wait_s = re.search(r"try again in\s+([0-9]+(?:\.[0-9]+)?)s", message)
    if wait_s:
        return max(0.5, min(float(wait_s.group(1)), 5.0))

    return 1.0


def _build_llm_candidates() -> list[tuple[str, object]]:
    candidates: list[tuple[str, object]] = []

    if GEMINI_API_KEY:
        candidates.append(
            (
                "gemini",
                ChatGoogleGenerativeAI(
                    model="gemini-flash-latest",
                    google_api_key=GEMINI_API_KEY,
                    temperature=0.0,
                ).bind_tools(all_tools),
            )
        )

    if ANTHROPIC_API_KEY:
        candidates.append(
            (
                "anthropic",
                ChatAnthropic(
                    model="claude-3-5-haiku-latest",
                    api_key=ANTHROPIC_API_KEY,
                    temperature=0.0,
                ).bind_tools(all_tools),
            )
        )

    if GROQ_API_KEY:
        candidates.append(
            (
                "groq",
                ChatGroq(
                    model="llama-3.3-70b-versatile",
                    api_key=GROQ_API_KEY,
                    temperature=0.0,
                ).bind_tools(all_tools),
            )
        )

    return candidates


LLM_CANDIDATES = _build_llm_candidates()


def invoke_with_fallback(messages: list[BaseMessage]):
    global ACTIVE_PROVIDER

    if not LLM_CANDIDATES:
        raise RuntimeError("No LLM providers are configured.")

    ordered_candidates = LLM_CANDIDATES
    if ACTIVE_PROVIDER:
        ordered_candidates = sorted(
            LLM_CANDIDATES,
            key=lambda item: 0 if item[0] == ACTIVE_PROVIDER else 1,
        )

    last_error: Exception | None = None
    for provider_name, client in ordered_candidates:
        for attempt in range(2):
            try:
                response = client.invoke(messages)
                if ACTIVE_PROVIDER != provider_name:
                    agent_logger.warning(f"🔁 LLM provider switched to {provider_name}.")
                ACTIVE_PROVIDER = provider_name
                return response
            except Exception as exc:
                last_error = exc
                retry_delay = _transient_retry_delay_seconds(exc)
                if retry_delay is not None and attempt == 0:
                    agent_logger.warning(
                        f"LLM provider '{provider_name}' hit a transient rate limit. Retrying in {retry_delay:.2f}s."
                    )
                    time.sleep(retry_delay)
                    continue

                quota_like = _quota_like_error(exc)
                level = agent_logger.warning if quota_like else agent_logger.error
                level(f"LLM provider '{provider_name}' failed: {exc}")
                break

    if last_error is not None:
        raise last_error
    raise RuntimeError("No LLM provider succeeded.")

# Initialize RAG for manual routing (Optional, we can also expose RAG as a tool later)
rag_agent = InformationAgent()

# Context Prompt
SYSTEM_PROMPT = """ROLE: myOS Secretariat
You are a high-efficiency personal assistant. Your sole purpose is to SAVE user time. Be extremely concise. No greetings, NO chit-chat.

TODAY: {CURRENT_DATETIME}

═══════════════════════════════════════════
1. THE MOST CRITICAL RULE — HOW TO HANDLE ACTIONS
═══════════════════════════════════════════
When you need to CREATE an event, SEND an email, or DELETE an event:

  ✅ CORRECT FLOW (MANDATORY):
     Step 1 → Immediately CALL the relevant tool(s) (e.g., create_draft, create_event, send_email).
     Step 2 → The system AUTOMATICALLY pauses for user approval. You do NOT need to ask.
     Step 3 → Present the content you included in the tool call so the user can review it.
     Step 4 → End with [[BUTTONS: ...]].

  ❌ WRONG FLOW (NEVER DO THIS):
     × Write "Here is a draft:" and show text WITHOUT calling the tool.
     × Ask "Shall I send this?" before calling the tool.
     × Assume the user will somehow approve something you didn't actually call.

WHY: The system has a built-in Human-in-the-Loop (HITL) interceptor. When you call a sensitive tool,
     execution is AUTOMATICALLY PAUSED before it runs. The user then approves/rejects.
     If you don't call the tool, there is nothing to approve — the system loops.

BUTTON APPROVALS: If the user sends "אשר", "שלח", or clicks an approval button,
     it means they are approving the PENDING tool call from the previous turn.
     Do NOT regenerate a new draft. Do NOT respond with the same message. The system handles it.
SEND APPROVALS: If the approved pending tool is a draft for a task/general email, the next step is send_email.
     Do NOT create a reminder, follow-up task, or calendar event unless the user explicitly asked for one.

═══════════════════════════════════════════
2. OPERATING RULES
═══════════════════════════════════════════
SILENT IGNORE: If an email is spam/junk/ad, output ONLY [IGNORE_EMAIL].
SUCCESS & STOP: After an action executes, confirm briefly and STOP.
PARALLEL EXECUTION: Call multiple safe tools (search + calendar) in the same turn.
LEAN SEARCH: Fetch full email body only when needed (use fetch_recent_emails first for metadata).

═══════════════════════════════════════════
3. LANGUAGE & DRAFTS
═══════════════════════════════════════════
INTERFACE: All explanations and buttons → HEBREW ONLY.
DRAFT LANGUAGE: Match the sender's language.
TRANSLATION: If draft is not Hebrew, add a Hebrew translation below it.
TONE: Formal (recruiters/work) | Semi-formal (colleagues) | Casual (friends/family).
STYLE: Dense operational Telegram cards. High information density, minimal chatter, no raw technical blocks.
PRIVACY: Never reveal private calendar details, lesson schedules, or personal reasons inside outbound drafts. Say only that the time does not work and propose an alternative.
PRIVACY STRICTNESS: Never mention the user's classes, gym, commute, personal routine, existing meetings, or "my schedule is full". External recipients should only hear the outcome: unavailable, available, proposed alternative, or confirmed.

═══════════════════════════════════════════
4. SCHEDULING INTELLIGENCE
═══════════════════════════════════════════
SEARCH FIRST: If entity/email is unknown → use search_emails or search_contacts.
FREE SLOTS: Before suggesting meeting times → call get_free_slots(date). Never ask "when are you free?".
BUFFERS: 45 min after events; 30 min before fixed activities (gym/class).
URGENCY: Mark [דחוף] ONLY for same-day cancellations or last-minute changes.
TASK EMAILS: For requests like documents, approvals, updates, invoices, or follow-up replies, do NOT create calendar events or reminders unless the user explicitly asked to add one to the calendar.
DEADLINE-ONLY EMAILS: A deadline, submission window, one-way interview, assessment, verification link, or "complete by DATE" is NOT a meeting. Do NOT call create_event for these unless the user explicitly asks to block calendar time.
EVENT TITLES: Every created/rescheduled meeting title must follow this format: [Purpose] - [Person/Company]. Examples: "שיחת היכרות - דנה קפלן", "ראיון טכני - Surecomp", "שיעור פרטי - גולן לוי".
GOLDEN WINDOWS: Prefer slots that preserve buffers, avoid back-to-back meetings across locations, and avoid using the exact minute another event ends unless the gap remains valid after travel/transition time.

═══════════════════════════════════════════
5. FORMATTING
═══════════════════════════════════════════
DATES: "יום [שם יום], DD.MM.YYYY בשעה HH:MM"
SUMMARIES: Always compress the email/request into 1-2 short sentences. Never paste the full email body or raw "From/Subject/Content" metadata into the user-facing summary.

BUTTONS: Every response requiring action MUST end with:
[[BUTTONS: Option A | Option B | אתן הכוונה]]
The 3rd button is ALWAYS "אתן הכוונה" as the manual override.
No buttons on final success confirmations.

═══════════════════════════════════════════
6. TEMPLATES
═══════════════════════════════════════════
A. Meeting / Calendar invite:
📅 [מטרת הפגישה - עם מי הפגישה]
👤 שולח: [שם/שולח]
⏰ מועד מבוקש: [תאריך אנושי]
📌 [סיכום קצר מאוד: עד 1-2 משפטים, בלי להעתיק את כל המייל]

💡 הצעה לפעולה: [מה בדיוק יאושר]
[משפט הסבר קצר אם צריך]
[[BUTTONS: אשר וסנכרן ליומן | דחה בנימוס | אתן הכוונה]]

B. Task / General:
[Emoji] [כותרת]
👤 שולח: [שם/שולח אם רלוונטי]
[⏰ מועד / דדליין אם רלוונטי]
📌 [פרטים קצרים]

✍️ טיוטת מענה ([שפת המקור]) או פעולה מוצעת:
[תוכן]
[תרגום לעברית אם לא בעברית]

💡 הצעה לפעולה: [אישור ושליחת הטיוטה / ביצוע הפעולה]
[[BUTTONS: אשר ושלח | דחה בנימוס | אתן הכוונה]]

C. Final success confirmation:
✅ [הפעולה בוצעה]
📅 [תאריך אם רלוונטי]
⏰ [שעה אם רלוונטי]
"""

# Message Trimmer to stay within Groq limits (TPM: 12,000)
# We use a simple character-based counter to avoid installing 'transformers' (very heavy package)
def estimate_tokens(messages):
    total_chars = 0
    for m in messages:
        if isinstance(m.content, str):
            total_chars += len(m.content)
        elif isinstance(m.content, list):
            for part in m.content:
                if isinstance(part, dict) and "text" in part:
                    total_chars += len(part["text"])
    return total_chars // 2 # Aggressive heuristic: ~2 characters per token to be safe

trimmer = trim_messages(
    max_tokens=15000, # Reduced from 30k to 15k to save tokens and improve speed
    strategy="last",
    token_counter=estimate_tokens,
    include_system=True,
    allow_partial=False,
    start_on="human",
)

def agent_node(state: AgentState):
    """The main LLM node that decides what to do."""
    messages = state["messages"]
    
    # Inject current datetime into prompt
    now = datetime.datetime.now()
    hebrew_days = ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"]
    day_name = hebrew_days[int(now.strftime("%w"))]
    current_time_str = f"יום {day_name}, {now.strftime('%d.%m.%Y')} בשעה {now.strftime('%H:%M')}"
    dynamic_prompt = SYSTEM_PROMPT.replace("{CURRENT_DATETIME}", current_time_str)
    
    sys_msg = SystemMessage(content=dynamic_prompt)
    
    # Trim messages to stay within token limits
    trimmed_messages = trimmer.invoke([sys_msg] + messages)
    
    # 🌟 Fix for Gemini "contents are required" bug 🌟
    # Gemini requires all messages in history to have non-empty content strings, even if they have tool_calls.
    sanitized_messages = []
    has_any_human = False
    for m in trimmed_messages:
        if isinstance(m, HumanMessage):
             has_any_human = True
             
        # Evaluate if content is missing, empty string, or empty list
        has_content = False
        content = getattr(m, "content", None)
        if isinstance(content, str) and content.strip():
            has_content = True
        elif isinstance(content, list) and len(content) > 0:
            has_content = True
            
        if not has_content:
            if isinstance(m, dict):
                 # Handle as dict if it somehow is one
                 m["content"] = " "
                 sanitized_messages.append(m)
            elif isinstance(m, ToolMessage):
                 new_kwargs = m.dict() if hasattr(m, "dict") else {"content": " ", "name": m.name, "tool_call_id": m.tool_call_id}
                 new_kwargs["content"] = "[Tool Completed]"
                 sanitized_messages.append(ToolMessage(**new_kwargs))
            else:
                 # Force string space to prevent 500 error
                 try:
                     new_kwargs = m.dict()
                 except: 
                     new_kwargs = {"content": m.content, "type": m.type}
                 new_kwargs["content"] = " " # Space character bypasses the empty check
                 sanitized_messages.append(m.__class__(**new_kwargs))
        else:
            sanitized_messages.append(m)
            
    # 🌟 Final Safety Step for Gemini 🌟
    # If no human message is present (e.g. trimmer cut it), Gemini fails with "contents are required".
    # We must ensure at least one HumanMessage exists if we have a SystemMessage.
    if not has_any_human:
         # Find the last human message in the ORIGINAL list to restore it, or add a placeholder
         last_human = next((msg for msg in reversed(messages) if isinstance(msg, HumanMessage)), None)
         if last_human:
              sanitized_messages.insert(1 if isinstance(sanitized_messages[0], SystemMessage) else 0, last_human)
         else:
              sanitized_messages.insert(1 if isinstance(sanitized_messages[0], SystemMessage) else 0, HumanMessage(content="[משימה ממשיכה]"))
    
    # Log sizes for debugging
    est_tokens = estimate_tokens(sanitized_messages)
    agent_logger.info(f"📊 Gemini Request: {len(sanitized_messages)} messages, Estimated tokens: {est_tokens}")
    for i, msg in enumerate(sanitized_messages):
        agent_logger.debug(f"  [Msg {i}] Type: {type(msg)}, Content: {repr(getattr(msg, 'content', None))}, ToolCalls: {getattr(msg, 'tool_calls', 'None')}")
    
    response = invoke_with_fallback(sanitized_messages)
    return {"messages": [response]}

def route_tools(state: AgentState) -> Literal["safe_tools", "sensitive_tools", "__end__"]:
    """Route to safe or sensitive tools, or end if no tools called."""
    messages = state["messages"]
    last_message = messages[-1]
    
    # If LLM didn't call any native tools, end
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return "__end__"
    
    # Check if ANY of the called tools are sensitive
    for tc in last_message.tool_calls:
        if tc["name"] in sensitive_tool_names:
            return "sensitive_tools"
            
    return "safe_tools"

# Create Tool Nodes
safe_tools_node = ToolNode(safe_tools)
sensitive_tools_node = ToolNode(sensitive_tools)

# Build the Graph
workflow = StateGraph(AgentState)

workflow.add_node("agent", agent_node)
workflow.add_node("safe_tools", safe_tools_node)
workflow.add_node("sensitive_tools", sensitive_tools_node)

workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", route_tools)

# After tools run, go back to agent
workflow.add_edge("safe_tools", "agent")
workflow.add_edge("sensitive_tools", "agent")

# Compile with Checkpointer (Memory) and Breakpoint (HITL)
# We will use MongoDBSaver in the main app, for now we will just return the compiled graph
def build_graph(checkpointer=None):
    if checkpointer:
        return workflow.compile(
            checkpointer=checkpointer,
            interrupt_before=["sensitive_tools"]
        )
    return workflow.compile()
