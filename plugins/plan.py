import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import Txt, Config

# Dictionary to store user's current plan page
user_plan_page = {}

# Plan data structure
PLANS = {
    1: {
        "name": "🆓 FREE TRIAL",
        "duration": "1 Hour Access",
        "price": "Free",
        "description": "Limited-time access to test the service\n➛ Perfect to check speed and features\n➛ No payment required",
        "photo": "https://graph.org/file/8b50e21db819f296661b7.jpg",
        "button_text": "Admit Link: @Anime_Library_N4"
    },
    2: {
        "name": "🟢 BASIC PASS",
        "duration": "7 Days",
        "price": "₹39",
        "description": "Suitable for light & short-term users\n➛ Full access during active period\n➛ Budget-friendly weekly plan\n➛ Check your active plan: /myplan",
        "photo": "https://graph.org/file/feebef43bbdf76e796b1b.jpg",
        "button_text": "Click here to buy plan"
    },
    3: {
        "name": "🔵 LITE PLAN",
        "duration": "15 Days",
        "price": "₹79",
        "description": "Best choice for regular users\n➛ More value compared to weekly plan\n➛ Smooth and uninterrupted access\n➛ Recommended for consistent usage",
        "photo": "https://graph.org/file/8b50e21db819f296661b7.jpg",
        "button_text": "Click here to buy plan"
    },
    4: {
        "name": "⭐ STANDARD PLAN",
        "duration": "30 Days",
        "price": "₹129",
        "description": "Most popular plan\n➛ Best balance of price & duration\n➛ Ideal for daily and long-term users\n➛ ⭐ Best for regular users",
        "photo": "https://graph.org/file/feebef43bbdf76e796b1b.jpg",
        "button_text": "Click here to buy plan"
    },
    5: {
        "name": "💎 PRO PLAN",
        "duration": "50 Days",
        "price": "₹199",
        "description": "Maximum savings for long-term users\n➛ Hassle-free extended access\n➛ Best value plan for power users\n➛ 💎 Long-term recommended",
        "photo": "https://graph.org/file/8b50e21db819f296661b7.jpg",
        "button_text": "Click here to buy plan"
    },
    6: {
        "name": "👑 ULTRA PLAN",
        "duration": "Coming Soon",
        "price": "TBA",
        "description": "Premium & exclusive access\n➛ Extra benefits and features\n➛ Designed for hardcore users\n➛ Stay tuned for launch 👀",
        "photo": "https://graph.org/file/feebef43bbdf76e796b1b.jpg",
        "button_text": "Click here to buy plan"
    }
}

# Main Plan Command Handler
@Client.on_message(filters.command("plan"))
async def plan_command(bot, message):
    user_id = message.from_user.id
    user_plan_page[user_id] = 0  # 0 = main page
    
    # Main page with all plan buttons
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🆓 FREE TRIAL", callback_data="plan_1"),
         InlineKeyboardButton("🟢 BASIC PASS", callback_data="plan_2")],
        [InlineKeyboardButton("🔵 LITE", callback_data="plan_3"),
         InlineKeyboardButton("⭐ STANDARD", callback_data="plan_4")],
        [InlineKeyboardButton("💎 PRO", callback_data="plan_5"),
         InlineKeyboardButton("👑 ULTRA", callback_data="plan_6")],
        [InlineKeyboardButton("❌ CLOSE", callback_data="close")]
    ])
    
    caption = f"""**📋 PLAN SELECTION PAGE**

👋 Hey {message.from_user.mention},
Choose your preferred plan from the options below:

🆓 **FREE TRIAL** - 1 Hour Free Access
🟢 **BASIC PASS** - 7 Days @ ₹39
🔵 **LITE PLAN** - 15 Days @ ₹79
⭐ **STANDARD PLAN** - 30 Days @ ₹129
💎 **PRO PLAN** - 50 Days @ ₹199
👑 **ULTRA PLAN** - Coming Soon

Click any plan button to view details!"""
    
    msg = await message.reply_photo(
        photo='https://graph.org/file/8b50e21db819f296661b7.jpg',
        caption=caption,
        reply_markup=buttons
    )
    
    user_plan_page[user_id] = {"message_id": msg.id, "page": 0}
    await asyncio.sleep(300)
    try:
        await msg.delete()
        await message.delete()
    except:
        pass

# Callback Query Handler for Plan Navigation
@Client.on_callback_query()
async def handle_callbacks(bot, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    data = callback_query.data
    
    # Close button
    if data == "close":
        try:
            await callback_query.message.delete()
        except:
            pass
        return
    
    # Back to main page
    elif data == "back_main":
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🆓 FREE TRIAL", callback_data="plan_1"),
             InlineKeyboardButton("🟢 BASIC PASS", callback_data="plan_2")],
            [InlineKeyboardButton("🔵 LITE", callback_data="plan_3"),
             InlineKeyboardButton("⭐ STANDARD", callback_data="plan_4")],
            [InlineKeyboardButton("💎 PRO", callback_data="plan_5"),
             InlineKeyboardButton("👑 ULTRA", callback_data="plan_6")],
            [InlineKeyboardButton("❌ CLOSE", callback_data="close")]
        ])
        
        caption = f"""**📋 PLAN SELECTION PAGE**

👋 Hey {callback_query.from_user.mention},
Choose your preferred plan from the options below:

🆓 **FREE TRIAL** - 1 Hour Free Access
🟢 **BASIC PASS** - 7 Days @ ₹39
🔵 **LITE PLAN** - 15 Days @ ₹79
⭐ **STANDARD PLAN** - 30 Days @ ₹129
💎 **PRO PLAN** - 50 Days @ ₹199
👑 **ULTRA PLAN** - Coming Soon

Click any plan button to view details!"""
        
        try:
            await callback_query.message.edit_caption(
                caption=caption,
                reply_markup=buttons
            )
            user_plan_page[user_id] = {"message_id": callback_query.message.id, "page": 0}
        except:
            pass
        return
    
    # Plan selection
    elif data.startswith("plan_"):
        plan_num = int(data.split("_")[1])
        plan = PLANS[plan_num]
        
        # Navigation buttons
        nav_buttons = []
        if plan_num > 1:
            nav_buttons.append(InlineKeyboardButton("◀️ Back", callback_data=f"plan_{plan_num-1}"))
        else:
            nav_buttons.append(InlineKeyboardButton("◀️ Back", callback_data="back_main"))
        
        if plan_num < 6:
            nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"plan_{plan_num+1}"))
        else:
            nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data="plan_1"))
        
        # Action button based on plan
        if plan_num == 1:
            action_button = [InlineKeyboardButton(plan["button_text"], url="https://t.me/Anime_library_n4")]
        else:
            action_button = [InlineKeyboardButton("💳 BUY NOW", callback_data=f"payment_{plan_num}")]
        
        buttons = InlineKeyboardMarkup([
            action_button,
            nav_buttons,
            [InlineKeyboardButton("📋 Back to Plans", callback_data="back_main"),
             InlineKeyboardButton("❌ Close", callback_data="close")]
        ])
        
        caption = f"""**{plan['name']} ({plan_num}/6)**

👋 Hey {callback_query.from_user.mention},

**{plan['name']}**
⏰ {plan['duration']}
💸 Plan Price ➛ {plan['price']}

{plan['description']}"""
        
        try:
            await callback_query.message.edit_media(
                media=InputMediaPhoto(plan['photo'])
            )
            await callback_query.message.edit_caption(
                caption=caption,
                reply_markup=buttons
            )
            user_plan_page[user_id] = {"message_id": callback_query.message.id, "page": plan_num}
        except:
            try:
                await callback_query.message.delete()
                msg = await callback_query.message.reply_photo(
                    photo=plan['photo'],
                    caption=caption,
                    reply_markup=buttons
                )
                user_plan_page[user_id] = {"message_id": msg.id, "page": plan_num}
            except:
                pass
        
        await callback_query.answer(f"Viewing {plan['name']}")
    
    # Payment selection
    elif data.startswith("payment_"):
        plan_num = int(data.split("_")[1])
        plan = PLANS[plan_num]
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 Pay via UPI ID", callback_data=f"upi_{plan_num}"),
             InlineKeyboardButton("📸 Scan QR Code", callback_data=f"qr_{plan_num}")],
            [InlineKeyboardButton("◀️ Back to Plan", callback_data=f"plan_{plan_num}"),
             InlineKeyboardButton("❌ Close", callback_data="close")]
        ])
        
        caption = f"""**💳 SELECT PAYMENT METHOD**

👋 Hey {callback_query.from_user.mention},

**Plan Selected:** {plan['name']}
**Amount:** {plan['price']}
**Duration:** {plan['duration']}

Choose your preferred payment method:"""
        
        try:
            await callback_query.message.edit_caption(
                caption=caption,
                reply_markup=buttons
            )
        except:
            pass
        
        await callback_query.answer("Select payment method")
    
    # UPI Payment
    elif data.startswith("upi_"):
        plan_num = int(data.split("_")[1])
        plan = PLANS[plan_num]
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("📸 Send Payment Screenshot", url="https://t.me/Anime_library_n4")],
            [InlineKeyboardButton("◀️ Back to Payment", callback_data=f"payment_{plan_num}"),
             InlineKeyboardButton("❌ Close", callback_data="close")]
        ])
        
        caption = f"""**💵 PAY VIA UPI ID**

👋 Hey {callback_query.from_user.mention},

**Plan:** {plan['name']}
**Amount:** {plan['price']}
**Duration:** {plan['duration']}

Pay the amount according to your selected plan and enjoy plan membership!

💵 **UPI ID:** dm @PYato

‼️ **Must send screenshot after payment** to: @Anime_library_n4"""
        
        try:
            await callback_query.message.edit_caption(
                caption=caption,
                reply_markup=buttons
            )
        except:
            pass
        
        await callback_query.answer("UPI Payment Details")
    
    # QR Payment
    elif data.startswith("qr_"):
        plan_num = int(data.split("_")[1])
        plan = PLANS[plan_num]
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("📸 Send Payment Screenshot", url="https://t.me/Anime_library_n4")],
            [InlineKeyboardButton("◀️ Back to Payment", callback_data=f"payment_{plan_num}"),
             InlineKeyboardButton("❌ Close", callback_data="close")]
        ])
        
        caption = f"""**📸 SCAN QR CODE**

👋 Hey {callback_query.from_user.mention},

**Plan:** {plan['name']}
**Amount:** {plan['price']}
**Duration:** {plan['duration']}

Pay the amount according to your membership price!

📸 **QR Code:** Click here to scan
https://t.me/Anime_library_n4

‼️ **Must send screenshot after payment** to: @Anime_library_n4"""
        
        try:
            await callback_query.message.edit_caption(
                caption=caption,
                reply_markup=buttons
            )
        except:
            pass
        
        await callback_query.answer("QR Payment Details")

# Premium Command Handler (unchanged)
@Client.on_message(filters.command("premium"))
async def getpremium(bot, message):
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("ᴏᴡɴᴇʀ", url="https://t.me/Anime_library_n4"), 
         InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="close")]
    ])
    yt = await message.reply_photo(
        photo='https://graph.org/file/feebef43bbdf76e796b1b.jpg', 
        caption=Txt.PREMIUM_TXT, 
        reply_markup=buttons
    )
    await asyncio.sleep(300)
    try:
        await yt.delete()
        await message.delete()
    except:
        pass
