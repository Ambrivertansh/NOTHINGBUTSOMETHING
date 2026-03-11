import os
import asyncio
import sqlite3
import random
import time
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiohttp import web

# --- 1. CONFIGURATION ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TOKEN_HERE")
MASTER_ADMIN = int(os.getenv("MASTER_ADMIN", "0"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- 2. DATABASE ARCHITECTURE ---
def db_query(query, args=(), fetchone=False, fetchall=False, commit=False):
    conn = sqlite3.connect('giveaway.db')
    c = conn.cursor()
    c.execute(query, args)
    res = None
    if fetchone:
        res = c.fetchone()
    elif fetchall:
        res = c.fetchall()
    if commit:
        conn.commit()
    conn.close()
    return res

def init_db():
    db_query('''CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)''', commit=True)
    db_query('''CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT)''', commit=True)
    db_query('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)''', commit=True) 
    db_query('''CREATE TABLE IF NOT EXISTS all_users (user_id INTEGER PRIMARY KEY)''', commit=True)
    db_query('''CREATE TABLE IF NOT EXISTS codes (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT, winner_id INTEGER)''', commit=True)
    db_query('''CREATE TABLE IF NOT EXISTS ui_mode (user_id INTEGER PRIMARY KEY, mode TEXT)''', commit=True) # New table for UI Toggle
    db_query("INSERT OR IGNORE INTO state (key, value) VALUES ('active', '0')", commit=True)

# Checks if they are legally an admin
def is_actual_admin(user_id):
    if user_id == MASTER_ADMIN: 
        return True
    return bool(db_query("SELECT user_id FROM admins WHERE user_id = ?", (user_id,), fetchone=True))

# Checks if they are an admin AND haven't toggled to User UI
def is_effective_admin(user_id):
    if not is_actual_admin(user_id): return False
    mode = db_query("SELECT mode FROM ui_mode WHERE user_id = ?", (user_id,), fetchone=True)
    if mode and mode[0] == 'user': return False
    return True

# --- 3. MASTER ADMIN ONLY COMMANDS ---

@dp.message(Command("addadmin"))
async def add_admin(message: types.Message):
    if message.from_user.id != MASTER_ADMIN: 
        return
    try:
        new_id = int(message.text.split()[1])
        db_query("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (new_id,), commit=True)
        await message.reply(f"✅ Success! User ID `{new_id}` has been granted Admin UI.", parse_mode="Markdown")
    except:
        await message.reply("⚠️ Error. Format: /addadmin <userid>")

@dp.message(Command("removeadmin"))
async def remove_admin(message: types.Message):
    if message.from_user.id != MASTER_ADMIN: 
        return
    try:
        target_id = int(message.text.split()[1])
        db_query("DELETE FROM admins WHERE user_id = ?", (target_id,), commit=True)
        # Also reset their UI mode if they get fired
        db_query("DELETE FROM ui_mode WHERE user_id = ?", (target_id,), commit=True) 
        await message.reply(f"🚫 Success! User ID `{target_id}` has been removed from admins.", parse_mode="Markdown")
    except:
        await message.reply("⚠️ Error. Format: /removeadmin <userid>")

# --- 4. QA TOGGLE COMMAND ---

@dp.message(Command("toggleui"))
async def toggle_ui(message: types.Message):
    user_id = message.from_user.id
    if not is_actual_admin(user_id): 
        return
        
    current_mode = db_query("SELECT mode FROM ui_mode WHERE user_id = ?", (user_id,), fetchone=True)
    
    if current_mode and current_mode[0] == 'user':
        # Switch back to Admin UI
        db_query("UPDATE ui_mode SET mode = 'admin' WHERE user_id = ?", (user_id,), commit=True)
        await message.reply("🔓 **ADMIN UI RESTORED**\nYou can now use /setup, /code, /broadcast, etc.", parse_mode="Markdown")
    else:
        # Switch to User UI
        db_query("INSERT OR REPLACE INTO ui_mode (user_id, mode) VALUES (?, 'user')", (user_id,), commit=True)
        await message.reply("🎭 **USER UI ACTIVATED**\nAdmin commands are now hidden from you. Type `/toggleui` to switch back.", parse_mode="Markdown")

# --- 5. STANDARD ADMIN COMMANDS ---

@dp.message(Command("setup"))
async def setup_cmd(message: types.Message):
    if not is_effective_admin(message.from_user.id): return
    try:
        hours = float(message.text.split()[1])
        end_time = time.time() + (hours * 3600)
        
        db_query("UPDATE state SET value = ? WHERE key = 'active'", ("1",), commit=True)
        db_query("INSERT OR REPLACE INTO state (key, value) VALUES ('end_time', ?)", (str(end_time),), commit=True)
        db_query("DELETE FROM users", commit=True)
        db_query("DELETE FROM codes", commit=True)
        
        await message.reply(f"⚙️ **Giveaway initialized for {hours} hours!**\n\nPlease use the `/code` command to add the codes now.")
    except:
        await message.reply("⚠️ Format error. Please use: /setup <hours>")

@dp.message(Command("code"))
async def process_codes(message: types.Message):
    if not is_effective_admin(message.from_user.id): return
    
    is_active = db_query("SELECT value FROM state WHERE key = 'active'", fetchone=True)
    count_codes = db_query("SELECT COUNT(*) FROM codes", fetchone=True)[0]
    
    if is_active and is_active[0] == "1" and count_codes == 0:
        lines = message.text.split('\n')[1:]
        lines = [line.strip() for line in lines if line.strip()]
        
        if not lines:
            await message.reply("⚠️ No codes found! Format:\n/code\nCODE1\nCODE2")
            return
            
        for code in lines:
            db_query("INSERT INTO codes (code) VALUES (?)", (code,), commit=True)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🟢 𝗥𝗘𝗚𝗜𝗦𝗧𝗘𝗥 𝗡𝗢𝗪 🟢", callback_data="register")],
            [InlineKeyboardButton(text="🔴 Join Updates Channel 🔴", url="https://t.me/CoolAppStore")]
        ])
        text = f"🎊 **𝗠𝗔𝗦𝗦𝗜𝗩𝗘 𝗚𝗜𝗩𝗘𝗔𝗪𝗔𝗬 𝗔𝗟𝗘𝗥𝗧!** 🎊\n\n🎁 We are giving away **{len(lines)}** exclusive codes!\n⏳ Don't miss out, tap the green button below to enter!\n\n👇👇👇"
        
        await message.reply("✅ Codes saved! Broadcasting the drop to all users now...")
        
        users = db_query("SELECT user_id FROM all_users", fetchall=True)
        success = 0
        for u in users:
            try:
                await bot.send_message(u[0], text, reply_markup=keyboard)
                success += 1
                await asyncio.sleep(0.05) 
            except Exception:
                pass 
                
        await message.reply(f"🚀 **Giveaway Live!** Successfully pushed to {success} users.")
    else:
        await message.reply("⚠️ No active giveaway is waiting for codes. Use /setup first.")

@dp.message(Command("broadcast"))
async def broadcast_cmd(message: types.Message):
    if not is_effective_admin(message.from_user.id): return
    text_to_send = message.text.replace("/broadcast", "").strip()
    if not text_to_send:
        await message.reply("⚠️ Please type a message to send.")
        return
        
    users = db_query("SELECT user_id FROM all_users", fetchall=True)
    success = 0
    await message.reply(f"⏳ Broadcasting to {len(users)} users...")
    for u in users:
        try:
            await bot.send_message(u[0], text_to_send)
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass 
    await message.reply(f"✅ **Broadcast Complete!**\nMessage successfully sent to {success} users.", parse_mode="Markdown")

@dp.message(Command("done"))
async def done_cmd(message: types.Message):
    if not is_effective_admin(message.from_user.id): return
    
    is_active = db_query("SELECT value FROM state WHERE key = 'active'", fetchone=True)
    if not is_active or is_active[0] != "1":
        await message.reply("⚠️ No active giveaway to end.")
        return

    db_query("UPDATE state SET value = '0' WHERE key = 'active'", commit=True)
    codes = db_query("SELECT id FROM codes WHERE winner_id IS NULL", fetchall=True)
    users = db_query("SELECT user_id FROM users", fetchall=True)
    
    num_winners = len(codes)
    participants = [u[0] for u in users]
    
    if not participants:
        await message.reply("⚠️ Giveaway ended, but nobody registered!")
        return
        
    winners = random.sample(participants, min(num_winners, len(participants)))
    
    for i, winner_id in enumerate(winners):
        code_id = codes[i][0]
        db_query("UPDATE codes SET winner_id = ? WHERE id = ?", (winner_id, code_id), commit=True)
        
    winner_text = "\n".join([f"🏆 `{w}`" for w in winners])
    await message.reply(f"✅ **𝗚𝗜𝗩𝗘𝗔𝗪𝗔𝗬 𝗘𝗡𝗗𝗘𝗗!**\n\n{len(winners)} codes distributed. Here are the winning IDs:\n{winner_text}", parse_mode="Markdown")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🍀 See your luck 🍀", callback_data="check_win")]
    ])
    end_text = "🚨 **𝗚𝗜𝗩𝗘𝗔𝗪𝗔𝗬 𝗢𝗩𝗘𝗥!** 🚨\n\nThe drop has officially ended and winners have been drawn! Tap the button below to see if you won."
    
    await message.reply("⏳ Broadcasting end message to users...")
    success = 0
    for p in participants:
        try:
            await bot.send_message(p, end_text, reply_markup=keyboard)
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass
    await message.reply(f"✅ Broadcast complete. Sent to {success} users.")

# --- 6. PUBLIC USER COMMANDS ---

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    db_query("INSERT OR IGNORE INTO all_users (user_id) VALUES (?)", (user_id,), commit=True)
    
    won_code = db_query("SELECT code FROM codes WHERE winner_id = ?", (user_id,), fetchone=True)
    
    if won_code:
        await message.reply(f"🎉 **CONGRATULATIONS!** 🎉\n\nYou won the giveaway! 🏆\nHere is your code:\n\n`{won_code[0]}`\n\nEnjoy!", parse_mode="Markdown")
    else:
        await message.reply("👋 **Welcome to the 𝘾𝙊𝙊𝙇𝘼𝙋𝙋𝙂𝙄𝙑𝙀𝘼𝙒𝘼𝙔 Bot!** 🚀\n\n✨ Keep an eye on this bot and the main channel for upcoming drops. When a giveaway starts, just tap the registration button to enter! 🎁")

@dp.callback_query(F.data == "register")
async def register_callback(call: CallbackQuery):
    is_active = db_query("SELECT value FROM state WHERE key = 'active'", fetchone=True)
    if not is_active or is_active[0] != "1":
        await call.answer("There is no active giveaway right now.", show_alert=True)
        return

    end_time_str = db_query("SELECT value FROM state WHERE key = 'end_time'", fetchone=True)[0]
    if time.time() > float(end_time_str):
        await call.answer("⏳ The registration time has ended!", show_alert=True)
        await call.message.edit_reply_markup(reply_markup=None)
        return

    user_id = call.from_user.id
    try:
        db_query("INSERT INTO users (user_id) VALUES (?)", (user_id,), commit=True)
        await call.answer("✅ Successfully registered! Good luck!", show_alert=True)
    except sqlite3.IntegrityError:
        await call.answer("⚠️ You are already registered for this drop!", show_alert=True)

@dp.callback_query(F.data == "check_win")
async def check_win_callback(call: CallbackQuery):
    user_id = call.from_user.id
    won_code = db_query("SELECT code FROM codes WHERE winner_id = ?", (user_id,), fetchone=True)
    
    if won_code:
        await call.answer()
        await bot.send_message(user_id, f"🎉 **𝗖𝗢𝗡𝗚𝗥𝗔𝗧𝗨𝗟𝗔𝗧𝗜𝗢𝗡𝗦!** 🎉\n\nYou are a winner! 🏆\nHere is your exclusive code:\n\n`{won_code[0]}`\n\nEnjoy!", parse_mode="Markdown")
    else:
        await call.answer("😢 Better luck next time! You didn't win this round.", show_alert=True)

# --- 7. KEEP-ALIVE WEB SERVER (For Render) ---
async def keep_alive(request):
    return web.Response(text="Giveaway Bot is Alive and running 24/7!")

async def main():
    init_db()
    app = web.Application()
    app.router.add_get('/', keep_alive)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
