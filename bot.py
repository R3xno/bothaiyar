import random
import math
import logging
import certifi
from pymongo import MongoClient
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

# ================= CONFIG =================
BOT_TOKEN = "7422247259:AAEDq4_ZJqJT-EtHFfRkJumKy-tyD38UdFs"
MONGO_URI = "mongodb+srv://<sixty9>:<sixty9>@cluster0.wcpenfo.mongodb.net/?appName=Cluster0"

TOTAL_POKEMON = 1025  # Up to Paldea
SHINY_CHANCE = 0.03

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
client = MongoClient(
    MONGO_URI,
    tls=True,
    tlsCAFile=certifi.where()
)

db = client["pokemon_bot"]
users = db["users"]
guesses = db["guesses"]

# ================= HELPERS =================
def sprite(pid, shiny=False):
    if shiny:
        return f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/shiny/{pid}.png"
    return f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{pid}.png"

def random_ivs():
    return {k: random.randint(0, 31) for k in ["HP", "ATK", "DEF", "SPA", "SPD", "SPE"]}

def get_user(uid):
    user = users.find_one({"_id": uid})
    if not user:
        user = {
            "_id": uid,
            "coins": 100,
            "pokemons": []
        }
        users.insert_one(user)
    return user

def add_pokemon(uid, poke):
    users.update_one({"_id": uid}, {"$push": {"pokemons": poke}})

# ================= COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    get_user(uid)

    pid = random.randint(1, TOTAL_POKEMON)
    shiny = random.random() < SHINY_CHANCE

    poke = {
        "id": pid,
        "name": f"Pokemon-{pid}",
        "shiny": shiny,
        "nature": random.choice(NATURES),
        "ivs": random_ivs()
    }

    add_pokemon(uid, poke)

    await update.message.reply_photo(
        photo=sprite(pid, shiny),
        caption=f"🎉 You got **{poke['name']}{' ✨' if shiny else ''}**!",
        parse_mode="Markdown"
    )

async def guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pid = random.randint(1, TOTAL_POKEMON)
    shiny = random.random() < (SHINY_CHANCE / 4)

    guesses.update_one(
        {"_id": update.effective_chat.id},
        {"$set": {"pid": pid, "shiny": shiny}},
        upsert=True
    )

    await update.message.reply_photo(
        photo=sprite(pid, shiny),
        caption="❓ Guess the Pokémon!\nUse `/catch <name>`",
        parse_mode="Markdown"
    )

async def catch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return

    data = guesses.find_one({"_id": update.effective_chat.id})
    if not data:
        return

    pid = data["pid"]
    shiny = data["shiny"]

    poke = {
        "id": pid,
        "name": f"Pokemon-{pid}",
        "shiny": shiny,
        "nature": random.choice(NATURES),
        "ivs": random_ivs()
    }

    add_pokemon(update.effective_user.id, poke)
    guesses.delete_one({"_id": update.effective_chat.id})

    await update.message.reply_text(
        f"✅ Caught **{poke['name']}{' ✨' if shiny else ''}**!",
        parse_mode="Markdown"
    )

async def mypokes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)

    page = int(context.args[0]) if context.args else 1
    per_page = 25
    total = len(user["pokemons"])
    pages = max(1, math.ceil(total / per_page))

    start = (page - 1) * per_page
    end = start + per_page

    text = f"📦 **Your Pokémon ({total})**\n\n"
    for i, p in enumerate(user["pokemons"][start:end], start + 1):
        text += f"{i}. {p['name']}{' ✨' if p['shiny'] else ''}\n"

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
    page = q.data.split(":")[1]
    context.args = [page]
    await mypokes(q, context)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return

    name = context.args[0].lower()
    user = get_user(update.effective_user.id)

    pokes = [p for p in user["pokemons"] if p["name"].lower() == name]

    if not pokes:
        await update.message.reply_text("❌ You don't own this Pokémon.")
        return

    if len(pokes) > 1:
        kb = [[InlineKeyboardButton(f"Pokémon #{i+1}", callback_data=f"stat:{i}")]
              for i in range(len(pokes))]
        context.user_data["stats_list"] = pokes
        await update.message.reply_text("Choose one:", reply_markup=InlineKeyboardMarkup(kb))
        return

    p = pokes[0]
    ivs = "\n".join(f"{k}: {v}" for k, v in p["ivs"].items())

    await update.message.reply_photo(
        photo=sprite(p["id"], p["shiny"]),
        caption=f"**{p['name']}{' ✨' if p['shiny'] else ''}**\nNature: {p['nature']}\n\nIVs:\n{ivs}",
        parse_mode="Markdown"
    )

async def stat_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    idx = int(q.data.split(":")[1])
    p = context.user_data["stats_list"][idx]

    ivs = "\n".join(f"{k}: {v}" for k, v in p["ivs"].items())
    await q.message.reply_photo(
        photo=sprite(p["id"], p["shiny"]),
        caption=f"**{p['name']}{' ✨' if p['shiny'] else ''}**\nNature: {p['nature']}\n\nIVs:\n{ivs}",
        parse_mode="Markdown"
    )

async def myinv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    await update.message.reply_text(f"💰 PokéCoins: **{user['coins']}**", parse_mode="Markdown")

async def send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message or not context.args:
        return

    amount = int(context.args[0])
    sender = get_user(update.effective_user.id)
    receiver = get_user(update.message.reply_to_message.from_user.id)

    if sender["coins"] < amount:
        await update.message.reply_text("❌ Not enough coins.")
        return

    users.update_one({"_id": sender["_id"]}, {"$inc": {"coins": -amount}})
    users.update_one({"_id": receiver["_id"]}, {"$inc": {"coins": amount}})

    await update.message.reply_text("✅ Coins sent!")

# ================= ERROR HANDLER =================
async def error_handler(update, context):
    logging.error(f"Update error: {context.error}")

# ================= START BOT =================
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("guess", guess))
app.add_handler(CommandHandler("catch", catch))
app.add_handler(CommandHandler("mypokes", mypokes))
app.add_handler(CallbackQueryHandler(mypokes_cb, pattern="^mypokes"))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(CallbackQueryHandler(stat_cb, pattern="^stat:"))
app.add_handler(CommandHandler("myinv", myinv))
app.add_handler(CommandHandler("send", send))

app.add_error_handler(error_handler)

app.run_polling()
