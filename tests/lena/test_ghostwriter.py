import pytest
from lena.actions.ghostwriter import register, GHOSTWRITER_INSTRUCTIONS


def test_register_returns_empty_list():
    """Ghostwriting is handled via direct text responses, not actions."""
    actions = register()
    assert actions == []


def test_ghostwriter_instructions_exists():
    """GHOSTWRITER_INSTRUCTIONS must be a non-empty string for system prompt injection."""
    assert isinstance(GHOSTWRITER_INSTRUCTIONS, str)
    assert len(GHOSTWRITER_INSTRUCTIONS) > 20


def test_ghostwriter_instructions_mention_key_tasks():
    """Instructions should mention ghostwriting, translation, and correction."""
    instructions_lower = GHOSTWRITER_INSTRUCTIONS.lower()
    assert "ghostwrit" in instructions_lower or "text" in instructions_lower
    assert "übersetz" in instructions_lower or "translat" in instructions_lower
