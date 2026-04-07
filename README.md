<div align="center">

# 🧠 myOS — Personal Agent Orchestration System

![Views](https://komarev.com/ghpvc/?username=GolanLevi-myOS&label=Project%20Views&color=0e75b6&style=flat)

**The Problem:** Manual digital management and context-switching drain cognitive energy.  
**The Solution:** A LangGraph-powered orchestration layer that centralizes Gmail, Calendar, and Telegram into a single intelligent infrastructure, ensuring 100% privacy and human oversight.

[🇮🇱 לקריאה בעברית](README_HE.md)

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

## Safe Contributor Setup
Before changing this repo locally, use the isolated Codex dev box under [`infra/docker-image-codex`](infra/docker-image-codex/README.md). It keeps the repo inside a Docker volume, lets you connect through SSH from VS Code, and avoids exposing runtime secrets inside the working tree.

Use this flow:
1. Copy `infra/docker-image-codex/.env.example` to `infra/docker-image-codex/.env`.
2. Fill in only the required values:
   - `SSH_PUBLIC_KEY` with the contents of your local `id_ed25519.pub`
   - `GITHUB_APP_ID` and `GITHUB_APP_INSTALLATION_ID`
   - `GH_APP_PRIVATE_KEY_FILE` with a PEM path outside the repo
   - `GIT_REPO_URL=https://github.com/GolanLevi/myOS.git`
   - `GIT_REF` with your working branch, not `main`
3. Keep `BOOTSTRAP_GIT_SYNC_MODE=resume` unless you explicitly want startup sync behavior.
4. Start the box from `infra/docker-image-codex`:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
Unblock-File .\scripts\start.ps1
.\scripts\start.ps1
```

5. Connect with SSH or VS Code Remote-SSH to `dev@127.0.0.1` on port `2222`.
6. Open `/workspace`.
7. Run `codex --login` once inside the container.

Use a feature branch while testing, keep real secret files outside the repository, and commit/push your changes from inside the container so the branch stays the portable source of truth. See the full setup guide in [`infra/docker-image-codex/README.md`](infra/docker-image-codex/README.md).

---

## � Why I Built This?
I was tired of wasting time manually managing my emails and context-switching between apps just to schedule a meeting. I wanted a digital twin that does the heavy lifting:

*   **Triage:** Identifying what is irrelevant and what is urgent.
*   **Preparation:** Checking the calendar and drafting responses in advance.
*   **Safety:** Nothing is ever executed (sending an email/booking a meeting) without my explicit physical approval via Telegram (Human-in-the-Loop).

---

## 🏗️ End-to-End Architecture
Here is how information flows from the moment an email arrives until an action is executed:

```mermaid
graph TD
    A["📧 n8n Webhook\n(New Email Detection)"] -->|POST /analyze_email| B["⚡ FastAPI Manager\n(Management Server)"]
    B --> C["🧠 Secretariat Graph\n(LangGraph)"]
    C --> D["🤖 LLM Node\n(Gemini Flash)"]
    D --> E{"🛠️ Tool Router"}
    
    E -->|Safe Tools| F["🔍 Read-Only APIs\n(Gmail Search, Calendar View)"]
    F --> D
    
    E -->|Sensitive Tools| G["⛔ BREAKPOINT\n(State Frozen for Approval)"]
    G --> H["💬 Telegram Bot UI\n(Card with Approval Buttons)"]
    
    H -->|Approve / Feedback| I["⚡ FastAPI /ask\n(Resume Command)"]
    I -->|Load Checkpoint| C
    
    C --> J["✅ Final Execution\n(Send Email, Create Event)"]
    
    M[("🗄️ MongoDB")] -. "Persistence\n(State Memory)" .- C
    N[("🧠 ChromaDB")] -. "RAG Context\n(Vector Memory)" .- D
```

---

## 💡 Key Engineering Pillars

### 1. State Persistence
Using `MongoDBSaver`, the system can "freeze" its execution state. When a user approves an action via Telegram (even hours later), the graph resumes exactly where it left off.

### 2. Human-in-the-Loop (HITL)
A hardcoded "safety brake" is built into the graph topology. Any tool that mutates data in the real world is defined as a Sensitive Tool. The graph automatically freezes before execution, preventing any AI hallucinations.

### 3. Vector Memory (RAG)
Integrating ChromaDB allows the agent to store important information. When asked about past events, the agent retrieves historical facts via vector search before formulating a response.

---

## � Code Snapshot: Graph Definition & Interrupts

```python
# Defining tools that require explicit human approval
sensitive_tool_names = ["create_event", "send_email", "trash_email", "delete_event"]

# Building the graph with a built-in Breakpoint
def build_secretariat_graph(checkpointer):
    return workflow.compile(
        checkpointer=checkpointer, # Persisting state in MongoDB
        interrupt_before=["sensitive_tools"] # Physical stop before sensitive actions
    )
```
