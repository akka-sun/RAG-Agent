from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260809_0005"
down_revision: str | None = "20260809_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS messages_sequence_number_seq")
    op.add_column(
        "messages",
        sa.Column("sequence_number", sa.BigInteger(), nullable=True),
    )
    op.execute(
        """
        WITH ordered_messages AS (
            SELECT
                id,
                row_number() OVER (ORDER BY created_at ASC, id ASC) AS sequence_number
            FROM messages
        )
        UPDATE messages
        SET sequence_number = ordered_messages.sequence_number
        FROM ordered_messages
        WHERE messages.id = ordered_messages.id
        """
    )
    op.execute(
        """
        SELECT setval(
            'messages_sequence_number_seq',
            COALESCE((SELECT MAX(sequence_number) FROM messages), 0) + 1,
            false
        )
        """
    )
    op.alter_column(
        "messages",
        "sequence_number",
        existing_type=sa.BigInteger(),
        nullable=False,
        server_default=sa.text("nextval('messages_sequence_number_seq'::regclass)"),
    )
    op.execute("ALTER SEQUENCE messages_sequence_number_seq OWNED BY messages.sequence_number")
    op.create_index(
        op.f("ix_messages_sequence_number"),
        "messages",
        ["sequence_number"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_messages_sequence_number"), table_name="messages")
    op.drop_column("messages", "sequence_number")
    op.execute("DROP SEQUENCE IF EXISTS messages_sequence_number_seq")
