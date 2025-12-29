import random
import math
import logging
import sqlite3
import os
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ================= CONFIG =================
BOT_TOKEN = "7422247259:AAGIZlgEPugM910XYHlhgSW5l3UAq4QJi-Y" 
OWNER_ID = 1101488645 # REPLACE with your numeric Telegram ID for backup access

TOTAL_POKEMON = 151 # Started with Gen 1 for simplicity, increase to 1025 later!
SHINY_CHANCE = 0.03

# Sample Name Dictionary - You will need to fill this list!
POKEMON_NAMES = {
    1: "Bulbasaur", 2: "Ivysaur", 3: "Venusaur",
    4: "Charmander", 5: "Charmeleon", 6: "Charizard",
    7: "Squirtle", 8: "Wartortle", 9: "Blastoise",
    25: "Pikachu"
    # ... add all other names here
}

NATURES = [
    "Hardy", "Lonely", "Brave", "Adamant", "Naughty",
    "Bold", "Docile", "Relaxed", "Impish", "Lax",
    "Timid", "Hasty", "Serious", "Jolly", "Naive",
    "Modest", "Mild", "Quiet", "Bashful", "Rash",
    "Calm", "Gentle", "Sassy", "Careful", "Quirky"
]

# ================= LOGGING =================
logging.basicConfig(level=logging.INFO)

# ================= DATABASE =================
conn = sqlite3.connect("pokemon.db", check_same_thread=False)
cur = conn.cursor()

# Create tables if they don't exist
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    coins INTEGER
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS pokemons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    pid INTEGER,
    shiny INTEGER,
    nature TEXT,
    iv_hp INTEGER,
    iv_atk INTEGER,
    iv_def INTEGER,
    iv_spa INTEGER,
    iv_spd INTEGER,
    iv_spe INTEGER
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS guesses (
    chat_id INTEGER PRIMARY KEY,
    pid INTEGER,
    shiny INTEGER
)
""")
conn.commit()

# ================= HELPERS =================
def get_name(pid):
    """Returns the name from our dictionary or a fallback ID name."""
    return POKEMON_NAMES.get(pid, f"Pokemon-{pid}")

def sprite(pid, shiny=False):
    """Returns High-Res image for normal, standard sprite for shiny."""
    if shiny:
        return f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/shiny/{pid}.png"
    # High-Res: Pad ID with zeros (e.g., 1 -> 001)
    padded_id = f"{pid:03d}"
    return f"https://raw.githubusercontent.com/HybridShivam/Pokemon/master/assets/images/{padded_id}.png"

def random_ivs():
    return [random.randint(0, 31) for _ in range(6)]

def get_user(uid):
    """Checks if user exists, returns coins. Does NOT create new user automatically."""
    cur.execute("SELECT coins FROM users WHERE user_id=?", (uid,))
    row = cur.fetchone()
    if row:
        return row[0]
    return None

def create_user(uid):
    """Creates a new user with starter coins."""
    cur.execute("INSERT INTO users VALUES (?, ?)", (uid, 100))
    conn.commit()

def add_pokemon(uid, pid, shiny, nature, ivs):
    cur.execute("""
    INSERT INTO pokemons
    (user_id, pid, shiny, nature,
     iv_hp, iv_atk, iv_def, iv_spa, iv_spd, iv_spe)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (uid, pid, shiny, nature, *ivs))
    conn.commit()

# ================= COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    
    # Check if user already exists
    if get_user(uid) is not None:
        await update.message.reply_text("👋 Welcome back! Use /guess to hunt for Pokémon.")
        return

    # First time setup
    create_user(uid)
    
    # Starter Pokemon
    pid = random.randint(1, TOTAL_POKEMON)
    shiny = 1 if random.random() < SHINY_CHANCE else 0
    nature = random.choice(NATURES)
    ivs = random_ivs()
    p_name = get_name(pid)

    add_pokemon(uid, pid, shiny, nature, ivs)

    await update.message.reply_photo(
        photo=sprite(pid, shiny),
        caption=f"🎉 **Welcome!**\nYou started your journey with *{p_name}{' ✨' if shiny else ''}*!",
        parse_mode="Markdown"
    )

async def guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pid = random.randint(1, TOTAL_POKEMON)
    shiny = 1 if random.random() < (SHINY_CHANCE / 4) else 0

    cur.execute(
        "REPLACE INTO guesses VALUES (?, ?, ?)",
        (update.effective_chat.id, pid, shiny)
    )
    conn.commit()

    await update.message.reply_photo(
        photo=sprite(pid, shiny),
        caption="❓ A wild Pokémon appeared!\nGuess its name and catch it with `/catch <name>`",
        parse_mode="Markdown"
    )

async def catch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: `/catch <name>`")
        return

    # Check active spawn
    cur.execute("SELECT pid, shiny FROM guesses WHERE chat_id=?", (update.effective_chat.id,))
    row = cur.fetchone()
    if not row:
        await update.message.reply_text("❌ No Pokémon to catch.")
        return

    pid, shiny = row
    target_name = get_name(pid).lower()
    user_guess = " ".join(context.args).lower()

    # Verify Guess
    if user_guess != target_name:
         await update.message.reply_text("❌ That's not the right name!")
         return

    # Catch Logic
    nature = random.choice(NATURES)
    ivs = random_ivs()
    real_name = get_name(pid)

    # Check if user exists (just in case)
    if get_user(update.effective_user.id) is None:
        create_user(update.effective_user.id)

    add_pokemon(update.effective_user.id, pid, shiny, nature, ivs)

    cur.execute("DELETE FROM guesses WHERE chat_id=?", (update.effective_chat.id,))
    conn.commit()

    await update.message.reply_text(
        f"✅ Gotcha! Caught *{real_name}{' ✨' if shiny else ''}*!\n"
        f"Nature: {nature} | IVs: {sum(ivs)}/186",
        parse_mode="Markdown"
    )

async def mypokes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    page = int(context.args[0]) if context.args else 1

    cur.execute("SELECT pid, shiny FROM pokemons WHERE user_id=?", (uid,))
    pokes = cur.fetchall()

    per_page = 10 # Lowered to avoid long message limits
    total = len(pokes)
    pages = max(1, math.ceil(total / per_page))

    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page

    text = f"📦 *Your Storage ({total})*\nPage {page}/{pages}\n\n"
    for i, p in enumerate(pokes[start_idx:end_idx], start_idx + 1):
        p_name = get_name(p[0])
        text += f"{i}. {p_name}{' ✨' if p[1] else ''}\n"
    
    text += "\nTo see details: `/stats <pokemon_name>`"

    buttons = []
    if page > 1:
        buttons.append(InlineKeyboardButton("⬅ Prev", callback_data=f"mypokes:{page-1}"))
    if page < pages:
        buttons.append(InlineKeyboardButton("Next ➡", callback_data=f"mypokes:{page+1}"))

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([buttons]) if buttons else None
    )

async def mypokes_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    page = int(q.data.split(":")[1])
    context.args = [str(page)]
    await q.message.delete()
    await mypokes(q, context)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("ℹ️ Usage: `/stats <pokemon_name>`")
        return

    uid = update.effective_user.id
    search_name = " ".join(context.args).lower()
    
    # Find the Pokemon ID based on name (simple search)
    target_pid = None
    for pid, name in POKEMON_NAMES.items():
        if name.lower() == search_name:
            target_pid = pid
            break
    
    if not target_pid:
        await update.message.reply_text("❓ I don't know that Pokémon name.")
        return

    # Fetch user's pokemon of that type
    cur.execute("""
        SELECT shiny, nature, iv_hp, iv_atk, iv_def, iv_spa, iv_spd, iv_spe 
        FROM pokemons WHERE user_id=? AND pid=?
    """, (uid, target_pid))
    
    rows = cur.fetchall()
    if not rows:
        await update.message.reply_text(f"❌ You don't own a {get_name(target_pid)}.")
        return

    # Show stats for the first one found (or list them if you prefer later)
    p = rows[0] 
    iv_total = sum(p[2:])
    iv_percent = round((iv_total / 186) * 100)

    text = (
        f"📊 *Stats for {get_name(target_pid)}*\n"
        f"{'✨ SHINY ✨' if p[0] else ''}\n"
        f"🧠 Nature: {p[1]}\n"
        f"💪 IVs: {iv_percent}% ({iv_total}/186)\n"
        f"❤️ HP: {p[2]} ⚔️ Atk: {p[3]} 🛡️ Def: {p[4]}\n"
        f"🔮 SpA: {p[5]} 🛡️ SpD: {p[6]} ⚡ Spe: {p[7]}"
    )

    await update.message.reply_text(text, parse_mode="Markdown")

async def backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Security check: Only owner can use this
    if update.effective_user.id != OWNER_ID:
        return

    chat_id = update.effective_chat.id
    try:
        await update.message.reply_text("📤 Uploading database...")
        # Send the file "pokemon.db"
        await context.bot.send_document(
            chat_id=chat_id,
            document=open("pokemon.db", "rb"),
            filename="pokemon_backup.db"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error during backup: {e}")

# ================= START =================
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("guess", guess))
app.add_handler(CommandHandler("catch", catch))
app.add_handler(CommandHandler("mypokes", mypokes))
app.add_handler(CallbackQueryHandler(mypokes_cb, pattern="^mypokes"))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(CommandHandler("backup", backup))

print("Bot is running...")
app.run_polling()
