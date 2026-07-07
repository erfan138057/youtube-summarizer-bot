import os
import requests
import feedparser
from datetime import datetime
from google import genai

# گرفتن اطلاعات از Secrets
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
YT_CHANNEL_ID = os.environ.get('YT_CHANNEL_ID')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
SUPADATA_API_KEY = os.environ.get('SUPADATA_API_KEY')

# تنظیم Gemini
client = genai.Client(api_key=GEMINI_API_KEY)

def get_latest_video_from_rss():
    """گرفتن آخرین ویدیو از RSS"""
    try:
        rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={YT_CHANNEL_ID}"
        feed = feedparser.parse(rss_url)
        if feed.entries:
            video_id = feed.entries[0].yt_videoid
            title = feed.entries[0].title
            thumbnail = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
            return video_id, title, thumbnail
        return None, None, None
    except Exception as e:
        print(f"خطا در RSS: {e}")
        return None, None, None

def get_transcript(video_id):
    """گرفتن Transcript از طریق Supadata API"""
    try:
        url = "https://api.supadata.ai/v1/youtube/transcript"
        headers = {"x-api-key": SUPADATA_API_KEY}

        # اول فارسی
        response = requests.get(url, params={"videoId": video_id, "lang": "fa"}, headers=headers, timeout=30)

        # اگه فارسی نداشت، انگلیسی امتحان کن
        if not response.ok or not response.json().get("content"):
            response = requests.get(url, params={"videoId": video_id, "lang": "en"}, headers=headers, timeout=30)

        if not response.ok:
            print(f"خطای Supadata: {response.status_code} - {response.text}")
            return None

        content = response.json().get("content", [])
        if not content:
            print("Transcript خالی برگشت")
            return None

        return [
            {"text": item["text"], "start": item["offset"] / 1000}
            for item in content
        ]

    except Exception as e:
        print(f"خطا در دریافت Transcript: {e}")
        return None

def summarize_with_gemini(transcript_text):
    """خلاصه‌سازی با Gemini"""
    if not transcript_text or len(transcript_text) < 50:
        return None

    prompt = f"""
    شما یک خبرنگار حرفه‌ای هستید. متن زیر، Transcript یک ویدیوی خبری است.
    
    وظیفه شما:
    ۱. متن را به بخش‌های جداگانه تقسیم کنید (هر خبر یک بخش)
    ۲. برای هر بخش، تایم‌استمپ دقیق را پیدا کنید
    ۳. خلاصه‌ای کوتاه (حداکثر ۱-۲ خط) از هر بخش بنویسید
    ۴. خروجی را دقیقاً به این شکل بنویسید:
    
    [تایم‌استمپ] خلاصه خبر
    
    مثال:
    [00:00] افزایش قیمت دلار و تاثیر آن بر بازار
    [02:15] اعلام نتایج جدیدترین نظرسنجی‌ها
    [04:30] تصویب لایحه جدید در مجلس
    
    متن Transcript:
    {transcript_text[:15000]}
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        return response.text
    except Exception as e:
        print(f"خطا در Gemini: {e}")
        return None

def send_to_telegram_with_photo(title, thumbnail_url, summary, video_url):
    """ارسال پیام با عکس به تلگرام"""
    try:
        caption = f"📺 <b>{title}</b>\n\n━━━━━━━━━━━━━━━━\n{summary}\n━━━━━━━━━━━━━━━━\n🔗 {video_url}"
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"

        if len(caption) > 4000:
            parts = [caption[i:i+4000] for i in range(0, len(caption), 4000)]
            payload = {'chat_id': TELEGRAM_CHAT_ID, 'photo': thumbnail_url, 'caption': parts[0], 'parse_mode': 'HTML'}
            requests.post(url, json=payload)
            for part in parts[1:]:
                send_to_telegram_text(part)
        else:
            payload = {'chat_id': TELEGRAM_CHAT_ID, 'photo': thumbnail_url, 'caption': caption, 'parse_mode': 'HTML'}
            response = requests.post(url, json=payload)
            return response.ok

    except Exception as e:
        print(f"خطا در ارسال به تلگرام: {e}")
        return False

def send_to_telegram_text(message):
    """ارسال پیام متنی به تلگرام"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
        response = requests.post(url, json=payload)
        return response.ok
    except Exception as e:
        print(f"خطا در ارسال متن: {e}")
        return False

def main():
    print(f"شروع بررسی در {datetime.now()}")

    video_id, title, thumbnail = get_latest_video_from_rss()
    if not video_id:
        print("ویدیویی پیدا نشد")
        return

    print(f"ویدیو پیدا شد: {title} - {video_id}")

    processed_file = 'processed.txt'
    if os.path.exists(processed_file):
        with open(processed_file, 'r') as f:
            processed = f.read().splitlines()
        if video_id in processed:
            print("این ویدیو قبلاً پردازش شده")
            return

    transcript = get_transcript(video_id)
    if not transcript:
        send_to_telegram_with_photo(title, thumbnail, "⚠️ این ویدیو Transcript ندارد.", f"https://youtu.be/{video_id}")
        with open(processed_file, 'a') as f:
            f.write(f"{video_id}\n")
        return

    transcript_text = " ".join([
        f"[{int(item['start']//60):02d}:{int(item['start']%60):02d}] {item['text']}"
        for item in transcript
    ])
    print(f"Transcript گرفته شد: {len(transcript_text)} کاراکتر")

    summary = summarize_with_gemini(transcript_text)
    if not summary:
        send_to_telegram_with_photo(title, thumbnail, "❌ خطا در خلاصه‌سازی", f"https://youtu.be/{video_id}")
        return

    send_to_telegram_with_photo(title, thumbnail, summary, f"https://youtu.be/{video_id}")

    with open(processed_file, 'a') as f:
        f.write(f"{video_id}\n")

    print("پردازش کامل شد!")

if __name__ == "__main__":
    main()
