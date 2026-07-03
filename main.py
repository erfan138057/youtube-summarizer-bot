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
            # گرفتن لینک thumbnail
            thumbnail = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
            return video_id, title, thumbnail
        return None, None, None
    except Exception as e:
        print(f"خطا در RSS: {e}")
        return None, None, None

def get_transcript(video_id):
    """گرفتن Transcript (زیرنویس رسمی) ویدیو"""
    try:
        # لیست تمام Transcript های موجود
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # اولویت: Transcript فارسی، انگلیسی یا خودکار
        try:
            transcript = transcript_list.find_transcript(['fa', 'en'])
        except:
            transcript = transcript_list.find_generated_transcript(['en'])
        
        # اگر Transcript پیدا شد
        if transcript:
            return transcript.fetch()
        return None
    except Exception as e:
        print(f"خطا در دریافت Transcript: {e}")
        return None

def format_transcript_with_timestamps(transcript):
    """تبدیل Transcript به متن با تایم‌استمپ"""
    if not transcript:
        return None
    
    transcript_text = ""
    for item in transcript:
        minutes = int(item["start"] // 60)
        seconds = int(item["start"] % 60)
        transcript_text += f"[{minutes:02}:{seconds:02}] {item['text']}\n"
    
    return transcript_text

def summarize_with_gemini(transcript_text):
    """خلاصه‌سازی بخش‌بندی‌شده با حفظ تایم‌استمپ"""
    if not transcript_text or len(transcript_text) < 50:
        return None
    
    prompt = f"""
شما یک خبرنگار حرفه‌ای هستید. متن زیر، Transcript (زیرنویس رسمی) یک ویدیوی خبری است که به همراه تایم‌استمپ هر بخش آمده است.

متن Transcript با تایم‌استمپ:
{transcript_text[:15000]}

وظیفه شما:
۱. متن را به بخش‌های جداگانه تقسیم کنید (هر خبر یا موضوع جداگانه یک بخش)
۲. برای هر بخش، از اولین تایم‌استمپ همان بخش استفاده کنید
۳. خلاصه‌ای کوتاه و مفید (حداکثر ۱-۲ خط) از هر بخش بنویسید
۴. خروجی را دقیقاً به این شکل بنویسید:

[تایم‌استمپ] خلاصه خبر

مثال:
[00:00] افزایش قیمت دلار و تاثیر آن بر بازار
[02:15] اعلام نتایج جدیدترین نظرسنجی‌ها
[04:30] تصویب لایحه جدید در مجلس

توجه بسیار مهم:
- تایم‌استمپ‌ها را از خودتان نسازید
- فقط از تایم‌استمپ‌هایی که در متن Transcript وجود دارد استفاده کنید
- هر جا موضوع عوض شد، از اولین تایم‌استمپ همان بخش استفاده کنید
- هیچ تایم‌استمپ جدیدی نسازید
- تایم‌استمپ‌ها را دقیقاً به فرمت [MM:SS] بنویسید
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
        # ۱. ساخت متن پیام
        caption = f"📺 <b>{title}</b>\n\n━━━━━━━━━━━━━━━━\n{summary}\n━━━━━━━━━━━━━━━━\n🔗 {video_url}"
        
        # ۲. ارسال با عکس
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        
        # اگه خلاصه خیلی طولانی بود، به چند بخش تقسیم کن
        if len(caption) > 4000:
            # فقط خلاصه رو تقسیم کن
            parts = [caption[i:i+4000] for i in range(0, len(caption), 4000)]
            
            # بخش اول با عکس
            payload = {
                'chat_id': TELEGRAM_CHAT_ID,
                'photo': thumbnail_url,
                'caption': parts[0],
                'parse_mode': 'HTML'
            }
            requests.post(url, json=payload)
            
            # بخش‌های بعدی بدون عکس
            for part in parts[1:]:
                send_to_telegram_text(part)
        else:
            # ارسال یکجا با عکس
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
        # اگه Transcript نداشت، فقط لینک رو بفرست
        msg = f"📺 <b>{title}</b>\n\n⚠️ این ویدیو Transcript ندارد.\n🔗 https://youtu.be/{video_id}"
        send_to_telegram_with_photo(title, thumbnail, "⚠️ این ویدیو Transcript ندارد.", f"https://youtu.be/{video_id}")
        with open(processed_file, 'a') as f:
            f.write(f"{video_id}\n")
        return
    
    # ۴. تبدیل به متن با تایم‌استمپ
    transcript_text = format_transcript_with_timestamps(transcript)
    print(f"Transcript گرفته شد: {len(transcript_text)} کاراکتر با تایم‌استمپ")
    
    # ۵. خلاصه‌سازی
    summary = summarize_with_gemini(transcript_text)
    if not summary:
        msg = f"📺 <b>{title}</b>\n\n❌ خطا در خلاصه‌سازی\n🔗 https://youtu.be/{video_id}"
        send_to_telegram_with_photo(title, thumbnail, "❌ خطا در خلاصه‌سازی", f"https://youtu.be/{video_id}")
        return
    
    # ۶. ارسال به تلگرام با عکس
    video_url = f"https://youtu.be/{video_id}"
    send_to_telegram_with_photo(title, thumbnail, summary, video_url)
    
    # ۷. ذخیره آی‌دی ویدیو
    with open(processed_file, 'a') as f:
        f.write(f"{video_id}\n")
    
    print("پردازش کامل شد!")

if __name__ == "__main__":
    main()
