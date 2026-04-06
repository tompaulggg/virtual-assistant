"""Ghostwriter action — drafts professional text from bullet points."""


async def ghostwrite(data: dict) -> str:
    text = data.get("text", "")
    tone = data.get("tone", "professionell")
    return (
        f"Hier ist der Text im Stil '{tone}':\n\n"
        f"(Der Brain leitet diese Anfrage an Claude weiter — "
        f"dieses Modul wird vom Brain als Action registriert, "
        f"die eigentliche Textgenerierung macht Claude im Brain.)\n\n"
        f"Stichpunkte: {text}"
    )


async def translate(data: dict) -> str:
    text = data.get("text", "")
    target = data.get("target_language", "englisch")
    return f"Übersetzung nach {target} wird vom Brain an Claude delegiert."


async def correct(data: dict) -> str:
    text = data.get("text", "")
    return "Korrektur wird vom Brain an Claude delegiert."


ACTIONS = [
    {
        "name": "ghostwrite",
        "description": "Formuliere professionellen Text aus Stichpunkten. Tonalität: formal, freundlich, kurz.",
        "parameters": {"text": "string", "tone": "string (formal|freundlich|kurz|englisch)"},
        "handler": ghostwrite,
    },
    {
        "name": "translate",
        "description": "Übersetze Text in eine andere Sprache.",
        "parameters": {"text": "string", "target_language": "string"},
        "handler": translate,
    },
    {
        "name": "correct",
        "description": "Korrigiere Grammatik und Stil ohne den Inhalt zu ändern.",
        "parameters": {"text": "string"},
        "handler": correct,
    },
]


def register() -> list[dict]:
    return ACTIONS
