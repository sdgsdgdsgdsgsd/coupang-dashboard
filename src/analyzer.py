"""
Claude API 기반 부동산 인사이트 분석기 — GitHub Actions / 독립 실행 환경용
raw_videos_{date}.json → report_{date}.json
"""

import json
import os
import sys
from datetime import datetime

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

ANALYSIS_SYSTEM_PROMPT = """당신은 대한민국 부동산 시장 전문 애널리스트입니다.
주어진 유튜브 영상 데이터(제목, 설명, 자막)를 분석하여 투자자에게 유용한 인사이트를 도출합니다.

분석 시 다음을 반드시 준수하세요:
- 사실에 기반한 분석 (추측 최소화)
- 한국어로 작성
- 구체적이고 실행 가능한 인사이트 우선
- 여러 유튜버의 공통적인 주장을 종합

결과는 반드시 유효한 JSON 형식으로만 출력하세요. 다른 텍스트 없이 JSON만 출력합니다."""


def build_analysis_prompt(videos: list[dict], date_str: str) -> str:
    parts = [f"# 오늘({date_str}) 부동산 유튜브 영상 분석 요청\n"]
    parts.append(f"총 {len(videos)}개 영상:\n")

    for i, v in enumerate(videos, 1):
        parts.append(f"\n## [{i}] {v.get('channel_name', '')} — {v.get('title', '')}")
        parts.append(f"URL: {v.get('url', '')}")
        if v.get("description"):
            parts.append(f"설명: {v['description'][:200]}")
        if v.get("transcript"):
            parts.append(f"자막(일부): {v['transcript'][:800]}")

    parts.append("""
---
위 영상들을 분석하여 아래 JSON 구조로만 응답하세요 (다른 텍스트 없이):

{
  "key_insights": ["인사이트1", "인사이트2", ...],
  "market_sentiment": {
    "overall": "positive|neutral|negative",
    "positive_ratio": 0.0,
    "neutral_ratio": 0.0,
    "negative_ratio": 0.0,
    "reasoning": "감성 판단 근거"
  },
  "topic_distribution": {"아파트": N, "재건축": N, "금리": N, "상가": N, "토지": N, "경매": N},
  "top_keywords": {"키워드": 빈도},
  "risk_factors": ["리스크1", ...],
  "investment_opportunities": ["기회1", ...],
  "policy_issues": ["이슈1", ...],
  "channel_summaries": [
    {
      "channel_name": "채널명",
      "videos": [
        {"title": "제목", "url": "URL", "views": 0, "summary": "2문장 요약", "sentiment": "positive|neutral|negative"}
      ]
    }
  ],
  "kakao_message": "[부동산 인사이트] MM/DD\\n📺 채널 N개 영상 M개 분석\\n🔑 핵심: ...\\n📈 시장: ...\\n⚠️ 리스크: ...\\n📧 상세보고서 이메일 발송완료"
}""")

    return "\n".join(parts)


def analyze_videos(date_str: str | None = None) -> str:
    """raw_videos JSON 분석 → report JSON 저장. 저장 경로 반환."""
    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")

    raw_path = os.path.join(DATA_DIR, f"raw_videos_{date_str}.json")
    if not os.path.exists(raw_path):
        raise FileNotFoundError(f"크롤링 결과 없음: {raw_path}")

    with open(raw_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    videos = raw_data.get("videos", [])
    if not videos:
        raise ValueError("분석할 영상이 없습니다.")

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY 환경변수 미설정")

    client = Anthropic(api_key=api_key)
    prompt = build_analysis_prompt(videos, date_str)

    print("Claude API 분석 중...")
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=ANALYSIS_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_json = response.content[0].text.strip()
    # JSON 블록 파싱 (```json ... ``` 형식 처리)
    if raw_json.startswith("```"):
        raw_json = raw_json.split("```")[1]
        if raw_json.startswith("json"):
            raw_json = raw_json[4:]

    report = json.loads(raw_json)
    report["date"] = date_str
    report["total_videos"] = len(videos)
    report["channels_covered"] = len({v["channel_name"] for v in videos})

    report_path = os.path.join(DATA_DIR, f"report_{date_str}.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"분석 완료 → {report_path}")
    return report_path


if __name__ == "__main__":
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    analyze_videos(date_arg)
