from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.repositories.knowledge_base import KnowledgeBaseRepository
from app.services.knowledge_base import KnowledgeBaseService

SessionDependency = Annotated[
    AsyncSession,
    Depends(get_session),
]


def get_knowledge_base_service(
    session: SessionDependency,
) -> KnowledgeBaseService:
    repository = KnowledgeBaseRepository(session)
    return KnowledgeBaseService(repository, session)


KnowledgeBaseServiceDependency = Annotated[
    KnowledgeBaseService,
    Depends(get_knowledge_base_service),
]
