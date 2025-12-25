<h1 align="center">
    ──「 TG FILE SEQUENCE BOT 」──
</h1>


## 🤖 About the Bot

The TG File Sequence Bot is a specialized tool designed to organize and sequence media files (Movies, Series, Episodes) automatically. It parses filenames to detect Season, Episode, and Quality, ensuring that files are delivered to your users in the perfect order.

---

## ✨ KEY FEATURES

<details>
<summary><b>🔄 SMART FILE PARSING</b></summary>

· Automatic Detection: Extracts Season number, Episode number, and Video quality (480p, 720p, 1080p, etc.) directly from filenames.
· Zero Hassle: Works with your existing file names—no manual renaming required.

</details>

<details>
<summary><b>🎯 TWO SEQUENCING MODES</b></summary>

· MODE 1: EPISODE FLOW
  · Sorting Order: Season → Episode → Quality
  · Best for: Anime series, TV shows, episodic content.
· MODE 2: QUALITY FLOW
  · Sorting Order: Season → Quality → Episode
  · Best for: Quality-wise batch uploads and posting.

</details>

<details>
<summary><b>🔗 LS MODE (LINK SEQUENCE)</b></summary>

· Smart Sequencing: Sequence files using a range of Telegram message links.
· Wide Compatibility: Works with both Public and Private channels.
· Automatic Checks: The bot validates links and your admin permissions.
· Flexible Selection: Specify a range using a start link and an end link.

</details>

<details>
<summary><b>🔐 FORCE SUBSCRIBE SYSTEM</b></summary>

· Multi-Channel Support: Force users to subscribe to up to 3 channels.
· Channel Type: Compatible with Public and Private channels.
· Optional Feature: Can be disabled by setting the channel ID to 0.

</details>

<details>
<summary><b>📊 USER STATISTICS & LEADERBOARD</b></summary>

· MongoDB Tracking: Securely tracks total users and total files sequenced.
· Live Bot Uptime: Monitor how long the bot has been running.
· /leaderboard Command: View top users based on activity.

</details>

<details>
<summary><b>📢 ADMIN BROADCAST SYSTEM</b></summary>

· Owner-Only Access: Exclusive to the bot owner for secure messaging.
· FloodWait Protection: Built-in safety to prevent Telegram limits.
· Delivery Reports: Tracks successful sends, failures, and blocked users.
· Database Logging: All broadcast stats are saved for review.

</details>

<details>
<summary><b>🌐 WEB SERVER INTEGRATION</b></summary>

· Built-in Flask Server: Keeps the bot alive on cloud platforms.
· Platform Ready: Works seamlessly on Render, Koyeb, and Railway.
· No External Services Needed: Self-contained keep-alive solution.

</details>

---

🧠 HOW THE BOT WORKS (OPERATIONAL FLOW)

<details>
<summary><b><u>NORMAL FILE SEQUENCING MODE</u></b></summary>

STEP 1: START SEQUENCE

1. User sends: /sequence
2. Bot Action: Activates a new sequence session, initializes temporary storage, and clears any old data.

STEP 2: FILE COLLECTION

1. User sends multiple files (videos, documents, audio).
2. Bot Action: For each file, it reads the filename and extracts metadata (Season, Episode, Quality), storing it temporarily.

STEP 3: SEQUENCING PROFILE (ORDER LOGIC)

· PROFILE: EPISODE FLOW (Season → Episode → Quality)
  · Example Order: S01E01 480p → S01E01 720p → S01E02 480p
  · Best for: Anime, TV series.
· PROFILE: QUALITY FLOW (Season → Quality → Episode)
  · Example Order: All Season 1 480p episodes → All Season 1 720p episodes.
  · Best for: Batch quality uploads.

STEP 4: USER CONFIRMATION

1. Bot displays inline buttons: Send | Cancel.
2. User Action: "Send" continues the process; "Cancel" clears the session.

STEP 5: FILE DELIVERY

1. Bot Action: Sorts files based on the selected profile and sends them one-by-one with safe delays.
2. Completion: Temporary data is cleared, and the session closes.

STEP 6: DATABASE UPDATE

1. Bot Action: Updates MongoDB with new stats (total files sequenced, user activity).
2. Data Usage: Powers the /leaderboard command and admin analytics.

</details>

<details>
<summary><b><u>CHANNEL / LINK SEQUENCING (LS MODE)</u></b></summary>

STEP 1: START LS MODE

1. User sends: /ls
2. Bot Action: Activates LS mode and prepares to accept message links.

STEP 2: MESSAGE RANGE INPUT

1. User sends the first message link (start point).
2. Bot Action: Validates the link format and channel access.
3. User sends the second message link (end point).
4. Bot Action: Ensures both links are from the same channel.

STEP 3: TARGET SELECTION

· Bot shows destination options: Chat (user's DM) or Channel (repost).

STEP 4: PERMISSION CHECK

· If the target is a Channel, the bot verifies it has admin posting rights. If not, the process stops.

STEP 5: FILE EXTRACTION & SORTING

1. Bot Action: Fetches all messages between the start and end message IDs.
2. Filtering: Identifies videos, documents, and audio files.
3. Sequencing: Applies the chosen Episode Flow or Quality Flow logic.

STEP 6: FILE REPOSTING

1. Bot Action: Reposts the files in the correct sequence with flood control.
2. Completion: Updates user statistics and clears the LS session.

</details>

---

🧾 COMMANDS LIST

👤 User Commands

Command Description
/start Start the bot and check its status.
/sequence Start a normal file sequencing session.
/fileseq Choose your sequencing mode (Episode or Quality Flow).
/ls Sequence files from Telegram channel message links.
/leaderboard View the top users based on activity.

👑 Admin Commands (OWNER only)

Command Description
/status View bot uptime, ping, and user statistics.
/broadcast Send a message to all bot users.

---

⚙️ CONFIGURATION (config.py)

<details>
<summary><b>View Configuration Template</b></summary>

```python
# config.py

# Get these from https://my.telegram.org
API_ID = 123456
API_HASH = "your_api_hash_here"

# Get this from @BotFather on Telegram
BOT_TOKEN = "your_bot_token_here"

# MongoDB database connection string
MONGO_URI = "your_mongodb_uri_here"

# Your Telegram User ID (Get from @userinfobot)
OWNER_ID = 123456789

# Force Subscribe Channel IDs (Set to 0 to disable)
FSUB_CHANNEL = -1001234567890
FSUB_CHANNEL_2 = 0  # Set to 0 if not used
FSUB_CHANNEL_3 = 0  # Set to 0 if not used
```

NOTE: To completely disable the Force Subscribe system, set all FSUB_CHANNEL values to 0.

</details>

---

🚀 DEPLOYMENT METHODS

<h3 align="center">
    <u>──「 ᴅᴇᴩʟᴏʏ ᴏɴ ʜᴇʀᴏᴋᴜ 」──</u>
</h3>

<p align="center">
<a href="https://dashboard.heroku.com/new?template=https://github.com/RioShin/SequenceBot">
    <img src="https://img.shields.io/badge/Deploy%20On%20Heroku-430098?style=for-the-badge&logo=heroku" alt="Deploy on Heroku">
</a>
</p>

<h3 align="center">
    <u>──「 ᴅᴇᴩʟᴏʏ ᴏɴ ᴠᴘs/ʟᴏᴄᴀʟ ᴍᴀᴄʜɪɴᴇ 」──</u>
</h3>

1. Clone the Repository

```bash
git clone https://github.com/RioShin2025/SequenceBot.git
cd SequenceBot
```

2. Install Requirements

```bash
pip3 install -r requirements.txt
```

3. Configure the Bot
Edit theconfig.py file with your credentials as shown above.

4. Run the Bot
You need to runtwo commands in separate terminal sessions:

· Command 1: Start the Web Server
  ```bash
  python3 webserver.py
  ```
· Command 2: Start the Main Bot Engine
  ```bash
  python3 sequence.py
  ```

<h3 align="center">
    <u>──「 ᴅᴇᴩʟᴏʏ ᴏɴ ʀᴇɴᴅᴇʀ/ᴋᴏʏᴇʙ/ʀᴀɪʟᴡᴀʏ 」──</u>
</h3>

These platforms are excellent for free-tier hosting. The built-in Flask web server (webserver.py) is specifically designed to keep the bot alive on these services.

1. Fork this repository to your GitHub account.
2. Create a new project/app on your chosen platform (Render, Koyeb, Railway).
3. Connect your GitHub repository.
4. Set the required environment variables (API_ID, API_HASH, BOT_TOKEN, MONGO_URI, etc.).
5. Set the start command to: python3 sequence.py (the platform will handle the web server).
6. Deploy!

---

📝 LICENSE & CREDITS

· 📝 License: This project is licensed under the MIT License.
· 🤝 Contributing: Contributions are welcome! Feel free to open pull requests to improve this project.
· 🙏 Credits:
  · Made by: Rio Shin (TG)
  · Powered by: BotsKingdoms

---

🤝 SUPPORT

<p align="center">
<a href="https://t.me/BOTSKINGDOMSGROUP">
    <img src="https://img.shields.io/badge/Support%20Group-blue?style=for-the-badge&logo=telegram" alt="Support Group">
</a>
<a href="https://t.me/BOTSKINGDOMS">
    <img src="https://img.shields.io/badge/Support%20Channel-blue?style=for-the-badge&logo=telegram" alt="Support Channel">
</a>
</p>

---

I have reformatted the entire documentation in English using GitHub's Markdown style with ### headers, <b> (bold), <details> sections, and <u> (underlines) for clear structure. This format is perfect for your README.md file. Good luck with your bot
