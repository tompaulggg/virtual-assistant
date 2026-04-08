import logging
from core.db import get_supabase

logger = logging.getLogger(__name__)


class Memory:
    def __init__(self, bot_name: str = ""):
        self.db = get_supabase()
        self.bot_name = bot_name

    def get_history(self, user_id: str, limit: int = 20) -> list[dict]:
        query = (
            self.db.table("conversations")
            .select("role, content")
            .eq("user_id", user_id)
        )
        if self.bot_name:
            query = query.eq("bot_name", self.bot_name)
        result = query.order("created_at").limit(limit).execute()
        return result.data

    def save(self, user_id: str, user_msg: str, assistant_msg: str):
        rows = [
            {"user_id": user_id, "role": "user", "content": user_msg},
            {"user_id": user_id, "role": "assistant", "content": assistant_msg},
        ]
        if self.bot_name:
            for row in rows:
                row["bot_name"] = self.bot_name
        self.db.table("conversations").insert(rows).execute()

    def remember_fact(self, user_id: str, category: str, key: str, value: str):
        self.db.table("facts").upsert({
            "user_id": user_id,
            "category": category,
            "key": key,
            "value": value,
        }).execute()

    def recall_facts(self, user_id: str, category: str | None = None) -> list[dict]:
        query = self.db.table("facts").select("*").eq("user_id", user_id)
        if category:
            query = query.eq("category", category)
        return query.execute().data

    def get_all_knowledge(self, user_id: str, limit: int = 100) -> list[dict]:
        result = (
            self.db.table("knowledge")
            .select("category, key, value")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data

    def store_knowledge(self, user_id: str, category: str, key: str, value: str):
        self.db.table("knowledge").upsert({
            "user_id": user_id,
            "category": category,
            "key": key,
            "value": value,
        }).execute()

    def log_action(self, user_id: str, action: str, details: dict | None = None):
        self.db.table("audit_log").insert({
            "user_id": user_id,
            "action": action,
            "details": details or {},
        }).execute()
