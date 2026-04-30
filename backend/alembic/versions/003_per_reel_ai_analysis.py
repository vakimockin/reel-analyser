"""per-reel AI analysis, reel metadata columns, niche summary

Revision ID: 003
Revises: 002
Create Date: 2026-04-29

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("viral_reels", sa.Column("likes_count", sa.Integer(), nullable=True))
    op.add_column("viral_reels", sa.Column("comments_count", sa.Integer(), nullable=True))
    op.add_column(
        "viral_reels",
        sa.Column("hashtags", postgresql.JSON(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("viral_reels", sa.Column("music", sa.Text(), nullable=True))

    op.add_column("analysis_runs", sa.Column("niche_summary", sa.Text(), nullable=True))

    op.drop_table("content_ideas")

    op.create_table(
        "content_ideas",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("reel_id", sa.Integer(), nullable=False),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("hook", sa.Text(), nullable=False),
        sa.Column("why_it_worked", sa.Text(), nullable=False),
        sa.Column("creator_script", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reel_id"], ["viral_reels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reel_id", name="uq_content_ideas_reel_id"),
    )


def downgrade() -> None:
    op.drop_table("content_ideas")

    op.create_table(
        "content_ideas",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("trend_analysis", sa.Text(), nullable=False),
        sa.Column("hook", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("cta", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.drop_column("analysis_runs", "niche_summary")
    op.drop_column("viral_reels", "music")
    op.drop_column("viral_reels", "hashtags")
    op.drop_column("viral_reels", "comments_count")
    op.drop_column("viral_reels", "likes_count")
