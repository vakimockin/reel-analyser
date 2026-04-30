from datetime import datetime
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.database import Base


class RunRecord(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    usernames: Mapped[list] = mapped_column(JSON, nullable=False)
    limit: Mapped[int] = mapped_column(Integer, nullable=False)
    total_reels_fetched: Mapped[int] = mapped_column(Integer, nullable=False)
    average_views: Mapped[float] = mapped_column(Float, nullable=False)
    viral_reels_count: Mapped[int] = mapped_column(Integer, nullable=False)
    viral_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    niche_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    reels: Mapped[list["ReelRecord"]] = relationship(
        "ReelRecord", back_populates="run", cascade="all, delete-orphan"
    )
    ideas: Mapped[list["IdeaRecord"]] = relationship(
        "IdeaRecord", back_populates="run", cascade="all, delete-orphan"
    )


class ReelRecord(Base):
    __tablename__ = "viral_reels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False)
    username: Mapped[str] = mapped_column(String, nullable=False)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    views: Mapped[int] = mapped_column(Integer, nullable=False)
    video_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    likes_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comments_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hashtags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    music: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped["RunRecord"] = relationship("RunRecord", back_populates="reels")
    idea: Mapped["IdeaRecord | None"] = relationship(
        "IdeaRecord", back_populates="reel", uselist=False
    )


class IdeaRecord(Base):
    __tablename__ = "content_ideas"
    __table_args__ = (UniqueConstraint("reel_id", name="uq_content_ideas_reel_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False)
    reel_id: Mapped[int] = mapped_column(Integer, ForeignKey("viral_reels.id", ondelete="CASCADE"), nullable=False)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    hook: Mapped[str] = mapped_column(Text, nullable=False)
    why_it_worked: Mapped[str] = mapped_column(Text, nullable=False)
    creator_script: Mapped[str] = mapped_column(Text, nullable=False)

    run: Mapped["RunRecord"] = relationship("RunRecord", back_populates="ideas")
    reel: Mapped["ReelRecord"] = relationship("ReelRecord", back_populates="idea")
