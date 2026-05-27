#!/usr/bin/env python3
"""Email newsletter sender for DailyDex."""

import json
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
DATA_FILE = os.environ.get("DATA_FILE", os.path.join(DATA_DIR, "data.json"))

# Mailgun SMTP settings
SMTP_HOST = "smtp.mailgun.org"
SMTP_PORT = 587
SMTP_USER = "Pi@homelabdev.space"
SMTP_PASS = "08June@1992"

FROM_NAME = "DailyDex"
FROM_EMAIL = "daily@ai-intel.com"
TO_EMAIL = "amonkarsidhant@outlook.com"


def load_data():
    with open(DATA_FILE) as f:
        return json.load(f)


def generate_summary(data):
    """Use LLM for intelligent summary."""
    import llm_summary

    try:
        return llm_summary.get_ollama_summary(data)
    except:
        return f"Today's AI news: {len(data.get('github', []))} trending repos, {len(data.get('blogs', []))} stories."


def generate_newsletter(data):
    """Generate consistent HTML newsletter."""
    summary = generate_summary(data)
    github = data.get("github", [])[:3]
    youtube = data.get("youtube", [])[:2]
    blogs = data.get("blogs", [])[:3]

    # Fixed CSS that never changes
    css = """* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0d0d0d; color: #e5e5e5; line-height: 1.5; }
.container { max-width: 580px; margin: 0 auto; }
.header { background: linear-gradient(135deg, #22c55e, #16a34a); padding: 2rem 1.5rem; text-align: center; }
.header h1 { font-size: 1.5rem; font-weight: 700; color: #fff; letter-spacing: 0.05em; }
.header .date { color: rgba(255,255,255,0.85); font-size: 0.8rem; margin-top: 0.25rem; }
.greeting { padding: 1.5rem; text-align: center; border-bottom: 1px solid #262626; }
.greeting p { color: #888; }
.summary { margin-top: 0.5rem; font-size: 1rem; color: #ccc; line-height: 1.4; word-wrap: break-word; }
.section { padding: 1.25rem 1.5rem; border-bottom: 1px solid #262626; }
.section-title { font-size: 0.7rem; font-weight: 600; color: #22c55e; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 0.75rem; }
.big-story { background: #161616; padding: 1rem; border-radius: 8px; }
.big-story a { color: #fff; text-decoration: none; }
.big-story h3 { font-size: 1rem; font-weight: 600; margin-bottom: 0.5rem; }
.big-story p { color: #888; font-size: 0.85rem; }
.item { display: flex; align-items: center; padding: 0.6rem 0; border-bottom: 1px solid #262626; }
.item:last-child { border: none; }
.item-num { color: #666; font-size: 0.8rem; width: 20px; }
.item-title { font-size: 0.85rem; flex: 1; }
.item-title a { color: #22c55e; text-decoration: none; }
.item-title a:hover { text-decoration: underline; }
.item-meta { color: #666; font-size: 0.75rem; }
.footer { padding: 1.5rem; text-align: center; border-top: 1px solid #262626; }
.footer p { color: #555; font-size: 0.75rem; }
.footer a { color: #22c55e; }"""

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>DailyDex</title>
<style>{css}</style>
</head>
<body>
<div class="container">
<div class="header">
        <h1>DAILYDEX</h1>
<p class="date">{datetime.now().strftime("%B %d, %Y")}</p>
</div>

<div class="greeting">
<p>Good morning.</p>
<p class="summary">{summary}</p>
</div>

<div class="section">
<div class="section-title">🔥 Top Repo</div>
<div class="big-story">
<a href="{github[0]["url"]}"><h3>{github[0]["title"]}</h3></a>
<p>{github[0].get("description", "")[:100]}...</p>
</div>
</div>

<div class="section">
<div class="section-title">📰 Latest News</div>
"""

    for i, item in enumerate(blogs[:3]):
        if item.get("title"):
            html += f"""<div class="item">
<span class="item-num">{i + 1}.</span>
<span class="item-title"><a href="{item["url"]}">{item["title"][:55]}</a></span>
<span class="item-meta">{item.get("source", "")[:12]}</span>
</div>"""

    html += """</div>

<div class="section">
<div class="section-title">🛠️ Trending on GitHub</div>
"""

    for i, item in enumerate(github[:3]):
        html += f"""<div class="item">
<span class="item-num">{i + 1}.</span>
<span class="item-title"><a href="{item["url"]}">{item["title"][:45]}</a></span>
<span class="item-meta">★{item.get("stars", "0")}</span>
</div>"""

    html += """</div>

<div class="section">
<div class="section-title">📺 Worth Watching</div>
"""

    for i, item in enumerate(youtube[:2]):
        html += f"""<div class="item">
<span class="item-num">{i + 1}.</span>
<span class="item-title"><a href="{item["url"]}">{item["title"][:50]}</a></span>
<span class="item-meta">{item.get("source", "").replace("YouTube - ", "")[:15]}</span>
</div>"""

    html += """</div>

<div class="footer">
<p><a href="http://192.168.2.16:8888/">View Web Version</a></p>
    <p style="margin-top:0.75rem;font-size:0.7rem;color:#444">DailyDex Daily • Automated Brief</p>
</div>
</div>
</body>
</html>"""

    return html


def send_email(html_content, subject="Your Daily AI Briefing"):
    """Send email via Mailgun SMTP."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{FROM_NAME} <{FROM_EMAIL}>"
    msg["To"] = TO_EMAIL

    html_part = MIMEText(html_content, "html")
    msg.attach(html_part)

    try:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(FROM_EMAIL, TO_EMAIL, msg.as_string())
        server.quit()
        return True, "Email sent successfully!"
    except Exception as e:
        return False, str(e)


def send_daily():
    """Send daily newsletter."""
    print("Generating newsletter...")
    data = load_data()
    html = generate_newsletter(data)

    print("Sending email...")
    success, message = send_email(html)
    print(message)
    return success


if __name__ == "__main__":
    send_daily()
