import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import json
import os
import time
from datetime import datetime, timezone, timedelta
from flask import Flask
from threading import Thread
import threading
import string
import random
from concurrent.futures import ThreadPoolExecutor

# 👇 NAYA FIX: Render deployment ke liye Dummy Server
# ==========================================
# ⚙️ CONFIGURATION & TOKENS
# ==========================================
TOKEN = '8706453784:AAEbIVcFv15JKjqzogg2sk7xHGzG2UAl5M8'
bot = telebot.TeleBot(TOKEN)

# Dono APIs alag alag set kar di hain
LIKE_API_URL = "https://like-api-mu-vert.vercel.app/like"
INFO_API_URL = "https://info-43yp.vercel.app/player-info"

# 👇 VPLINK SHORTENER SETUP 👇
VPLINK_API_KEY = "c98c6414ee95c040c319b79703888333fcf89435"
pending_likes = {} # Memory for tokens

# ==========================================
# ⚙️ SHORTLINK ON/OFF SWITCH
# ==========================================
# 🔴 Shortlink band karne ke liye: SHORTLINK_ENABLED = False
# 🟢 Shortlink wapas chalu karne ke liye: SHORTLINK_ENABLED = True  ← BAS YE EK LINE BADLO
SHORTLINK_ENABLED = False

# ==========================================
# ⚙️ DAILY LIMIT SYSTEM (RESETS AT 4 AM IST)
# ==========================================
IST = timezone(timedelta(hours=5, minutes=30))
# KEY = 'user_id:uid' — har user ke liye har UID pe alag limit
daily_like_usage = {}  # {'user_id:uid': datetime (IST)}

def get_ff_day_start():
    """Current Free Fire day start kab hua (4 AM IST)"""
    now_ist = datetime.now(IST)
    today_4am = now_ist.replace(hour=4, minute=0, second=0, microsecond=0)
    if now_ist >= today_4am:
        return today_4am
    else:
        return today_4am - timedelta(days=1)

def has_used_daily_like(user_id, uid):
    """Check karo ki user ne aaj is UID pe like bheja hai ya nahi"""
    key = f"{user_id}:{uid}"
    if key not in daily_like_usage:
        return False
    last_use = daily_like_usage[key]
    ff_day_start = get_ff_day_start()
    return last_use >= ff_day_start

def set_daily_like_used(user_id, uid):
    """User ka daily like us specific UID ke liye mark karo"""
    key = f"{user_id}:{uid}"
    daily_like_usage[key] = datetime.now(IST)

def get_next_reset_time():
    """Next 4 AM IST kitne baje hoga (text format mein)"""
    now_ist = datetime.now(IST)
    today_4am = now_ist.replace(hour=4, minute=0, second=0, microsecond=0)
    if now_ist >= today_4am:
        next_reset = today_4am + timedelta(days=1)
    else:
        next_reset = today_4am
    return next_reset.strftime("%d %B %Y at 4:00 AM IST")

# ==========================================
# ⚙️ MULTI-JOIN FORCE SUBSCRIBE SETUP
# ==========================================
GROUP_USERNAME = "@LikeBotFreeFireMax"
GROUP_CHAT_ID = "@LikeBotFreeFireMax"  # Group mein result bhejne ke liye
CHANNEL_1 = "@ROLEX857J" 
CHANNEL_2 = "@rolexlike" 

BOT_1_USERNAME = "@Rolex_KnowInfo_bot"
BOT_1_LINK = "https://t.me/Rolex_KnowInfo_bot"

BOT_2_USERNAME = "@RolexLike_bot"
BOT_2_LINK = "https://t.me/RolexLike_bot"

REQUIRED_CHATS = [GROUP_USERNAME, CHANNEL_1, CHANNEL_2]

# ==========================================
# ⚙️ SUPERFAST LIVE TEXT DATABASE SYSTEM
# ==========================================
USER_FILE = "verified_users.txt"
ALL_USERS_FILE = "all_users_bot.txt"
LEFT_USERS_FILE = "left_users_log.txt"

for file in [USER_FILE, ALL_USERS_FILE, LEFT_USERS_FILE]:
    if not os.path.exists(file):
        with open(file, "w") as f:
            pass

user_cooldowns = {}
user_locks = {}  # Per-user locks for concurrent processing
user_locks_mutex = threading.Lock()
like_executor = ThreadPoolExecutor(max_workers=10)  # 10 users ek sath handle honge

def get_user_lock(user_id):
    with user_locks_mutex:
        if user_id not in user_locks:
            user_locks[user_id] = threading.Lock()
        return user_locks[user_id]

def is_user_verified(user_id):
    with open(USER_FILE, "r") as f:
        users = f.read().splitlines()
    return str(user_id) in users

def add_verified_user(user_id):
    if not is_user_verified(user_id):
        with open(USER_FILE, "a") as f:
            f.write(f"{user_id}\n")

def remove_verified_user(user_id):
    if is_user_verified(user_id):
        with open(USER_FILE, "r") as f:
            users = f.read().splitlines()
        users.remove(str(user_id))
        with open(USER_FILE, "w") as f:
            f.write("\n".join(users) + "\n")

def log_active_user(user_id):
    with open(ALL_USERS_FILE, "r") as f:
        users = f.read().splitlines()
    if str(user_id) not in users:
        with open(ALL_USERS_FILE, "a") as f:
            f.write(f"{user_id}\n")

def log_left_user(user_id):
    with open(LEFT_USERS_FILE, "a") as f:
        f.write(f"{user_id} left at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

# ==========================================
# 🛑 LEAVE & BLOCK TRACKER (AUTO-REMOVE)
# ==========================================
@bot.message_handler(content_types=['left_chat_member'])
def handle_left_member(message):
    user_id = message.left_chat_member.id
    remove_verified_user(user_id)
    log_left_user(user_id)

@bot.message_handler(content_types=['new_chat_members'])
def handle_new_member(message):
    for member in message.new_chat_members:
        log_active_user(member.id)

@bot.my_chat_member_handler()
def handle_bot_block(message: telebot.types.ChatMemberUpdated):
    if message.new_chat_member.status in ['kicked', 'left']:
        remove_verified_user(message.from_user.id)
        log_left_user(message.from_user.id)

# ==========================================
# 🔥 FF RANK & STARS LOGIC
# ==========================================
def get_br_rank(rank_id, points):
    pts = int(points)
    r = str(rank_id)
    if pts >= 6000: return "Master"
    if pts >= 3200: return "Heroic"
    ranks = {
        "11": "Bronze I", "12": "Bronze II", "13": "Bronze III",
        "21": "Silver I", "22": "Silver II", "23": "Silver III",
        "31": "Gold I", "32": "Gold II", "33": "Gold III", "34": "Gold IV",
        "41": "Platinum I", "42": "Platinum II", "43": "Platinum III", "44": "Platinum IV", "45": "Platinum V",
        "51": "Diamond I", "52": "Diamond II", "53": "Diamond III", "54": "Diamond IV", "55": "Diamond V",
        "61": "Heroic", "62": "Elite Heroic",
        "71": "Master", "72": "Elite Master",
        "81": "Grandmaster I", "82": "Grandmaster II", "83": "Grandmaster III", "84": "Grandmaster IV", "85": "Grandmaster V",
        "321": "Diamond V", "322": "Diamond IV", "323": "Diamond III", "324": "Diamond II", "325": "Diamond I",
        "401": "Heroic", "402": "Elite Heroic", "501": "Master", "502": "Elite Master"
    }
    return ranks.get(r, f"Rank {r}")

def get_cs_rank(rank_id):
    r = str(rank_id)
    ranks = {
        "11": "Bronze I", "12": "Bronze II", "13": "Bronze III",
        "21": "Silver I", "22": "Silver II", "23": "Silver III",
        "31": "Gold I", "32": "Gold II", "33": "Gold III", "34": "Gold IV",
        "41": "Platinum I", "42": "Platinum II", "43": "Platinum III", "44": "Platinum IV", "45": "Platinum V",
        "51": "Diamond I", "52": "Diamond II", "53": "Diamond III", "54": "Diamond IV", "55": "Diamond V",
        "61": "Heroic", "62": "Elite Heroic",
        "71": "Master", "72": "Elite Master",
        "81": "Grandmaster I", "82": "Grandmaster II", "83": "Grandmaster III", "84": "Grandmaster IV", "85": "Grandmaster V",
        "91": "Grandmaster",
        "324": "Elite Master", "321": "Master", "311": "Heroic",
        "211": "Diamond I", "212": "Diamond II", "213": "Diamond III", "214": "Diamond IV"
    }
    return ranks.get(r, f"Rank {r}")

def get_cs_stars(rank_id, points):
    pts = int(points)
    r_id = int(rank_id)
    if r_id >= 311: return max(0, pts - 87)
    return pts

def fmt_t(ts):
    if ts and str(ts).isdigit():
        return datetime.fromtimestamp(int(ts)).strftime('%d %B %Y at %I:%M:%S %p')
    return "N/A"

# ==========================================
# 🛑 COMMON FORCE JOIN MESSAGE HELPER
# ==========================================
def send_force_join_msg(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    markup = InlineKeyboardMarkup()
    
    markup.row(InlineKeyboardButton("🌟 JOIN VIP GROUP 🌟", url=f"https://t.me/{GROUP_USERNAME.replace('@', '')}"))
    markup.row(InlineKeyboardButton("📢 Join Channel 1", url=f"https://t.me/{CHANNEL_1.replace('@', '')}"))
    markup.row(InlineKeyboardButton("📢 Join Channel 2", url=f"https://t.me/{CHANNEL_2.replace('@', '')}"))
    markup.row(InlineKeyboardButton(f"🤖 Bot 1 ({BOT_1_USERNAME})", url=BOT_1_LINK))
    markup.row(InlineKeyboardButton(f"🤖 Bot 2 ({BOT_2_USERNAME})", url=BOT_2_LINK))
    markup.row(InlineKeyboardButton("🔄 REFRESH / VERIFY 🔄", callback_data=f"verify_{user_id}"))

    hacker_look_warning = (
        f"🚫 **ACCESS DENIED** 🚫\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 **User:** {first_name}\n\n"
        f"⚠️ **PLEASE JOIN ALL CHANNELS/GROUPS TO USE THIS BOT!** ✨\n\n"
        f"DUE TO HEAVY OVERLOAD, ONLY SUBSCRIBERS CAN USE THIS PRIVATE VIP BOT! 😁\n\n"
        f"👇 **HOW TO UNLOCK:**\n"
        f"1️⃣ Join the VIP Group and *both* Channels above.\n"
        f"2️⃣ Start/Check the other bots.\n"
        f"3️⃣ Wapas aakar **'REFRESH / VERIFY'** dabao."
    )
    
    try:
        with open('2.png', 'rb') as photo:
            bot.send_photo(message.chat.id, photo, caption=hacker_look_warning, reply_markup=markup, parse_mode="Markdown")
    except FileNotFoundError:
        bot.reply_to(message, hacker_look_warning, reply_markup=markup, parse_mode="Markdown")

# ==========================================
# 🎮 VERIFICATION GATE (CHECKER)
# ==========================================
def check_join_status(user_id):
    not_joined_chats = []
    valid_statuses = ['creator', 'administrator', 'member', 'restricted']
    
    for chat in REQUIRED_CHATS:
        try:
            status = bot.get_chat_member(chat, user_id).status
            if status not in valid_statuses:
                not_joined_chats.append(chat)
        except Exception:
            not_joined_chats.append(chat)
            
    return not_joined_chats

# ==========================================
# 🔗 SHORTLINK MAKER MACHINE
# ==========================================
def get_shortlink(destination_url):
    api_url = f"https://vplink.in/api?api={VPLINK_API_KEY}&url={destination_url}"
    try:
        # Thoda timeout kam kiya hai speed badhane ke liye
        res = requests.get(api_url, timeout=5).json()
        if res.get("status") == "success":
            return res.get("shortenedUrl")
    except Exception as e:
        print("Shortlink Error:", e)
    return destination_url 

# ==========================================
# 🎮 COMMAND: /start (DEEP LINK & ANTI-BYPASS)
# ==========================================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    if message.chat.id < 0: return 
    
    user_id = message.from_user.id
    log_active_user(user_id)
    
    not_joined_chats = check_join_status(user_id)

    if not_joined_chats:
        remove_verified_user(user_id) 
        send_force_join_msg(message)
        return

    # 👇 NAYA: ANTI-BYPASS TIMER LOGIC (SAD FEELINGS) 👇
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("VPL_"):
        token = args[1]
        if token in pending_likes:
            data = pending_likes[token]
            if data['user_id'] == user_id:
                
                # Check kitna time laga user ko aane me
                time_taken = time.time() - data['timestamp']
                
                if time_taken < 120: # 120 SECONDS (2 MINUTES) KA LOGIC
                    bypass_warn = (
                        "🥺 *Bhai, ek chhoti si request hai...* 💔\n"
                        "━━━━━━━━━━━━━━━━━━\n"
                        "Hum bohot mehnat aur paise lagakar ye VIP bot aapke liye **FREE** chalate hain.\n"
                        "Aapne bypass bot use karke 2 minute se pehle hi link khol liya... 😔\n\n"
                        "Agar sab log bypass karenge, toh humein vplink se kuch nahi milega aur majbooran humein apna ye pyara bot hamesha ke liye **BAND** karna padega. 🚫\n\n"
                        "🙏 *Please bhai, agli baar se thoda waqt nikal kar imandaari se link verify karna. Hum aapke support ke bina aage nahi badh sakte.*\n\n"
                        "👉 Ek baar wapas `/like` lagao aur thoda time dekar ad dekh lo."
                    )
                    
                    try:
                        with open('bypass.mp4', 'rb') as video_file:
                            bot.send_video(message.chat.id, video=video_file, caption=bypass_warn, parse_mode="Markdown")
                    except FileNotFoundError:
                        bot.reply_to(message, bypass_warn, parse_mode="Markdown")

                    # Bypass alert group mein bhi bhejo
                    bypass_group_text = (
                        f"⚠️ *BYPASS DETECTED!* ⚠️\n"
                        "━━━━━━━━━━━━━━━━━━\n"
                        f"👤 *User:* [{message.from_user.first_name}](tg://user?id={message.from_user.id})\n"
                        f"🆔 *User ID:* `{message.from_user.id}`\n"
                        "━━━━━━━━━━━━━━━━━━\n"
                        "🚫 *Is user ne shortlink bypass karke 2 min se pehle link khola!*\n"
                        "🚀 *Powered by VIP Rolex Engine*"
                    )
                    try:
                        bot.send_message(GROUP_CHAT_ID, bypass_group_text, parse_mode='Markdown')
                    except Exception as ge:
                        print(f"Group bypass send error: {ge}")

                    del pending_likes[token] # Link uda do
                    return
                    
                elif time_taken > 600: # Agar 10 minutes se upar lag gaye toh expire
                    bot.reply_to(message, "❌ **Link Expired!** 10 minute se zyada ho gaye. Kripya naya `/like` command lagayein.", parse_mode="Markdown")
                    del pending_likes[token]
                    return
                    
                else:
                    # Link proper verify ho gaya aur time bhi sahi hai!
                    del pending_likes[token] 
                    process_actual_like(message, data['server_name'], data['uid'])
                    return
            else:
                bot.reply_to(message, "❌ Ye verification link tumhara nahi hai! Apna command khud use karo.")
                return
        else:
            bot.reply_to(message, "❌ Link Expire ho gaya hai ya invalid hai! Dobara `/like` command lagao.")
            return

    # Normal /start ka message
    example_text = (
        "👑 *ROLEX VIP SYSTEM MEIN SWAGAT HAI* 👑\n\n"
        "Tum pehle se verified ho! 🎉\n\n"
        "👇 *Available Commands:*\n"
        "1️⃣ `/info IND UID` - ID scan nikalne ke liye\n"
        "2️⃣ `/like IND UID` - Likes bhejne ke liye\n\n"
        "⚡ *System ekdum Ready Hai!*"
    )
    try:
        with open('2.png', 'rb') as photo:
            bot.send_photo(message.chat.id, photo, caption=example_text, parse_mode="Markdown")
    except FileNotFoundError:
        bot.reply_to(message, example_text, parse_mode='Markdown')


# ==========================================
# 🎮 COMMAND: /like (SHORTLINK GENERATOR)
# ==========================================
@bot.message_handler(commands=['like'])
def handle_like(message):
    user_id = message.from_user.id
    log_active_user(user_id)

    if check_join_status(user_id):
        remove_verified_user(user_id) 
        send_force_join_msg(message)
        return

    current_time = time.time()
    if user_id in user_cooldowns:
        elapsed = current_time - user_cooldowns[user_id]
        if elapsed < 8:
            bot.reply_to(message, f"⏳ Bhai, spam mat karo! Agli command {int(8 - elapsed)} second baad dena.")
            return
    user_cooldowns[user_id] = current_time

    msg_args = message.text.split()
    
    if len(msg_args) < 3:
        error_txt = "❌ *INVALID FORMAT* ❌\n━━━━━━━━━━━━━━━━━━\n👉 *Sahi Example:* `/like IND 2652073509`"
        bot.reply_to(message, error_txt, parse_mode='Markdown')
        return

    server_name = msg_args[1].upper()
    uid = msg_args[2]

    # ==========================================
    # 🚫 DAILY LIMIT CHECK
    # ==========================================
    if has_used_daily_like(user_id, uid):
        next_reset = get_next_reset_time()
        limit_msg = (
            "🚫 *DAILY LIMIT REACHED!* 🚫\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"👤 *Hey {message.from_user.first_name},*\n\n"
            "Aapka aaj ka Free Like quota already use ho chuka hai! 💔\n\n"
            "🎮 *Free Fire ki tarah, har cheez ka ek limit hota hai.*\n"
            "Yeh bot bhi daily ek hi baar like bhejne ki permission deta hai.\n\n"
            "⏰ *Aapka limit reset hoga:*\n"
            f"📅 `{next_reset}`\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "🔁 Kal subah *4:00 AM IST* ke baad wapas aana!\n"
            "🚀 *Powered by VIP Rolex Engine*"
        )
        try:
            with open('daily.mp4', 'rb') as video_file:
                bot.send_video(message.chat.id, video=video_file, caption=limit_msg, parse_mode='Markdown')
        except FileNotFoundError:
            bot.reply_to(message, limit_msg, parse_mode='Markdown')
        return

    # Limit tab lagegi jab like success ho — neeche API response mein

    # ==========================================
    # 🔗 SHORTLINK ON/OFF SWITCH
    # ==========================================
    if SHORTLINK_ENABLED:
        # ----- SHORTLINK MODE (jab SHORTLINK_ENABLED = True) -----
        # Turant user ko processing message dikhao taaki wo wait kare
        status_msg = bot.reply_to(message, "⚡ *Shortening your secure link... Please hold on!* 🔗", parse_mode='Markdown')

        def generate_and_send():
            token = "VPL_" + ''.join(random.choices(string.ascii_letters + string.digits, k=10))
            
            pending_likes[token] = {
                "user_id": user_id,
                "server_name": server_name,
                "uid": uid,
                "timestamp": time.time() 
            }

            bot_info = bot.get_me() 
            dest_url = f"https://t.me/{bot_info.username}?start={token}" 
            
            bot.edit_message_text("🔐 *Encrypting & generating VIP link... Almost done!* ✨", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode='Markdown')
            
            short_url = get_shortlink(dest_url) 
            
            verify_msg = (
                "⚠️ *VERIFICATION REQUIRED!* ⚠️\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"👤 **Target UID:** `{uid}`\n\n"
                "👉 *Likes bhejne ke liye is link ko verify karo:*\n"
                f"🔗 **Link:** {short_url}\n\n"
                "*(Link open karo, ad skip karo, aur wapas aakar 'Start' dabao tabhi like jayega!)*"
            )
            
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("🔗 OPEN LINK & VERIFY", url=short_url))
            markup.row(InlineKeyboardButton("📹 How to Verify? Watch Here", url="https://www.youtube.com/watch?v=jSDNzzqFkYw"))
            
            bot.edit_message_text(verify_msg, chat_id=message.chat.id, message_id=status_msg.message_id, reply_markup=markup, parse_mode='Markdown', disable_web_page_preview=True)

        like_executor.submit(generate_and_send)

    else:
        # ----- DIRECT MODE (jab SHORTLINK_ENABLED = False) -----
        # Seedha like process karo, koi shortlink nahi
        process_actual_like(message, server_name, uid)

# ==========================================
# 🚀 ACTUAL LIKE INJECTION (VERIFY HONE KE BAAD)
# ==========================================
def process_actual_like(message, server_name, uid):
    def _do_like():
        status_msg = bot.reply_to(message, "⏳ *Link Verified! Verifying Access...*", parse_mode='Markdown')
        user_id = message.from_user.id
        user_lock = get_user_lock(user_id)

        with user_lock:
            bot.edit_message_text("🔍 *Rolex Engine Processing...*", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode='Markdown')
            
            try:
                api_request_url = f"{LIKE_API_URL}?uid={uid}&server_name={server_name}"
                response = requests.get(api_request_url)
                data = response.json()

                if response.status_code == 200 and 'error' not in data:
                    likes_given = int(data.get('LikesGivenByAPI', 0))
                    likes_after = int(data.get('LikesafterCommand', 0))
                    likes_before = likes_after - likes_given
                    
                    if likes_given == 0:
                        final_text = (
                            "⚠️ *LIKE PEHLE SE DE DIYA GAYA HAI!* ⚠️\n"
                            "━━━━━━━━━━━━━━━━━━\n"
                            f"👤 *Player Name:* `{data.get('PlayerNickname', 'Unknown')}`\n"
                            f"🆔 *Player UID:* `{data.get('UID', uid)}`\n"
                            f"🌍 *Region:* `{data.get('Region', server_name)}`\n"
                            "━━━━━━━━━━━━━━━━━━\n"
                            f"📉 *Before Likes:* `{likes_before}`\n"
                            f"📈 *Likes Injected:* `+0` (Daily Limit)\n"
                            f"📊 *Total Likes Now:* `{likes_after}`\n"
                            "━━━━━━━━━━━━━━━━━━\n"
                            "🚀 *Powered by VIP Rolex Engine*"
                        )
                    else:
                        final_text = (
                            "✅ *SUCCESS BY ROLEX* ✅\n"
                            "━━━━━━━━━━━━━━━━━━\n"
                            f"👤 *Player Name:* `{data.get('PlayerNickname', 'Unknown')}`\n"
                            f"🆔 *Player UID:* `{data.get('UID', uid)}`\n"
                            f"🌍 *Region:* `{data.get('Region', server_name)}`\n"
                            "━━━━━━━━━━━━━━━━━━\n"
                            f"📉 *Before Likes:* `{likes_before}`\n"
                            f"📈 *Likes Injected:* `+{likes_given}`\n"
                            f"📊 *Total Likes Now:* `{likes_after}`\n"
                            "━━━━━━━━━━━━━━━━━━\n"
                            "🚀 *Powered by VIP Rolex Engine*"
                        )                    
                    try:
                        with open('success.mp4', 'rb') as video_file:
                            bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)
                            bot.send_video(message.chat.id, video=video_file, caption=final_text, parse_mode='Markdown', timeout=60)
                    except Exception as e:
                        print(f"MP4 Error: {e}") 
                        bot.edit_message_text(final_text, chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode='Markdown')

                    # Result group mein bhi bhejo (success + already liked dono cases)
                    try:
                        bot.send_message(GROUP_CHAT_ID, final_text, parse_mode='Markdown')
                    except Exception as ge:
                        print(f"Group send error: {ge}")

                else:
                    final_text = "❌ *OPERATION FAILED* ❌\n━━━━━━━━━━━━━━━━━━\n⚠️ *API Error:* Token Expired or Invalid\n━━━━━━━━━━━━━━━━━━\n📩 *Owner:* @RolexBoss62"
                    bot.edit_message_text(final_text, chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode='Markdown')

            except Exception as e:
                final_text = "⚠️ *CONNECTION TIMEOUT* ⚠️\n━━━━━━━━━━━━━━━━━━\nBot API Server down hai!\n👉 *Owner:* @RolexBoss62"
                bot.edit_message_text(final_text, chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode='Markdown')

    like_executor.submit(_do_like)

# ==========================================
# 🎮 COMMAND: /info
# ==========================================
@bot.message_handler(commands=['info'])
def get_player_info(message):
    # 👇 NAYA FIX: Group mein /info block karna
    if message.chat.type in ['group', 'supergroup']:
        bot.reply_to(message, "⚠️ Bhai, `/info` command sirf bot ke DM (Private Chat) mein kaam karta hai. Group mein allow nahi hai!", parse_mode="Markdown")
        return
        
    if message.chat.id < 0:
        return

    user_id = message.from_user.id
    log_active_user(user_id)

    status_msg = bot.reply_to(message, "⏳ *Verifying Access...*", parse_mode='Markdown')

    if check_join_status(user_id):
        bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)
        remove_verified_user(user_id)
        send_force_join_msg(message)
        return

    current_time = time.time()
    if user_id in user_cooldowns:
        elapsed = current_time - user_cooldowns[user_id]
        if elapsed < 8:
            bot.edit_message_text(f"⏳ Bhai, spam mat karo! Agli command {int(8 - elapsed)} second baad dena.", chat_id=message.chat.id, message_id=status_msg.message_id)
            return
    user_cooldowns[user_id] = current_time

    args = message.text.split()
    if len(args) != 3:
        error_msg = "⚠️ **Bhai, command adhoori ya galat hai!**\nSahi tarika ye hai:\n👉 `/info ind 123456789`"
        bot.edit_message_text(error_msg, chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
        return

    region = args[1].upper() 
    uid = args[2]
    bot.edit_message_text("⚡ **EXTRACTING VIP DETAILS...**", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")

    try:
        response = requests.get(INFO_API_URL, params={'region': region, 'uid': uid}, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list): data = data[0]
            
            basic = data.get("basicInfo", {})
            profile = data.get("profileInfo", {})
            clan = data.get("clanBasicInfo", {})
            captain = data.get("captainBasicInfo", {})
            pet = data.get("petInfo", {})
            social = data.get("socialInfo", {})
            credit = data.get("creditScoreInfo", {})

            gender = str(social.get('gender', 'Male')).replace('Gender_', '').title()
            bp_pass = "Premium" if basic.get('hasElitePass') else "Free"
            mode_prefer = str(social.get('modePrefer', 'CsRanked')).replace('ModePrefer_', '')
            language = str(social.get('language', 'English')).replace('Language_', '')
            
            cs_stars_player = get_cs_stars(basic.get('csRank', 0), basic.get('csRankingPoints', 0))
            cs_stars_leader = get_cs_stars(captain.get('csRank', 0), captain.get('csRankingPoints', 0))

            br_rank_str = f"{get_br_rank(basic.get('rank', 0), basic.get('rankingPoints', 0))} ({basic.get('rankingPoints', 0)})"
            cs_rank_str = f"{get_cs_rank(basic.get('csRank', 0))} ({cs_stars_player} Star)"
            
            leader_br_str = f"{get_br_rank(captain.get('rank', 0), captain.get('rankingPoints', 0))} ({captain.get('rankingPoints', 0)})"
            leader_cs_str = f"{get_cs_rank(captain.get('csRank', 0))} ({cs_stars_leader} Star)"

            reply = f"""**ACCOUNT INFORMATION:**
┌ ACCOUNT BASIC INFORMATION
├─ Name: {basic.get('nickname', 'Unknown')}
├─ UID: {uid}
├─ Level: {basic.get('level', 0)}
├─ Region: {region}
├─ Likes: {basic.get('liked', 0)}
├─ Honor Score: {credit.get('creditScore', 'N/A')}
└─ Signature: {social.get('signature', 'No Signature')}

**ACCOUNT ACTIVITY:**
┌ ACCOUNT ACTIVITY
├─ Fire Pass: {bp_pass}
├─ Br Rank: {br_rank_str}
├─ Cs Rank: {cs_rank_str}
├─ Gender: {gender}
├─ Created At: {fmt_t(basic.get('createAt'))}
└─ Last Login: {fmt_t(basic.get('lastLoginAt'))}

**GUILD INFORMATION:**
┌ GUILD INFORMATION
├─ Guild Name: {clan.get('clanName', 'No Guild')}
├─ Guild ID: {clan.get('clanId', 'N/A')}
├─ Guild Level: {clan.get('clanLevel', 'N/A')}
├─ Live Members: {clan.get('memberNum', 0)}/{clan.get('capacity', 0)}
└─ Leader Name: {captain.get('nickname', 'N/A')}

✨ *Bot By ROLEX*"""

            bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)
            
            try:
                with open('1.png', 'rb') as photo:
                    bot.send_photo(message.chat.id, photo, caption=reply, parse_mode="Markdown")
            except FileNotFoundError:
                bot.send_message(message.chat.id, reply, parse_mode="Markdown")

        else:
            bot.edit_message_text("❌ **Error:** API ne reply nahi diya.", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode='Markdown')
            
    except requests.exceptions.Timeout:
        bot.edit_message_text("❌ **API Error:** Server abhi slow hai. Kripya thodi der baad try karein!", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode='Markdown')
    except Exception:
        bot.edit_message_text("❌ OPERATION FAILED ❌\n⚠️ API Error: Owner ko message karo @RolexBoss62", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode='Markdown')

# ==========================================
# 🎮 COMMAND: /status
# ==========================================
@bot.message_handler(commands=['status'])
def check_status(message):
    user_id = message.from_user.id
    if check_join_status(user_id):
        return

    try:
        with open("tokens.json", "r") as f:
            tokens = json.load(f)
        total_tokens = len(tokens)
        status_text = f"📊 **ROLEX SYSTEM STATUS** 📊\n━━━━━━━━━━━━━━━━━━\n✅ **Active Tokens:** `{total_tokens}`\n🔥 *System ekdum makkhan chal raha hai!*"
    except Exception as e:
        status_text = "❌ *ERROR:* `tokens.json` file missing ya empty hai!"

    bot.reply_to(message, status_text, parse_mode='Markdown')

# ==========================================
# ✅ MULTI-VERIFY BUTTON LOGIC
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith('verify_'))
def verify_callback(call):
    original_user_id = int(call.data.split('_')[1])
    clicker_id = call.from_user.id

    if clicker_id != original_user_id:
        bot.answer_callback_query(call.id, "❌ STOP! Ye button tumhare liye nahi hai!", show_alert=True)
        return

    if not check_join_status(clicker_id): 
        add_verified_user(clicker_id)
        log_active_user(clicker_id)
        
        bot.answer_callback_query(call.id, "✅ Verified Successfully! Ab aap bot use kar sakte hain.", show_alert=True)
        bot.delete_message(call.message.chat.id, call.message.message_id)
        
        bot.send_message(call.message.chat.id, f"✅ *Verification Successful for {call.from_user.first_name}!*\n👑 Welcome to Rolex VIP System. Now you can use commands.", parse_mode='Markdown')
    else:
        bot.answer_callback_query(call.id, "❌ ERROR: Aapne abhi tak saare group/channels join nahi kiye hain!", show_alert=True)

hacker_look_banner = """
\033[1;32m
██████╗  ██████╗ ██╗     ███████╗██╗  ██╗
██╔══██╗██╔═══██╗██║     ██╔════╝╚██╗██╔╝
██████╔╝██║   ██║██║     █████╗   ╚███╔╝ 
██╔══██╗██║   ██║██║     ██╔══╝   ██╔██╗ 
██║  ██║╚██████╔╝███████╗███████╗██╔╝ ██╗
╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚══════╝╚═╝  ╚═╝
\033[0m
\033[1;36m[+] ROLEX VIP SYSTEM INITIALIZED\033[0m
\033[1;36m[+] SERVER: ONLINE\033[0m
\033[1;36m[+] MULTI-FORCE JOIN: ACTIVE\033[0m
\033[1;33m[+] VPLINK SHORTENER: DISABLED (Set SHORTLINK_ENABLED=True to re-enable)\033[0m
\033[1;36m[+] DAILY LIMIT SYSTEM: ACTIVE (Resets at 4 AM IST)\033[0m
\033[1;36m[+] ANTI-BYPASS SHIELD: ON (2 MIN TIMER)\033[0m
\033[1;36m[+] CONCURRENT USERS: 10 (THREAD POOL ACTIVE)\033[0m
"""
print(hacker_look_banner)

# 👇 NAYA FIX: Render Dummy Server Start 👇
# ==========================================
# 🌐 RENDER DUMMY WEB SERVER
# ==========================================
app = Flask(__name__)

@app.route('/')
def home():
    return "Rolex Bot is Alive and Running!"

def run():
    # Render khud ek PORT deta hai, warna 8080 use hoga
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

print("[+] ROLEX LIKE BOT v2 INITIALIZED — ALL SYSTEMS GO!")
keep_alive() # Dummy server start kiya
bot.remove_webhook()
bot.infinity_polling(allowed_updates=telebot.util.update_types)




bot.infinity_polling(allowed_updates=telebot.util.update_types)


