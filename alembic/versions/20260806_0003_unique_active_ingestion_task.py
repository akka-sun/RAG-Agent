from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260806_0003"
down_revision: str | None = "20260806_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "uq_ingestion_tasks_active_document"


def upgrade() -> None:
    op.create_index(
        INDEX_NAME,
        "ingestion_tasks",
        ["document_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'processing')"),
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="ingestion_tasks")
