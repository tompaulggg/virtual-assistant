import os
import logging
from supabase import create_client

logger = logging.getLogger(__name__)


class Memory:
    def __init__(self):
        self.db = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_KEY"),
        )

    def get_history(self, user_id: str, limit: int = 20) -> list[dict]:
        result = (
            self.db.table("conversations")
            .select("role, content")
            .eq("user_id", user_id)
            .order("created_at")
            .limit(limit)
            .execute()
        )
        return result.data

    def save(self, user_id: str, user_msg: str, assistant_msg: str):
        self.db.table("conversations").insert([
            {"user_id": user_id, "role": "user", "content": user_msg},
            {"user_id": user_id, "role": "assistant", "content": assistant_msg},
        ]).execute()

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

    def log_action(self, user_id: str, action: str, details: dict | None = None):
        self.db.table("audit_log").insert({
            "user_id": user_id,
            "action": action,
            "details": details or {},
        }).execute()
