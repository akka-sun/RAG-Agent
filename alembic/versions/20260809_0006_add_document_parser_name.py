from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260809_0006"
down_revision: str | None = "20260809_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "parser_name",
            sa.String(length=32),
            server_default=sa.text("'local'"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        op.f("ck_documents_parser_name_valid"),
        "documents",
        "parser_name IN ('local', 'mineru', 'paddlex')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_documents_parser_name_valid"), "documents", type_="check")
    op.drop_column("documents", "parser_name")
