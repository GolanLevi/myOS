
import os
import sys

# Ensure project root is in path
sys.path.append(os.getcwd())

from utils.gmail_tools import fetch_recent_emails
from agents.secretariat_agent import SecretariatAgent

def main():
    print("🚀 Initializing Secretariat Agent for DRY RUN...")
    try:
        agent = SecretariatAgent()
    except Exception as e:
        print(f"❌ Failed to initialize agent: {e}")
        return

    print("📥 Fetching last 10 emails...")
    try:
        emails = fetch_recent_emails(limit=10)
    except Exception as e:
        print(f"❌ Failed to fetch emails (check credentials): {e}")
        return

    print(f"\n🔍 Analyzing {len(emails)} emails...\n")
    print(f"{'ACTION TYPE':<20} | {'SENDER':<25} | {'SUBJECT'}")
    print("-" * 80)

    for email in emails:
        # Construct the input text similar to how the production system would
        # Combining Sender, Subject, and Snippet gives the AI context
        user_input = f"From: {email['sender']}\nSubject: {email['subject']}\nContent: {email['snippet']}"
        
        try:
            # ONLY PROCESS, DO NOT EXECUTE actions
            proposal = agent.process(user_input)
            
            action = proposal.action_type
            sender_short = (email['sender'][:22] + '..') if len(email['sender']) > 22 else email['sender']
            subject_short = (email['subject'][:30] + '..') if len(email['subject']) > 30 else email['subject']
            
            icon = "❓"
            if action == "schedule_event": icon = "📅"
            elif action == "update_event": icon = "⚠️"
            elif action == "action_required": icon = "🔴"
            elif action == "critical_info": icon = "📢"
            elif action == "log_info": icon = "🗞️"
            elif action == "trash": icon = "🗑️"
            
            print(f"{icon} {action:<18} | {sender_short:<25} | {subject_short}")
            
        except Exception as e:
            print(f"❌ Error processing {email['id']}: {e}")

    print("\n✅ Simulation Complete. No actions were executed.")

if __name__ == "__main__":
    main()
