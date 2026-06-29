"""
Gmail SMTP 이메일 발송 — report_{date}.json + charts → HTML 이메일 전송
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

SENTIMENT_LABELS = {
    "positive": "긍정 (상승 분위기)",
    "neutral": "중립 (관망세)",
    "negative": "부정 (하락 우려)",
}


def load_report(date_str: str) -> dict:
    path = os.path.join(DATA_DIR, f"report_{date_str}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"리포트 없음: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def render_html(report: dict) -> str:
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    template = env.get_template("daily_report.html")

    date_str = report.get("date", datetime.now().strftime("%Y%m%d"))
    try:
        dt = datetime.strptime(date_str, "%Y%m%d")
        date_display = dt.strftime("%Y년 %m월 %d일")
    except ValueError:
        date_display = date_str

    sentiment = report.get("market_sentiment", {})
    overall = sentiment.get("overall", "neutral")

    return template.render(
        date=date_str,
        date_display=date_display,
        total_videos=report.get("total_videos", 0),
        channels_covered=report.get("channels_covered", 0),
        market_sentiment=sentiment,
        sentiment_label=SENTIMENT_LABELS.get(overall, overall),
        key_insights=report.get("key_insights", []),
        channel_summaries=report.get("channel_summaries", []),
        risk_factors=report.get("risk_factors", []),
        investment_opportunities=report.get("investment_opportunities", []),
        policy_issues=report.get("policy_issues", []),
        charts=report.get("charts", {}),
    )


def send_email(html_content: str, date_str: str) -> None:
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        raise EnvironmentError("GMAIL_USER 또는 GMAIL_APP_PASSWORD 환경변수 미설정")

    try:
        dt = datetime.strptime(date_str, "%Y%m%d")
        subject = f"[부동산 인사이트] {dt.strftime('%Y/%m/%d')} 유튜브 분석 리포트"
    except ValueError:
        subject = f"[부동산 인사이트] {date_str} 유튜브 분석 리포트"

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

    print(f"리포트 로드: {date_str}")
    report = load_report(date_str)

    print("HTML 렌더링 중...")
    html = render_html(report)

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
