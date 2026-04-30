import os
from apify_client import ApifyClient
from core.schemas import ReelMeta


APIFY_ACTOR_ID = "apify/instagram-scraper"


def _get_client() -> ApifyClient:
    token = os.getenv("APIFY_TOKEN")
    if not token:
        raise RuntimeError("APIFY_TOKEN is not set")
    return ApifyClient(token)


async def fetch_reels(usernames: list[str], limit: int) -> list[dict]:
    """Run the Apify Instagram scraper actor and return raw reel items."""
    client = _get_client()

    run_input = {
        "directUrls": [f"https://www.instagram.com/{u.lstrip('@')}/" for u in usernames],
        "resultsType": "posts",
        "resultsLimit": limit,
        "mediaType": "VIDEO",
        "addParentData": False,
    }

    actor_client = client.actor(APIFY_ACTOR_ID)
    run = actor_client.call(run_input=run_input)

    items: list[dict] = []
    dataset_client = client.dataset(run["defaultDatasetId"])
    for item in dataset_client.iterate_items():
        items.append(item)

    return items


def _parse_reel(item: dict) -> ReelMeta | None:
    """Extract relevant fields from a raw Apify item."""
    views = item.get("videoPlayCount") or item.get("videoViewCount")
    if views is None:
        return None

    owner = item.get("ownerUsername") or item.get("owner", {}).get("username", "unknown")

    music_info = item.get("musicInfo") or item.get("music") or {}
    music_name = (
        music_info.get("musicName")
        or music_info.get("name")
        or item.get("musicName")
    )
    if music_name and music_info.get("musicArtistName"):
        music_name = f"{music_name} — {music_info['musicArtistName']}"

    hashtags = item.get("hashtags") or []
    if hashtags and isinstance(hashtags[0], dict):
        hashtags = [h.get("name", "") for h in hashtags]

    return ReelMeta(
        username=owner,
        caption=item.get("caption") or item.get("text"),
        duration=item.get("videoDuration"),
        views=int(views),
        likes=item.get("likesCount"),
        comments=item.get("commentsCount"),
        hashtags=[str(h).lstrip("#") for h in hashtags if h],
        music=music_name,
        video_url=item.get("videoUrl"),
        thumbnail_url=item.get("displayUrl") or item.get("thumbnailUrl"),
    )


def filter_viral_reels(raw_items: list[dict]) -> tuple[list[ReelMeta], float, float]:
    """
    Parse items, compute average views, return viral reels where views > avg * 3.
    Returns (viral_reels, average_views, viral_threshold).
    """
    parsed = [r for item in raw_items if (r := _parse_reel(item)) is not None]

    if not parsed:
        return [], 0.0, 0.0

    average = sum(r.views for r in parsed) / len(parsed)
    threshold = average * 3
    viral = [r for r in parsed if r.views > threshold]

    return viral, round(average, 2), round(threshold, 2)


def parse_reels(raw_items: list[dict]) -> list[ReelMeta]:
    """Parse all valid reels from raw Apify items."""
    return [r for item in raw_items if (r := _parse_reel(item)) is not None]
