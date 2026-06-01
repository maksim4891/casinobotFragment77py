import random
import time
import sqlite3
import urllib.request
import urllib.error
import json
import telebot
from telebot import types

# === НАСТРОЙКА HTTP ПРОКСИ ===
PROXY_HOST = "193.22.244.75"
PROXY_PORT = 3128

# Настройка прокси для urllib
proxy_handler = urllib.request.ProxyHandler({
    'http': f'http://{PROXY_HOST}:{PROXY_PORT}',
    'https': f'http://{PROXY_HOST}:{PROXY_PORT}'
})
opener = urllib.request.build_opener(proxy_handler)
urllib.request.install_opener(opener)

# Настройка прокси для telebot
from telebot import apihelper
apihelper.proxy = {'https': f'http://{PROXY_HOST}:{PROXY_PORT}'}

print("✅ HTTP прокси настроен!")

# === НАСТРОЙКИ БОТА ===
TOKEN = '8742929536:AAGX-oAF4CZktcfxNwAHPnavt-sUZk-JY1Y'
ADMIN_ID = 1178979444
CRYPTO_BOT_TOKEN = '586791:AAYuv27u6bqo0uF2zeuQ7GRzYbc1H7rnRqz'

bot = telebot.TeleBot(TOKEN)
DB_NAME = 'casino.db'

admin_states = {}
active_crash_games = {}
roulette_tmp = {}

SLOT_EMOJIS = ["🍒", "🍋", "💎", "🍇", "🍊", "🔔", "7️⃣"]
RED_NUMBERS = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]
BLACK_NUMBERS = [2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35]

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance INTEGER DEFAULT 0,
            deposited INTEGER DEFAULT 0,
            withdrawn INTEGER DEFAULT 0,
            games_played INTEGER DEFAULT 0,
            active_voucher TEXT DEFAULT NULL
        )
    ''')
    cursor.execute('CREATE TABLE IF NOT EXISTS vouchers (code TEXT PRIMARY KEY, percent INTEGER, uses_left INTEGER)')
    cursor.execute('CREATE TABLE IF NOT EXISTS voucher_history (user_id INTEGER, code TEXT, PRIMARY KEY (user_id, code))')
    cursor.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, val TEXT)')
    
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN active_voucher TEXT DEFAULT NULL")
    except: pass
    try:
        cursor.execute("ALTER TABLE vouchers ADD COLUMN percent INTEGER")
    except: pass
    
    default_settings = {
        "txt_start": "👑 <b>Добро пожаловать в VIP Casino!</b> 👑\n\nТвой баланс: <b>{balance}$</b>\nИспытай свою удачу прямо сейчас!",
        "img_start": "",
        "txt_profile": "👤 <b>Ваш профиль:</b>\n\n💰 Баланс: <b>{balance}$</b>\n📊 Сыграно игр: {games_played}\n📥 Пополнений: {deposited}$\n📤 Выведено: {withdrawn}$",
        "img_profile": "",
        "txt_wallet": "💳 <b>Кошелек / Касса</b>\n\nПополнение через CryptoBot USDT (TON).\nМинимальный вывод: <b>5$</b>",
        "img_wallet": "",
        "txt_games_menu": "🎮 <b>Выберите игровой режим:</b>",
        "img_games_menu": "",
        "txt_voucher_menu": "🎫 <b>Введите секретный ваучер:</b>",
        "img_voucher_menu": "",
        "txt_slots_info": "🎰 <b>Игровой автомат 777</b>\n\nШанс выигрыша — 35%!\nВыигрыш: x3",
        "img_slots": "",
        "txt_crash_info": "🚀 <b>Режим Crash</b>\n\nРакета летит вверх. Успей забрать!",
        "img_crash": "",
        "txt_dice_info": "🎲 <b>Игра в Кости</b>\n\nШанс победы — 35%.\nВыигрыш: x2",
        "img_dice": "",
        "txt_roulette_info": "🎡 <b>Рулетка (Double Zero)</b>\n\nСтавь на число (x36), цвет (x2) или чет/нечет (x2).",
        "img_roulette": "",
        "txt_win": "🎉 <b>ПОБЕДА!</b>\n\nВыигрыш: <b>{win}$</b>",
        "txt_lose": "😢 <b>ПОРАЖЕНИЕ...</b>\n\nКазино забирает ставку"
    }
    for k, v in default_settings.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, val) VALUES (?, ?)", (k, v))
    conn.commit()
    conn.close()

def get_set(key, **kwargs):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT val FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    text = row[0] if row else ""
    if kwargs:
        try: text = text.format(**kwargs)
        except: pass
    return text

def set_set(key, val):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, val) VALUES (?, ?)", (key, val))
    conn.commit()
    conn.close()

def get_user(user_id, username="Игрок"):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, balance, deposited, withdrawn, games_played, active_voucher FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT INTO users (user_id, username, balance) VALUES (?, ?, 0)", (user_id, username))
        conn.commit()
        cursor.execute("SELECT user_id, username, balance, deposited, withdrawn, games_played, active_voucher FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
    conn.close()
    return {"user_id": user[0], "username": user[1], "balance": user[2], "deposited": user[3], "withdrawn": user[4], "games_played": user[5], "active_voucher": user[6]}

def update_balance(user_id, amount):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def update_stats(user_id, deposit=0, withdraw=0, game=0):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET deposited = deposited + ?, withdrawn = withdrawn + ?, games_played = games_played + ? WHERE user_id = ?', (deposit, withdraw, game, user_id))
    conn.commit()
    conn.close()

def create_crypto_invoice(amount, user_id):
    urls = ["https://pay.crypt.bot/api/createInvoice"]
    payload = {"asset": "USDT", "amount": str(amount), "description": f"Пополнение ID{user_id}", "payload": str(user_id), "expires_in": 3600}
    data = json.dumps(payload).encode('utf-8')
    for url in urls:
        try:
            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Crypto-Pay-API-Token", CRYPTO_BOT_TOKEN)
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=15) as response:
                res_json = json.loads(response.read().decode())
                if res_json.get("ok") and res_json.get("result"):
                    return res_json["result"]["pay_url"], res_json["result"]["invoice_id"]
        except: pass
    return None, None

def check_crypto_invoice(invoice_id):
    urls = ["https://pay.crypt.bot/api/getInvoices"]
    payload = {"invoice_ids": invoice_id}
    data = json.dumps(payload).encode('utf-8')
    for url in urls:
        try:
            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Crypto-Pay-API-Token", CRYPTO_BOT_TOKEN)
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=10) as response:
                res_json = json.loads(response.read().decode())
                if res_json.get("ok") and res_json.get("result") and res_json["result"].get("items"):
                    return res_json["result"]["items"][0].get("status") == "paid"
        except: pass
    return False

def send_or_edit(chat_id, text, markup, msg_id=None, img_key=None):
    img_val = get_set(img_key) if img_key else ""
    if img_val and img_val.strip():
        if msg_id:
            try: bot.delete_message(chat_id, msg_id)
            except: pass
        return bot.send_photo(chat_id, img_val, caption=text, parse_mode="HTML", reply_markup=markup)
    else:
        if msg_id:
            try: return bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text, parse_mode="HTML", reply_markup=markup)
            except: pass
        return bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)

def support_btn(markup):
    markup.add(types.InlineKeyboardButton("👨‍💻 Тех. Поддержка", url="https://t.me/GoPlaySupport"))
    return markup

def main_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎮 Игры", callback_data="menu_games"),
        types.InlineKeyboardButton("👤 Профиль", callback_data="menu_profile"),
        types.InlineKeyboardButton("💳 Кошелек", callback_data="menu_wallet"),
        types.InlineKeyboardButton("🎫 Ваучер", callback_data="menu_voucher")
    )
    return support_btn(markup)

@bot.message_handler(commands=['start'])
def start_cmd(message):
    u = get_user(message.from_user.id, message.from_user.first_name)
    t = get_set("txt_start", balance=u['balance'])
    send_or_edit(message.chat.id, t, main_menu(), img_key="img_start")

@bot.message_handler(commands=['admin'])
def admin_cmd(message):
    if message.from_user.id != ADMIN_ID: return
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📝 Изменить Текст", callback_data="adm_text_list"),
        types.InlineKeyboardButton("🖼 Изменить Фото", callback_data="adm_img_list"),
        types.InlineKeyboardButton("💰 Изменить баланс", callback_data="adm_change_bal"),
        types.InlineKeyboardButton("🎫 Создать ваучер", callback_data="adm_create_voucher"),
        types.InlineKeyboardButton("📢 Сделать рассылку", callback_data="adm_broadcast")
    )
    bot.send_message(message.chat.id, "🛠 <b>Панель администратора</b>", parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("check_"))
def check_payment(call):
    _, invoice_id, amount = call.data.split("_")
    user_id = call.from_user.id
    amount = int(amount)
    if check_crypto_invoice(invoice_id):
        percent = get_user_voucher_percent(user_id)
        bonus = 0
        if percent > 0:
            bonus = int(amount * (percent / 100))
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET active_voucher = NULL WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
        total_credit = amount + bonus
        update_balance(user_id, total_credit)
        update_stats(user_id, deposit=amount)
        bot.answer_callback_query(call.id, f"🎉 Пополнено на {total_credit}$!", show_alert=True)
        bot.send_message(user_id, f"✅ Зачислено <b>{total_credit}$</b>", parse_mode="HTML")
    else:
        bot.answer_callback_query(call.id, "❌ Не оплачено", show_alert=True)

@bot.callback_query_handler(func=lambda call: True)
def callback_listener(call):
    user_id = call.from_user.id
    u = get_user(user_id, call.from_user.first_name)
    m_id = call.message.message_id
    chat_id = call.message.chat.id
    
    if call.data == "main_menu":
        t = get_set("txt_start", balance=u['balance'])
        send_or_edit(chat_id, t, main_menu(), m_id, "img_start")
        
    elif call.data == "menu_games":
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🎰 Слоты", callback_data="bet_slots"),
            types.InlineKeyboardButton("🚀 Crash", callback_data="bet_crash"),
            types.InlineKeyboardButton("🎲 Кости", callback_data="bet_dice"),
            types.InlineKeyboardButton("🎡 Рулетка", callback_data="bet_roulette"),
            types.InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")
        )
        send_or_edit(chat_id, get_set("txt_games_menu"), support_btn(markup), m_id, "img_games_menu")
        
    elif call.data == "menu_profile":
        v_status = f"\n🎫 Бонус: +{get_user_voucher_percent(user_id)}%" if u['active_voucher'] else ""
        t = get_set("txt_profile", balance=u['balance'], games_played=u['games_played'], deposited=u['deposited'], withdrawn=u['withdrawn']) + v_status
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("⬅️ Назад", callback_data="main_menu"))
        send_or_edit(chat_id, t, support_btn(markup), m_id, "img_profile")
        
    elif call.data == "menu_wallet":
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📥 Пополнить", callback_data="wallet_deposit"),
            types.InlineKeyboardButton("📤 Вывести", callback_data="wallet_withdraw"),
            types.InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")
        )
        send_or_edit(chat_id, get_set("txt_wallet"), support_btn(markup), m_id, "img_wallet")

    elif call.data == "menu_voucher":
        msg = bot.send_message(chat_id, get_set("txt_voucher_menu"), parse_mode="HTML")
        bot.register_next_step_handler(msg, process_activate_voucher)

    elif call.data == "wallet_deposit":
        msg = bot.send_message(chat_id, "💵 <b>Сумма ($):</b>", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_deposit_amount)
        
    elif call.data == "wallet_withdraw":
        msg = bot.send_message(chat_id, "📤 <b>Адрес и сумма:</b>", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_withdraw_request)

    elif call.data == "bet_slots":
        msg = bot.send_message(chat_id, f"💰 <b>Ставка?</b>\nБаланс: {u['balance']}$", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_get_bet, "slots")
    elif call.data == "bet_crash":
        msg = bot.send_message(chat_id, f"💰 <b>Ставка?</b>\nБаланс: {u['balance']}$", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_get_bet, "crash")
    elif call.data == "bet_dice":
        msg = bot.send_message(chat_id, f"💰 <b>Ставка?</b>\nБаланс: {u['balance']}$", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_get_bet, "dice")
    elif call.data == "bet_roulette":
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🎲 Число (x36)", callback_data="roulette_type_number"),
            types.InlineKeyboardButton("🔴/⚫ Цвет (x2)", callback_data="roulette_type_color"),
            types.InlineKeyboardButton("📊 Чет/Нечет (x2)", callback_data="roulette_type_parity"),
            types.InlineKeyboardButton("⬅️ Назад", callback_data="menu_games")
        )
        bot.edit_message_text("🎡 <b>Тип ставки:</b>", chat_id, m_id, parse_mode="HTML", reply_markup=markup)

    elif call.data == "roulette_type_number":
        roulette_tmp[user_id] = {"bet_type": "number"}
        msg = bot.send_message(chat_id, "🎲 <b>Число 0-36</b>\n(36 = 00)", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_roulette_number)
    elif call.data == "roulette_type_color":
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🔴 Красное", callback_data="roulette_color_red"),
            types.InlineKeyboardButton("⚫ Черное", callback_data="roulette_color_black"),
            types.InlineKeyboardButton("🟢 Зеленое", callback_data="roulette_color_green"),
            types.InlineKeyboardButton("⬅️ Назад", callback_data="bet_roulette")
        )
        bot.edit_message_text("🎨 <b>Цвет:</b>", chat_id, m_id, parse_mode="HTML", reply_markup=markup)
    elif call.data == "roulette_type_parity":
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📊 Четное", callback_data="roulette_parity_even"),
            types.InlineKeyboardButton("📊 Нечетное", callback_data="roulette_parity_odd"),
            types.InlineKeyboardButton("⬅️ Назад", callback_data="bet_roulette")
        )
        bot.edit_message_text("🎲 <b>Четность:</b>", chat_id, m_id, parse_mode="HTML", reply_markup=markup)

    elif call.data == "roulette_color_red":
        roulette_tmp[user_id] = {"bet_type": "color", "bet_value": "red"}
        msg = bot.send_message(chat_id, f"💰 <b>Ставка на КРАСНОЕ?</b>\nБаланс: {u['balance']}$", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_roulette_bet_amount)
    elif call.data == "roulette_color_black":
        roulette_tmp[user_id] = {"bet_type": "color", "bet_value": "black"}
        msg = bot.send_message(chat_id, f"💰 <b>Ставка на ЧЕРНОЕ?</b>\nБаланс: {u['balance']}$", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_roulette_bet_amount)
    elif call.data == "roulette_color_green":
        roulette_tmp[user_id] = {"bet_type": "color", "bet_value": "green"}
        msg = bot.send_message(chat_id, f"💰 <b>Ставка на ЗЕЛЕНОЕ?</b>\nБаланс: {u['balance']}$", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_roulette_bet_amount)
    elif call.data == "roulette_parity_even":
        roulette_tmp[user_id] = {"bet_type": "parity", "bet_value": "even"}
        msg = bot.send_message(chat_id, f"💰 <b>Ставка на ЧЕТНОЕ?</b>\nБаланс: {u['balance']}$", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_roulette_bet_amount)
    elif call.data == "roulette_parity_odd":
        roulette_tmp[user_id] = {"bet_type": "parity", "bet_value": "odd"}
        msg = bot.send_message(chat_id, f"💰 <b>Ставка на НЕЧЕТНОЕ?</b>\nБаланс: {u['balance']}$", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_roulette_bet_amount)

    elif call.data.startswith("startgame_"):
        _, game_type, bet = call.data.split("_")
        bet = int(bet)
        if u['balance'] < bet:
            bot.answer_callback_query(call.id, "❌ Нет денег!", show_alert=True)
            return
        update_balance(user_id, -bet)
        update_stats(user_id, game=1)
        if game_type == "slots":
            play_slots(chat_id, user_id, bet, m_id)
        elif game_type == "crash":
            play_crash(chat_id, user_id, bet, m_id)
        elif game_type == "dice":
            play_dice(chat_id, user_id, bet, m_id)

    elif call.data == "claim_crash":
        if user_id in active_crash_games and active_crash_games[user_id]["status"] == "flying":
            try:
                text = call.message.text
                parsed_x = float(text.split("множитель: ")[1].split("x")[0])
            except: parsed_x = 1.05
            active_crash_games[user_id]["status"] = "claimed"
            active_crash_games[user_id]["final_x"] = parsed_x
            bot.answer_callback_query(call.id, "✅ Забрано!")

    elif call.data.startswith("playerdice_"):
        _, bet, c_score = call.data.split("_")
        bet, c_score = int(bet), int(c_score)
        if random.random() <= 0.35:
            p_score = random.randint(c_score + 1, 12)
            win = bet * 2
            update_balance(user_id, win)
            t = f"🎲 Ты: {p_score}\n🤵 Дилер: {c_score}\n\n" + get_set("txt_win", win=win)
        else:
            p_score = random.randint(2, c_score)
            t = f"🎲 Ты: {p_score}\n🤵 Дилер: {c_score}\n\n" + get_set("txt_lose")
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🎲 Еще", callback_data="bet_dice"), types.InlineKeyboardButton("⬅️ Меню", callback_data="main_menu"))
        bot.edit_message_text(t, chat_id, m_id, parse_mode="HTML", reply_markup=markup)

    elif call.data == "adm_text_list":
        markup = types.InlineKeyboardMarkup()
        keys = ["txt_start", "txt_profile", "txt_wallet", "txt_games_menu", "txt_slots_info", "txt_crash_info", "txt_dice_info", "txt_roulette_info", "txt_win", "txt_lose"]
        for k in keys: markup.add(types.InlineKeyboardButton(f"✏️ {k}", callback_data=f"editkey_{k}"))
        bot.edit_message_text("✏️ <b>Тексты:</b>", chat_id, m_id, parse_mode="HTML", reply_markup=markup)
    elif call.data == "adm_img_list":
        markup = types.InlineKeyboardMarkup()
        keys = ["img_start", "img_profile", "img_wallet", "img_games_menu", "img_slots", "img_crash", "img_dice", "img_roulette"]
        for k in keys: markup.add(types.InlineKeyboardButton(f"🖼 {k}", callback_data=f"editphoto_{k}"))
        bot.edit_message_text("🖼 <b>Фото:</b>", chat_id, m_id, parse_mode="HTML", reply_markup=markup)
    elif call.data.startswith("editkey_"):
        key = call.data.split("_")[1]
        msg = bot.send_message(chat_id, f"📝 Новый текст для {key}:", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_save_setting, key)
    elif call.data.startswith("editphoto_"):
        key = call.data.split("_")[1]
        admin_states[user_id] = key
        bot.send_message(chat_id, f"🖼 Отправь фото для {key}\nили «убрать»")
    elif call.data == "adm_change_bal":
        msg = bot.send_message(chat_id, "📝 <code>ID СУММА</code>", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_admin_balance)
    elif call.data == "adm_create_voucher":
        msg = bot.send_message(chat_id, "🎫 <code>КОД % АКТИВАЦИЙ</code>", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_admin_voucher)
    elif call.data == "adm_broadcast":
        msg = bot.send_message(chat_id, "📢 Текст рассылки:", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_admin_broadcast)

@bot.message_handler(content_types=['photo', 'text'])
def handle_admin_media(message):
    user_id = message.from_user.id
    if user_id == ADMIN_ID and user_id in admin_states:
        key = admin_states[user_id]
        if message.content_type == 'photo':
            file_id = message.photo[-1].file_id
            set_set(key, file_id)
            bot.send_message(message.chat.id, f"✅ Фото {key} сохранено!")
            del admin_states[user_id]
        elif message.content_type == 'text' and message.text.lower() == 'убрать':
            set_set(key, "")
            bot.send_message(message.chat.id, f"✅ Фото {key} удалено!")
            del admin_states[user_id]

def play_slots(chat_id, user_id, bet, m_id):
    is_win = random.random() <= 0.35
    if is_win:
        win_emoji = random.choice(["7️⃣", "💎", "🔔", "🍒"])
        final_res = [win_emoji, win_emoji, win_emoji]
    else:
        res1 = random.choice(SLOT_EMOJIS)
        res2 = random.choice([e for e in SLOT_EMOJIS if e != res1])
        res3 = random.choice(SLOT_EMOJIS)
        final_res = [res1, res2, res3]
    for _ in range(12):
        fake = [random.choice(SLOT_EMOJIS) for _ in range(3)]
        try: bot.edit_message_text(f"🎰 [ {fake[0]} | {fake[1]} | {fake[2]} ]", chat_id, m_id, parse_mode="HTML")
        except: pass
        time.sleep(0.1)
    if is_win:
        win = bet * 3
        update_balance(user_id, win)
        t = f"🎰 [ {final_res[0]} | {final_res[1]} | {final_res[2]} ]\n\n" + get_set("txt_win", win=win)
    else:
        t = f"🎰 [ {final_res[0]} | {final_res[1]} | {final_res[2]} ]\n\n" + get_set("txt_lose")
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🎰 Еще", callback_data="bet_slots"), types.InlineKeyboardButton("⬅️ Меню", callback_data="main_menu"))
    bot.send_message(chat_id, t, parse_mode="HTML", reply_markup=markup)

def play_crash(chat_id, user_id, bet, m_id):
    ranges = [(1.00,1.00),(1.01,1.12),(1.13,1.18),(1.19,1.35),(1.36,1.50),(1.51,1.75),(1.76,1.99),(2.00,2.10),(2.11,2.20),(2.21,2.70),(2.71,3.00)]
    weights = [5,55,8,5,4,5,5,3,3,2,2]
    chosen_range = random.choices(ranges, weights=weights, k=1)[0]
    crash_limit = round(random.uniform(chosen_range[0], chosen_range[1]), 2)
    active_crash_games[user_id] = {"status": "flying", "bet": bet}
    current_x = 1.00
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💰 ЗАБРАТЬ", callback_data="claim_crash"))
    while current_x < crash_limit:
        if active_crash_games.get(user_id, {}).get("status") == "claimed": break
        try: bot.edit_message_text(f"🚀 Множитель: {round(current_x, 2)}x\n💰 Выигрыш: {int(bet * current_x)}$", chat_id, m_id, parse_mode="HTML", reply_markup=markup)
        except: pass
        time.sleep(0.9)
        current_x += 0.03 + random.uniform(0.005, 0.02)
    if active_crash_games.get(user_id, {}).get("status") == "claimed":
        final_x = active_crash_games[user_id]["final_x"]
        win = int(bet * final_x)
        update_balance(user_id, win)
        t = f"🚀 Забрано на x{round(final_x, 2)}!\n\n" + get_set("txt_win", win=win)
    else:
        t = f"💥 Взрыв на x{crash_limit}!\n\n" + get_set("txt_lose")
    if user_id in active_crash_games: del active_crash_games[user_id]
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🚀 Еще", callback_data="bet_crash"), types.InlineKeyboardButton("⬅️ Меню", callback_data="main_menu"))
    bot.send_message(chat_id, t, parse_mode="HTML", reply_markup=markup)

def play_dice(chat_id, user_id, bet, m_id):
    dealer = random.randint(7, 11)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🎲 Бросить", callback_data=f"playerdice_{bet}_{dealer}"))
    bot.edit_message_text(f"🤵 Дилер: {dealer}\nТвой ход!", chat_id, m_id, parse_mode="HTML", reply_markup=markup)

def process_roulette_number(message):
    user_id = message.from_user.id
    try:
        number = int(message.text.strip())
        if number < 0 or number > 36:
            bot.send_message(message.chat.id, "❌ 0-36")
            return
        roulette_tmp[user_id]["bet_value"] = number
        u = get_user(user_id)
        msg = bot.send_message(message.chat.id, f"💰 Ставка на {number}?\nБаланс: {u['balance']}$", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_roulette_bet_amount)
    except:
        bot.send_message(message.chat.id, "❌ Число")

def process_roulette_bet_amount(message):
    user_id = message.from_user.id
    try:
        bet = int(message.text.strip())
        u = get_user(user_id)
        if bet <= 0 or bet > u['balance']:
            bot.send_message(message.chat.id, "❌ Ошибка")
            return
        if user_id not in roulette_tmp:
            bot.send_message(message.chat.id, "❌ Ошибка")
            return
        bet_type = roulette_tmp[user_id]["bet_type"]
        bet_value = roulette_tmp[user_id]["bet_value"]
        update_balance(user_id, -bet)
        update_stats(user_id, game=1)
        play_roulette(message.chat.id, user_id, bet, bet_type, bet_value, message.message_id)
        del roulette_tmp[user_id]
    except:
        bot.send_message(message.chat.id, "❌ Число")

def play_roulette(chat_id, user_id, bet_amount, bet_type, bet_value, msg_id):
    sectors = list(range(0, 37))
    result_num = random.choice(sectors)
    is_00 = (result_num == 36)
    display_num = "00" if is_00 else str(result_num)
    
    if result_num == 0 or is_00:
        color = "🟢"
        color_name = "green"
        color_text = "ЗЕЛЁНОЕ (0/00)"
    elif result_num in RED_NUMBERS:
        color = "🔴"
        color_name = "red"
        color_text = "КРАСНОЕ"
    else:
        color = "⚫"
        color_name = "black"
        color_text = "ЧЁРНОЕ"
    
    frames = 40
    for i in range(frames):
        fake_num = random.choice(sectors)
        fake_00 = (fake_num == 36)
        fake_display = "00" if fake_00 else str(fake_num)
        
        if fake_num == 0 or fake_00:
            fake_color = "🟢"
        elif fake_num in RED_NUMBERS:
            fake_color = "🔴"
        else:
            fake_color = "⚫"
        
        ball = ["🎯", "⚪", "🔴", "🎲"][i % 4]
        progress = int((i + 1) / frames * 20)
        bar = "█" * progress + "░" * (20 - progress)
        
        try:
            bot.edit_message_text(
                f"🎡 <b>РУЛЕТКА КРУТИТСЯ</b> {ball}\n\n"
                f"┌─────────────────┐\n"
                f"│     {fake_color} {fake_display:>3} {fake_color}      │\n"
                f"└─────────────────┘\n\n"
                f"⚡ {bar}\n"
                f"⏳ {i+1}/{frames}",
                chat_id, msg_id, parse_mode="HTML"
            )
        except: pass
        
        if i < frames * 0.6:
            time.sleep(0.05)
        elif i < frames * 0.85:
            time.sleep(0.08)
        else:
            time.sleep(0.12)
    
    time.sleep(0.5)
    
    try:
        bot.edit_message_text(
            f"🎡 <b>ШАРИК ОСТАНОВИЛСЯ!</b>\n\n"
            f"┌─────────────────┐\n"
            f"│     {color} {display_num:>3} {color}      │\n"
            f"└─────────────────┘\n\n"
            f"🔍 {color_text}",
            chat_id, msg_id, parse_mode="HTML"
        )
    except: pass
    
    time.sleep(0.8)
    
    win = 0
    win_text = ""
    
    if bet_type == "number":
        if not is_00 and result_num == bet_value:
            win = bet_amount * 36
            win_text = f"🎉 Твоя ставка на число {bet_value} сыграла!"
        else:
            win_text = "❌ Твоя ставка на число не сыграла..."
    elif bet_type == "color":
        if bet_value == color_name:
            win = bet_amount * 2
            win_text = f"🎉 Ставка на {color_text.lower()} сыграла!"
        else:
            win_text = f"❌ Ставка на {color_text.lower()} не сыграла..."
    elif bet_type == "parity":
        if bet_value == "even":
            if result_num % 2 == 0 and result_num != 0 and not is_00:
                win = bet_amount * 2
                win_text = "🎉 Ставка на чётное сыграла!"
            else:
                win_text = "❌ Ставка на чётное не сыграла..."
        elif bet_value == "odd":
            if result_num % 2 == 1 and not is_00:
                win = bet_amount * 2
                win_text = "🎉 Ставка на нечётное сыграла!"
            else:
                win_text = "❌ Ставка на нечётное не сыграла..."
    
    if win > 0:
        update_balance(user_id, win)
        final_text = f"🎡 <b>РЕЗУЛЬТАТ РУЛЕТКИ</b>\n\n┌─────────────────┐\n│     {color} {display_num:>3} {color}      │\n└─────────────────┘\n\n{win_text}\n\n✨ <b>Твой выигрыш: +{win}$</b>\n\n{get_set('txt_win', win=win)}"
    else:
        final_text = f"🎡 <b>РЕЗУЛЬТАТ РУЛЕТКИ</b>\n\n┌─────────────────┐\n│     {color} {display_num:>3} {color}      │\n└─────────────────┘\n\n{win_text}\n\n💸 <b>Ставка проиграна</b>\n\n{get_set('txt_lose')}"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🎡 Играть ещё", callback_data="bet_roulette"), types.InlineKeyboardButton("⬅️ В меню", callback_data="main_menu"))
    bot.send_message(chat_id, final_text, parse_mode="HTML", reply_markup=markup)

def process_get_bet(message, game_type):
    try:
        bet = int(message.text.strip())
        u = get_user(message.from_user.id)
        if bet <= 0 or bet > u['balance']:
            bot.send_message(message.chat.id, "❌ Некорректно")
            return
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔥 ИГРАТЬ", callback_data=f"startgame_{game_type}_{bet}"), types.InlineKeyboardButton("❌ Отмена", callback_data="menu_games"))
        send_or_edit(message.chat.id, f"{get_set(f'txt_{game_type}_info')}\n\nСтавка: <b>{bet}$</b>", markup, img_key=f"img_{game_type}")
    except: bot.send_message(message.chat.id, "❌ Число")

def process_deposit_amount(message):
    try:
        amount = int(message.text.strip())
        if amount <= 0:
            bot.send_message(message.chat.id, "❌ >0")
            return
        pay_url, invoice_id = create_crypto_invoice(amount, message.from_user.id)
        if not pay_url:
            bot.send_message(message.chat.id, "❌ Ошибка создания счета")
            return
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💳 Оплатить USDT", url=pay_url), types.InlineKeyboardButton("🔄 Проверить", callback_data=f"check_{invoice_id}_{amount}"))
        bot.send_message(message.chat.id, f"💰 Счет на <b>{amount}$</b> создан!", parse_mode="HTML", reply_markup=markup)
    except: bot.send_message(message.chat.id, "❌ Число")

def process_withdraw_request(message):
    try:
        parts = message.text.split()
        address, amount = parts[0], int(parts[1])
        u = get_user(message.from_user.id)
        if amount < 5 or amount > u['balance']:
            bot.send_message(message.chat.id, "❌ 5+")
            return
        update_balance(message.from_user.id, -amount)
        update_stats(message.from_user.id, withdraw=amount)
        bot.send_message(message.chat.id, "✅ Заявка принята")
        bot.send_message(ADMIN_ID, f"📥 Вывод @{message.from_user.username}: {amount}$\n{address}")
    except: bot.send_message(message.chat.id, "❌ Формат: АДРЕС СУММА")

def process_activate_voucher(message):
    code = message.text.strip().upper()
    user_id = message.from_user.id
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT percent, uses_left FROM vouchers WHERE code = ?", (code,))
    voucher = cursor.fetchone()
    if not voucher:
        bot.send_message(message.chat.id, "❌ Неверно")
        conn.close()
        return
    percent, uses_left = voucher
    cursor.execute("SELECT 1 FROM voucher_history WHERE user_id = ? AND code = ?", (user_id, code))
    if cursor.fetchone():
        bot.send_message(message.chat.id, "❌ Уже активирован")
        conn.close()
        return
    if uses_left <= 0:
        bot.send_message(message.chat.id, "❌ Не активен")
        conn.close()
        return
    cursor.execute("UPDATE users SET active_voucher = ? WHERE user_id = ?", (code, user_id))
    cursor.execute("UPDATE vouchers SET uses_left = uses_left - 1 WHERE code = ?", (code,))
    cursor.execute("INSERT INTO voucher_history VALUES (?, ?)", (user_id, code))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, f"🎫 Активирован! +{percent}%", parse_mode="HTML")

def get_user_voucher_percent(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT active_voucher FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row and row[0]:
        cursor.execute("SELECT percent FROM vouchers WHERE code = ?", (row[0],))
        v_row = cursor.fetchone()
        conn.close()
        return v_row[0] if v_row else 0
    conn.close()
    return 0

def process_save_setting(message, key):
    set_set(key, message.text)
    bot.send_message(message.chat.id, f"✅ {key} сохранен")

def process_admin_balance(message):
    try:
        user_id, amount = map(int, message.text.split())
        update_balance(user_id, amount)
        bot.send_message(message.chat.id, f"✅ Баланс {user_id} = {amount}$")
    except: bot.send_message(message.chat.id, "❌ ID СУММА")

def process_admin_voucher(message):
    try:
        code, percent, uses = message.text.split()
        percent, uses = int(percent), int(uses)
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO vouchers (code, percent, uses_left) VALUES (?,?,?)", (code.upper(), percent, uses))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"✅ Ваучер {code}: +{percent}%, {uses} раз")
    except: bot.send_message(message.chat.id, "❌ КОД % АКТИВАЦИЙ")

def process_admin_broadcast(message):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()
    count = 0
    for user in users:
        try:
            bot.send_message(user[0], f"📢 <b>РАССЫЛКА</b>\n\n{message.text}", parse_mode="HTML")
            count += 1
            time.sleep(0.05)
        except: pass
    bot.send_message(message.chat.id, f"✅ Отправлено {count}")

if __name__ == '__main__':
    init_db()
    print("🎰 КАЗИНО V13.0 ЗАПУЩЕНО!")
    print("🌐 Прокси активен!")
    bot.infinity_polling()