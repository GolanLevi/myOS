import os
from utils.logger import memory_logger
import re
import time
import uuid
from pymongo import MongoClient

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")


class WorkflowStateStore:
    def __init__(self):
        memory_logger.info("💾 Connecting to MongoDB...")
        try:
            self.client = MongoClient(MONGODB_URL, serverSelectionTimeoutMS=5000)
            # בדיקת חיבור
            self.client.server_info()
            self.db = self.client["myos"]
            self.actions = self.db["pending_actions"]
            self.messages = self.db["message_map"]
            self.contacts = self.db["contacts"]
            # אינדקס ייחודי לפי משתמש + כתובת מייל (multi-tenant)
            self.contacts.create_index([("user_id", 1), ("email", 1)], unique=True)
            memory_logger.info(f"✅ Connected to MongoDB ({MONGODB_URL})")
        except Exception as e:
            memory_logger.error(f"❌ MongoDB connection failed: {e}")
            memory_logger.warning("⚠️ Falling back to in-memory mode!")
            self.client = None
            self.db = None
            self.actions = None
            self.messages = None
            self.contacts = None
            # Fallback - שימוש בזיכרון אם אין MongoDB
            self._memory_actions = {}
            self._memory_messages = {}
            self._memory_contacts = {}

    # --- שמירת פעולה ---
    def save_action(self, user_id: str, agent_name: str, action_type: str, params: dict) -> str:
        """שומר פעולה חדשה ומחזיר מזהה פנימי (Internal ID)"""
        action_id = str(uuid.uuid4())[:8]

        doc = {
            "_id": action_id,
            "user_id": user_id,
            "agent": agent_name,
            "action": action_type,
            "params": params,
            "status": "pending",
            "created_at": time.time(),
            "updated_at": time.time()
        }

        memory_logger.info(f"💾 Saving action '{action_type}' (ID: {action_id})")
        if self.actions is not None:
            self.actions.insert_one(doc)
        else:
            self._memory_actions[action_id] = doc

        memory_logger.info(f"💾 Saving action '{action_type}' (ID: {action_id})")
        return action_id

    # --- מיפוי הודעות טלגרם ---
    def map_telegram_id(self, internal_id: str, telegram_msg_id: str):
        """מקשר בין הודעה בטלגרם לפעולה בזיכרון"""
        # בדיקה שהפעולה קיימת
        action = self._get_action_doc(internal_id)
        if not action:
            return False

        memory_logger.info(f"🔗 Mapped Telegram Msg {telegram_msg_id} -> Action {internal_id}")

        if self.messages is not None:
            self.messages.update_one(
                {"telegram_id": str(telegram_msg_id)},
                {"$set": {"telegram_id": str(telegram_msg_id), "action_id": internal_id}},
                upsert=True
            )
        else:
            self._memory_messages[str(telegram_msg_id)] = internal_id

        return True

    # --- שליפה לפי הודעת טלגרם ---
    def get_action_by_message(self, telegram_msg_id: str):
        """שולף פעולה לפי מזהה הודעה בטלגרם"""
        if self.messages is not None:
            mapping = self.messages.find_one({"telegram_id": str(telegram_msg_id)})
            if mapping:
                action_id = mapping.get("action_id")
                if action_id:
                    return self._get_action_as_dict(action_id)
        else:
            action_id = self._memory_messages.get(str(telegram_msg_id))
            if action_id:
                doc = self._memory_actions.get(action_id)
                if doc:
                    return self._doc_to_legacy(doc)
        return None

    # --- Backward Compatibility ---
    def set_pending_action(self, user_id: str, agent_name: str, action_type: str, params: dict):
        """פונקציית מעטפת לתמיכה בקוד קיים"""
        return self.save_action(user_id, agent_name, action_type, params)

    def get_pending_action(self, user_id: str, max_age_minutes: int = 30):
        """מחזיר את הפעולה האחרונה של המשתמש (רק אם היא עדכנית)"""
        cutoff = time.time() - (max_age_minutes * 60)
        
        if self.actions is not None:
            doc = self.actions.find_one(
                {"user_id": user_id, "status": "pending", "created_at": {"$gte": cutoff}},
                sort=[("created_at", -1)]
            )
            if doc:
                return self._doc_to_legacy(doc)
            # אם לא מצאנו — ננקה פעולות ישנות אוטומטית
            self.actions.update_many(
                {"user_id": user_id, "status": "pending", "created_at": {"$lt": cutoff}},
                {"$set": {"status": "expired", "updated_at": time.time()}}
            )
        else:
            for aid in reversed(list(self._memory_actions.keys())):
                data = self._memory_actions[aid]
                if data["user_id"] == user_id and data.get("created_at", 0) >= cutoff:
                    return self._doc_to_legacy(data)
        return None

    # --- ניקוי ---
    def clear_action(self, action_id: str):
        """מסמן פעולה בודדת כ-completed"""
        if self.actions is not None:
            result = self.actions.update_one(
                {"_id": action_id},
                {"$set": {"status": "completed", "updated_at": time.time()}}
            )
            if result.modified_count > 0:
                memory_logger.info(f"🧹 Completed Action {action_id}")
        else:
            if action_id in self._memory_actions:
                del self._memory_actions[action_id]
                memory_logger.info(f"🧹 Cleared Action {action_id}")

    def clear_state(self, user_id: str):
        """מנקה את כל הפעולות הממתינות של משתמש מסוים"""
        if self.actions is not None:
            result = self.actions.update_many(
                {"user_id": user_id, "status": "pending"},
                {"$set": {"status": "completed", "updated_at": time.time()}}
            )
            if result.modified_count > 0:
                memory_logger.info(f"🧹 Completed {result.modified_count} actions for user '{user_id}'")
        else:
            ids_to_remove = [aid for aid, data in self._memory_actions.items() if data["user_id"] == user_id]
            for aid in ids_to_remove:
                del self._memory_actions[aid]
            if ids_to_remove:
                memory_logger.info(f"🧹 Cleared {len(ids_to_remove)} actions for user '{user_id}'")

    # --- פונקציות פנימיות ---
    def _get_action_doc(self, action_id: str):
        """שולף מסמך פעולה גולמי"""
        if self.actions is not None:
            return self.actions.find_one({"_id": action_id})
        else:
            return self._memory_actions.get(action_id)

    def _get_action_as_dict(self, action_id: str):
        """שולף פעולה ומחזיר בפורמט Legacy"""
        doc = self._get_action_doc(action_id)
        if doc:
            return self._doc_to_legacy(doc)
        return None

    def _doc_to_legacy(self, doc: dict) -> dict:
        """ממיר מסמך MongoDB לפורמט שהקוד הקיים מצפה לו"""
        return {
            "user_id": doc.get("user_id"),
            "agent": doc.get("agent"),
            "action": doc.get("action"),
            "params": doc.get("params", {}),
            "timestamp": doc.get("created_at", 0)
        }

    # ===== מערכת אנשי קשר =====

    def save_contact(self, user_id: str, name: str, email: str):
        """שומר או מעדכן איש קשר (upsert לפי user_id + כתובת מייל)"""
        email = email.strip().lower()
        name = name.strip()
        
        if not email or not name:
            return
        
        # לא לשמור כתובות noreply
        if any(skip in email for skip in ["noreply", "no-reply", "mailer-daemon", "notifications"]):
            return
        
        if self.contacts is not None:
            self.contacts.update_one(
                {"user_id": user_id, "email": email},
                {"$set": {
                    "user_id": user_id,
                    "name": name,
                    "email": email,
                    "last_seen": time.time()
                },
                "$inc": {"interactions": 1}},
                upsert=True
            )
        else:
            key = f"{user_id}:{email}"
            existing = self._memory_contacts.get(key, {})
            self._memory_contacts[key] = {
                "user_id": user_id,
                "name": name,
                "email": email,
                "last_seen": time.time(),
                "interactions": existing.get("interactions", 0) + 1
            }
        
        memory_logger.info(f"👤 Contact saved: {name} <{email}> (user: {user_id})")

    def find_contacts(self, user_id: str, search_name: str) -> list:
        """מחפש אנשי קשר לפי שם (חיפוש גמיש — חלקי, עברית ואנגלית)"""
        search_name = search_name.strip()
        if not search_name:
            return []
        
        results = []
        
        if self.contacts is not None:
            # חיפוש regex — מוצא גם חלק מהשם, מסונן לפי user_id
            pattern = re.compile(re.escape(search_name), re.IGNORECASE)
            cursor = self.contacts.find({
                "user_id": user_id,
                "$or": [
                    {"name": {"$regex": pattern}},
                    {"email": {"$regex": pattern}}
                ]
            })
            for doc in cursor:
                results.append({
                    "name": doc["name"],
                    "email": doc["email"],
                    "interactions": doc.get("interactions", 0)
                })
        else:
            for contact in self._memory_contacts.values():
                if contact.get("user_id") != user_id:
                    continue
                if search_name.lower() in contact["name"].lower() or \
                   search_name.lower() in contact["email"].lower():
                    results.append({
                        "name": contact["name"],
                        "email": contact["email"],
                        "interactions": contact.get("interactions", 0)
                    })
        
        # מיון לפי כמות אינטראקציות (הכי נפוץ קודם)
        results.sort(key=lambda x: x.get("interactions", 0), reverse=True)
        return results

    def get_all_contacts(self, user_id: str) -> list:
        """מחזיר את כל אנשי הקשר של משתמש ספציפי"""
        if self.contacts is not None:
            return list(self.contacts.find(
                {"user_id": user_id},
                {"_id": 0, "name": 1, "email": 1, "interactions": 1}
            ).sort("interactions", -1))
        else:
            return [c for c in self._memory_contacts.values() if c.get("user_id") == user_id]


# Backward-compatible alias during the naming transition.
StateManager = WorkflowStateStore
