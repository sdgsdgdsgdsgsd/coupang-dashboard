"""
YouTube 자막 수집 — raw_videos_{date}.json의 transcript 필드를 채움
"""

import json
import os
import sys
from datetime import datetime

from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

MAX_TRANSCRIPT_CHARS = 4000  # Claude 분석용 최대 자막 길이


def fetch_transcript(video_id: str, languages: list[str]) -> str:
    """video_id의 자막 텍스트 반환. 없으면 빈 문자열."""
    if not video_id:
        return ""
    try:
        if hasattr(YouTubeTranscriptApi, "get_transcript"):
            # youtube-transcript-api < 1.0
            entries = YouTubeTranscriptApi.get_transcript(video_id, languages=languages)
            text = " ".join(entry["text"] for entry in entries)
        else:
            # youtube-transcript-api >= 1.0: 인스턴스 fetch() 사용
            fetched = YouTubeTranscriptApi().fetch(video_id, languages=languages)
            text = " ".join(snippet.text for snippet in fetched)
        return text[:MAX_TRANSCRIPT_CHARS]
    except (TranscriptsDisabled, NoTranscriptFound):
        return ""
    except Exception as e:
        print(f"  [자막 오류] {video_id}: {e}")
        return ""


def enrich_with_transcripts(raw_path: str, languages: list[str] | None = None) -> None:
    """raw_videos JSON의 각 영상에 transcript 필드를 채워 저장."""
    if languages is None:
        languages = ["ko", "en"]

    with open(raw_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    videos = data.get("videos", [])
    print(f"자막 수집 시작: {len(videos)}개 영상")

    for i, video in enumerate(videos, 1):
        video_id = video.get("video_id")
        title = video.get("title", "")
        if video.get("transcript"):
            print(f"  [{i}/{len(videos)}] 이미 자막 있음: {title[:30]}")
            continue

        print(f"  [{i}/{len(videos)}] 자막 수집: {title[:40]}...")
        transcript = fetch_transcript(video_id, languages)
        video["transcript"] = transcript
        status = f"{len(transcript)}자" if transcript else "없음"
        print(f"           → {status}")

    before_count = len(videos)
    videos = [
        v for v in videos
        if v.get("transcript") or v.get("description")
    ]
    removed = before_count - len(videos)
    if removed:
        print(f"자막·설명 없는 영상 제거: {removed}개 (남은 영상: {len(videos)}개)")

    data["videos"] = videos
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    transcribed = sum(1 for v in videos if v.get("transcript"))
    print(f"자막 수집 완료: {transcribed}/{len(videos)}개")


def run_transcript(date_str: str | None = None) -> str:
    """지정 날짜(기본: 오늘)의 raw_videos JSON에 자막 보강."""
    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")

    raw_path = os.path.join(DATA_DIR, f"raw_videos_{date_str}.json")
    if not os.path.exists(raw_path):
        raise FileNotFoundError(f"크롤링 결과 파일 없음: {raw_path}")

    enrich_with_transcripts(raw_path)
    return raw_path


if __name__ == "__main__":
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    run_transcript(date_arg)
