"""Shared Supabase client factory — HTTP/1.1 only to avoid StreamReset on Railway."""

import os
import httpx
from supabase import create_client

_client = None


def get_supabase():
    """Return a singleton Supabase client with HTTP/2 disabled."""
    global _client
    if _client is None:
        _client = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_KEY"),
        )
        # Replace postgrest session with HTTP/1.1 to avoid StreamReset
        old_session = _client.postgrest.session
        _client.postgrest.session = httpx.Client(
            base_url=old_session.base_url,
            headers=dict(old_session.headers),
            http2=False,
            timeout=30.0,
        )
    return _client
