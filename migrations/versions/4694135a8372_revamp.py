"""Revamp

Revision ID: 4694135a8372
Revises: 83974dbb16bb
Create Date: 2026-06-29 01:14:56.355815

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4694135a8372"
down_revision: Union[str, None] = "83974dbb16bb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create temporary subscription table with the new schema
    op.create_table(
        "subscription_tmp",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("guild_id", sa.Integer(), nullable=False),
        sa.Column(
            "youtube_channel_name",
            sa.Unicode(length=100).with_variant(sa.TEXT(), "sqlite"),
            nullable=False,
        ),
        sa.Column(
            "youtube_channel_id",
            sa.String(length=50).with_variant(sa.TEXT(), "sqlite"),
            nullable=False,
        ),
        sa.Column(
            "youtube_upload_playlist",
            sa.String(length=50).with_variant(sa.TEXT(), "sqlite"),
            nullable=False,
        ),
        sa.Column(
            "announcement_target",
            sa.String(length=50).with_variant(sa.TEXT(), "sqlite"),
            nullable=True,
        ),
        sa.Column("notification_channel_id", sa.Integer(), nullable=False),
        sa.Column(
            "last_checked_at",
            sa.DateTime().with_variant(sa.TEXT(), "sqlite"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["guild_id"],
            ["guild.id"],
            name=op.f("fk_subscription_guild_id_guild"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subscription")),
        sa.UniqueConstraint(
            "guild_id",
            "youtube_channel_id",
            name=op.f("uq_subscription_guild_id"),
        ),
        sqlite_strict=True,
    )

    # 2. Dump data: copy from subscription, using guild.bot_channel as notification_channel_id
    op.execute(
        sa.text(
            """
            INSERT INTO subscription_tmp (
                guild_id, youtube_channel_name, youtube_channel_id,
                youtube_upload_playlist, announcement_target,
                notification_channel_id, last_checked_at
            )
            SELECT
                s.guild_id, s.youtube_channel_name, s.youtube_channel_id,
                s.youtube_upload_playlist, s.announcement_target,
                g.bot_channel, s.last_checked_at
            FROM subscription s
            JOIN guild g ON s.guild_id = g.id
            """
        )
    )

    # 3. Drop the old subscription table
    op.drop_table("subscription")

    # 4. Rename the temp table to subscription
    op.rename_table("subscription_tmp", "subscription")

    # 5. Drop bot_channel from guild
    op.drop_column("guild", "bot_channel")


def downgrade() -> None:
    # Restore bot_channel on guild from notification_channel_id
    op.add_column(
        "guild",
        sa.Column("bot_channel", sa.INTEGER(), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE guild
            SET bot_channel = subscription.notification_channel_id
            FROM subscription
            WHERE subscription.guild_id = guild.id
            """
        )
    )

    # Revert unique constraint and drop notification_channel_id
    op.drop_constraint(
        op.f("uq_subscription_guild_id_youtube_channel_id"),
        "subscription",
        type_="unique",
    )
    op.drop_column("subscription", "notification_channel_id")
