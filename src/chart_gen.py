"""
인포그래픽 차트 생성 — report_{date}.json을 읽어 matplotlib 차트 PNG를 base64로 저장
"""

import base64
import io
import json
import os
import sys
from datetime import datetime

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

matplotlib.use("Agg")  # 헤드리스 환경

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
CHARTS_DIR = os.path.join(DATA_DIR, "charts")

# 한글 폰트 설정 — 파일 직접 등록 (시스템 캐시 불필요)
def _setup_korean_font():
    nanum_paths = [
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf",
        "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    ]
    for path in nanum_paths:
        if os.path.exists(path):
            fm.fontManager.addfont(path)
            prop = fm.FontProperties(fname=path)
            plt.rcParams["font.family"] = prop.get_name()
            return
    # 시스템 폰트 탐색 폴백
    candidates = ["NanumGothic", "NanumBarunGothic", "Malgun Gothic", "AppleGothic"]
    available = {f.name for f in fm.fontManager.ttflist}
    for font in candidates:
        if font in available:
            plt.rcParams["font.family"] = font
            return

_setup_korean_font()
plt.rcParams["axes.unicode_minus"] = False

PALETTE = ["#2563EB", "#16A34A", "#DC2626", "#D97706", "#7C3AED", "#0891B2", "#DB2777"]
BG_COLOR = "#F8FAFC"
CARD_COLOR = "#FFFFFF"


def _fig_to_b64(fig: plt.Figure) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor=BG_COLOR)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def chart_sentiment(report: dict, date_str: str) -> str:
    """채널별 시장 감성 수평 막대 차트."""
    summaries = report.get("channel_summaries", [])
    if not summaries:
        return ""

    channels, pos, neu, neg = [], [], [], []

    for ch in summaries:
        channels.append(ch["channel_name"])
        videos = ch.get("videos", [])
        total = len(videos) or 1
        p = sum(1 for v in videos if v.get("sentiment") == "positive") / total
        neg_r = sum(1 for v in videos if v.get("sentiment") == "negative") / total
        pos.append(p)
        neg.append(neg_r)
        neu.append(1 - p - neg_r)

    fig, ax = plt.subplots(figsize=(8, max(3, len(channels) * 0.7 + 1)), facecolor=BG_COLOR)
    ax.set_facecolor(CARD_COLOR)
    y = range(len(channels))
    ax.barh(y, pos, color="#16A34A", label="긍정", height=0.5)
    ax.barh(y, neu, left=pos, color="#D97706", label="중립", height=0.5)
    ax.barh(y, neg, left=[p + n for p, n in zip(pos, neu)], color="#DC2626", label="부정", height=0.5)
    ax.set_yticks(list(y))
    ax.set_yticklabels(channels, fontsize=10)
    ax.set_xlim(0, 1)
    ax.set_xlabel("비율", fontsize=9)
    ax.set_title("채널별 시장 감성", fontsize=12, fontweight="bold", pad=10)
    ax.legend(loc="lower right", fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()

    b64 = _fig_to_b64(fig)
    plt.close(fig)
    return b64


def chart_topic_distribution(report: dict, date_str: str) -> str:
    """주제 분포 파이 차트."""
    topics = report.get("topic_distribution", {})
    if not topics:
        return ""

    labels = list(topics.keys())
    sizes = list(topics.values())
    if not any(sizes):
        return ""

    fig, ax = plt.subplots(figsize=(7, 5), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    wedges, texts, autotexts = ax.pie(
        sizes,
        labels=labels,
        autopct="%1.0f%%",
        colors=PALETTE[: len(labels)],
        startangle=90,
        pctdistance=0.82,
    )
    for text in texts:
        text.set_fontsize(9)
    for autotext in autotexts:
        autotext.set_fontsize(8)
        autotext.set_color("white")
        autotext.set_fontweight("bold")
    ax.set_title("오늘의 주제 분포", fontsize=12, fontweight="bold", pad=15)
    plt.tight_layout()

    b64 = _fig_to_b64(fig)
    plt.close(fig)
    return b64


def chart_top_keywords(report: dict, date_str: str) -> str:
    """언급 빈도 키워드 Top10 수평 막대."""
    keywords_raw = report.get("top_keywords", [])
    if not keywords_raw:
        return ""

    if isinstance(keywords_raw, dict):
        items = sorted(keywords_raw.items(), key=lambda x: x[1], reverse=True)[:10]
        words, counts = zip(*items) if items else ([], [])
    else:
        words = keywords_raw[:10]
        counts = list(range(len(words), 0, -1))

    if not words:
        return ""

    fig, ax = plt.subplots(figsize=(8, max(3, len(words) * 0.5 + 1.5)), facecolor=BG_COLOR)
    ax.set_facecolor(CARD_COLOR)
    colors = [PALETTE[i % len(PALETTE)] for i in range(len(words))]
    bars = ax.barh(list(range(len(words))), counts, color=colors, height=0.6)
    ax.set_yticks(list(range(len(words))))
    ax.set_yticklabels(list(words), fontsize=10)
    ax.invert_yaxis()
    ax.set_xlabel("언급 빈도", fontsize=9)
    ax.set_title("오늘의 핵심 키워드 Top10", fontsize=12, fontweight="bold", pad=10)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(left=False)
    for bar, val in zip(bars, counts):
        ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                str(val), va="center", fontsize=8, color="#374151")
    plt.tight_layout()

    b64 = _fig_to_b64(fig)
    plt.close(fig)
    return b64


def chart_videos_per_channel(report: dict, date_str: str) -> str:
    """채널별 영상 수 막대 차트."""
    summaries = report.get("channel_summaries", [])
    if not summaries:
        return ""

    channels = [ch["channel_name"] for ch in summaries]
    counts = [len(ch.get("videos", [])) for ch in summaries]

    fig, ax = plt.subplots(figsize=(max(5, len(channels) * 1.2), 4), facecolor=BG_COLOR)
    ax.set_facecolor(CARD_COLOR)
    bars = ax.bar(channels, counts, color=PALETTE[: len(channels)], width=0.5)
    ax.set_ylabel("영상 수", fontsize=9)
    ax.set_title("채널별 오늘의 신규 영상", fontsize=12, fontweight="bold", pad=10)
    ax.spines[["top", "right"]].set_visible(False)
    for bar, val in zip(bars, counts):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                str(val), ha="center", fontsize=10, fontweight="bold")
    plt.xticks(rotation=15, ha="right", fontsize=9)
    plt.tight_layout()

    b64 = _fig_to_b64(fig)
    plt.close(fig)
    return b64


def generate_all_charts(date_str: str | None = None) -> dict[str, str]:
    """
    raw_videos_{date}.json을 읽어 모든 차트를 생성하고
    {chart_name: base64_png} 딕셔너리를 반환 + charts_{date}.json에 저장.
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")

    raw_path = os.path.join(DATA_DIR, f"raw_videos_{date_str}.json")
    if not os.path.exists(raw_path):
        raise FileNotFoundError(f"크롤링 결과 없음: {raw_path}")

    with open(raw_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # Build channel_summaries from raw videos for chart functions
    channels_map: dict[str, list] = {}
    for v in raw.get("videos", []):
        cname = v.get("channel_name", "Unknown")
        if cname not in channels_map:
            channels_map[cname] = []
        channels_map[cname].append(v)

    report = {
        "channel_summaries": [
            {"channel_name": name, "videos": vids}
            for name, vids in channels_map.items()
        ]
    }

    os.makedirs(CHARTS_DIR, exist_ok=True)

    generators = {
        "sentiment": chart_sentiment,
        "topic": chart_topic_distribution,
        "keywords": chart_top_keywords,
        "videos_per_channel": chart_videos_per_channel,
    }

    charts: dict[str, str] = {}
    for name, fn in generators.items():
        print(f"  차트 생성: {name}")
        b64 = fn(report, date_str)
        if b64:
            charts[name] = b64
            out_path = os.path.join(CHARTS_DIR, f"{name}_{date_str}.b64")
            with open(out_path, "w") as f:
                f.write(b64)

    # Save charts index for email_sender.py
    charts_path = os.path.join(DATA_DIR, f"charts_{date_str}.json")
    with open(charts_path, "w", encoding="utf-8") as f:
        json.dump({"charts": charts}, f, ensure_ascii=False)

    print(f"차트 생성 완료: {len(charts)}개")
    return charts


if __name__ == "__main__":
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    generate_all_charts(date_arg)
