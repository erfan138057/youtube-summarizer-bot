import os
import requests
import feedparser
from datetime import datetime
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled
import google.generativeai as genai

# گرفتن اطلاعات از Secrets
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
YT_CHANNEL_ID = os.environ.get('YT_CHANNEL_ID')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# تنظیم Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash-latest')

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
    """گرفتن Transcript با استفاده از youtube-transcript-api v1.x"""
    api = YouTubeTranscriptApi()

    # اولویت: فارسی، انگلیسی، هر زبانی
    for langs in [['fa'], ['en'], ['fa', 'en']]:
        try:
            transcript = api.fetch(video_id, languages=langs)
            # در v1.x مستقیماً قابل iterate است
            return [{'text': s.text, 'start': s.start} for s in transcript]
        except NoTranscriptFound:
            continue
        except TranscriptsDisabled:
            print(f"Transcript برای {video_id} غیرفعال است")
            return None
        except Exception as e:
            print(f"خطا برای زبان {langs}: {e}")
            continue

    # تلاش آخر: هر زبانی که موجود باشد
    try:
        transcript_list = api.list(video_id)
        for t in transcript_list:
            fetched = t.fetch()
            return [{'text': s.text, 'start': s.start} for s in fetched]
    except Exception as e:
        print(f"خطا در دریافت Transcript: {e}")

    return None

def summarize_with_gemini(transcript_text):
    """خلاصه‌سازی بخش‌بندی‌شده با حفظ تایم‌استمپ"""
    if not transcript_text or len(transcript_text) < 50:
        return None

    prompt = f"""
    شما یک خبرنگار حرفه‌ای هستید. متن زیر، Transcript (زیرنویس رسمی) یک ویدیوی خبری است.
    
    وظیفه شما:
    ۱. متن را به بخش‌های جداگانه تقسیم کنید (هر خبر یک بخش)
    ۲. برای هر بخش، تایم‌استمپ دقیق را پیدا کنید (از Transcript مشخص است)
    ۳. خلاصه‌ای کوتاه و مفید (حداکثر ۱-۲ خط) از هر بخش بنویسید
    ۴. خروجی را دقیقاً به این شکل بنویسید:
    
    [تایم‌استمپ] خلاصه خبر
    
    مثال:
    [00:00] افزایش قیمت دلار و تاثیر آن بر بازار
    [02:15] اعلام نتایج جدیدترین نظرسنجی‌ها
    [04:30] تصویب لایحه جدید در مجلس
    
    توجه: تایم‌استمپ‌ها باید دقیقاً از روی Transcript استخراج شوند.
    
    متن Transcript:
    {transcript_text[:15000]}
    """

    try:
        response = model.generate_content(prompt)
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
            payload = {
                'chat_id': TELEGRAM_CHAT_ID,
                'photo': thumbnail_url,
                'caption': parts[0],
                'parse_mode': 'HTML'
            }
            requests.post(url, json=payload)
            for part in parts[1:]:
                send_to_telegram_text(part)
        else:
            payload = {
                'chat_id': TELEGRAM_CHAT_ID,
                'photo': thumbnail_url,
                'caption': caption,
                'parse_mode': 'HTML'
            }
            response = requests.post(url, json=payload)
            return response.ok

    except Exception as e:
        print(f"خطا در ارسال به تلگرام: {e}")
        return False

def send_to_telegram_text(message):
    """ارسال پیام متنی ساده به تلگرام"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML'
        }
        response = requests.post(url, json=payload)
        return response.ok
    except Exception as e:
        print(f"خطا در ارسال متن: {e}")
        return False

def main():
    print(f"شروع بررسی در {datetime.now()}")

    # ۱. گرفتن آخرین ویدیو
    video_id, title, thumbnail = get_latest_video_from_rss()
    if not video_id:
        print("ویدیویی پیدا نشد")
        return

    print(f"ویدیو پیدا شد: {title} - {video_id}")

    # ۲. چک کردن اینکه قبلاً پردازش شده یا نه
    processed_file = 'processed.txt'
    if os.path.exists(processed_file):
        with open(processed_file, 'r') as f:
            processed = f.read().splitlines()
        if video_id in processed:
            print("این ویدیو قبلاً پردازش شده")
            return

    # ۳. دریافت Transcript
    transcript = get_transcript(video_id)
    if not transcript:
        send_to_telegram_with_photo(
            title, thumbnail,
            "⚠️ این ویدیو Transcript ندارد.",
            f"https://youtu.be/{video_id}"
        )
        with open(processed_file, 'a') as f:
            f.write(f"{video_id}\n")
        return

    # ۴. تبدیل به متن (با تایم‌استمپ برای Gemini)
    transcript_text = " ".join([
        f"[{int(item['start']//60):02d}:{int(item['start']%60):02d}] {item['text']}"
        for item in transcript
    ])
    print(f"Transcript گرفته شد: {len(transcript_text)} کاراکتر")

    # ۵. خلاصه‌سازی
    summary = summarize_with_gemini(transcript_text)
    if not summary:
        send_to_telegram_with_photo(
            title, thumbnail,
            "❌ خطا در خلاصه‌سازی",
            f"https://youtu.be/{video_id}"
        )
        return

    # ۶. ارسال به تلگرام
    send_to_telegram_with_photo(title, thumbnail, summary, f"https://youtu.be/{video_id}")

    # ۷. ذخیره آی‌دی ویدیو
    with open(processed_file, 'a') as f:
        f.write(f"{video_id}\n")

    print("پردازش کامل شد!")

if __name__ == "__main__":
    main()
