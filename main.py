import os
import requests
import feedparser
from datetime import datetime
from youtube_transcript_api import YouTubeTranscriptApi
import google.generativeai as genai

# گرفتن اطلاعات از Secrets
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
YT_CHANNEL_ID = os.environ.get('YT_CHANNEL_ID')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# تنظیم Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def get_latest_video_from_rss():
    """گرفتن آخرین ویدیو از RSS"""
    try:
        rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={YT_CHANNEL_ID}"
        feed = feedparser.parse(rss_url)
        
        if feed.entries:
            video_id = feed.entries[0].yt_videoid
            title = feed.entries[0].title
            return video_id, title
        return None, None
    except Exception as e:
        print(f"خطا در RSS: {e}")
        return None, None

def get_transcript(video_id):
    """گرفتن زیرنویس ویدیو"""
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        # اولویت با زیرنویس فارسی، انگلیسی یا خودکار
        try:
            transcript = transcript_list.find_transcript(['fa', 'en'])
        except:
            transcript = transcript_list.find_generated_transcript(['en'])
        
        return transcript.fetch()
    except Exception as e:
        print(f"خطا در دریافت زیرنویس: {e}")
        return None

def summarize_with_gemini(transcript_text):
    """خلاصه‌سازی بخش‌بندی‌شده با Gemini"""
    prompt = f"""
    شما یک خبرنگار حرفه‌ای هستید. متن زیر زیرنویس یک ویدیوی خبری است.
    
    وظیفه شما:
    ۱. متن را به بخش‌های جداگانه (هر خبر یک بخش) تقسیم کنید
    ۲. برای هر بخش، تایم‌استمپ دقیق را پیدا کنید
    ۳. خلاصه‌ای کوتاه و مفید از هر بخش بنویسید
    ۴. خروجی را به شکل زیر بنویسید:
    
    [تایم‌استمپ] خلاصه خبر
    
    مثال:
    [00:00] افزایش قیمت دلار و تاثیر آن بر بازار
    [02:15] اعلام نتایج جدیدترین نظرسنجی‌ها
    [04:30] تصویب لایحه جدید در مجلس
    
    متن زیرنویس:
    {transcript_text[:15000]}
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"خطا در Gemini: {e}")
        return None

def send_to_telegram(message):
    """ارسال پیام به تلگرام"""
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
        print(f"خطا در ارسال به تلگرام: {e}")
        return False

def main():
    print(f"شروع بررسی در {datetime.now()}")
    
    # ۱. گرفتن آخرین ویدیو
    video_id, title = get_latest_video_from_rss()
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
    
    # ۳. دریافت زیرنویس
    transcript = get_transcript(video_id)
    if not transcript:
        msg = f"📺 <b>{title}</b>\n\n⚠️ این ویدیو زیرنویس ندارد.\n🔗 https://youtu.be/{video_id}"
        send_to_telegram(msg)
        # ذخیره میکنیم تا دوباره چک نکنه
        with open(processed_file, 'a') as f:
            f.write(f"{video_id}\n")
        return
    
    # ۴. تبدیل به متن
    full_text = " ".join([item['text'] for item in transcript])
    print(f"زیرنویس گرفته شد: {len(full_text)} کاراکتر")
    
    # ۵. خلاصه‌سازی
    summary = summarize_with_gemini(full_text)
    if not summary:
        msg = f"📺 <b>{title}</b>\n\n❌ خطا در خلاصه‌سازی\n🔗 https://youtu.be/{video_id}"
        send_to_telegram(msg)
        return
    
    # ۶. ارسال به تلگرام
    video_url = f"https://youtu.be/{video_id}"
    message = f"📺 <b>{title}</b>\n\n━━━━━━━━━━━━━━━━\n{summary}\n━━━━━━━━━━━━━━━━\n🔗 {video_url}"
    
    # اگه پیام طولانی بود، چند بخش کن
    if len(message) > 4000:
        parts = [message[i:i+4000] for i in range(0, len(message), 4000)]
        for part in parts:
            send_to_telegram(part)
    else:
        send_to_telegram(message)
    
    # ۷. ذخیره آی‌دی ویدیو
    with open(processed_file, 'a') as f:
        f.write(f"{video_id}\n")
    
    print("پردازش کامل شد!")

if __name__ == "__main__":
    main()
