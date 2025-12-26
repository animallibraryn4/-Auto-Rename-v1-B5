import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import Txt, Config

# --- Constants ---
PLAN_PHOTO = "https://graph.org/file/8b50e21db819f296661b7.jpg"

# --- Main Command ---
@Client.on_message(filters.command("plan"))
async def plan_menu(bot, message):
    buttons = [
        [InlineKeyboardButton("Free Trial", callback_data="view_free"), InlineKeyboardButton("Basic Pass", callback_data="view_basic")],
        [InlineKeyboardButton("Lite", callback_data="view_lite"), InlineKeyboardButton("Standard", callback_data="view_standard")],
        [InlineKeyboardButton("Pro", callback_data="view_pro"), InlineKeyboardButton("Ultra", callback_data="view_ultra")],
        [InlineKeyboardButton("Close", callback_data="close")]
    ]
    await message.reply_photo(
        photo=PLAN_PHOTO,
        caption=Txt.PLAN_MAIN_TXT.format(message.from_user.first_name),
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# --- Callback Handlers ---
@Client.on_callback_query(filters.regex(r'^(main_plan|view_free|view_basic|view_lite|view_standard|view_pro|view_ultra|pay_basic|pay_lite|pay_standard|pay_pro|pay_ultra|upi_|qr_|close)$'))
async def handle_callbacks(bot, query: CallbackQuery):
    data = query.data
    user_name = query.from_user.first_name

    # Navigation Logic
    if data == "main_plan":
        buttons = [
            [InlineKeyboardButton("Free Trial", callback_data="view_free"), InlineKeyboardButton("Basic Pass", callback_data="view_basic")],
            [InlineKeyboardButton("Lite", callback_data="view_lite"), InlineKeyboardButton("Standard", callback_data="view_standard")],
            [InlineKeyboardButton("Pro", callback_data="view_pro"), InlineKeyboardButton("Ultra", callback_data="view_ultra")],
            [InlineKeyboardButton("Close", callback_data="close")]
        ]
        await query.message.edit_caption(
            caption=Txt.PLAN_MAIN_TXT.format(user_name), 
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data.startswith("view_"):
        plan_type = data.split("_")[1]
        
        # Define Plan Content: (Text, Page, Prev, Next, Pay_Callback)
        plans = {
            "free": (Txt.FREE_TXT, "1/6", "view_ultra", "view_basic", None),
            "basic": (Txt.BASIC_TXT, "2/6", "view_free", "view_lite", "pay_basic"),
            "lite": (Txt.LITE_TXT, "3/6", "view_basic", "view_standard", "pay_lite"),
            "standard": (Txt.STANDARD_TXT, "4/6", "view_lite", "view_pro", "pay_standard"),
            "pro": (Txt.PRO_TXT, "5/6", "view_standard", "view_ultra", "pay_pro"),
            "ultra": (Txt.ULTRA_TXT, "6/6", "view_pro", "view_free", "pay_ultra")
        }
        
        txt, page, prev_p, next_p, pay_callback = plans[plan_type]
        
        btn = []
        if pay_callback:
            btn.append([InlineKeyboardButton("Click here to buy plan", callback_data=pay_callback)])
        elif plan_type == "free":
            btn.append([InlineKeyboardButton("Admit Link", url="https://t.me/Anime_Library_N4")])
            
        btn.append([
            InlineKeyboardButton("Back", callback_data=prev_p), 
            InlineKeyboardButton(page, callback_data="none"), 
            InlineKeyboardButton("Next", callback_data=next_p)
        ])
        btn.append([InlineKeyboardButton("Back to Menu", callback_data="main_plan")])
        
        await query.message.edit_caption(
            caption=txt.format(user_name), 
            reply_markup=InlineKeyboardMarkup(btn)
        )

    elif data.startswith("pay_"):
        plan_origin = data.split("_")[1]
        buttons = [
            [InlineKeyboardButton("Pay via UPI ID", callback_data=f"upi_{plan_origin}")],
            [InlineKeyboardButton("Scan QR Code", callback_data=f"qr_{plan_origin}")],
            [InlineKeyboardButton("Back", callback_data=f"view_{plan_origin}")]
        ]
        await query.message.edit_caption(
            caption=Txt.SELECT_PAYMENT_TXT, 
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data.startswith("upi_") or data.startswith("qr_"):
        method, origin = data.split("_")
        txt = Txt.UPI_TXT if method == "upi" else Txt.QR_TXT
        buttons = [
            [InlineKeyboardButton("Send payment screenshot here", url="https://t.me/Animelibraryn4")],
            [InlineKeyboardButton("Back", callback_data=f"pay_{origin}")]
        ]
        await query.message.edit_caption(
            caption=txt.format(user_name), 
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data == "close":
        await query.message.delete()
