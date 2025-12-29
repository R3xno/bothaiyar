import random
import logging
import sqlite3
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ================= CONFIG =================
BOT_TOKEN = "7422247259:AAGIZlgEPugM910XYHlhgSW5l3UAq4QJi-Y" 
TOTAL_POKEMON = 151 
SHINY_CHANCE = 0.05  # Increased to 5% so you can actually see them testing!

# Expanded dictionary for testing
POKEMON_NAMES = {
    1: "Bulbasaur", 2: "Ivysaur", 3: "Venusaur",
    4: "Charmander", 5: "Charmeleon", 6: "Charizard",
    7: "Squirtle", 8: "Wartortle", 9: "Blastoise",
    25: "Pikachu", 150: "Mewtwo", 151: "Mew"
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
    """Returns High Quality 3D/Official Artwork."""
    # Official Artwork is much higher resolution than the standard sprites
    base = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork"
    if shiny:
        return f"{base}/shiny/{pid}.png"
    return f"{base}/{pid}.png"

def generate_hint(name):
    """Replaces roughly 50% of letters with underscores."""
    hint = ""
    for char in name:
        if char == " ":
            hint += " "
        elif random.random() > 0.4:
            hint += char
        else:
            hint += "_"
    return hint

def random_ivs():
    return [random.randint(0, 31) for _ in range(6)]

# ================= COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cur.execute("SELECT user_id FROM users WHERE user_id=?", (uid,))
    if not cur.fetchone():
        cur.execute("INSERT INTO users VALUES (?, ?)", (uid, 100))
        pid = random.randint(1, TOTAL_POKEMON)
        shiny = 1 if random.random() < SHINY_CHANCE else 0
        ivs, nature = random_ivs(), random.choice(NATURES)
        cur.execute("INSERT INTO pokemons (user_id, pid, shiny, nature, iv_hp, iv_atk, iv_def, iv_spa, iv_spd, iv_spe) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                    (uid, pid, shiny, nature, *ivs))
        conn.commit()
        await update.message.reply_photo(photo=get_sprite(pid, shiny), caption=f"Welcome! You received a **{get_name(pid)}** as your starter!", parse_mode="Markdown")
    else:
        await update.message.reply_text("You've already started your journey!")

async def guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pid = random.randint(1, TOTAL_POKEMON)
    shiny = 1 if random.random() < SHINY_CHANCE else 0
    cur.execute("INSERT OR REPLACE INTO guesses (chat_id, pid, shiny) VALUES (?, ?, ?)", (update.effective_chat.id, pid, shiny))
    conn.commit()
    await update.message.reply_photo(photo=get_sprite(pid, shiny), caption="❓ **A wild Pokémon appeared!**\nUse `/catch <name>` to claim it!", parse_mode="Markdown")

async def catch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage: `/catch <name>`")
    
    uid, chat_id = update.effective_user.id, update.effective_chat.id
    user_guess = " ".join(context.args).strip().lower()
    cur.execute("SELECT pid, shiny FROM guesses WHERE chat_id=?", (chat_id,))
    row = cur.fetchone()
    
    if not row:
        return await update.message.reply_text("Nothing to catch! Use /guess first.")
    
    pid, shiny = row
    correct_name = get_name(pid).lower()

    if user_guess == correct_name:
        ivs, nature = random_ivs(), random.choice(NATURES)
        cur.execute("INSERT INTO pokemons (user_id, pid, shiny, nature, iv_hp, iv_atk, iv_def, iv_spa, iv_spd, iv_spe) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (uid, pid, shiny, nature, *ivs))
        cur.execute("DELETE FROM guesses WHERE chat_id=?", (chat_id,))
        conn.commit()
        tag = " ✨" if shiny else ""
        await update.message.reply_text(f"✅ Success! You caught **{get_name(pid)}{tag}**!")
    else:
        hint = generate_hint(get_name(pid))
        await update.message.reply_text(f"❌ Wrong name! \n**Hint:** `{hint}`", parse_mode="Markdown")

async def mypokes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cur.execute("SELECT pid, shiny FROM pokemons WHERE user_id=?", (uid,))
    pokes = cur.fetchall()
    if not pokes:
        return await update.message.reply_text("You don't have any Pokémon yet!")
    
    msg = "📜 **Your Pokémon Collection:**\n"
    for p in pokes:
        tag = "✨ " if p[1] else ""
        msg += f"- {tag}{get_name(p[0])}\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

# ================= APP INIT =================
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("guess", guess))
app.add_handler(CommandHandler("catch", catch))
app.add_handler(CommandHandler("mypokes", mypokes))

print("Bot is live with HD images...")
app.run_polling()
        
