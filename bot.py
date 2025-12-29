import random
import math
import logging
import sqlite3
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# ================= CONFIG =================
BOT_TOKEN = "7422247259:AAGIZlgEPugM910XYHlhgSW5l3UAq4QJi-Y" 
OWNER_ID = 1101488645 

TOTAL_POKEMON = 151 
SHINY_CHANCE = 0.01  # 1% chance (Rare)

# Fill this dictionary or use a library like 'pokebase' for the full 1025
POKEMON_NAMES = {
    1: "Bulbasaur", 2: "Ivysaur", 3: "Venusaur",
    4: "Charmander", 5: "Charmeleon", 6: "Charizard",
    7: "Squirtle", 8: "Wartortle", 9: "Blastoise",
    25: "Pikachu"
}

NATURES = ["Hardy", "Lonely", "Brave", "Adamant", "Naughty", "Bold", "Docile", "Relaxed", "Impish", "Lax", "Timid", "Hasty", "Serious", "Jolly", "Naive", "Modest", "Mild", "Quiet", "Bashful", "Rash", "Calm", "Gentle", "Sassy", "Careful", "Quirky"]

# ================= DATABASE SETUP =================
conn = sqlite3.connect("pokemon.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, coins INTEGER)")
cur.execute("""CREATE TABLE IF NOT EXISTS pokemons (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, pid INTEGER, 
    shiny INTEGER, nature TEXT, iv_hp INTEGER, iv_atk INTEGER, 
    iv_def INTEGER, iv_spa INTEGER, iv_spd INTEGER, iv_spe INTEGER)""")
cur.execute("CREATE TABLE IF NOT EXISTS guesses (chat_id INTEGER PRIMARY KEY, pid INTEGER, shiny INTEGER)")
conn.commit()

# ================= HELPERS =================
def get_name(pid):
    return POKEMON_NAMES.get(pid, f"Pokemon-{pid}")

def get_sprite(pid, shiny=False):
    """Returns the URL for the Pokemon sprite."""
    if shiny:
        return f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/shiny/{pid}.png"
    return f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{pid}.png"

def random_ivs():
    return [random.randint(0, 31) for _ in range(6)]

# ================= COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cur.execute("SELECT user_id FROM users WHERE user_id=?", (uid,))
    if not cur.fetchone():
        cur.execute("INSERT INTO users VALUES (?, ?)", (uid, 100))
        conn.commit()
        
        pid = random.randint(1, TOTAL_POKEMON)
        shiny = 1 if random.random() < SHINY_CHANCE else 0
        ivs = random_ivs()
        nature = random.choice(NATURES)
        
        # FIXED: Corrected number of placeholders (10)
        cur.execute("INSERT INTO pokemons (user_id, pid, shiny, nature, iv_hp, iv_atk, iv_def, iv_spa, iv_spd, iv_spe) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                    (uid, pid, shiny, nature, *ivs))
        conn.commit()
        
        name = get_name(pid)
        shiny_tag = " ✨" if shiny else ""
        await update.message.reply_photo(photo=get_sprite(pid, shiny), caption=f"Welcome! You received a **{name}{shiny_tag}** as your starter!", parse_mode="Markdown")
    else:
        await update.message.reply_text("You've already started your journey!")

async def guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pid = random.randint(1, TOTAL_POKEMON)
    shiny = 1 if random.random() < SHINY_CHANCE else 0
    
    cur.execute("INSERT OR REPLACE INTO guesses (chat_id, pid, shiny) VALUES (?, ?, ?)", (update.effective_chat.id, pid, shiny))
    conn.commit()
    
    await update.message.reply_photo(
        photo=get_sprite(pid, shiny), 
        caption="❓ **A wild Pokémon appeared!**\nUse `/catch <name>` to claim it!", 
        parse_mode="Markdown"
    )

async def catch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage: `/catch <name>`")
    
    uid = update.effective_user.id
    chat_id = update.effective_chat.id
    user_guess = " ".join(context.args).strip().lower()

    cur.execute("SELECT pid, shiny FROM guesses WHERE chat_id=?", (chat_id,))
    row = cur.fetchone()
    
    if not row:
        return await update.message.reply_text("Nothing to catch! Use /guess first.")
    
    pid, shiny = row
    correct_name = get_name(pid).lower()

    if user_guess == correct_name:
        ivs = random_ivs()
        nature = random.choice(NATURES)
        
        # Add to collection
        cur.execute("INSERT INTO pokemons (user_id, pid, shiny, nature, iv_hp, iv_atk, iv_def, iv_spa, iv_spd, iv_spe) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                    (uid, pid, shiny, nature, *ivs))
        cur.execute("DELETE FROM guesses WHERE chat_id=?", (chat_id,))
        conn.commit()
        
        shiny_tag = " ✨" if shiny else ""
        await update.message.reply_text(f"✅ Success! You caught **{get_name(pid)}{shiny_tag}**!")
    else:
        await update.message.reply_text("❌ Wrong name! Try again.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage: `/stats <pokemon_name>`")
    
    uid = update.effective_user.id
    search_name = " ".join(context.args).strip().lower()
    
    # Simple ID lookup
    target_pid = next((pid for pid, name in POKEMON_NAMES.items() if name.lower() == search_name), None)
    
    if not target_pid:
        return await update.message.reply_text("Pokemon not found in Database.")

    cur.execute("SELECT shiny, nature, iv_hp, iv_atk, iv_def, iv_spa, iv_spd, iv_spe FROM pokemons WHERE user_id=? AND pid=? ORDER BY id DESC LIMIT 1", (uid, target_pid))
    p = cur.fetchone()

    if not p:
        return await update.message.reply_text(f"You don't own a {search_name.capitalize()}.")

    iv_total = sum(p[2:])
    iv_percent = round((iv_total / 186) * 100, 2)
    shiny_tag = " ✨ SHINY ✨" if p[0] else ""

    stat_msg = (
        f"📊 **{get_name(target_pid)} Stats**{shiny_tag}\n"
        f"🆔 **PokeID:** `{target_pid}`\n"
        f"🧠 **Nature:** `{p[1]}`\n"
        f"📈 **IV Percentage:** `{iv_percent}%` (`{iv_total}/186`)\n"
        f"--- IV Details ---\n"
        f"HP: `{p[2]}` | ATK: `{p[3]}` | DEF: `{p[4]}`\n"
        f"SpA: `{p[5]}` | SpD: `{p[6]}` | SPE: `{p[7]}`"
    )
    
    await update.message.reply_photo(photo=get_sprite(target_pid, p[0]), caption=stat_msg, parse_mode="Markdown")

# ================= APP INIT =================
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("guess", guess))
app.add_handler(CommandHandler("catch", catch))
app.add_handler(CommandHandler("stats", stats))

print("Bot is live...")
app.run_polling()
