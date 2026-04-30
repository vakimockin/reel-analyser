from datetime import datetime
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.schemas import (
    AnalyzeRequest,
    AnalysisResponse,
    AnalysisRunSummary,
    ReelAnalysis,
    ReelAnalysisItem,
    ReelDetail,
    ReelMeta,
    RegenerateResponse,
)
from db.database import get_db
from db.models import IdeaRecord, ReelRecord, RunRecord
from services.ai_service import generate_reel_analyses, maybe_niche_summary
from services.apify_service import fetch_reels, filter_viral_reels, parse_reels
from services.reel_helpers import pairs_for_ai, reel_meta_from_record
from services.telegram_notify import send_run_notification

router = APIRouter(prefix="/api/v1", tags=["analysis"])
logger = logging.getLogger("api.routes")


def _sorted_full_metas(reels: list[ReelRecord]) -> list[ReelMeta]:
    ordered = sorted(reels, key=lambda r: r.views, reverse=True)
    return [reel_meta_from_record(r) for r in ordered]


def _raw_preview(raw_items: list[dict], limit: int = 5) -> tuple[int, list[ReelMeta]]:
    parsed = parse_reels(raw_items)
    ordered = sorted(parsed, key=lambda r: r.views, reverse=True)
    return len(parsed), ordered[:limit]


def _analysis_items_from_pairs(
    reel_rows: list[ReelRecord],
    analyses: list[tuple[int, ReelAnalysis]],
) -> list[ReelAnalysisItem]:
    by_id = {r.id: r for r in reel_rows}
    out: list[ReelAnalysisItem] = []
    for reel_id, analysis in analyses:
        r = by_id[reel_id]
        out.append(
            ReelAnalysisItem(
                reel_id=reel_id,
                reel=reel_meta_from_record(r),
                analysis=analysis,
            )
        )
    return out


def _analysis_items_from_run(reels: list[ReelRecord], ideas: list[IdeaRecord]) -> list[ReelAnalysisItem]:
    idea_map = {i.reel_id: i for i in ideas}
    items: list[ReelAnalysisItem] = []
    for r in sorted(reels, key=lambda x: x.views, reverse=True):
        row = idea_map.get(r.id)
        if not row:
            continue
        items.append(
            ReelAnalysisItem(
                reel_id=r.id,
                reel=reel_meta_from_record(r),
                analysis=ReelAnalysis(
                    topic=row.topic,
                    hook=row.hook,
                    why_it_worked=row.why_it_worked,
                    creator_script=row.creator_script,
                ),
            )
        )
    return items


@router.post("/analyze", response_model=AnalysisResponse, status_code=201)
async def analyze_reels(
    request: AnalyzeRequest,
    db: AsyncSession = Depends(get_db),
) -> AnalysisResponse:
    try:
        raw_items = await fetch_reels(request.usernames, request.limit)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Apify scraping failed: {exc}")

    if not raw_items:
        raise HTTPException(status_code=404, detail="No reels found for the given usernames.")

    raw_items_count, raw_preview = _raw_preview(raw_items)
    viral_reels, average_views, viral_threshold = filter_viral_reels(raw_items)

    run = RunRecord(
        usernames=request.usernames,
        limit=request.limit,
        total_reels_fetched=len(raw_items),
        average_views=average_views,
        viral_reels_count=len(viral_reels),
        viral_threshold=viral_threshold,
        created_at=datetime.utcnow(),
    )
    db.add(run)
    await db.flush()

    if not viral_reels:
        await db.commit()
        response = AnalysisResponse(
            run_id=run.id,
            total_reels_fetched=len(raw_items),
            raw_items_count=raw_items_count,
            raw_preview=raw_preview,
            average_views=average_views,
            viral_reels_count=0,
            viral_threshold=viral_threshold,
            niche_summary=None,
            viral_reels=[],
            reel_analyses=[],
        )
        try:
            await send_run_notification(response)
        except Exception:
            # Notification failures should not break API flow.
            logger.exception("Failed to send Telegram notification for run_id=%s", run.id)
        return response

    for reel in viral_reels:
        db.add(
            ReelRecord(
                run_id=run.id,
                username=reel.username,
                caption=reel.caption,
                duration=reel.duration,
                views=reel.views,
                video_url=reel.video_url,
                thumbnail_url=reel.thumbnail_url,
                likes_count=reel.likes,
                comments_count=reel.comments,
                hashtags=reel.hashtags,
                music=reel.music,
            )
        )

    await db.commit()

    reels_result = await db.execute(select(ReelRecord).where(ReelRecord.run_id == run.id))
    reel_rows = list(reels_result.scalars().all())
    pairs = pairs_for_ai(reel_rows)
    metas_for_summary = [m for _, m in pairs]

    try:
        niche_summary = await maybe_niche_summary(metas_for_summary)
        analyses = await generate_reel_analyses(pairs)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"{exc} (reels saved — retry with POST /api/v1/analyses/{run.id}/regenerate)",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"AI generation failed: {exc} (reels saved — retry with POST /api/v1/analyses/{run.id}/regenerate)",
        )

    run.niche_summary = niche_summary

    for reel_id, analysis in analyses:
        db.add(
            IdeaRecord(
                run_id=run.id,
                reel_id=reel_id,
                topic=analysis.topic,
                hook=analysis.hook,
                why_it_worked=analysis.why_it_worked,
                creator_script=analysis.creator_script,
            )
        )

    await db.commit()

    response = AnalysisResponse(
        run_id=run.id,
        total_reels_fetched=len(raw_items),
        raw_items_count=raw_items_count,
        raw_preview=raw_preview,
        average_views=average_views,
        viral_reels_count=len(viral_reels),
        viral_threshold=viral_threshold,
        niche_summary=niche_summary,
        viral_reels=_sorted_full_metas(reel_rows),
        reel_analyses=_analysis_items_from_pairs(reel_rows, analyses),
    )
    try:
        await send_run_notification(response)
    except Exception:
        # Notification failures should not break API flow.
        logger.exception("Failed to send Telegram notification for run_id=%s", run.id)
    return response


@router.get("/analyses", response_model=list[AnalysisRunSummary])
async def list_analyses(
    db: AsyncSession = Depends(get_db),
    limit: int = 20,
    offset: int = 0,
) -> list[AnalysisRunSummary]:
    result = await db.execute(
        select(RunRecord).order_by(RunRecord.created_at.desc()).limit(limit).offset(offset)
    )
    runs = result.scalars().all()
    return [
        AnalysisRunSummary(
            run_id=r.id,
            usernames=r.usernames,
            total_reels_fetched=r.total_reels_fetched,
            average_views=r.average_views,
            viral_reels_count=r.viral_reels_count,
            created_at=r.created_at,
        )
        for r in runs
    ]


@router.get("/analyses/{run_id}", response_model=AnalysisResponse)
async def get_analysis(run_id: int, db: AsyncSession = Depends(get_db)) -> AnalysisResponse:
    run = await db.get(RunRecord, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis run not found.")

    reels_result = await db.execute(select(ReelRecord).where(ReelRecord.run_id == run_id))
    ideas_result = await db.execute(select(IdeaRecord).where(IdeaRecord.run_id == run_id))

    reels_list = list(reels_result.scalars().all())
    ideas_list = list(ideas_result.scalars().all())

    return AnalysisResponse(
        run_id=run.id,
        total_reels_fetched=run.total_reels_fetched,
        raw_items_count=None,
        raw_preview=[],
        average_views=run.average_views,
        viral_reels_count=run.viral_reels_count,
        viral_threshold=run.viral_threshold,
        niche_summary=run.niche_summary,
        viral_reels=_sorted_full_metas(reels_list),
        reel_analyses=_analysis_items_from_run(reels_list, ideas_list),
    )


@router.get("/reels", response_model=list[ReelDetail])
async def list_reels(
    db: AsyncSession = Depends(get_db),
    username: str | None = None,
    run_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ReelDetail]:
    query = select(ReelRecord).order_by(ReelRecord.id.desc()).limit(limit).offset(offset)
    if username:
        query = query.where(ReelRecord.username == username)
    if run_id:
        query = query.where(ReelRecord.run_id == run_id)
    result = await db.execute(query)
    return [
        ReelDetail(
            id=r.id,
            run_id=r.run_id,
            username=r.username,
            caption=r.caption,
            duration=r.duration,
            views=r.views,
        )
        for r in result.scalars().all()
    ]


@router.get("/analyses/{run_id}/reels", response_model=list[ReelDetail])
async def list_run_reels(run_id: int, db: AsyncSession = Depends(get_db)) -> list[ReelDetail]:
    run = await db.get(RunRecord, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis run not found.")
    result = await db.execute(select(ReelRecord).where(ReelRecord.run_id == run_id))
    return [
        ReelDetail(
            id=r.id,
            run_id=r.run_id,
            username=r.username,
            caption=r.caption,
            duration=r.duration,
            views=r.views,
        )
        for r in result.scalars().all()
    ]


@router.post("/analyses/{run_id}/regenerate", response_model=RegenerateResponse)
async def regenerate_ideas(run_id: int, db: AsyncSession = Depends(get_db)) -> RegenerateResponse:
    run = await db.get(RunRecord, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis run not found.")

    reels_result = await db.execute(select(ReelRecord).where(ReelRecord.run_id == run_id))
    reels = list(reels_result.scalars().all())
    if not reels:
        raise HTTPException(status_code=404, detail="No viral reels found for this run.")

    pairs = pairs_for_ai(reels)
    metas_for_summary = [m for _, m in pairs]

    try:
        niche_summary = await maybe_niche_summary(metas_for_summary)
        analyses = await generate_reel_analyses(pairs)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI generation failed: {exc}")

    run.niche_summary = niche_summary

    existing_ideas = await db.execute(select(IdeaRecord).where(IdeaRecord.run_id == run_id))
    for idea in existing_ideas.scalars().all():
        await db.delete(idea)

    for reel_id, analysis in analyses:
        db.add(
            IdeaRecord(
                run_id=run_id,
                reel_id=reel_id,
                topic=analysis.topic,
                hook=analysis.hook,
                why_it_worked=analysis.why_it_worked,
                creator_script=analysis.creator_script,
            )
        )

    await db.commit()

    return RegenerateResponse(
        run_id=run_id,
        viral_reels_count=len(reels),
        niche_summary=niche_summary,
        reel_analyses=_analysis_items_from_pairs(reels, analyses),
    )


@router.get("/health")
async def health_check() -> dict:
    return {"status": "ok"}
