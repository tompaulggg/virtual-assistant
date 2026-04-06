import pytest
from lena.actions.ghostwriter import register, ACTIONS


def test_register_returns_action_list():
    actions = register()
    names = [a["name"] for a in actions]
    assert "ghostwrite" in names
    assert "translate" in names
    assert "correct" in names


def test_action_definitions_have_required_fields():
    actions = register()
    for action in actions:
        assert "name" in action
        assert "description" in action
        assert "parameters" in action
        assert "handler" in action
        assert callable(action["handler"])


@pytest.mark.asyncio
async def test_ghostwrite_handler():
    actions = register()
    ghostwrite = next(a for a in actions if a["name"] == "ghostwrite")
    assert ghostwrite["parameters"]["text"] == "string"
    assert "tone" in ghostwrite["parameters"]


@pytest.mark.asyncio
async def test_translate_handler():
    actions = register()
    translate = next(a for a in actions if a["name"] == "translate")
    assert "text" in translate["parameters"]
    assert "target_language" in translate["parameters"]
