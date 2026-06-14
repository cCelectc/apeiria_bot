"""Widen turn_disposition CHECK constraint from 4 to 8 values

Revision ID: 0005_fix_turn_disposition_constraint
Revises: 0004_chat_message_indexes
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_fix_turn_disposition_constraint"
down_revision = "0004_chat_message_indexes"

_TURN_DISPOSITION_VALUES = (
    "active",
    "observed",
    "generated",
    "tool",
    "system",
    "pruned",
    "summarized",
    "archived",
)

_TURN_DISPOSITION_CHECK = (
    "turn_disposition IN ("
    "'active', 'observed', 'generated', 'tool', "
    "'system', 'pruned', 'summarized', 'archived')"
)

_OLD_TURN_DISPOSITION_VALUES = (
    "active",
    "pruned",
    "summarized",
    "archived",
)

_OLD_TURN_DISPOSITION_CHECK = (
    "turn_disposition IN ('active', 'pruned', 'summarized', 'archived')"
)

_CONSTRAINT_NAME = "ck_chat_message_turn_disposition"


def upgrade() -> None:
    with op.batch_alter_table("chat_message") as batch_op:
        batch_op.drop_constraint(_CONSTRAINT_NAME, type_="check")
        batch_op.create_check_constraint(
            _CONSTRAINT_NAME,
            _TURN_DISPOSITION_CHECK,
        )


def downgrade() -> None:
    with op.batch_alter_table("chat_message") as batch_op:
        batch_op.drop_constraint(_CONSTRAINT_NAME, type_="check")
        batch_op.create_check_constraint(
            _CONSTRAINT_NAME,
            _OLD_TURN_DISPOSITION_CHECK,
        )
