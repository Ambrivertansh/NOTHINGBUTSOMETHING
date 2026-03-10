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
    db_query("INSERT OR IGNORE INTO state (key, value) VALUES ('active', '0')", commit=True)

def is_admin(user_id):
    if user_id == MASTER_ADMIN: 
        return True
    return bool(db_query("SELECT user_id FROM admins WHERE user_id = ?", (user_id,), fetchone=True))

# --- 3. BOT LOGIC & COMMANDS ---

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    
    # Silently add to broadcast list
    db_query("INSERT OR IGNORE INTO all_users (user_id) VALUES (?)", (user_id,), commit=True)
    
    won_code = db_query("SELECT code FROM codes WHERE winner_id = ?", (user_id,), fetchone=True)
    
    if won_code:
        await message.reply(f"🎉 **CONGRATULATIONS!** 🎉\n\nYou won the giveaway! 🏆\nHere is your code:\n\n`{won_code[0]}`\n\nEnjoy!", parse_mode="Markdown")
    else:
        await message.reply("👋 **Welcome to the 𝘾𝙊𝙊𝙇𝘼𝙋𝙋𝙂𝙄𝙑𝙀𝘼𝙒𝘼𝙔 Bot!** 🚀\n\n✨ Keep an eye on this bot and the main channel for upcoming drops. When a giveaway starts, just tap the registration button to enter! 🎁")

@dp.message(Command("setbotadmin"))
async def set_admin(message: types.Message):
    if not is_admin(message.from_user.id): 
        return
    try:
        new_id = int(message.text.split()[1])
        db_query("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (new_id,), commit=True)
        await message.reply(f"✅ Success! User ID {new_id} is now an admin.")
    except:
        await message.reply("⚠️ Error. Please use the exact format: /setbotadmin <userid>")

@dp.message(Command("broadcast"))
async def broadcast_cmd(message: types.Message):
    if not is_admin(message.from_user.id): 
        return
    
    text_to_send = message.text.replace("/broadcast", "").strip()
    
    if not text_to_send:
        await message.reply("⚠️ Please type a message to send. Example:\n`/broadcast Hey everyone, new drop in 5 mins!`", parse_mode="Markdown")
        return
        
    users = db_query("SELECT user_id FROM all_users", fetchall=True)
    success = 0
    
    await message.reply(f"⏳ Broadcasting to {len(users)} users. Please wait...")
    
    for u in users:
        try:
            await bot.send_message(u[0], text_to_send)
            success += 1
            await asyncio.sleep(0.05) # Anti-ban sleep timer
        except Exception:
            pass 
            
    await message.reply(f"✅ **Broadcast Complete!**\nMessage successfully sent to {success} users.", parse_mode="Markdown")

@dp.message(Command("setup"))
async def setup_cmd(message: types.Message):
    if not is_admin(message.from_user.id): 
        return
    try:
        hours = float(message.text.split()[1])
        end_time = time.time() + (hours * 3600)
        
        db_query("UPDATE state SET value = ? WHERE key = 'active'", ("1",), commit=True)
        db_query("INSERT OR REPLACE INTO state (key, value) VALUES ('end_time', ?)", (str(end_time),), commit=True)
        db_query("DELETE FROM users", commit=True)
        db_query("DELETE FROM codes", commit=True)
        
        await message.reply(f"⚙️ **Giveaway initialized for {hours} hours!**\n\nPlease use the `/code` command to add the codes now.")
    except:
        await message.reply("⚠️ Format error. Please use: /setup <hours>\nExample: /setup 2.5")

@dp.message(Command("code"))
async def process_codes(message: types.Message):
    if not is_admin(message.from_user.id): 
        return
    
    is_active = db_query("SELECT value FROM state WHERE key = 'active'", fetchone=True)
    count_codes = db_query("SELECT COUNT(*) FROM codes", fetchone=True)[0]
    
    if is_active and is_active[0] == "1" and count_codes == 0:
        lines = message.text.split('\n')[1:]
        lines = [line.strip() for line in lines if line.strip()]
        
        if not lines:
            await message.reply("⚠️ No codes found! Please format exactly like this:\n/code\nCODE1\nCODE2")
            return
            
        for code in lines:
            db_query("INSERT INTO codes (code) VALUES (?)", (code,), commit=True)
        
        # UI Polish: Using Emoji Blocks for the "Colored Button" illusion
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🟢 𝗥𝗘𝗚𝗜𝗦𝗧𝗘𝗥 𝗡𝗢𝗪 🟢", callback_data="register")],
            [InlineKeyboardButton(text="🔴 Join Updates Channel 🔴", url="https://t.me/CoolAppStore")]
        ])
        text = f"🎊 **𝗠𝗔𝗦𝗦𝗜𝗩𝗘 𝗚𝗜𝗩𝗘𝗔𝗪𝗔𝗬 𝗔𝗟𝗘𝗥𝗧!** 🎊\n\n🎁 We are giving away **{len(lines)}** exclusive codes!\n⏳ Don't miss out, tap the green button below to enter!\n\n👇👇👇"
        await message.answer(text, reply_markup=keyboard)
    else:
        await message.reply("⚠️ No active giveaway is waiting for codes. Use /setup first.")

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

@dp.message(Command("done"))
async def done_cmd(message: types.Message):
    if not is_admin(message.from_user.id): 
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
        
    winner_text = "\n".join([f"🏆 Winner: `{w}`" for w in winners])
    await message.answer(f"🎉 **𝗚𝗜𝗩𝗘𝗔𝗪𝗔𝗬 𝗘𝗡𝗗𝗘𝗗!** 🎉\n\nHere are the lucky winners:\n{winner_text}\n\n✨ Winners, please send /start to this bot to claim your code!", parse_mode="Markdown")

# --- 4. KEEP-ALIVE WEB SERVER (For Render 24/7 Uptime) ---
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
