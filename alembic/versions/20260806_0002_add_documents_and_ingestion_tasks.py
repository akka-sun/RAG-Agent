from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260806_0002"
down_revision: str | None = "20260718_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("knowledge_base_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("source_object_key", sa.String(length=1024), nullable=False),
        sa.Column("parsed_object_key", sa.String(length=1024), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("chunk_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name=op.f("ck_documents_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_base_id"],
            ["knowledge_bases.id"],
            name=op.f("fk_documents_knowledge_base_id_knowledge_bases"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
    )
    op.create_index(
        op.f("ix_documents_knowledge_base_id"),
        "documents",
        ["knowledge_base_id"],
        unique=False,
    )
    op.create_table(
        "ingestion_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("arq_job_id", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "stage",
            sa.String(length=32),
            server_default=sa.text("'queued'"),
            nullable=False,
        ),
        sa.Column("progress", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "progress BETWEEN 0 AND 100",
            name=op.f("ck_ingestion_tasks_progress_range"),
        ),
        sa.CheckConstraint(
            "stage IN ('queued', 'parsing', 'chunking', 'embedding', 'indexing', 'completed')",
            name=op.f("ck_ingestion_tasks_stage_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name=op.f("ck_ingestion_tasks_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_ingestion_tasks_document_id_documents"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ingestion_tasks")),
    )
    op.create_index(
        op.f("ix_ingestion_tasks_document_id"),
        "ingestion_tasks",
        ["document_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_ingestion_tasks_document_id"), table_name="ingestion_tasks")
    op.drop_table("ingestion_tasks")
    op.drop_index(op.f("ix_documents_knowledge_base_id"), table_name="documents")
    op.drop_table("documents")
