import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto

# --- Constants & Layouts ---
PAYMENT_LINK = "https://t.me/Animelibraryn4"
OWNER_LINK = "https://t.me/PYato"
THUMBNAIL = "https://graph.org/file/8b50e21db819f296661b7.jpg"

def get_main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Free Trial", callback_data="p_free"), InlineKeyboardButton("Basic Pass", callback_data="p_basic")],
        [InlineKeyboardButton("Lite", callback_data="p_lite"), InlineKeyboardButton("Standard", callback_data="p_standard")],
        [InlineKeyboardButton("Pro", callback_data="p_pro"), InlineKeyboardButton("Ultra", callback_data="p_ultra")],
        [InlineKeyboardButton("✖️ Close", callback_data="close")]
    ])

def get_nav_buttons(back_val, next_val, buy=True):
    btns = []
    if buy:
        btns.append([InlineKeyboardButton("💳 Click here to buy plan", callback_data="pay_method")])
    else:
        btns.append([InlineKeyboardButton("📢 Admit Link", url=PAYMENT_LINK)])
    btns.append([InlineKeyboardButton("⬅️ Back", callback_data=back_val), InlineKeyboardButton("➡️ Next", callback_data=next_val)])
    return InlineKeyboardMarkup(btns)

# --- Handlers ---

@Client.on_message(filters.command("plan"))
async def plan_cmd(bot, message):
    await message.reply_photo(
        photo=THUMBNAIL,
        caption="**Welcome to our Premium Plans!**\n\nPlease select a plan from the buttons below to view details.",
        reply_markup=get_main_menu()
    )

@Client.on_callback_query(filters.regex(r"^p_"))
async def plan_pages(bot, cb):
    user_name = cb.from_user.first_name
    page = cb.data.split("_")[1]
    
    pages = {
        "free": {
            "text": f"👋 Hey {user_name},\n\n🆓 **FREE TRIAL (1/6)**\n⏰ 1 Hour Access\n💸 Price: Free\n\n➛ Limited-time access to test the service\n➛ Perfect to check speed and features\n➛ No payment required",
            "markup": get_nav_buttons("main", "p_basic", buy=False)
        },
        "basic": {
            "text": f"👋 Hey {user_name},\n\n🟢 **BASIC PASS (2/6)**\n⏰ 7 Days\n💸 Price: ₹39\n\n➛ Suitable for light users\n➛ Full access\n➛ Budget-friendly\n➛ Check status: /myplan",
            "markup": get_nav_buttons("p_free", "p_lite")
        },
        "lite": {
            "text": f"👋 Hey {user_name},\n\n🔵 **LITE PLAN (3/6)**\n⏰ 15 Days\n💸 Price: ₹79\n\n➛ Best for regular users\n➛ More value\n➛ Smooth access",
            "markup": get_nav_buttons("p_basic", "p_standard")
        },
        "standard": {
            "text": f"👋 Hey {user_name},\n\n⭐ **STANDARD PLAN (4/6)**\n⏰ 30 Days\n💸 Price: ₹129\n\n➛ Most popular plan\n➛ Best balance\n➛ Ideal for daily users",
            "markup": get_nav_buttons("p_lite", "p_pro")
        },
        "pro": {
            "text": f"👋 Hey {user_name},\n\n💎 **PRO PLAN (5/6)**\n⏰ 50 Days\n💸 Price: ₹199\n\n➛ Maximum savings\n➛ Extended access\n➛ Best for power users",
            "markup": get_nav_buttons("p_standard", "p_ultra")
        },
        "ultra": {
            "text": f"👋 Hey {user_name},\n\n👑 **ULTRA PLAN (6/6)**\n⏰ Coming Soon\n💸 Price: TBA\n\n➛ Premium & exclusive\n➛ Extra benefits\n➛ Stay tuned 👀",
            "markup": get_nav_buttons("p_pro", "main")
        }
    }
    
    if page == "main":
        await cb.edit_message_caption(caption="**Main Menu**", reply_markup=get_main_menu())
    else:
        p_data = pages[page]
        await cb.edit_message_caption(caption=p_data["text"], reply_markup=p_data["markup"])

@Client.on_callback_query(filters.regex("pay_method"))
async def payment_menu(bot, cb):
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("💵 Pay via UPI ID", callback_data="pay_upi")],
        [InlineKeyboardButton("📸 Scan QR Code", callback_data="pay_qr")],
        [InlineKeyboardButton("⬅️ Back", callback_data="p_basic")]
    ])
    await cb.edit_message_caption(caption="💳 **SELECT YOUR PAYMENT METHOD**", reply_markup=buttons)

@Client.on_callback_query(filters.regex(r"^pay_(upi|qr)"))
async def process_pay(bot, cb):
    method = cb.data.split("_")[1]
    user_name = cb.from_user.first_name
    
    if method == "upi":
        msg = f"👋 Hey {user_name},\n\nPay the amount according to your plan!\n\n💵 **UPI ID:** `{OWNER_LINK.split('/')[-1]}`\n\n‼️ Must send screenshot after payment"
    else:
        msg = f"👋 Hey {user_name},\n\nPay the amount according to your membership price!\n\n📸 **QR Code:** [Click here to scan]({PAYMENT_LINK})\n\n‼️ Must send screenshot after payment"
        
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Send screenshot", url=PAYMENT_LINK)],
        [InlineKeyboardButton("⬅️ Back", callback_data="pay_method")]
    ])
    await cb.edit_message_caption(caption=msg, reply_markup=buttons)

@Client.on_callback_query(filters.regex("close"))
async def close(bot, cb):
    await cb.message.delete()

