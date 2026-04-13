import os
import re
import time
import uuid
from typing import Any

from pymongo import MongoClient

from utils.logger import memory_logger

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")


class WorkflowStateStore:
    def __init__(self):
        memory_logger.info("Connecting to MongoDB...")
        try:
            self.client = MongoClient(MONGODB_URL, serverSelectionTimeoutMS=5000)
            self.client.server_info()
            self.db = self.client["myos"]
            self.actions = self.db["pending_actions"]
            self.history = self.db["action_history"]
            self.messages = self.db["message_map"]
            self.contacts = self.db["contacts"]
            self.contacts.create_index([("user_id", 1), ("email", 1)], unique=True)
            self.history.create_index([("user_id", 1), ("timestamp", -1)])
            self.history.create_index([("action_id", 1), ("timestamp", -1)])
            memory_logger.info(f"Connected to MongoDB ({MONGODB_URL})")
        except Exception as e:
            memory_logger.error(f"MongoDB connection failed: {e}")
            memory_logger.warning("Falling back to in-memory mode.")
            self.client = None
            self.db = None
            self.actions = None
            self.history = None
            self.messages = None
            self.contacts = None
            self._memory_actions: dict[str, dict[str, Any]] = {}
            self._memory_history: list[dict[str, Any]] = []
            self._memory_messages: dict[str, str] = {}
            self._memory_contacts: dict[str, dict[str, Any]] = {}

    def save_action(
        self,
        user_id: str,
        agent_name: str,
        action_type: str,
        params: dict[str, Any],
        *,
        status: str = "pending",
    ) -> str:
        action_id = str(uuid.uuid4())[:8]
        now = time.time()
        doc = {
            "_id": action_id,
            "user_id": user_id,
            "agent": agent_name,
            "action": action_type,
            "params": params or {},
            "status": status,
            "created_at": now,
            "updated_at": now,
        }

        memory_logger.info(f"Saving action '{action_type}' (ID: {action_id}, status: {status})")
        if self.actions is not None:
            self.actions.insert_one(doc)
        else:
            self._memory_actions[action_id] = doc

        self._record_history_event(doc, event_type="created", metadata={"status": status})
        return action_id

    def update_action(
        self,
        action_id: str,
        *,
        status: str | None = None,
        params: dict[str, Any] | None = None,
        merge_params: dict[str, Any] | None = None,
        **extra_fields: Any,
    ) -> bool:
        fields_to_set: dict[str, Any] = {"updated_at": time.time(), **extra_fields}
        if status is not None:
            fields_to_set["status"] = status
        if params is not None:
            fields_to_set["params"] = params

        if self.actions is not None:
            existing_doc = self.actions.find_one({"_id": action_id})
            if not existing_doc:
                return False

            update_doc: dict[str, Any] = {"$set": fields_to_set}
            if merge_params:
                for key, value in merge_params.items():
                    update_doc["$set"][f"params.{key}"] = value

            result = self.actions.update_one({"_id": action_id}, update_doc)
            if result.modified_count > 0 or result.matched_count > 0:
                updated_doc = self.actions.find_one({"_id": action_id}) or existing_doc
                event_type = status if status and status != existing_doc.get("status") else "updated"
                self._record_history_event(
                    updated_doc,
                    event_type=event_type,
                    metadata={
                        "changed_fields": sorted(fields_to_set.keys()),
                        "merged_params": sorted((merge_params or {}).keys()),
                    },
                )
                memory_logger.info(f"Updated action '{action_id}'")
                return True
            return False

        doc = self._memory_actions.get(action_id)
        if not doc:
            return False

        previous_status = doc.get("status")
        doc.update(fields_to_set)
        if params is not None:
            doc["params"] = params
        elif merge_params:
            doc.setdefault("params", {}).update(merge_params)

        event_type = status if status and status != previous_status else "updated"
        self._record_history_event(
            doc,
            event_type=event_type,
            metadata={
                "changed_fields": sorted(fields_to_set.keys()),
                "merged_params": sorted((merge_params or {}).keys()),
            },
        )
        memory_logger.info(f"Updated action '{action_id}'")
        return True

    def map_telegram_id(self, internal_id: str, telegram_msg_id: str):
        action = self._get_action_doc(internal_id)
        if not action:
            return False

        memory_logger.info(f"Mapped Telegram Msg {telegram_msg_id} -> Action {internal_id}")
        if self.messages is not None:
            self.messages.update_one(
                {"telegram_id": str(telegram_msg_id)},
                {"$set": {"telegram_id": str(telegram_msg_id), "action_id": internal_id}},
                upsert=True,
            )
        else:
            self._memory_messages[str(telegram_msg_id)] = internal_id
        return True

    def get_action_by_message(self, telegram_msg_id: str):
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

    def set_pending_action(self, user_id: str, agent_name: str, action_type: str, params: dict):
        return self.save_action(user_id, agent_name, action_type, params)

    def get_pending_action(self, user_id: str, max_age_minutes: int = 30):
        cutoff = time.time() - (max_age_minutes * 60)
        if self.actions is not None:
            doc = self.actions.find_one(
                {"user_id": user_id, "status": "pending", "created_at": {"$gte": cutoff}},
                sort=[("created_at", -1)],
            )
            if doc:
                return self._doc_to_legacy(doc)
            self.actions.update_many(
                {"user_id": user_id, "status": "pending", "created_at": {"$lt": cutoff}},
                {"$set": {"status": "expired", "updated_at": time.time()}},
            )
        else:
            for aid in reversed(list(self._memory_actions.keys())):
                data = self._memory_actions[aid]
                if data["user_id"] == user_id and data.get("created_at", 0) >= cutoff:
                    return self._doc_to_legacy(data)
        return None

    def clear_action(self, action_id: str):
        if self.update_action(action_id, status="completed"):
            memory_logger.info(f"Completed Action {action_id}")

    def clear_state(self, user_id: str):
        if self.actions is not None:
            result = self.actions.update_many(
                {"user_id": user_id, "status": "pending"},
                {"$set": {"status": "completed", "updated_at": time.time()}},
            )
            if result.modified_count > 0:
                memory_logger.info(f"Completed {result.modified_count} actions for user '{user_id}'")
        else:
            ids_to_remove = [aid for aid, data in self._memory_actions.items() if data["user_id"] == user_id]
            for aid in ids_to_remove:
                self.update_action(aid, status="completed")
            if ids_to_remove:
                memory_logger.info(f"Completed {len(ids_to_remove)} actions for user '{user_id}'")

    def get_action(self, action_id: str) -> dict[str, Any] | None:
        return self._get_action_doc(action_id)

    def list_history(self, user_id: str, limit: int = 50, page: int = 1) -> list[dict[str, Any]]:
        start = max(0, (page - 1) * limit)
        if self.history is not None:
            cursor = self.history.find({"user_id": user_id}).sort("timestamp", -1).skip(start).limit(limit)
            return list(cursor)
        entries = [doc for doc in self._memory_history if doc.get("user_id") == user_id]
        entries.sort(key=lambda item: item.get("timestamp", 0), reverse=True)
        return entries[start : start + limit]

    def _get_action_doc(self, action_id: str):
        if self.actions is not None:
            return self.actions.find_one({"_id": action_id})
        return self._memory_actions.get(action_id)

    def _get_action_as_dict(self, action_id: str):
        doc = self._get_action_doc(action_id)
        if doc:
            return self._doc_to_legacy(doc)
        return None

    def _doc_to_legacy(self, doc: dict) -> dict:
        return {
            "user_id": doc.get("user_id"),
            "agent": doc.get("agent"),
            "action": doc.get("action"),
            "params": doc.get("params", {}),
            "timestamp": doc.get("created_at", 0),
        }

    def _record_history_event(self, action_doc: dict[str, Any], *, event_type: str, metadata: dict[str, Any] | None = None) -> None:
        entry = {
            "action_id": str(action_doc.get("_id") or ""),
            "thread_id": str(action_doc.get("_id") or ""),
            "user_id": action_doc.get("user_id"),
            "agent": action_doc.get("agent"),
            "action": action_doc.get("action"),
            "event_type": event_type,
            "status": action_doc.get("status"),
            "params": action_doc.get("params", {}) or {},
            "metadata": metadata or {},
            "timestamp": time.time(),
        }
        if self.history is not None:
            self.history.insert_one(entry)
            return
        self._memory_history.append(entry)

    def save_contact(self, user_id: str, name: str, email: str):
        email = email.strip().lower()
        name = name.strip()
        if not email or not name:
            return
        if any(skip in email for skip in ["noreply", "no-reply", "mailer-daemon", "notifications"]):
            return

        if self.contacts is not None:
            self.contacts.update_one(
                {"user_id": user_id, "email": email},
                {
                    "$set": {
                        "user_id": user_id,
                        "name": name,
                        "email": email,
                        "last_seen": time.time(),
                    },
                    "$inc": {"interactions": 1},
                },
                upsert=True,
            )
        else:
            key = f"{user_id}:{email}"
            existing = self._memory_contacts.get(key, {})
            self._memory_contacts[key] = {
                "user_id": user_id,
                "name": name,
                "email": email,
                "last_seen": time.time(),
                "interactions": existing.get("interactions", 0) + 1,
            }

        memory_logger.info(f"Contact saved: {name} <{email}> (user: {user_id})")

    def find_contacts(self, user_id: str, search_name: str) -> list:
        search_name = search_name.strip()
        if not search_name:
            return []

        results = []
        if self.contacts is not None:
            pattern = re.compile(re.escape(search_name), re.IGNORECASE)
            cursor = self.contacts.find(
                {
                    "user_id": user_id,
                    "$or": [
                        {"name": {"$regex": pattern}},
                        {"email": {"$regex": pattern}},
                    ],
                }
            )
            for doc in cursor:
                results.append(
                    {
                        "name": doc["name"],
                        "email": doc["email"],
                        "interactions": doc.get("interactions", 0),
                    }
                )
        else:
            for contact in self._memory_contacts.values():
                if contact.get("user_id") != user_id:
                    continue
                if search_name.lower() in contact["name"].lower() or search_name.lower() in contact["email"].lower():
                    results.append(
                        {
                            "name": contact["name"],
                            "email": contact["email"],
                            "interactions": contact.get("interactions", 0),
                        }
                    )

        results.sort(key=lambda x: x.get("interactions", 0), reverse=True)
        return results

    def get_all_contacts(self, user_id: str) -> list:
        if self.contacts is not None:
            return list(
                self.contacts.find(
                    {"user_id": user_id},
                    {"_id": 0, "name": 1, "email": 1, "interactions": 1},
                ).sort("interactions", -1)
            )
        return [c for c in self._memory_contacts.values() if c.get("user_id") == user_id]


StateManager = WorkflowStateStore
