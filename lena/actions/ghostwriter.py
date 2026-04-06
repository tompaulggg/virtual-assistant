"""Ghostwriter — ghostwriting/translation/correction are handled as direct text responses.

These actions are intentionally NOT registered with the Brain. Instead, the system
prompt instructs Claude to handle ghostwriting, translation, and correction directly
as text responses (not as JSON actions). This avoids a double-Claude-call and keeps
the output natural.
"""

# These system prompt instructions are injected by the Brain when building the prompt.
GHOSTWRITER_INSTRUCTIONS = """
## Ghostwriting, Übersetzung, Korrektur
Wenn der User Text verfassen, übersetzen oder korrigieren lassen will, antworte DIREKT
mit dem fertigen Text — kein JSON, keine Aktion. Gib den Text so aus, dass der User ihn
sofort verwenden kann. Füge kurze Kontexthinweise hinzu wenn nötig (z.B. "Übersetzung:").
"""


def register() -> list[dict]:
    """No actions registered — ghostwriting is handled as direct text responses."""
    return []
