
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import psycopg2
import logging

TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")
GROUP_ID = int(os.getenv("GROUP_ID"))
ADMIN_ID = int(os.getenv("ADMIN_ID"))

DB_CONFIG = {
    'dbname': os.getenv("DB_NAME"),
    'user': os.getenv("DB_USER"),
    'password': os.getenv("DB_PASSWORD"),
    'host': os.getenv("DB_HOST"),
    'port': os.getenv("DB_PORT")
}

logging.basicConfig(level=logging.INFO)

GROUP_LINK = 'https://t.me/buxgalteriyani_organamiz'

def init_db():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute(''' 
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            referred_by BIGINT,
            points INTEGER DEFAULT 0,
            invite_sent BOOLEAN DEFAULT FALSE
        );
    ''')
    conn.commit()
    cur.close()
    conn.close()

def add_user(user_id, username, referred_by):
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE user_id = %s", (user_id,))
    if not cur.fetchone():
        cur.execute("INSERT INTO users (user_id, username, referred_by) VALUES (%s, %s, %s)",
                    (user_id, username, referred_by))
        if referred_by:
            cur.execute("UPDATE users SET points = points + 1 WHERE user_id = %s", (referred_by,))
    conn.commit()
    cur.close()
    conn.close()

def get_user_points(user_id):
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT points FROM users WHERE user_id = %s", (user_id,))
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result[0] if result else 0

def has_invite_been_sent(user_id):
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT invite_sent FROM users WHERE user_id = %s", (user_id,))
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result[0] if result else False

def mark_invite_as_sent(user_id):
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("UPDATE users SET invite_sent = TRUE WHERE user_id = %s", (user_id,))
    conn.commit()
    cur.close()
    conn.close()

async def check_subscription(user_id, context):
    try:
        member = await context.bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

async def send_invite_if_needed(user_id, context):
    points = get_user_points(user_id)
    if points >= 3 and not has_invite_been_sent(user_id):
        try:
            invite_link = await context.bot.create_chat_invite_link(
                chat_id=GROUP_ID,
                member_limit=1,
                creates_join_request=False
            )
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    "🎉 Tabriklaymiz! Siz 3 ta foydalanuvchini taklif qildingiz.\n"
                    f"Bu yerda kurs guruhiga qo‘shilish havolasi 👇\n{invite_link.invite_link}\n\n"
                    "❗️Eslatma: Havola faqat siz uchun va faqat 1 marta ishlaydi."
                )
            )
            mark_invite_as_sent(user_id)
        except Exception as e:
            logging.error(f"Invite link error: {e}")
            await context.bot.send_message(chat_id=user_id, text="Havola yaratishda xatolik yuz berdi.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    referred_by = None

    if context.args:
        try:
            referred_by = int(context.args[0])
        except:
            pass

    add_user(user.id, user.username or "", referred_by)

    is_subscribed = await check_subscription(user.id, context)
    if is_subscribed:
        await show_menu(update, context)
        if referred_by:
            await send_invite_if_needed(referred_by, context)
    else:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Kanalga obuna bo'lish", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")],
            [InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub")]
        ])
        await update.message.reply_text("❗️ Iltimos, kanalga obuna bo‘ling:", reply_markup=keyboard)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    is_subscribed = await check_subscription(user_id, context)
    if is_subscribed:
        await query.edit_message_text("✅ Obuna tasdiqlandi. Menyu ochildi.")
        await show_menu(query, context)
    else:
        await query.answer("❌ Obuna aniqlanmadi.", show_alert=True)

async def show_menu(update_or_query, context):
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            ["📚 Bepul kurs haqida"],
            ["📝 Darsda qatnashish sharti"],
            ["🔗 Taklif havolasi"],
            ["🎯 Ballarim"]
        ],
        resize_keyboard=True
    )
    if isinstance(update_or_query, Update):
        await update_or_query.message.reply_text("📋 Assalomu alekum yaxshimisiz? ...", reply_markup=keyboard)
    else:
        await context.bot.send_message(chat_id=update_or_query.from_user.id, text="📋 Asosiy menyu:", reply_markup=keyboard)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    if text == "📚 Bepul kurs haqida":
        await update.message.reply_text("⚡️Bepul kursda nimalar kutib turibdi💡\n...")
    elif text == "📝 Darsda qatnashish sharti":
        await update.message.reply_text("🎁 Sizga berilgan takliif havoladan ...")
    elif text == "🔗 Taklif havolasi":
        await update.message.reply_text(f"Sizning referal havolangiz: https://t.me/{{context.bot.username}}?start={{user_id}}")
    elif text == "🎯 Ballarim":
        ballar = get_user_points(user_id)
        await update.message.reply_text(f"Sizning ballaringiz: {ballar} ball")
    else:
        await update.message.reply_text("Iltimos, menyudan tugmani tanlang.")

async def sendall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔️ Sizga bu buyruqdan foydalanish huquqi yo‘q.")
        return
    if not context.args:
        await update.message.reply_text("✉️ Xabar matnini yozing: /sendall Bu xabar barcha foydalanuvchilarga yuboriladi.")
        return
    message_text = " ".join(context.args)
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users")
    users = cur.fetchall()
    cur.close()
    conn.close()
    count = 0
    for user in users:
        try:
            await context.bot.send_message(chat_id=user[0], text=message_text)
            count += 1
        except Exception as e:
            logging.warning(f"Xatolik foydalanuvchi {user[0]} ga yuborishda: {e}")
    await update.message.reply_text(f"✅ {count} ta foydalanuvchiga xabar yuborildi.")

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("sendall", sendall))
    app.add_handler(CallbackQueryHandler(button_handler, pattern="check_sub"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == '__main__':
    main()
