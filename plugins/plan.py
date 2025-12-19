import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import Txt, Config

# --- Constants for Page Logic ---
# These match the text you provided
PLAN_TEXTS = [
    Txt.FREE_TRIAL_TXT,  # 1/6
    Txt.BASIC_PASS_TXT,  # 2/6
    Txt.LITE_PLAN_TXT,   # 3/6
    Txt.STANDARD_PLAN_TXT, # 4/6
    Txt.PRO_PLAN_TXT,    # 5/6
    Txt.ULTRA_PLAN_TXT   # 6/6
]

# --- Helper Function for Navigation ---
def get_plan_keyboard(index):
    buttons = []
    # Navigation Row
    nav_row = []
    if index > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Back", callback_data=f"plan_{index-1}"))
    if index < len(PLAN_TEXTS) - 1:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"plan_{index+1}"))
    
    if nav_row:
        buttons.append(nav_row)
    
    # Action Row
    buttons.append([InlineKeyboardButton("💳 Buy Now", callback_data="select_payment")])
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close")])
    return InlineKeyboardMarkup(buttons)

# --- Handlers ---

@Client.on_message(filters.command("plan"))
async def plan_cmd(bot, message):
    # Initial page (Free Trial - index 0)
    await message.reply_photo(
        photo='https://graph.org/file/8b50e21db819f296661b7.jpg',
        caption=PLAN_TEXTS[0].format(user_name=message.from_user.first_name),
        reply_markup=get_plan_keyboard(0)
    )

@Client.on_callback_query(filters.regex(r"^plan_(\d+)"))
async def plan_nav(bot, query: CallbackQuery):
    index = int(query.data.split("_")[1])
    await query.message.edit_caption(
        caption=PLAN_TEXTS[index].format(user_name=query.from_user.first_name),
        reply_markup=get_plan_keyboard(index)
    )

@Client.on_callback_query(filters.regex("select_payment"))
async def payment_menu(bot, query: CallbackQuery):
    buttons = [
        [InlineKeyboardButton("💵 UPI ID", callback_data="pay_upi")],
        [InlineKeyboardButton("📸 QR Code", callback_data="pay_qr")],
        [InlineKeyboardButton("⬅️ Back to Plans", callback_data="plan_0")]
    ]
    await query.message.edit_caption(
        caption=Txt.PAYMENT_METHOD_TXT.format(user_name=query.from_user.first_name),
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex(r"^pay_(upi|qr)"))
async def final_payment(bot, query: CallbackQuery):
    method = query.data.split("_")[1]
    text = Txt.UPI_PAY_TXT if method == "upi" else Txt.QR_PAY_TXT
    
    buttons = [[InlineKeyboardButton("📤 Send Screenshot", url="https://t.me/Anime_library_n4")]]
    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="select_payment")])
    
    await query.message.edit_caption(
        caption=text.format(user_name=query.from_user.first_name),
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex("close"))
async def close_menu(bot, query: CallbackQuery):
    await query.message.delete()

