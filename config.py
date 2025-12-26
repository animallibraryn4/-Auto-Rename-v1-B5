import re, os, time
from os import environ, getenv
id_pattern = re.compile(r'^.\d+$') 


class Config(object):
    # pyro client config
    API_ID    = os.environ.get("API_ID", "22299340")
    API_HASH  = os.environ.get("API_HASH", "")
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "") 

    # database config
    DB_NAME = os.environ.get("DB_NAME","mikota4432")     
    DB_URL  = os.environ.get("DB_URL","mongodb+srv://mikota4432:jkJDQuZH6o8pxxZe@cluster0.2vngilq.mongodb.net/?retryWrites=true&w=majority")
    PORT = os.environ.get("PORT", "9090")
 
    # other configs
    BOT_UPTIME  = time.time()
    START_PIC   = os.environ.get("START_PIC", "https://images8.alphacoders.com/138/1384114.png")
    ADMIN       = [int(admin) if id_pattern.search(admin) else admin for admin in os.environ.get('ADMIN', '5380609667').split()]
    FORCE_SUB_CHANNELS = os.environ.get('FORCE_SUB_CHANNELS', 'animelibraryn4').split(',')
    LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", "-1002263636517"))
    DUMP_CHANNEL = int(os.environ.get("DUMP_CHANNEL", "-1002263636517"))
    WEBHOOK = bool(os.environ.get("WEBHOOK", "True"))
    
    # Season Extraction Configuration (New)
    # Agar aap season extraction ke liye koi custom placeholder ya default value set karna chahte hain,
    # to yahan add kar sakte hain.
    SEASON_PLACEHOLDER = "{season}"  # Yeh placeholder aapke auto rename format mein replace hoga.


class Txt(object):
    # part of text configuration
        
    START_TXT = """👋 ʜᴇʏ, {}!  

🚀FEATURES:  
✅ ᴀᴜᴛᴏ ʀᴇɴᴀᴍᴇ ꜰɪʟᴇꜱ
✅ ᴄᴜꜱᴛᴏᴍ ᴛʜᴜᴍʙɴᴀɪʟ & ᴄᴀᴘᴛɪᴏɴ
✅ ᴍᴇᴛᴀᴅᴀᴛᴀ ᴇᴅɪᴛ & ᴠɪᴅᴇᴏ ⇄ ꜰɪʟᴇ ᴄᴏɴᴠᴇʀꜱɪᴏɴ

💡 ᴜꜱᴇ /tutorial ᴛᴏ ɢᴇᴛ ꜱᴛᴀʀᴛᴇᴅ!  

🤖 ᴘᴏᴡᴇʀᴇᴅ ʙʏ @animelibraryn4"""

    FILE_NAME_TXT = """<b><pre>»sᴇᴛᴜᴘ ᴀᴜᴛᴏ ʀᴇɴᴀᴍᴇ ғᴏʀᴍᴀᴛ</pre></b>

<b>ᴠᴀʀɪᴀʙʟᴇꜱ :</b>
➲ EP[EP.NUM] - ᴛᴏ ʀᴇᴘʟᴀᴄᴇ ᴇᴘɪꜱᴏᴅᴇ ɴᴜᴍʙᴇʀ  
➲ S[SE.NUM] - ᴛᴏ ʀᴇᴘʟᴀᴄᴇ ꜱᴇᴀꜱᴏɴ ɴᴜᴍʙᴇʀ  
➲ [QUALITY] - ᴛᴏ ʀᴇᴘʟᴀᴄᴇ ǫᴜᴀʟɪᴛʏ

<b>‣ ꜰᴏʀ ᴇx:- </b> <code>  /autorename [S[SE.NUM]-E[EP.NUM]] Pokemon [[QUALITY]] [Dual] @Animelibraryn4 | @onlyfans_n4</code>

<b>‣ /Autorename: ʀᴇɴᴀᴍᴇ ʏᴏᴜʀ ᴍᴇᴅɪᴀ ꜰɪʟᴇs ʙʏ ɪɴᴄʟᴜᴅɪɴɢ 'ᴇᴘɪꜱᴏᴅᴇ', 'ꜱᴇᴀꜱᴏɴ' ᴀɴᴅ 'ǫᴜᴀʟɪᴛʏ' ᴠᴀʀɪᴀʙʟᴇꜱ ɪɴ ʏᴏᴜʀ ᴛᴇxᴛ, ᴛᴏ ᴇxᴛʀᴀᴄᴛ ᴇᴘɪꜱᴏᴅᴇ, ꜱᴇᴀꜱᴏɴ ᴀɴᴅ ǫᴜᴀʟɪᴛʏ ᴘʀᴇꜱᴇɴᴛ ɪɴ ᴛʜᴇ ᴏʀɪɢɪɴᴀʟ ꜰɪʟᴇɴᴀᴍᴇ. """
    
    ABOUT_TXT = f"""<b>❍ ᴍʏ ɴᴀᴍᴇ : <a href="https://t.me/animelibraryn4">ᴀᴜᴛᴏ ʀᴇɴᴀᴍᴇ</a>
❍ ᴅᴇᴠᴇʟᴏᴩᴇʀ : <a href="https://t.me/animelibraryn4">ᴀɴɪᴍᴇ ʟɪʙʀᴀʀʏ ɴ4</a>
❍ ɢɪᴛʜᴜʙ : <a href="https://t.me/animelibraryn4">ᴀɴɪᴍᴇ ʟɪʙʀᴀʀʏ ɴ4</a>
❍ ʟᴀɴɢᴜᴀɢᴇ : <a href="https://www.python.org/">ᴘʏᴛʜᴏɴ</a>
❍ ᴅᴀᴛᴀʙᴀꜱᴇ : <a href="https://www.mongodb.com/">ᴍᴏɴɢᴏ ᴅʙ</a>
❍ ʜᴏꜱᴛᴇᴅ ᴏɴ : <a href="https://t.me/animelibraryn4">ᴠᴘs</a>
❍ ᴍᴀɪɴ ᴄʜᴀɴɴᴇʟ : <a href="https://t.me/animelibraryn4">ᴀɴɪᴍᴇ ʟɪʙʀᴀʀʏ ɴ4</a>"""

    
    THUMBNAIL_TXT = """<b><pre>»ᴛʜᴜᴍʙɴᴀɪʟ ᴍᴀɴᴀɢᴇʀ</pre></b>

➲ /smart_thumb: ᴏᴘᴇɴ ᴀ ᴍᴇɴᴜ ᴛᴏ ꜱᴇᴛ, ᴠɪᴇᴡ, ᴏʀ ᴅᴇʟᴇᴛᴇ ᴛʜᴜᴍʙɴᴀɪʟꜱ ꜰᴏʀ ᴇᴀᴄʜ ᴠɪᴅᴇᴏ ǫᴜᴀʟɪᴛʏ (360p, 480p, 720p, 1080p, 2K, 4K, etc).

➲ ꜱᴇɴᴅ ᴀ ᴘʜᴏᴛᴏ ᴀꜰᴛᴇʀ ᴄʜᴏᴏꜱɪɴɢ ǫᴜᴀʟɪᴛʏ ᴛᴏ ꜱᴀᴠᴇ ɪᴛ ᴀꜱ ᴀ ᴛʜᴜᴍʙɴᴀɪʟ.
➲ ᴜꜱᴇ ʙᴜᴛᴛᴏɴꜱ ᴛᴏ 👀 ᴠɪᴇᴡ, 🖼️ ꜱᴇᴛ ɴᴇᴡ, ᴏʀ 🗑 ᴅᴇʟᴇᴛᴇ ᴛʜᴜᴍʙꜱ.
➲ ʏᴏᴜ ᴄᴀɴ ᴀʟꜱᴏ ᴅᴇʟᴇᴛᴇ ᴀʟʟ ᴛʜᴜᴍʙɴᴀɪʟꜱ ᴀᴛ ᴏɴᴄᴇ.

ɴᴏᴛᴇ: ɪꜰ ɴᴏ ꜱᴘᴇᴄɪꜰɪᴄ ǫᴜᴀʟɪᴛʏ ᴛʜᴜᴍʙɴᴀɪʟ ɪꜱ ꜱᴇᴛ, ᴏʀɪɢɪɴᴀʟ ꜰɪʟᴇ'ꜱ ᴛʜᴜᴍʙɴᴀɪʟ ᴡɪʟʟ ʙᴇ ᴜꜱᴇᴅ ʙʏ ᴅᴇꜰᴀᴜʟᴛ.
"""
    
    CAPTION_TXT = """<b><pre>»ᴛᴏ ꜱᴇᴛ ᴄᴜꜱᴛᴏᴍ ᴄᴀᴘᴛɪᴏɴ ᴀɴᴅ ᴍᴇᴅɪᴀ ᴛʏᴘᴇ</pre></b>
    
<b>ᴠᴀʀɪᴀʙʟᴇꜱ :</b>         
ꜱɪᴢᴇ: {ꜰɪʟᴇꜱɪᴢᴇ}
ᴅᴜʀᴀᴛɪᴏɴ: {duration}
ꜰɪʟᴇɴᴀᴍᴇ: {ꜰɪʟᴇɴᴀᴍᴇ}

➲ /set_caption: ᴛᴏ ꜱᴇᴛ ᴀ ᴄᴜꜱᴛᴏᴍ ᴄᴀᴘᴛɪᴏɴ.
➲ /see_caption: ᴛᴏ ᴠɪᴇᴡ ʏᴏᴜʀ ᴄᴜꜱᴛᴏᴍ ᴄᴀᴘᴛɪᴏɴ.
➲ /del_caption: ᴛᴏ ᴅᴇʟᴇᴛᴇ ʏᴏᴜʀ ᴄᴜꜱᴛᴏᴍ ᴄᴀᴘᴛɪᴏɴ.

» ꜰᴏʀ ᴇx:- /set_caption ꜰɪʟᴇ ɴᴀᴍᴇ: {ꜰɪʟᴇɴᴀᴍᴇ}"""

    PROGRESS_BAR = """\n
<b>» Size</b> : {1} | {2}
<b>» Done</b> : {0}%
<b>» Speed</b> : {3}/s
<b>» ETA</b> : {4} """
    
    
    DONATE_TXT = """<blockquote> ᴛʜᴀɴᴋs ғᴏʀ sʜᴏᴡɪɴɢ ɪɴᴛᴇʀᴇsᴛ ɪɴ ᴅᴏɴᴀᴛɪᴏɴ</blockquote>

<b><i>💞  ɪꜰ ʏᴏᴜ ʟɪᴋᴇ ᴏᴜʀ ʙᴏᴛ ꜰᴇᴇʟ ꜰʀᴇᴇ ᴛᴏ ᴅᴏɴᴀᴛᴇ ᴀɴʏ ᴀᴍᴏᴜɴᴛ ₹𝟷𝟶, ₹𝟸𝟶, ₹𝟻𝟶, ₹𝟷𝟶𝟶, ᴇᴛᴄ.</i></b>

ᴅᴏɴᴀᴛɪᴏɴs ᴀʀᴇ ʀᴇᴀʟʟʏ ᴀᴘᴘʀᴇᴄɪᴀᴛᴇᴅ ɪᴛ ʜᴇʟᴘs ɪɴ ʙᴏᴛ ᴅᴇᴠᴇʟᴏᴘᴍᴇɴᴛ

 <u>ʏᴏᴜ ᴄᴀɴ ᴀʟsᴏ ᴅᴏɴᴀᴛᴇ ᴛʜʀᴏᴜɢʜ ᴜᴘɪ</u>

 ᴜᴘɪ ɪᴅ : <code>@fam</code>

ɪғ ʏᴏᴜ ᴡɪsʜ ʏᴏᴜ ᴄᴀɴ sᴇɴᴅ ᴜs ss
ᴏɴ - """

    PREMIUM_TXT = """<b>ᴜᴘɢʀᴀᴅᴇ ᴛᴏ ᴏᴜʀ ᴘʀᴇᴍɪᴜᴍ sᴇʀᴠɪᴄᴇ ᴀɴᴅ ᴇɴJᴏʏ ᴇxᴄʟᴜsɪᴠᴇ ғᴇᴀᴛᴜʀᴇs:
○ ᴜɴʟɪᴍɪᴛᴇᴅ Rᴇɴᴀᴍɪɴɢ: ʀᴇɴᴀᴍᴇ ᴀs ᴍᴀɴʏ ғɪʟᴇs ᴀs ʏᴏᴜ ᴡᴀɴᴛ ᴡɪᴛʜᴏᴜᴛ ᴀɴʏ ʀᴇsᴛʀɪᴄᴛɪᴏɴs.
○ ᴇᴀʀʟʏ Aᴄᴄᴇss: ʙᴇ ᴛʜᴇ ғɪʀsᴛ ᴛᴏ ᴛᴇsᴛ ᴀɴᴅ ᴜsᴇ ᴏᴜʀ ʟᴀᴛᴇsᴛ ғᴇᴀᴛᴜʀᴇs ʙᴇғᴏʀᴇ ᴀɴʏᴏɴᴇ ᴇʟsᴇ.

• ᴜꜱᴇ /plan ᴛᴏ ꜱᴇᴇ ᴀʟʟ ᴏᴜʀ ᴘʟᴀɴꜱ ᴀᴛ ᴏɴᴄᴇ.

➲ ғɪʀsᴛ sᴛᴇᴘ : ᴘᴀʏ ᴛʜᴇ ᴀᴍᴏᴜɴᴛ ᴀᴄᴄᴏʀᴅɪɴɢ ᴛᴏ ʏᴏᴜʀ ғᴀᴠᴏʀɪᴛᴇ ᴘʟᴀɴ ᴛᴏ ᴛʜɪs rohit162@fam ᴜᴘɪ ɪᴅ.

➲ secoɴᴅ sᴛᴇᴘ : ᴛᴀᴋᴇ ᴀ sᴄʀᴇᴇɴsʜᴏᴛ ᴏғ ʏᴏᴜʀ ᴘᴀʏᴍᴇɴᴛ ᴀɴᴅ sʜᴀʀᴇ ɪᴛ ᴅɪʀᴇᴄᴛʟʏ ʜᴇʀᴇ: @sewxiy 

➲ ᴀʟᴛᴇʀɴᴀᴛɪᴠᴇ sᴛᴇᴘ : ᴏʀ ᴜᴘʟᴏᴀᴅ ᴛʜᴇ sᴄʀᴇᴇɴsʜᴏᴛ ʜᴇʀᴇ ᴀɴᴅ ʀᴇᴘʟʏ ᴡɪᴛʜ ᴛʜᴇ /bought ᴄᴏᴍᴍᴀɴᴅ.

Yᴏᴜʀ ᴘʀᴇᴍɪᴜᴍ ᴘʟᴀɴ ᴡɪʟʟ ʙᴇ ᴀᴄᴛɪᴠᴀᴛᴇᴅ ᴀғᴛᴇʀ ᴠᴇʀɪғɪᴄᴀᴛɪᴏɴ</b>"""

    PREPLANS_TXT = """<b><pre>🎖️ᴀᴠᴀɪʟᴀʙʟᴇ ᴘʟᴀɴs:</pre>

Pʀɪᴄɪɴɢ:
➜ ᴍᴏɴᴛʜʟʏ ᴘʀᴇᴍɪᴜᴍ: ₹109/ᴍᴏɴᴛʜ
➜ ᴅᴀɪʟʏ ᴘʀᴇᴍɪᴜᴍ: ₹19/ᴅᴀʏ
➜ ᴄᴏɴᴛᴀᴄᴛ: @Anime_Library_N4

➲ ᴜᴘɪ ɪᴅ - <code>@</code>

‼️ᴜᴘʟᴏᴀᴅ ᴛʜᴇ ᴘᴀʏᴍᴇɴᴛ sᴄʀᴇᴇɴsʜᴏᴛ ʜᴇʀᴇ ᴀɴᴅ ʀᴇᴘʟʏ ᴡɪᴛʜ ᴛʜᴇ /bought ᴄᴏᴍᴍᴀɴᴅ.</b>"""
    
    HELP_TXT = """ʜᴇʀᴇ ɪꜱ ʜᴇʟᴘ ᴍᴇɴᴜ ɪᴍᴘᴏʀᴛᴀɴᴛ ᴄᴏᴍᴍᴀɴᴅꜱ:

ᴀᴡᴇsᴏᴍᴇ ғᴇᴀᴛᴜʀᴇs🫧

ʀᴇɴᴀᴍᴇ ʙᴏᴛ ɪꜱ ᴀ ʜᴀɴᴅʏ ᴛᴏᴏʟ ᴛʜᴀᴛ ʜᴇʟᴘꜱ ʏᴏᴜ ʀᴇɴᴀᴍᴇ ᴀɴᴅ ᴍᴀɴᴀɢᴇ ʏᴏᴜʀ ꜰɪʟᴇs ᴇꜰꜰᴏʀᴛʟᴇꜱꜱʟʏ.

➲ /Autorename: ᴀᴜᴛᴏ ʀᴇɴᴀᴍᴇ ʏᴏᴜʀ ꜰɪʟᴇs.
➲ /Metadata: ᴄᴏɱᴍᴀɴᴅꜱ ᴛᴏ ᴛᴜʀɴ ᴏɴ ᴏғғ ᴍᴇᴛᴀᴅᴀᴛᴀ.
➲ /smart_thumb: ᴏᴘᴇɴ ᴀ ᴍᴇɴᴜ ᴛᴏ ꜱᴇᴛ, ᴠɪᴇᴡ, ᴏʀ ᴅᴇʟᴇᴛᴇ ᴛʜᴜᴍʙɴᴀɪʟꜱ ꜰᴏʀ ᴇᴀᴄʜ ᴠɪᴅᴇᴏ ǫᴜᴀʟɪᴛʏ (360p, 480p, 720p, 1080p, 2K, 4K, etc).
➲ /get_token: ɢᴇᴛ ᴀ ᴛᴏᴋᴇɴ ᴛᴏ ᴠᴇʀɪғʏ ʏᴏᴜʀsᴇʟғ ᴀɴᴅ ᴜsᴇ ᴛʜᴇ ʙᴏᴛ ᴡɪᴛʜᴏᴜᴛ ʀᴇsᴛʀɪᴄᴛɪᴏɴs."""

    SEND_METADATA = """
<b><pre>Metadata Settings:</pre></b>

➜ /metadata: Turn on or off metadata.

<b>Description</b> : Metadata will change MKV video files including all audio, streams, and subtitle titles."""


    SOURCE_TXT = """
<b>ʜᴇʏ,
 ᴛʜɪs ɪs ᴀᴜᴛᴏ ʀᴇɴᴀᴍᴇ ʙᴏᴛ,
ᴀ ᴘʀɪᴠᴀᴛᴇ ᴛᴇʟᴇɢʀᴀᴍ ᴀᴜᴛᴏ ʀᴇɴᴀᴍᴇ ʙᴏᴛ.</b>"""

    META_TXT = """
**ᴍᴀɴᴀɢɪɴɢ ᴍᴇᴛᴀᴅᴀᴛᴀ ғᴏʀ ʏᴏᴜʀ ᴠɪᴅᴇᴏs ᴀɴᴅ ғɪʟᴇs**

**ᴠᴀʀɪᴏᴜꜱ ᴍᴇᴛᴀᴅᴀᴛᴀ:**

- **ᴛɪᴛʟᴇ**: Descriptive title of the media.
- **ᴀᴜᴛʜᴏʀ**: The creator or owner of the media.
- **ᴀʀᴛɪꜱᴛ**: The artist associated with the media.
- **ᴀᴜᴅɪᴏ**: Title or description of audio content.
- **ꜱᴜʙᴛɪᴛʟᴇ**: Title of subtitle content.
- **ᴠɪᴅᴇᴏ**: Title or description of video content.

**ᴄᴏᴍᴍᴀɴᴅꜱ ᴛᴏ ᴛᴜʀɴ ᴏɴ ᴏғғ ᴍᴇᴛᴀᴅᴀᴛᴀ:**
➜ /metadata: Turn on or off metadata.

**ᴄᴏᴍᴍᴀɴᴅꜱ ᴛᴏ ꜱᴇᴛ ᴍᴇᴛᴀᴅᴀᴛᴀ:**

➜ /settitle: Set a custom title of media.
➜ /setauthor: Set the author.
➜ /setartist: Set the artist.
➜ /setaudio: Set audio title.
➜ /setsubtitle: Set subtitle title.
➜ /setvideo: Set video title.

**ᴇxᴀᴍᴘʟᴇ:** /settitle Your Title Here

**ᴜꜱᴇ ᴛʜᴇꜱᴇ ᴄᴏᴍᴍᴀɴᴅꜱ ᴛᴏ ᴇɴʀɪᴄʜ ʏᴏᴜʀ ᴍᴇᴅɪᴀ ᴡɪᴛʜ ᴀᴅᴅɪᴛɪᴏɴᴀʟ ᴍᴇᴛᴀᴅᴀᴛᴀ ɪɴꜰᴏʀᴍᴀᴛɪᴏɴ!**
"""

    PLAN_MAIN_TXT = "<b>👋 Hey, {}!\n\nSelect a plan that suits your needs from the options below:</b>"
    
    FREE_TXT = "🆓 Free Trial\n⏰ 1 hour access\n💸 Plan price ➛ Free\n\n➛ Limited-time access to test the service\n➛ Perfect to check speed and features\n➛ No payment required"
    
    BASIC_TXT = "🟢 Basic Pass\n⏰ 7 days\n💸 Plan price ➛ ₹39\n\n➛ Suitable for light and short-term users\n➛ Full access during active period\n➛ Budget-friendly weekly plan\n➛ Check your active plan: /myplan"
    
    LITE_TXT = "🔵 Lite Plan\n⏰ 15 days\n💸 Plan price ➛ ₹79\n\n➛ Best choice for regular users\n➛ More value compared to weekly plan\n➛ Smooth and uninterrupted access\n➛ Recommended for consistent usage"
    
    STANDARD_TXT = "⭐ Standard Plan\n⏰ 30 days\n💸 Plan price ➛ ₹129\n\n➛ Most popular plan\n➛ Best balance of price and duration\n➛ Ideal for daily and long-term users\n➛ ⭐ Best for regular users"
    
    PRO_TXT = "💎 Pro Plan\n⏰ 50 days\n💸 Plan price ➛ ₹199\n\n➛ Maximum savings for long-term users\n➛ Hassle-free extended access\n➛ Best value plan for power users\n➛ 💎 Long-term recommended"
    
    ULTRA_TXT = "👑 Ultra Plan\n⏰ Coming soon\n💸 Price ➛ TBA\n\n➛ Premium and exclusive access\n➛ Extra benefits and features\n➛ Designed for hardcore users\n➛ Stay tuned for launch 👀"

    SELECT_PAYMENT_TXT = "<b>Select Your Payment Method</b>"
    
    UPI_TXT = "👋 Hey {},\n\nPay the amount according to your selected plan and enjoy plan membership!\n\n💵 <b>UPI ID:</b> <code>dm @PYato</code>\n\n‼️ You must send a screenshot after payment."
    
    QR_TXT = "👋 Hey {},\n\nPay the amount according to your membership price!\n\n📸 <b>QR Code:</b> <a href='https://t.me/Animelibraryn4'>Click here to scan</a>\n\n‼️ You must send a screenshot after payment."
    
# Add to Txt class in config.py:
    MERGE_HELP_TXT = """🔧 **Audio/Subtitle Merger Tool**

**Command:** /merging

**How to use:**
1. Type `/merging` to start
2. Send source files (with audio/subtitles to extract)
3. Type `/done_sources` when finished
4. Send target files (to add tracks to)
5. Type `/done_targets` to start merging

**Features:**
• No re-encoding (file size preserved)
• Original filenames maintained
• Episode-by-episode matching
• Multiple audio/subtitle tracks supported

**Commands:**
• `/merging` - Start merging session
• `/cancel_merge` - Cancel current session
• `/done_sources` - Finish sending source files
• `/done_targets` - Finish sending target files"""
