"""editor_json + clip_audio_tracks

Revision ID: a1b2c3d4e5f6
Revises: 20f5e4fbf676
Create Date: 2026-11-27 22:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "20f5e4fbf676"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("clips", schema=None) as batch_op:
        batch_op.add_column(sa.Column("editor_json", sa.JSON(), nullable=True))

    op.create_table(
        "clip_audio_tracks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("clip_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("muted", sa.Boolean(), nullable=False),
        sa.Column("exclude_from_export", sa.Boolean(), nullable=False),
        sa.Column("volume", sa.Float(), nullable=False),
        sa.Column("fade_in_seconds", sa.Float(), nullable=False),
        sa.Column("fade_out_seconds", sa.Float(), nullable=False),
        sa.Column("start_seconds", sa.Float(), nullable=False),
        sa.Column("trim_start_seconds", sa.Float(), nullable=False),
        sa.Column("trim_end_seconds", sa.Float(), nullable=True),
        sa.Column("sync_offset_seconds", sa.Float(), nullable=False),
        sa.Column("locked", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("meta_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["clip_id"], ["clips.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("clip_audio_tracks", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_clip_audio_tracks_clip_id"), ["clip_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("clip_audio_tracks", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_clip_audio_tracks_clip_id"))
    op.drop_table("clip_audio_tracks")
    with op.batch_alter_table("clips", schema=None) as batch_op:
        batch_op.drop_column("editor_json")
