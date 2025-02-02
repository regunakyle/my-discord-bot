"""First migration

Revision ID: a29aedea6bce
Revises:
Create Date: 2025-02-02 22:16:04.229508

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a29aedea6bce"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "guild",
        sa.Column(
            "id",
            sa.Integer(),
            sa.Identity(always=True, start=1, increment=1),
            nullable=False,
        ),
        sa.Column("guild_id", sa.Integer(), nullable=False),
        sa.Column("guild_name", sa.String(length=100), nullable=False),
        sa.Column("bot_channel", sa.Integer(), nullable=True),
        sa.Column("welcome_message", sa.String(length=2000), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_guild")),
        sa.UniqueConstraint("guild_id", name=op.f("uq_guild_guild_id")),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("guild")
    # ### end Alembic commands ###
