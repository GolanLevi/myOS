import time

class StateManager:
    def __init__(self):
        # המבנה: { "user_id": { "action": "...", "params": {...}, "agent": "...", "timestamp": 12345 } }
        self.pending_actions = {}

    def set_pending_action(self, user_id: str, agent_name: str, action_type: str, params: dict):
        """שומר פעולה שממתינה לאישור המשתמש"""
        print(f"💾 StateManager: Saving pending action '{action_type}' for user '{user_id}'")
        self.pending_actions[user_id] = {
            "agent": agent_name,
            "action": action_type,
            "params": params,
            "timestamp": time.time()
        }

    def get_pending_action(self, user_id: str):
        """שולף את הפעולה הממתינה (אם יש)"""
        return self.pending_actions.get(user_id)

    def clear_state(self, user_id: str):
        """מנקה את המצב אחרי שהפעולה בוצעה או בוטלה"""
        if user_id in self.pending_actions:
            del self.pending_actions[user_id]
            print(f"🧹 StateManager: State cleared for user '{user_id}'")
