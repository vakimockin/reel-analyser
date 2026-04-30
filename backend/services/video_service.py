import base64
import os
import tempfile

import cv2
import httpx


async def _download(url: str, dest: str) -> None:
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        r = await client.get(url)
        r.raise_for_status()
        with open(dest, "wb") as f:
            f.write(r.content)


def _b64_file(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _sample_frames(video_path: str, n: int) -> list[str]:
    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total == 0:
        cap.release()
        return []

    # Evenly spaced, avoid first/last 5% (often black/logo frames)
    margin = int(total * 0.05)
    usable = total - 2 * margin
    step = usable / (n + 1) if n else usable
    positions = [margin + int(step * (i + 1)) for i in range(n)] if n else []

    frames: list[str] = []
    for pos in positions:
        cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
        ok, frame = cap.read()
        if ok:
            _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            frames.append(base64.b64encode(buf).decode())

    cap.release()
    return frames


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return int(raw)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return default


async def get_reel_images(
    video_url: str | None,
    thumbnail_url: str | None,
    num_frames: int | None = None,
    thumbnail_only: bool | None = None,
) -> list[str]:
    """
    Returns base64 JPEGs: thumbnail first, then num_frames sampled from the video.
    Silently skips failures so the AI call still proceeds text-only if download fails.

    Env: AI_THUMBNAIL_ONLY (default false), OPENAI_FRAMES_PER_REEL (default 2).
    """
    if num_frames is None:
        num_frames = _env_int("OPENAI_FRAMES_PER_REEL", 2)
    if thumbnail_only is None:
        thumbnail_only = _env_bool("AI_THUMBNAIL_ONLY", False)

    images: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        if thumbnail_url:
            thumb = os.path.join(tmp, "thumb.jpg")
            try:
                await _download(thumbnail_url, thumb)
                images.append(_b64_file(thumb))
            except Exception:
                pass

        if thumbnail_only or num_frames <= 0:
            return images

        if video_url:
            video = os.path.join(tmp, "reel.mp4")
            try:
                await _download(video_url, video)
                images.extend(_sample_frames(video, num_frames))
            except Exception:
                pass

    return images
