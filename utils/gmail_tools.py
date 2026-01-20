import base64
from email.mime.text import MIMEText
from utils.gmail_connector import get_gmail_service

def fetch_recent_emails(limit=5):
    """
    מושך את המיילים האחרונים מהתיבה (Inbox)
    מחזיר רשימה נקייה של: מי שלח, הנושא, ותקציר התוכן.
    """
    service = get_gmail_service()
    
    print(f"📥 Fetching last {limit} emails...")
    
    # שליפת רשימת ההודעות
    results = service.users().messages().list(userId='me', labelIds=['INBOX'], maxResults=limit).execute()
    messages = results.get('messages', [])

    clean_emails = []

    if not messages:
        print("No messages found.")
        return []

    for msg in messages:
        # קריאת התוכן המלא של כל הודעה
        txt = service.users().messages().get(userId='me', id=msg['id']).execute()
        
        # חילוץ כותרות (מי שלח, מה הנושא)
        headers = txt['payload']['headers']
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), "No Subject")
        sender = next((h['value'] for h in headers if h['name'] == 'From'), "Unknown Sender")
        
        # חילוץ תקציר (Snippet)
        snippet = txt.get('snippet', '')

        clean_emails.append({
            "id": msg['id'],
            "sender": sender,
            "subject": subject,
            "snippet": snippet
        })
    
    return clean_emails

def create_draft(to_email, subject, body):
    """
    יוצר טיוטה חדשה ב-Gmail (לא שולח, רק שומר ב-Drafts)
    """
    service = get_gmail_service()
    
    message = MIMEText(body)
    message['to'] = to_email
    message['subject'] = subject
    
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    body = {'message': {'raw': raw}}
    
    try:
        draft = service.users().drafts().create(userId='me', body=body).execute()
        print(f"📝 Draft created! ID: {draft['id']}")
        return draft
    except Exception as e:
        print(f"❌ Error creating draft: {e}")
        return None

def create_label(label_name):
    """יוצר תווית חדשה בג'ימייל אם היא לא קיימת"""
    service = get_gmail_service()
    try:
        results = service.users().labels().list(userId='me').execute()
        labels = results.get('labels', [])
        for label in labels:
            if label['name'].lower() == label_name.lower():
                return label['id']
        
        label_object = {'name': label_name, 'labelListVisibility': 'labelShow', 'messageListVisibility': 'show'}
        created = service.users().labels().create(userId='me', body=label_object).execute()
        print(f"🏷️ Label created: {label_name}")
        return created['id']
    except Exception as e:
        print(f"❌ Error creating label: {e}")
        return None

def add_label_to_email(msg_id, label_name):
    """מוסיף תווית למייל ספציפי"""
    service = get_gmail_service()
    label_id = create_label(label_name)
    
    if label_id:
        try:
            body = {'addLabelIds': [label_id]}
            service.users().messages().modify(userId='me', id=msg_id, body=body).execute()
            print(f"🏷️ Label '{label_name}' added to email {msg_id}")
        except Exception as e:
            print(f"❌ Error adding label: {e}")

def archive_email(msg_id):
    """מעביר מייל לארכיון (מסיר אותו מה-Inbox)"""
    service = get_gmail_service()
    try:
        body = {'removeLabelIds': ['INBOX']}
        service.users().messages().modify(userId='me', id=msg_id, body=body).execute()
        print(f"🗄️ Email {msg_id} archived.")
    except Exception as e:
        print(f"❌ Error archiving email: {e}")

def trash_email(msg_id):
    """מעביר מייל לאשפה (Trash)"""
    service = get_gmail_service()
    try:
        service.users().messages().trash(userId='me', id=msg_id).execute()
        print(f"🗑️ Email {msg_id} moved to TRASH.")
        return True
    except Exception as e:
        print(f"❌ Error trashing email: {e}")
        return False