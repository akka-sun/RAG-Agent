from sqlalchemy import inspect

from app.models import Conversation, Message, MessageCitation


def test_message_citation_requires_message_document_and_source_fields() -> None:
    citation_columns = inspect(MessageCitation).columns

    assert "message_id" in citation_columns
    assert "document_id" in citation_columns
    assert "chunk_id" in citation_columns
    assert "source_label" in citation_columns
    assert "quote" in citation_columns
    assert "score" in citation_columns


def test_conversation_relationships_preserve_message_and_citation_history() -> None:
    assert Message.conversation.property.back_populates == "messages"
    assert MessageCitation.message.property.back_populates == "citations"
    assert "delete" not in Conversation.messages.property.cascade
    assert "delete" not in Message.citations.property.cascade
