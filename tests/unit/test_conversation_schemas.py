import pytest
from pydantic import ValidationError

from app.schemas.conversations import ConversationCreate


def test_conversation_title_trims_whitespace() -> None:
    payload = ConversationCreate(title="  Support Docs  ")

    assert payload.title == "Support Docs"


def test_conversation_title_rejects_blank_text() -> None:
    with pytest.raises(ValidationError):
        ConversationCreate(title="   ")
