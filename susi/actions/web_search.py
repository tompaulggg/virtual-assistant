"""Web search via Brave Search API."""

import logging
import os
import httpx

logger = logging.getLogger(__name__)

BRAVE_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY", "")
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


async def _web_search(data: dict) -> str:
    query = data.get("query", "").strip()
    if not query:
        return "Ich brauch einen Suchbegriff."

    if not BRAVE_API_KEY:
        return "Web-Suche nicht konfiguriert (BRAVE_SEARCH_API_KEY fehlt)."

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                BRAVE_SEARCH_URL,
                params={
                    "q": query,
                    "search_lang": "de",
                    "country": "AT",
                    "count": 5,
                },
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": BRAVE_API_KEY,
                },
            )

            if resp.status_code != 200:
                return f"Suche fehlgeschlagen (HTTP {resp.status_code})"

            results = resp.json()
            web_results = results.get("web", {}).get("results", [])

            if not web_results:
                return f"Keine Ergebnisse fuer '{query}'."

            lines = [f"Suchergebnisse fuer '{query}':\n"]
            for i, r in enumerate(web_results[:5], 1):
                title = r.get("title", "?")
                url = r.get("url", "")
                desc = r.get("description", "")
                lines.append(f"{i}. {title}")
                if desc:
                    lines.append(f"   {desc}")
                lines.append(f"   {url}\n")

            return "\n".join(lines)

    except httpx.ConnectError:
        return "Brave Search nicht erreichbar."
    except Exception as e:
        logger.error(f"Web search failed: {e}")
        return f"Suche fehlgeschlagen: {e}"


ACTIONS = [
    {
        "name": "web_search",
        "description": "Im Web suchen. Nutze das wenn du aktuelle Infos brauchst (Adressen, Termine, Fakten) oder wenn der User 'such mal' sagt. Du kannst mehrere Suchen hintereinander machen.",
        "parameters": {"query": "string (Suchbegriff)"},
        "handler": _web_search,
    },
]


def register() -> list[dict]:
    return ACTIONS
