import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models import Conversation, Document, KnowledgeBase, MessageRole
from app.repositories.conversations import ConversationRepository
from app.repositories.messages import (
    CitationValidationError,
    MessageCitationInput,
    MessageRepository,
)


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(get_settings().test_database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            await session.execute(
                text(
                    "TRUNCATE TABLE message_citations, messages, conversations, "
                    "ingestion_tasks, documents, knowledge_bases"
                )
            )
            await session.commit()
            yield session
            await session.rollback()
            await session.execute(
                text(
                    "TRUNCATE TABLE message_citations, messages, conversations, "
                    "ingestion_tasks, documents, knowledge_bases"
                )
            )
            await session.commit()
    finally:
        await engine.dispose()


async def create_document(db_session: AsyncSession) -> Document:
    knowledge_base = KnowledgeBase(
        name=f"repo-{uuid.uuid4()}",
        description="",
        embedding_model="hashing",
        embedding_dimension=16,
    )
    db_session.add(knowledge_base)
    await db_session.flush()
    document = Document(
        knowledge_base_id=knowledge_base.id,
        filename="policy.md",
        content_type="text/markdown",
        size_bytes=42,
        source_object_key="source/policy.md",
    )
    db_session.add(document)
    await db_session.flush()
    return document


async def create_conversation(db_session: AsyncSession, document: Document) -> Conversation:
    conversation = await ConversationRepository(db_session).create(
        knowledge_base_id=document.knowledge_base_id,
        title="Research",
    )
    return conversation


async def test_conversation_repository_create_list_get_and_delete(
    db_session: AsyncSession,
) -> None:
    document = await create_document(db_session)
    repository = ConversationRepository(db_session)

    conversation = await repository.create(
        knowledge_base_id=document.knowledge_base_id,
        title="Research",
    )

    assert await repository.get(conversation.id) is conversation
    assert await repository.list_by_knowledge_base(document.knowledge_base_id) == [conversation]

    await repository.delete(conversation)
    assert await repository.get(conversation.id) is None


async def test_message_repository_adds_messages_and_citations(
    db_session: AsyncSession,
) -> None:
    document = await create_document(db_session)
    conversation = await create_conversation(db_session, document)
    repository = MessageRepository(db_session)

    user_message = await repository.add_user_message(
        conversation_id=conversation.id,
        content="What is the policy?",
    )
    assistant_message = await repository.add_assistant_message_with_citations(
        conversation_id=conversation.id,
        content="answer [S1]",
        citations=[
            MessageCitationInput(
                source_label="S1",
                document_id=document.id,
                chunk_id="chunk-1",
                quote="quoted evidence",
                score=0.95,
            )
        ],
        valid_labels={"S1"},
    )

    messages = await repository.list_by_conversation(conversation.id)

    assert [message.role for message in messages] == [
        MessageRole.USER,
        MessageRole.ASSISTANT,
    ]
    assert user_message in messages
    assert assistant_message.citations[0].source_label == "S1"
    assert assistant_message.citations[0].document_id == document.id


async def test_add_assistant_message_rejects_invalid_citation_without_partial_write(
    db_session: AsyncSession,
) -> None:
    document = await create_document(db_session)
    conversation = await create_conversation(db_session, document)
    repository = MessageRepository(db_session)

    with pytest.raises(CitationValidationError):
        await repository.add_assistant_message_with_citations(
            conversation_id=conversation.id,
            content="answer [S1]",
            citations=[
                MessageCitationInput(
                    source_label="S2",
                    document_id=document.id,
                    chunk_id="chunk-1",
                    quote="wrong label evidence",
                )
            ],
            valid_labels={"S1"},
        )

    assert await repository.list_by_conversation(conversation.id) == []
