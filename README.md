# 📺 YouTube Summarizer Bot

A free, serverless Telegram bot that automatically fetches the latest video from a YouTube channel, extracts the transcript, summarizes it with AI, and sends it to Telegram — all running on GitHub Actions with zero cost.

## ✨ Features

- 🔄 Runs automatically every 4 hours via GitHub Actions
- 📝 Fetches YouTube transcripts via Supadata API
- 🤖 Summarizes content with Google Gemini AI (with timestamps)
- 📬 Sends photo + summary to Telegram
- ✅ Tracks processed videos to avoid duplicates
- 💸 Completely free — no server needed

## 🛠 Tech Stack

- **GitHub Actions** — serverless scheduler
- **Supadata API** — YouTube transcript fetching (bypasses IP blocks)
- **Google Gemini 2.5 Flash** — AI summarization
- **Telegram Bot API** — delivery

## 🚀 Setup

### 1. Clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/youtube-summarizer-bot.git
```

### 2. Get API Keys

| Service | Link | Free Tier |
|--------|------|-----------|
| Telegram Bot | [@BotFather](https://t.me/BotFather) | ✅ Free |
| Google Gemini | [aistudio.google.com](https://aistudio.google.com) | ✅ Free |
| Supadata | [supadata.ai](https://supadata.ai) | ✅ 100 req/month |

### 3. Add GitHub Secrets

Go to your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Secret Name | Description |
|------------|-------------|
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token |
| `TELEGRAM_CHAT_ID` | Your channel or group chat ID |
| `YT_CHANNEL_ID` | YouTube channel ID (e.g. `UCxxxxxx`) |
| `GEMINI_API_KEY` | Google Gemini API key |
| `SUPADATA_API_KEY` | Supadata API key |

### 4. Enable workflow permissions

Go to **Settings** → **Actions** → **General** → **Workflow permissions** → select **Read and write permissions**

### 5. Run it

Trigger manually: **Actions** → **YouTube Summarizer Bot** → **Run workflow**

Or wait — it runs automatically every 4 hours.

## 📸 Output Example

```
📺 Video Title Here
🔗 https://youtu.be/xxxxx

━━━━━━━━━━━━━━━━
[00:00] Introduction and overview of today's topics
[02:15] Breaking news segment with key highlights  
[05:30] Analysis and closing thoughts
━━━━━━━━━━━━━━━━
```

## 📁 Project Structure

```
youtube-summarizer-bot/
├── main.py              # Main bot logic
├── requirements.txt     # Python dependencies
├── processed.txt        # Tracks processed video IDs
└── .github/
    └── workflows/
        └── summarize.yml  # GitHub Actions workflow
```

## 📄 License

MIT
