from langchain_core.tools import tool
from typing import List, Optional, Any
from pydantic import BaseModel, Field
import json
import utils.gmail_tools as base_gmail

# --- Input Schemas ---

class EmailIdInput(BaseModel):
    msg_id: str = Field(..., description="The unique message ID of the email.")

class CreateDraftInput(BaseModel):
    to_email: str = Field(..., description="The recipient's email address.")
    subject: str = Field(..., description="The subject of the email.")
    body: str = Field(..., description="The main text body of the email.")
    thread_id: Optional[str] = Field(None, description="The thread ID to reply to, if applicable, to keep the conversation grouped.")

class SendEmailInput(BaseModel):
    to_email: str = Field(..., description="The recipient's email address.")
    subject: str = Field(..., description="The subject of the email.")
    body: str = Field(..., description="The main text body of the email.")
    thread_id: Optional[str] = Field(None, description="The thread ID to reply to, if applicable.")

class BatchManageInput(BaseModel):
    msg_ids: List[str] = Field(..., description="A list of unique message IDs for batch operations.")

class AddLabelInput(BaseModel):
    msg_id: str = Field(..., description="The unique message ID of the email.")
    label_name: str = Field(..., description="The name of the label to apply (e.g., 'Work', 'Invoices').")

class AttachmentInput(BaseModel):
    msg_id: str = Field(..., description="The ID of the email containing the attachment.")
    attachment_id: str = Field(..., description="The specific ID of the attachment to download.")


class EmailArtifactsInput(BaseModel):
    msg_id: str = Field(..., description="The ID of the email to inspect.")

# --- Tools ---

@tool("fetch_recent_emails")
def fetch_recent_emails(limit: int = 5) -> str:
    """Fetch the most recent emails from the Inbox.
    Returns only metadata and snippets to minimize token usage.
    Use 'fetch_full_email' for complete content.
    """
    try:
        emails = base_gmail.fetch_recent_emails(limit)
        if not emails:
            return "No recent emails found."
        optimized = []
        for e in emails:
            optimized.append({
                "id": e.get("id"),
                "threadId": e.get("threadId"),
                "sender": e.get("sender"),
                "subject": e.get("subject"),
                "snippet": e.get("snippet"),
                "has_attachments": bool(e.get("attachments")),
                "reply_possible": bool(e.get("reply_possible", True)),
            })
        return json.dumps(optimized, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error fetching emails: {str(e)}"

@tool("search_emails")
def search_emails(query: str) -> str:
    """Search for emails using Gmail search operators (e.g., 'from:boss@company.com', 'label:work', 'subject:invoice').
    Returns snippets and IDs for relevant messages.
    """
    try:
        service = base_gmail.get_gmail_service()
        res = service.users().messages().list(userId='me', q=query, maxResults=5).execute()
        messages = res.get('messages', [])
        if not messages:
            return f"No emails found for query: {query}"
        results = []
        for m in messages:
            msg = service.users().messages().get(userId='me', id=m['id'], format='minimal').execute()
            results.append({
                "id": msg['id'],
                "threadId": msg['threadId'],
                "snippet": msg.get('snippet', '')
            })
        return json.dumps(results, ensure_ascii=False)
    except Exception as e:
        return f"Search error: {str(e)}"

@tool("fetch_full_email", args_schema=EmailIdInput)
def fetch_full_email(msg_id: str) -> str:
    """Retrieve the complete content of an email, including the full body and a list of attachment IDs.
    Use this only after identifying the email ID via fetch_recent_emails or search_emails.
    """
    try:
        email_data = base_gmail.fetch_email_by_id(msg_id)
        if not email_data:
            return "Email not found."
        return json.dumps(email_data, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error fetching full email: {str(e)}"


@tool("inspect_email_artifacts", args_schema=EmailArtifactsInput)
def inspect_email_artifacts(msg_id: str) -> str:
    """Return verified email metadata for decision-making: sender, replyability, attachment names, and calendar-invite presence.
    Use this when you need to decide whether a draft is possible, whether attachments are truly present, or whether the email is likely a no-reply notification.
    """
    try:
        email_data = base_gmail.fetch_email_by_id(msg_id)
        if not email_data:
            return "Email not found."
        payload = {
            "id": email_data.get("id"),
            "threadId": email_data.get("threadId"),
            "sender": email_data.get("sender"),
            "sender_name": email_data.get("sender_name"),
            "sender_email": email_data.get("sender_email"),
            "reply_to_email": email_data.get("reply_to_email"),
            "effective_reply_email": email_data.get("effective_reply_email"),
            "reply_possible": bool(email_data.get("reply_possible")),
            "subject": email_data.get("subject"),
            "has_calendar_invite": bool(email_data.get("has_calendar_invite")),
            "attachments": [
                {
                    "filename": item.get("filename"),
                    "mimeType": item.get("mimeType"),
                    "size": item.get("size"),
                }
                for item in email_data.get("attachments", [])
            ],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error inspecting email artifacts: {str(e)}"

@tool("create_draft", args_schema=CreateDraftInput)
def create_draft(to_email: str, subject: str, body: str, thread_id: Optional[str] = None) -> str:
    """Create a new email draft (does NOT send). If thread_id is provided, the draft is a reply in that conversation."""
    try:
        draft = base_gmail.create_draft(to_email, subject, body, thread_id=thread_id)
        return f"Draft created successfully. ID: {draft['id']}"
    except Exception as e:
        return f"Failed to create draft: {str(e)}"

@tool("send_email", args_schema=SendEmailInput)
def send_email(to_email: str, subject: str, body: str, thread_id: Optional[str] = None) -> str:
    """Send an email immediately. ONLY use this tool after receiving explicit user approval (אשר/שלח)."""
    try:
        msg_id = base_gmail.send_email(to_email, subject, body, thread_id=thread_id)
        return f"Email sent successfully. Message ID: {msg_id}"
    except Exception as e:
        return f"Failed to send email: {str(e)}"

@tool("mark_as_read", args_schema=EmailIdInput)
def mark_as_read(msg_id: str) -> str:
    """Mark an email as read by removing the 'UNREAD' label."""
    try:
        base_gmail.remove_label(msg_id, 'UNREAD')
        return f"Email {msg_id} marked as read."
    except Exception as e:
        return f"Error marking as read: {str(e)}"

@tool("mark_as_unread", args_schema=EmailIdInput)
def mark_as_unread(msg_id: str) -> str:
    """Mark an email as unread by adding the 'UNREAD' label."""
    try:
        base_gmail.add_label_to_email(msg_id, 'UNREAD')
        return f"Email {msg_id} marked as unread."
    except Exception as e:
        return f"Error marking as unread: {str(e)}"

@tool("list_labels")
def list_labels() -> str:
    """Fetch a list of all available Gmail labels in the user's account."""
    try:
        service = base_gmail.get_gmail_service()
        results = service.users().labels().list(userId='me').execute()
        labels = [l['name'] for l in results.get('labels', [])]
        return json.dumps(labels, ensure_ascii=False)
    except Exception as e:
        return f"Error listing labels: {str(e)}"

@tool("batch_archive", args_schema=BatchManageInput)
def batch_archive(msg_ids: List[str]) -> str:
    """Archive multiple emails at once by removing them from the Inbox."""
    try:
        for mid in msg_ids:
            base_gmail.archive_email(mid)
        return f"Successfully archived {len(msg_ids)} emails."
    except Exception as e:
        return f"Batch operation failed: {str(e)}"

@tool("download_attachment", args_schema=AttachmentInput)
def download_attachment(msg_id: str, attachment_id: str) -> str:
    """Download a specific attachment from an email and return its size in bytes."""
    try:
        import base64 as b64
        service = base_gmail.get_gmail_service()
        att_data = service.users().messages().attachments().get(
            userId='me', messageId=msg_id, id=attachment_id
        ).execute()
        raw_bytes = b64.urlsafe_b64decode(att_data['data'])
        return f"Attachment retrieved. Size: {len(raw_bytes)} bytes."
    except Exception as e:
        return f"Download failed: {str(e)}"

@tool("archive_email", args_schema=EmailIdInput)
def archive_email(msg_id: str) -> str:
    """Archive a single email by removing it from the INBOX label."""
    try:
        base_gmail.archive_email(msg_id)
        return f"Email {msg_id} archived successfully."
    except Exception as e:
        return f"Failed to archive email: {str(e)}"

@tool("trash_email", args_schema=EmailIdInput)
def trash_email(msg_id: str) -> str:
    """Move an email to the Trash."""
    try:
        res = base_gmail.trash_email(msg_id)
        if res:
            return f"Email {msg_id} moved to Trash."
        return "Failed to trash email."
    except Exception as e:
        return f"Failed to trash email: {str(e)}"

@tool("add_label_to_email", args_schema=AddLabelInput)
def add_label_to_email(msg_id: str, label_name: str) -> str:
    """Add a label to an email (creates the label if it does not exist)."""
    try:
        base_gmail.add_label_to_email(msg_id, label_name)
        return f"Label '{label_name}' added to email {msg_id}."
    except Exception as e:
        return f"Failed to add label: {str(e)}"

# --- Final Tools List ---

gmail_tools = [
    fetch_recent_emails,
    search_emails,
    fetch_full_email,
    inspect_email_artifacts,
    create_draft,
    send_email,
    mark_as_read,
    mark_as_unread,
    list_labels,
    batch_archive,
    download_attachment,
    archive_email,
    trash_email,
    add_label_to_email,
]
