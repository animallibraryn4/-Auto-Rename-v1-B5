import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import Txt, Config

# --- Constants for Data ---
PLAN_DATA = {
    "free": {"name": "Free Trial", "time": "1 hour", "price": "Free", "desc": "Limited-time access to test the service\n➛ Perfect to check speed and features\n➛ No payment required", "page": "1/6"},
    "basic": {"name": "Basic Pass", "time": "7 days", "price": "₹39", "desc": "Suitable for light and short-term users\n➛ Full access during active period\n➛ Budget-friendly weekly plan\n➛ Check your active plan: /myplan", "page": "2/6"},
    "lite": {"name": "Lite Plan", "time": "15 days", "price": "₹79", "desc": "Best choice for regular users\n➛ More value compared to weekly plan\n➛ Smooth and uninterrupted access\n➛ Recommended for consistent usage", "page": "3/6"},
    "standard": {"name": "Standard Plan", "time": "30 days", "price": "₹129", "desc": "Most popular plan\n➛ Best balance of price and duration\n➛ Ideal for daily and long-term users\n➛ ⭐ Best for regular users", "page": "4/6"},
    "pro": {"name": "Pro Plan", "time": "50 days", "price": "₹199", "desc": "Maximum savings for long-term users\n➛ Hassle-free extended access\n➛ Best value plan for power users\n➛ 💎 Long-term recommended", "page": "5/6"},
    "ultra": {"name": "Ultra Plan", "time": "Coming soon", "price": "TBA", "desc": "Premium and exclusive access\n➛ Extra benefits and features\n➛ Designed for hardcore users\n➛ Stay tuned for launch 👀", "page": "6/6"},
}

# --- Command Handler ---
@Client.on_message(filters.command(["plan", "premium"]))
async def plan_cmd(bot, message):
    buttons = [
        [InlineKeyboardButton("Free Trial", callback_data="view_free"), InlineKeyboardButton("Basic Pass", callback_data="view_basic")],
        [InlineKeyboardButton("Lite", callback_data="view_lite"), InlineKeyboardButton("Standard", callback_data="view_standard")],
        [InlineKeyboardButton("Pro", callback_data="view_pro"), InlineKeyboardButton("Ultra", callback_data="view_ultra")],
        [InlineKeyboardButton("Close", callback_data="close")]
    ]
    await message.reply_photo(
        photo='https://graph.org/file/8b50e21db819f296661b7.jpg',
        caption=Txt.PREPLANS_TXT if message.text == "/plan" else Txt.PREMIUM_TXT,
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# --- Callback Query Handler ---
@Client.on_callback_query()
async def cb_handler(bot, query: CallbackQuery):
    data = query.data
    user_name = query.from_user.first_name

    if data == "close":
        await query.message.delete()
        
    elif data == "main_plan":
        # Returns to the main selection grid
        buttons = [
            [InlineKeyboardButton("Free Trial", callback_data="view_free"), InlineKeyboardButton("Basic Pass", callback_data="view_basic")],
            [InlineKeyboardButton("Lite", callback_data="view_lite"), InlineKeyboardButton("Standard", callback_data="view_standard")],
            [InlineKeyboardButton("Pro", callback_data="view_pro"), InlineKeyboardButton("Ultra", callback_data="view_ultra")],
            [InlineKeyboardButton("Close", callback_data="close")]
        ]
        await query.message.edit_caption(caption=Txt.PREPLANS_TXT, reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("view_"):
        plan_key = data.split("_")[1]
        plan = PLAN_DATA[plan_key]
        
        # Determine Next/Back logic for pagination
        keys = list(PLAN_DATA.keys())
        curr_idx = keys.index(plan_key)
        next_plan = keys[(curr_idx + 1) % len(keys)]
        prev_plan = keys[(curr_idx - 1) % len(keys)]

        text = f"👋 Hey {user_name},\n\n{plan['name']}\n⏰ {plan['time']}\n💸 Plan price ➛ {plan['price']}\n➛ {plan['desc']}"
        
        buttons = []
        if plan_key == "free":
            buttons.append([InlineKeyboardButton("Admit Link: @Anime_Library_N4", url="https://t.me/Anime_library_n4")])
        else:
            buttons.append([InlineKeyboardButton("Click here to buy plan", callback_data=f"pay_{plan_key}")])
            
        buttons.append([InlineKeyboardButton(f"Page {plan['page']}", callback_data="none")])
        buttons.append([InlineKeyboardButton("← Back", callback_data=f"view_{prev_plan}"), InlineKeyboardButton("Next →", callback_data=f"view_{next_plan}")])
        buttons.append([InlineKeyboardButton("Back to Menu", callback_data="main_plan")])

        await query.message.edit_caption(caption=text, reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("pay_"):
        plan_key = data.split("_")[1]
        buttons = [
            [InlineKeyboardButton("Pay via UPI ID", callback_data=f"method_upi_{plan_key}")],
            [InlineKeyboardButton("Scan QR Code", callback_data=f"method_qr_{plan_key}")],
            [InlineKeyboardButton("Back", callback_data=f"view_{plan_key}")]
        ]
        await query.message.edit_caption(caption="**Select Your Payment Method**", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("method_"):
        _, method, plan_key = data.split("_")
        if method == "upi":
            text = f"👋 Hey {user_name},\n\nPay the amount according to your selected plan and enjoy plan membership!\n\n💵 **UPI ID:** `dm @PYato` \n\n‼️ You must send a screenshot after payment."
        else:
            text = f"👋 Hey Anime Library N4,\n\nPay the amount according to your membership price!\n\n📸 **QR Code:** [Click here to scan](https://t.me/Animelibraryn4)\n\n‼️ You must send a screenshot after payment."
            
        buttons = [
            [InlineKeyboardButton("Send payment screenshot here", url="https://t.me/Animelibraryn4")],
            [InlineKeyboardButton("Back", callback_data=f"pay_{plan_key}")]
        ]
        await query.message.edit_caption(caption=text, reply_markup=InlineKeyboardMarkup(buttons))
        
