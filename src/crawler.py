"""
Apify YouTube 크롤러 — 구독 채널의 최근 24시간 신규 영상 수집
"""

import json
import os
import re
import time
from datetime import datetime, timedelta, timezone

import yaml
from apify_client import ApifyClient
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def extract_video_id(url: str) -> str | None:
    patterns = [
        r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})",
        r"shorts/([A-Za-z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def is_within_lookback(upload_date_str: str, lookback_hours: int) -> bool:
    """uploadDate 문자열이 lookback_hours 이내인지 확인."""
    if not upload_date_str:
        return False
    try:
        # Apify가 반환하는 형식: "2026-06-29T00:00:00.000Z" or "2026-06-29"
        upload_date_str = upload_date_str.replace("Z", "+00:00")
        if "T" in upload_date_str:
            dt = datetime.fromisoformat(upload_date_str)
        else:
            dt = datetime.fromisoformat(upload_date_str + "T00:00:00+00:00")
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        return dt >= cutoff
    except (ValueError, AttributeError):
        return False


def crawl_channel(client: ApifyClient, channel: dict, config: dict) -> list[dict]:
    """단일 채널에서 최근 영상 수집."""
    settings = config["settings"]
    actor_id = settings.get("apify_actor", "streamers/youtube-scraper")
    max_videos = settings.get("max_videos_per_channel", 5)
    lookback_hours = settings.get("lookback_hours", 24)

    run_input = {
        "startUrls": [{"url": channel["url"]}],
        "maxResults": max_videos * 3,  # 필터 후 충분한 수 확보
        "type": "CHANNEL",
    }

    print(f"  [{channel['name']}] Apify 실행 중...")
    try:
        run = client.actor(actor_id).call(run_input=run_input)
    except Exception as e:
        print(f"  [{channel['name']}] 오류: {e}")
        return []

    items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    recent_videos = []
    for item in items:
        upload_date = item.get("uploadDate") or item.get("publishedAt") or ""
        if is_within_lookback(upload_date, lookback_hours):
            video_id = extract_video_id(item.get("url", "") or item.get("id", ""))
            recent_videos.append(
                {
                    "channel_name": channel["name"],
                    "channel_url": channel["url"],
                    "video_id": video_id,
                    "title": item.get("title", ""),
                    "url": item.get("url", f"https://www.youtube.com/watch?v={video_id}"),
                    "upload_date": upload_date,
                    "views": item.get("viewCount", 0),
                    "likes": item.get("likes", 0),
                    "description": (item.get("description", "") or "")[:500],
                    "transcript": "",  # transcript.py에서 채움
                }
            )
            if len(recent_videos) >= max_videos:
                break

    print(f"  [{channel['name']}] {len(recent_videos)}개 신규 영상 발견")
    return recent_videos


def run_crawler() -> str:
    """전체 채널 크롤링 후 JSON 저장. 저장된 파일 경로 반환."""
    api_token = os.getenv("APIFY_API_TOKEN")
    if not api_token:
        raise EnvironmentError("APIFY_API_TOKEN 환경변수가 설정되지 않았습니다.")

    config = load_config()
    channels = config.get("channels", [])
    if not channels:
        raise ValueError("config.yaml에 채널이 설정되지 않았습니다.")

    client = ApifyClient(api_token)
    date_str = datetime.now().strftime("%Y%m%d")
    os.makedirs(DATA_DIR, exist_ok=True)
    output_path = os.path.join(DATA_DIR, f"raw_videos_{date_str}.json")

    all_videos = []
    print(f"총 {len(channels)}개 채널 크롤링 시작...")
    for channel in channels:
        videos = crawl_channel(client, channel, config)
        all_videos.extend(videos)
        time.sleep(2)  # Apify rate limit 방지

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "crawled_at": datetime.now().isoformat(),
                "date": date_str,
                "total_videos": len(all_videos),
                "videos": all_videos,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"크롤링 완료: 총 {len(all_videos)}개 영상 → {output_path}")
    return output_path


if __name__ == "__main__":
    run_crawler()
