-- Add bot_name to conversations so each bot only sees its own chats
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS bot_name text DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_conversations_bot ON conversations (user_id, bot_name, created_at);
