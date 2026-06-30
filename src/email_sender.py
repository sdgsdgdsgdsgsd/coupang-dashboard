"""
Gmail SMTP 이메일 발송 — raw_videos_{date}.json → HTML 이메일 전송
"""

import json
import os
import smtplib
import ssl
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", GMAIL_USER)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def load_raw_videos(date_str: str) -> dict:
    path = os.path.join(DATA_DIR, f"raw_videos_{date_str}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"크롤링 결과 없음: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_channel_summaries(videos: list[dict]) -> list[dict]:
    channels: dict[str, dict] = {}
    for v in videos:
        cname = v.get("channel_name", "Unknown")
        if cname not in channels:
            channels[cname] = {"channel_name": cname, "videos": []}
        snippet = (v.get("description") or v.get("transcript") or "")[:200]
        channels[cname]["videos"].append(
            {
                "title": v.get("title", ""),
                "url": v.get("url", ""),
                "views": v.get("views", 0),
                "summary": snippet,
                "sentiment": None,
            }
        )
    return list(channels.values())


def render_html(raw: dict) -> str:
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    template = env.get_template("daily_report.html")

    date_str = raw.get("date", datetime.now().strftime("%Y%m%d"))
    try:
        dt = datetime.strptime(date_str, "%Y%m%d")
        date_display = dt.strftime("%Y년 %m월 %d일")
    except ValueError:
        date_display = date_str

    videos = raw.get("videos", [])
    channel_names = {v.get("channel_name") for v in videos}

    return template.render(
        date=date_str,
        date_display=date_display,
        total_videos=raw.get("total_videos", len(videos)),
        channels_covered=len(channel_names),
        market_sentiment={},
        sentiment_label="",
        key_insights=[],
        channel_summaries=build_channel_summaries(videos),
        risk_factors=[],
        investment_opportunities=[],
        policy_issues=[],
        charts={},
    )


def send_email(html_content: str, date_str: str) -> None:
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        raise EnvironmentError("GMAIL_USER 또는 GMAIL_APP_PASSWORD 환경변수 미설정")

    try:
        dt = datetime.strptime(date_str, "%Y%m%d")
        subject = f"[부동산 인사이트] {dt.strftime('%Y/%m/%d')} 유튜브 신규 영상 리포트"
    except ValueError:
        subject = f"[부동산 인사이트] {date_str} 유튜브 신규 영상 리포트"

    msg = MIMEMultipart("alternative")
    msg["From"] = GMAIL_USER
    msg["To"] = RECIPIENT_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls(context=context)
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, RECIPIENT_EMAIL, msg.as_string())

    print(f"이메일 발송 완료 → {RECIPIENT_EMAIL}")


def run_email_sender(date_str: str | None = None, test_mode: bool = False) -> None:
    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")

    print(f"크롤링 결과 로드: {date_str}")
    raw = load_raw_videos(date_str)

    print("HTML 렌더링 중...")
    html = render_html(raw)

    if test_mode:
        out = os.path.join(DATA_DIR, f"email_preview_{date_str}.html")
        with open(out, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"테스트 모드: HTML 미리보기 저장 → {out}")
        return

    print("Gmail SMTP 발송 중...")
    send_email(html, date_str)


if __name__ == "__main__":
    test = "--test" in sys.argv
    date_arg = next((a for a in sys.argv[1:] if not a.startswith("--")), None)
    run_email_sender(date_arg, test_mode=test)
