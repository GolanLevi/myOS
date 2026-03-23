# myOS Project Summary

## One-Line Summary

`myOS` is a local-first AI assistant that helps manage email, calendar, memory, and approvals through a unified FastAPI and Telegram workflow.

## Current Focus

The repository currently emphasizes:

- LangGraph orchestration for operational tasks
- Native Telegram approvals instead of outsourced chat handling
- Gmail ingestion via n8n
- Google Calendar scheduling with approval gates
- ChromaDB memory and MongoDB-backed state/checkpoints

## Public Demo Story

The strongest repository story today is:

1. An email arrives through Gmail and n8n.
2. The FastAPI server routes it through LangGraph.
3. The system summarizes it, prepares a draft or meeting action, and pauses.
4. Telegram presents the decision to the user.
5. The user approves, rejects, or edits the action.

This story is already supported by the screenshots in `docs/` and the Telegram formatter tests in the root of the repository.

## What Should Be Public

- Source code for orchestration, tools, bot, and state handling
- Sanitized screenshots and workflow exports
- Example configuration files
- Focused tests that demonstrate behavioral quality

## What Should Stay Private

- `.env`, `credentials.json`, `token.json`
- Local databases and exported SQLite snapshots
- Personal workflow exports with live IDs or sensitive content
- Personal documents and scratch files

## Recommended Next Improvements

- Add CI for at least one focused test file
- Add a small `docs/setup.md` for onboarding
- Add a sanitized request/response fixture for `/analyze_email`
- Add screenshots of Telegram approval cards in both English and Hebrew scenarios
