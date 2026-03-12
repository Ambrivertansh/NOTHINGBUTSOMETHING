import os
import json
import random
import asyncio
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandObject
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiohttp import web

# --- CONFIGURATION ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
INITIAL_MASTER_ID = int(os.getenv("MASTER_ID", 0))

# --- DATA STORAGE ---
DATA_FILE = "bot_data.json"

data = {
    "master_admins": [INITIAL_MASTER_ID] if INITIAL_MASTER_ID else [],
    "admins": [],
    "all_users": [],
    "giveaway": {
        "active": False,
        "end_time": None,
        "codes": [],
        "participants": [],
        "participant_usernames": {}, 
        "winners": {} 
    }
}

toggled_admins = set()

if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        loaded_data = json.load(f)
        data.update(loaded_data)

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

# --- HELPER FUNCTIONS ---
def is_master(user_id: int) -> bool:
    return user_id in data["master_admins"]

def is_admin(user_id: int) -> bool:
    return user_id in data["admins"] or is_master(user_id)

def get_role(user_id: int) -> str:
    if user_id in toggled_admins:
        return "user"
    if is_master(user_id):
        return "master"
    if is_admin(user_id):
        return "admin"
    return "user"

# --- BOT SETUP ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()

# --- COMMANDS ---

@router.message(Command("start"))
async def cmd_start(message: Message):
    # SECURITY FIX: Ignore if someone adds bot to a group chat
    if message.chat.type != "private": return 

    user_id = message.from_user.id
    
    if user_id not in data["all_users"]:
        data["all_users"].append(user_id)
        save_data()

    role = get_role(user_id)

    if role == "master":
        text = (
            "🛠️ *MASTER ADMIN PANEL* 🛠️\n\n"
            "Welcome back, Boss. Here are your commands:\n"
            "/addmadmin <userid> - Add a Master Admin\n"
            "/addadmin <userid> - Add a standard Admin\n"
            "/removeadmin <userid> - Remove any admin\n"
            "/setup <hours> - Start timer & clear old drop\n"
            "/code - Save codes & blast Register button\n"
            "/done - Close drop, pick winners, send luck button\n"
            "/stats - View live participants\n"
            "/broadcast <message> - DM everyone\n"
            "/toggleui - Test what normal users see"
        )
        await message.answer(text, parse_mode=ParseMode.MARKDOWN)
    
    elif role == "admin":
        text = (
            "🛠️ *ADMIN PANEL* 🛠️\n\n"
            "Welcome to the team. Here are your commands:\n"
            "/setup <hours> - Start timer & clear old drop\n"
            "/code - Save codes & blast Register button\n"
            "/done - Close drop, pick winners, send luck button\n"
            "/stats - View live participants\n"
            "/broadcast <message> - DM everyone\n"
            "/toggleui - Test what normal users see"
        )
        await message.answer(text, parse_mode=ParseMode.MARKDOWN)
    
    else:
        text = (
            "👋 *Welcome to the 𝘾𝙊𝙊𝙇𝘼𝙋𝙋𝙂𝙄𝙑𝙀𝘼𝙒𝘼𝙔 Bot!* 🚀\n\n"
            "✨ Keep an eye on this bot and the main channel for upcoming drops. "
            "When a giveaway starts, just tap the registration button to enter! 🎁"
        )
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔴 Join Updates Channel 🔴", url="https://t.me/CoolAppStore")]
        ])
        await message.answer(text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)

@router.message(Command("toggleui"))
async def cmd_toggleui(message: Message):
    if message.chat.type != "private": return 
    user_id = message.from_user.id
    if not (is_master(user_id) or is_admin(user_id)): return

    if user_id in toggled_admins:
        toggled_admins.remove(user_id)
        await message.answer("👁️ Admin powers restored. You are seeing the Admin UI.")
    else:
        toggled_admins.add(user_id)
        await message.answer("🥸 Testing Mode ON. You are now seeing what normal users see. Type /start to test.")

@router.message(Command("addmadmin"))
async def cmd_addmadmin(message: Message, command: CommandObject):
    if message.chat.type != "private": return 
    if not is_master(message.from_user.id) or get_role(message.from_user.id) == "user": return
    try:
        new_id = int(command.args)
        if new_id not in data["master_admins"]:
            data["master_admins"].append(new_id)
            save_data()
        await message.answer(f"✅ User {new_id} is now a Master Admin.")
    except (TypeError, ValueError):
        await message.answer("❌ Usage: /addmadmin <userid>")

@router.message(Command("addadmin"))
async def cmd_addadmin(message: Message, command: CommandObject):
    if message.chat.type != "private": return 
    if not is_master(message.from_user.id) or get_role(message.from_user.id) == "user": return
    try:
        new_id = int(command.args)
        if new_id not in data["admins"]:
            data["admins"].append(new_id)
            save_data()
        await message.answer(f"✅ User {new_id} is now an Admin.")
    except (TypeError, ValueError):
        await message.answer("❌ Usage: /addadmin <userid>")

@router.message(Command("removeadmin"))
async def cmd_removeadmin(message: Message, command: CommandObject):
    if message.chat.type != "private": return 
    if not is_master(message.from_user.id) or get_role(message.from_user.id) == "user": return
    try:
        target_id = int(command.args)
        if target_id in data["master_admins"] and target_id != INITIAL_MASTER_ID:
            data["master_admins"].remove(target_id)
        if target_id in data["admins"]:
            data["admins"].remove(target_id)
        save_data()
        await message.answer(f"✅ User {target_id} removed from all admin roles.")
    except (TypeError, ValueError):
        await message.answer("❌ Usage: /removeadmin <userid>")

@router.message(Command("setup"))
async def cmd_setup(message: Message, command: CommandObject):
    if message.chat.type != "private": return 
    if not is_admin(message.from_user.id) or get_role(message.from_user.id) == "user": return
    try:
        hours = float(command.args)
        end_time = datetime.now() + timedelta(hours=hours)
        
        data["giveaway"]["active"] = True
        data["giveaway"]["end_time"] = end_time.timestamp()
        data["giveaway"]["codes"] = []
        data["giveaway"]["participants"] = []
        data["giveaway"]["participant_usernames"] = {} 
        data["giveaway"]["winners"] = {}
        save_data()
        
        await message.answer(f"⚙️ *Giveaway initialized for {hours} hours!*\n\nPlease use the `/code` command to add the codes now.", parse_mode=ParseMode.MARKDOWN)
    except (TypeError, ValueError):
        await message.answer("⚠️ Format error. Please use: /setup <hours>")

@router.message(Command("code"))
async def cmd_code(message: Message):
    if message.chat.type != "private": return 
    if not is_admin(message.from_user.id) or get_role(message.from_user.id) == "user": return
    
    lines = message.text.split('\n')
    if len(lines) < 2:
        await message.answer("❌ Paste codes below the command.\nExample:\n/code\nCODE1\nCODE2")
        return

    codes = [line.strip() for line in lines[1:] if line.strip()]
    data["giveaway"]["codes"] = codes
    save_data()

    await message.answer("✅ Codes saved! Broadcasting the drop to all users now...")

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 𝗥𝗘𝗚𝗜𝗦𝗧𝗘𝗥 𝗡𝗢𝗪 🟢", callback_data="register")],
        [InlineKeyboardButton(text="🔴 Join Updates Channel 🔴", url="https://t.me/CoolAppStore")]
    ])
    
    broadcast_text = (
        "🎊 *𝗠𝗔𝗦𝗦𝗜𝗩𝗘 𝗚𝗜𝗩𝗘𝗔𝗪𝗔𝗬 𝗔𝗟𝗘𝗥𝗧!* 🎊\n\n"
        f"🎁 We are giving away *{len(codes)}* exclusive codes!\n"
        "⏳ Don't miss out, tap the green button below to enter!\n\n"
        "👇👇👇"
    )
    
    success_count = 0
    for user_id in data["all_users"]:
        # SECURITY FIX: Don't spam admins with user broadcasts
        if get_role(user_id) in ["admin", "master"]: 
            continue 
            
        try:
            await bot.send_message(
                chat_id=user_id, 
                text=broadcast_text, 
                reply_markup=markup,
                parse_mode=ParseMode.MARKDOWN
            )
            success_count += 1
            await asyncio.sleep(0.05)
        except Exception: 
            pass 
            
    await message.answer(f"🚀 *Giveaway Live!* Successfully pushed to {success_count} normal users.", parse_mode=ParseMode.MARKDOWN)

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    if message.chat.type != "private": return 
    if not data["giveaway"]["active"]:
        await message.answer("⚠️ There is no active giveaway right now. Stay tuned for the next drop!")
        return
        
    role = get_role(message.from_user.id)
    participants = data["giveaway"]["participants"]
    count = len(participants)
    
    if role in ["admin", "master"]:
        if count == 0:
            await message.answer("📊 *Admin Live Stats*\n\n🔥 Total Registered: *0*\n\n📋 *Participant IDs:*\nNo users registered yet.", parse_mode=ParseMode.MARKDOWN)
            return
        
        await message.answer(f"📊 *Admin Live Stats*\n\n🔥 Total Registered: *{count}*\n\n📋 *Participants:*", parse_mode=ParseMode.MARKDOWN)
        
        lines = []
        for uid in participants:
            uname = data["giveaway"]["participant_usernames"].get(str(uid), "No Username")
            lines.append(f"ID: {uid} | Username: @{uname}")
            
        chunk = ""
        for line in lines:
            if len(chunk) + len(line) + 1 > 4000:
                await message.answer(chunk) 
                chunk = line + "\n"
            else:
                chunk += line + "\n"
        if chunk:
            await message.answer(chunk)
            
    else:
        await message.answer(f"📊 *Live Giveaway Stats*\n\n🔥 Total Users Registered: *{count}*\n\n⏳ Tap the registration button on the main message to join!", parse_mode=ParseMode.MARKDOWN)

@router.message(Command("done"))
async def cmd_done(message: Message):
    if message.chat.type != "private": return 
    if not is_admin(message.from_user.id) or get_role(message.from_user.id) == "user": return
    
    if not data["giveaway"]["active"]:
        await message.answer("❌ No active giveaway to close.")
        return

    data["giveaway"]["active"] = False
    
    participants = data["giveaway"]["participants"]
    codes = data["giveaway"]["codes"]
    
    num_winners = min(len(participants), len(codes))
    winners = random.sample(participants, num_winners)
    
    for i in range(num_winners):
        data["giveaway"]["winners"][str(winners[i])] = codes[i]
        
    save_data()

    await message.answer(f"✅ Giveaway closed! {num_winners} winners chosen.\nBlasting the 'See your luck' button...")

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🍀 See your luck 🍀", callback_data="check_luck")]
    ])
    
    for user_id in participants:
        try:
            await bot.send_message(
                chat_id=user_id, 
                text="🏁 *THE DRAW IS COMPLETE!* 🏁\n\nClick below to see if you won a code!", 
                reply_markup=markup,
                parse_mode=ParseMode.MARKDOWN
            )
            await asyncio.sleep(0.05)
        except Exception:
            pass

@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, command: CommandObject):
    if message.chat.type != "private": return 
    if not is_admin(message.from_user.id) or get_role(message.from_user.id) == "user": return
    
    if not command.args:
        await message.answer("❌ Usage: /broadcast Hello everyone!")
        return

    success_count = 0
    await message.answer("⏳ Broadcasting...")
    for user_id in data["all_users"]:
        if get_role(user_id) in ["admin", "master"]: continue 
        
        try:
            await bot.send_message(chat_id=user_id, text=f"📢 {command.args}")
            success_count += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass
    await message.answer(f"✅ Broadcast sent to {success_count} normal users!")

# --- CALLBACK (BUTTON) HANDLERS ---
@router.callback_query(F.data == "register")
async def cb_register(callback: CallbackQuery):
    user_id = callback.from_user.id
    username = callback.from_user.username or "No Username" 
    
    if is_admin(user_id) and user_id not in toggled_admins:
        await callback.answer("⚠️ You are an Admin. Use /toggleui to test buttons.", show_alert=True)
        return

    if not data["giveaway"]["active"]:
        await callback.answer("❌ This giveaway has already ended!", show_alert=True)
        return
        
    if data["giveaway"]["end_time"] and datetime.now().timestamp() > data["giveaway"]["end_time"]:
         await callback.answer("⏰ Time is up! You cannot register anymore.", show_alert=True)
         return

    if user_id in data["giveaway"]["participants"]:
        await callback.answer("✅ You are already registered! Just wait for the results.", show_alert=True)
        return
        
    # SECURITY FIX: Ensure they are in the all_users list even if they never typed /start
    if user_id not in data["all_users"]:
        data["all_users"].append(user_id)

    data["giveaway"]["participants"].append(user_id)
    data["giveaway"]["participant_usernames"][str(user_id)] = username 
    save_data()
    
    try:
        await bot.send_message(chat_id=user_id, text="🎉 *SUCCESS!* You are registered for the drop!", parse_mode=ParseMode.MARKDOWN)
        await callback.answer("✅ Registered successfully!")
    except TelegramAPIError:
        # SECURITY FIX: Catch users who clicked from a forwarded message but blocked the bot
        data["giveaway"]["participants"].remove(user_id)
        del data["giveaway"]["participant_usernames"][str(user_id)]
        await callback.answer("⚠️ ERROR: You must send /start to the bot directly before registering!", show_alert=True)

@router.callback_query(F.data == "check_luck")
async def cb_check_luck(callback: CallbackQuery):
    user_id = callback.from_user.id
    str_user_id = str(user_id)
    
    if str_user_id in data["giveaway"]["winners"]:
        winning_code = data["giveaway"]["winners"][str_user_id]
        
        try:
            await bot.send_message(
                chat_id=user_id, 
                text=f"🏆 *CONGRATULATIONS!* 🏆\n\nYour secret code is: `{winning_code}`", 
                parse_mode=ParseMode.MARKDOWN
            )
            await callback.answer(f"🎉 YOU WON! 🎉\n\nYour code is:\n{winning_code}", show_alert=True)
        except TelegramAPIError:
            await callback.answer(f"🎉 YOU WON! 🎉\nYour code is:\n{winning_code}\n\n(Note: Unblock bot to get DM)", show_alert=True)
    else:
        await callback.answer("Better luck next time! 😔", show_alert=True)

# --- KEEP-ALIVE WEB SERVER ---
async def keep_alive(request):
    return web.Response(text="Bot is securely alive and running on Render!")

async def main():
    if not BOT_TOKEN:
        print("CRITICAL ERROR: BOT_TOKEN is missing!")
        return
    
    dp.include_router(router)
    
    app = web.Application()
    app.router.add_get('/', keep_alive)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

    print("Bot is booting up with aiogram on a Web Service...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
