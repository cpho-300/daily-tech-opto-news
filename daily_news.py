import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from openai import OpenAI
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os

# ====================== 配置 ======================
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_TO = "cp.ho@auo.com"
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

TECH_FEEDS = [
    "https://techcrunch.com/feed/",
    "https://www.theverge.com/rss/tech/index.xml",
    "https://feeds.arstechnica.com/arstechnica/technology-lab",
    "https://www.wired.com/feed/rss"
]

OPTO_FEEDS = [
    "https://www.photonics.com/rss/rss.ashx",
    "https://phys.org/rss-topic.php?topic=optics",
    "https://www.nature.com/subjects/optics-and-photonics.rss"
]

# ====================== LLM 摘要 ======================
def llm_summarize(title, content, category):
    prompt = f"""
你是專業科技產業分析師，用繁體中文撰寫一段精煉摘要（90-130 字）。
包含：核心事件、對產業的影響、未來意義。
類別：{category}
標題：{title}
內容：{content[:7500]}
"""
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"摘要生成失敗: {str(e)}"

def get_article_content(url):
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer"]):
            tag.decompose()
        paragraphs = soup.find_all('p')
        text = "\n".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text()) > 30)
        return text[:8000]
    except:
        return ""

# ====================== 主要功能 ======================
def get_news(feeds, num=5, category="科技"):
    all_news = []
    for url in feeds:
        feed = feedparser.parse(url)
        for entry in feed.entries[:8]:
            title = entry.title
            link = entry.link
            content = get_article_content(link)
            summary = llm_summarize(title, content or entry.get("summary", ""), category)
            all_news.append({
                "title": title,
                "link": link,
                "summary": summary,
                "time": entry.get("published", "N/A")
            })
    
    # 去重
    seen = set()
    return [n for n in all_news if not (n["title"] in seen or seen.add(n["title"]))][:num]

def send_email(html_content):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_FROM
    msg['To'] = EMAIL_TO
    msg['Subject'] = f"📰 AUO 每日科技與光電新聞精選 - {datetime.now().strftime('%Y年%m月%d日')}"

    msg.attach(MIMEText(html_content, 'html'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_FROM, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("✅ Email 寄送成功！")
    except Exception as e:
        print(f"❌ 寄信失敗: {e}")

# ====================== 主程式 ======================
def main():
    print(f"開始執行 - {datetime.now()}")
    
    tech_news = get_news(TECH_FEEDS, 5, "科技")
    opto_news = get_news(OPTO_FEEDS, 5, "光電/光子學")

    # 產生 HTML
    html = f"""
    <html><body style="font-family: Arial, sans-serif; line-height: 1.7; color: #333;">
    <h2>📰 AUO 每日科技與光電新聞精選 - {datetime.now().strftime('%Y年%m月%d日')}</h2>
    <h3>🚀 科技新聞 Top 5</h3>
    """
    for i, n in enumerate(tech_news, 1):
        html += f"<h4>{i}. {n['title']}</h4><p><strong>摘要：</strong>{n['summary']}</p><p><a href='{n['link']}'>閱讀全文 →</a></p><hr>"

    html += "<h3>🔦 光電 / 光子學新聞 Top 5</h3>"
    for i, n in enumerate(opto_news, 1):
        html += f"<h4>{i}. {n['title']}</h4><p><strong>摘要：</strong>{n['summary']}</p><p><a href='{n['link']}'>閱讀全文 →</a></p><hr>"

    html += "<p><small>此報告由 GitHub Actions + AI 自動產生，每天自動寄送</small></p></body></html>"

    send_email(html)

if __name__ == "__main__":
    main()
