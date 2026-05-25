import random
import time
import sqlite3
import telebot
from telebot import types
import requests

# === НАСТРОЙКИ БОТА ===
TOKEN = '8742929536:AAHYbXlX0KK_DakQ_3MB95xZ7bnzIhUmsa0'
ADMIN_ID = 1178979444
CRYPTO_BOT_TOKEN = '586791:AAYuv27u6bqo0uF2zeuQ7GRzYbc1H7rnRqz'

bot = telebot.TeleBot(TOKEN)
DB_NAME = 'casino.db'

admin_states = {}
active_crash_games = {}

# Список смайликов для анимации слотов
SLOT_EMOJIS = ["<tg-emoji emoji-id=5197468567750067655>🍒</tg-emoji>", "<tg-emoji emoji-id=5465456020006391799>🍋</tg-emoji>", "<tg-emoji emoji-id=5328287967301624438>💎</tg-emoji>", "<tg-emoji emoji-id=5217877328922693007>🍇</tg-emoji>", "<tg-emoji emoji-id=5359377882642667557>🌟</tg-emoji>", "<tg-emoji emoji-id=6080159332912075516>🥲</tg-emoji>", "<tg-emoji emoji-id=5199690788123994137>👑</tg-emoji>"]

# --- ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, balance INTEGER DEFAULT 0,
            deposited INTEGER DEFAULT 0, withdrawn INTEGER DEFAULT 0, games_played INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('CREATE TABLE IF NOT EXISTS vouchers (code TEXT PRIMARY KEY, amount INTEGER, uses_left INTEGER)')
    cursor.execute('CREATE TABLE IF NOT EXISTS voucher_history (user_id INTEGER, code TEXT, PRIMARY KEY (user_id, code))')
    cursor.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, val TEXT)')
    
    default_settings = {
        "txt_start": "👑 <b>Добро пожаловать в VIP Casino!</b> 👑\n\nТвой баланс: <b>{balance}$</b>\nИспытай свою удачу прямо сейчас!",
        "img_start": "",
        "txt_profile": "👤 <b>Ваш профиль:</b>\n\n💰 Баланс: <b>{balance}$</b>\n📊 Сыграно игр: {games_played}\n📥 Пополнений: {deposited}$\n📤 Выведено: {withdrawn}$",
        "img_profile": "",
        "txt_wallet": "💳 <b>Кошелек / Касса</b>\n\nПополнение через CryptoBot USDT (TON).\nМинимальный вывод: <b>5$</b>",
        "img_wallet": "",
        "txt_games_menu": "🎮 <b>Выберите игровой режим:</b>\n\nПомни: фортуна любит смелых!",
        "img_games_menu": "",
        "txt_voucher_menu": "🎫 <b>Введите секретный ваучер:</b>",
        "img_voucher_menu": "",
        "txt_slots_info": "🎰 <b>Игровой автомат 777</b>\n\nКлассический однорукий бандит. Шанс выигрыша — 35%!",
        "img_slots": "",
        "txt_crash_info": "🚀 <b>Режим Crash (Ракетка)</b>\n\nРакета летит вверх. Успей нажать кнопку «ЗАБРАТЬ» до взрыва!",
        "img_crash": "",
        "txt_dice_info": "🎲 <b>Игра в Кости (Dice)</b>\n\nСыграй против профессионального дилера казино. Шанс победы — 35%.",
        "img_dice": "",
        "txt_win": "🎉 <b>ПОБЕДА!</b>\n\nВы выиграли: <b>{win}$</b>! Забирай куш!",
        "txt_lose": "😢 <b>ПОРАЖЕНИЕ...</b>\n\nКазино забирает ставку. В следующий раз точно повезет!"
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
        except Exception: pass
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
    cursor.execute("SELECT user_id, username, balance, deposited, withdrawn, games_played FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT INTO users (user_id, username, balance) VALUES (?, ?, 0)", (user_id, username))
        conn.commit()
        cursor.execute("SELECT user_id, username, balance, deposited, withdrawn, games_played FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
    conn.close()
    return {"user_id": user[0], "username": user[1], "balance": user[2], "deposited": user[3], "withdrawn": user[4], "games_played": user[5]}

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

# --- СИСТЕМА ПОПОЛНЕНИЯ ---
def create_crypto_invoice(amount, user_id):
    urls = [
        "https://pay.cryptobot.site/api/createInvoice", 
        "https://pay.cryptobot.in/api/createInvoice",
        "https://pay.cryptobot.pay/api/createInvoice"
    ]
    headers = {"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN}
    payload = {"asset": "USDT", "amount": str(amount), "description": f"ID {user_id}", "payload": str(user_id)}
    
    for url in urls:
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=6)
            res_json = response.json()
            if res_json.get("result"):
                return res_json["result"]["pay_url"], res_json["result"]["invoice_id"]
        except Exception: pass
    return None, None

def check_crypto_invoice(invoice_id):
    urls = ["https://pay.cryptobot.site/api/getInvoices", "https://pay.cryptobot.in/api/getInvoices"]
    headers = {"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN}
    payload = {"invoice_ids": str(invoice_id)}
    for url in urls:
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=5).json()
            if response.get("result") and response["result"]["items"]:
                return response["result"]["items"][0]["status"] == "paid"
        except Exception: pass
    return False

def send_or_edit(chat_id, text, markup, msg_id=None, img_key=None):
    img_val = get_set(img_key) if img_key else ""
    if img_val and img_val.strip():
        if msg_id:
            try: bot.delete_message(chat_id, msg_id)
            except Exception: pass
        return bot.send_photo(chat_id, img_val, caption=text, parse_mode="HTML", reply_markup=markup)
    else:
        if msg_id:
            try: return bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text, parse_mode="HTML", reply_markup=markup)
            except Exception: pass
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
        types.InlineKeyboardButton("🖼 Изменить Фото / Картинку", callback_data="adm_img_list"),
        types.InlineKeyboardButton("💰 Изменить баланс игроку", callback_data="adm_change_bal"),
        types.InlineKeyboardButton("🎫 Создать ваучер", callback_data="adm_create_voucher"),
        types.InlineKeyboardButton("📢 Сделать рассылку", callback_data="adm_broadcast")
    )
    bot.send_message(message.chat.id, "🛠 <b>Панель администратора V8.1</b>", parse_mode="HTML", reply_markup=markup)

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
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🎰 Слоты 777", callback_data="bet_slots"),
            types.InlineKeyboardButton("🚀 Ракетка (Crash)", callback_data="bet_crash"),
            types.InlineKeyboardButton("🎲 Кости (Dice)", callback_data="bet_dice"),
            types.InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")
        )
        send_or_edit(chat_id, get_set("txt_games_menu"), support_btn(markup), m_id, "img_games_menu")
        
    elif call.data == "menu_profile":
        t = get_set("txt_profile", balance=u['balance'], games_played=u['games_played'], deposited=u['deposited'], withdrawn=u['withdrawn'])
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="main_menu"))
        send_or_edit(chat_id, t, support_btn(markup), m_id, "img_profile")
        
    elif call.data == "menu_wallet":
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📥 Пополнить", callback_data="wallet_deposit"),
            types.InlineKeyboardButton("📤 Вывести", callback_data="wallet_withdraw"),
            types.InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")
        )
        send_or_edit(chat_id, get_set("txt_wallet"), support_btn(markup), m_id, "img_wallet")

    elif call.data == "wallet_deposit":
        msg = bot.send_message(chat_id, "💵 <b>Введите сумму пополнения ($):</b>", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_deposit_amount)
        
    elif call.data == "wallet_withdraw":
        msg = bot.send_message(chat_id, "📤 <b>Вывод средств (Минимум 5$)</b>\n\nВведите адрес и сумму через пробел:", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_withdraw_request)

    elif call.data.startswith("bet_"):
        game_type = call.data.split("_")[1]
        msg = bot.send_message(chat_id, f"💰 <b>Какую сумму вы хотите поставить на {game_type}?</b>\nВаш баланс: {u['balance']}$", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_get_bet, game_type)

    elif call.data.startswith("startgame_"):
        _, game_type, bet = call.data.split("_")
        bet = int(bet)
        if u['balance'] < bet:
            bot.answer_callback_query(call.id, "❌ Не хватает баланса!", show_alert=True)
            return
        
        update_balance(user_id, -bet)
        update_stats(user_id, game=1)
        
        # ==========================================================
        # 🎰 СЛОТЫ (Шанс 35%, Турбо-прокрутка 0.25с, 20 раз за 5с)
        # ==========================================================
        if game_type == "slots":
            is_win = random.random() <= 0.35
            
            if is_win:
                win_emoji = random.choice(["7️⃣", "💎", "🔔", "🍒"])
                final_res = [win_emoji, win_emoji, win_emoji]
            else:
                res1 = random.choice(SLOT_EMOJIS)
                res2 = random.choice([e for e in SLOT_EMOJIS if e != res1])
                res3 = random.choice(SLOT_EMOJIS)
                final_res = [res1, res2, res3]

            for _ in range(20):
                fake_1 = random.choice(SLOT_EMOJIS)
                fake_2 = random.choice(SLOT_EMOJIS)
                fake_3 = random.choice(SLOT_EMOJIS)
                try:
                    bot.edit_message_text(
                        f"🎰 <b>БАРАБАНЫ КРУТЯТСЯ (ТУРБО)...</b>\n\n[ {fake_1} | {fake_2} | {fake_3} ]\n\nУдача уже близко!",
                        chat_id, m_id, parse_mode="HTML"
                    )
                except Exception: pass
                time.sleep(0.25)

            if is_win:
                win = bet * 3
                update_balance(user_id, win)
                t = f"🎰 ИТОГОВЫЙ РЕЗУЛЬТАТ: [ {final_res[0]} | {final_res[1]} | {final_res[2]} ]\n\n" + get_set("txt_win", win=win)
            else:
                t = f"🎰 ИТОГОВЫЙ РЕЗУЛЬТАТ: [ {final_res[0]} | {final_res[1]} | {final_res[2]} ]\n\n" + get_set("txt_lose")
                
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🎰 Еще раз", callback_data="bet_slots"), types.InlineKeyboardButton("⬅️ Меню", callback_data="main_menu"))
            bot.send_message(chat_id, t, parse_mode="HTML", reply_markup=markup)

        # ==========================================
        # 🚀 РАКЕТКА (Сетка по новым шансам из ТЗ)
        # ==========================================
        elif game_type == "crash":
            ranges = [
                (1.00, 1.00), (1.01, 1.12), (1.13, 1.18), (1.19, 1.35),
                (1.36, 1.50), (1.51, 1.75), (1.76, 1.99), (2.00, 2.10),
                (2.11, 2.20), (2.21, 2.70), (2.71, 3.00), (3.01, 3.15),
                (3.16, 3.30), (3.31, 3.54)
            ]
            weights = [5, 55, 8, 5, 4, 5, 5, 3, 3, 2, 2, 1, 1, 1]
            
            chosen_range = random.choices(ranges, weights=weights, k=1)[0]
            crash_limit = round(random.uniform(chosen_range[0], chosen_range[1]), 2)
                
            active_crash_games[user_id] = {"status": "flying", "bet": bet}
            current_x = 1.00
            step = 0.02
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("💰 ЗАБРАТЬ ВЫИГРЫШ! <t", callback_data="claim_crash"))
            
            while current_x < crash_limit:
                if active_crash_games.get(user_id, {}).get("status") == "claimed":
                    break
                try:
                    bot.edit_message_text(
                        f"🚀 <b>Ракетка летит медленно...</b>\n\n📈 Текущий множитель: <b>{round(current_x, 2)}x</b>\n💰 Возможный выигрыш: {int(bet * current_x)}$\n\nУспей забрать до взрыва!",
                        chat_id, m_id, parse_mode="HTML", reply_markup=markup
                    )
                except Exception: pass
                
                time.sleep(1)
                current_x += step + random.uniform(0.005, 0.015)

            if active_crash_games.get(user_id, {}).get("status") == "claimed":
                final_x = active_crash_games[user_id]["final_x"]
                win = int(bet * final_x)
                update_balance(user_id, win)
                t = f"🚀 Вы успешно забрали деньги на коэффициенте <b>{round(final_x, 2)}x</b>!\n\n" + get_set("txt_win", win=win)
            else:
                t = f"💥 <b>КРАШ! Ракета взорвалась на отметке {round(crash_limit, 2)}x!</b>\n\nВы не успели нажать на кнопку.\n" + get_set("txt_lose")
                
            if user_id in active_crash_games: del active_crash_games[user_id]
            
            end_markup = types.InlineKeyboardMarkup()
            end_markup.add(types.InlineKeyboardButton("🚀 Запустить еще", callback_data="bet_crash"), types.InlineKeyboardButton("⬅️ Меню", callback_data="main_menu"))
            bot.send_message(chat_id, t, parse_mode="HTML", reply_markup=end_markup)

        # ==========================================
        # 🎲 КОСТИ (Шанс выигрыша поднят до 35%)
        # ==========================================
        elif game_type == "dice":
            c_score = random.randint(7, 11)
            t = f"🤵 <b>Дилер казино делает бросок...</b>\n\n🎲 Результат дилера: <b>{c_score}</b>\n\nТеперь ваша очередь!"
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🎲 Бросить свои кости", callback_data=f"playerdice_{bet}_{c_score}"))
            bot.edit_message_text(t, chat_id, m_id, parse_mode="HTML", reply_markup=markup)

    elif call.data == "claim_crash":
        if user_id in active_crash_games and active_crash_games[user_id]["status"] == "flying":
            try:
                text = call.message.text
                parsed_x = float(text.split("множитель: ")[1].split("x")[0])
            except Exception: parsed_x = 1.05
            
            active_crash_games[user_id]["status"] = "claimed"
            active_crash_games[user_id]["final_x"] = parsed_x
            bot.answer_callback_query(call.id, "✅ Успешно снято!")

    elif call.data.startswith("playerdice_"):
        _, bet, c_score = call.data.split("_")
        bet, c_score = int(bet), int(c_score)
        
        if random.random() <= 0.35:
            p_score = random.randint(c_score + 1, 12)
            win = bet * 2
            update_balance(user_id, win)
            t = f"🎲 Твои очки: <b>{p_score}</b>\n🤵 Очки дилера: <b>{c_score}</b>\n\n" + get_set("txt_win", win=win)
        else:
            p_score = random.randint(2, c_score)
            t = f"🎲 Твои очки: <b>{p_score}</b>\n🤵 Очки дилера: <b>{c_score}</b>\n\n" + get_set("txt_lose")
            
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🎲 Еще раз", callback_data="bet_dice"), types.InlineKeyboardButton("⬅️ Меню", callback_data="main_menu"))
        bot.edit_message_text(t, chat_id, m_id, parse_mode="HTML", reply_markup=markup)

    # АДМИНКА
    elif call.data == "adm_text_list":
        markup = types.InlineKeyboardMarkup()
        keys = ["txt_start", "txt_profile", "txt_wallet", "txt_games_menu", "txt_slots_info", "txt_crash_info", "txt_dice_info", "txt_win", "txt_lose"]
        for k in keys: markup.add(types.InlineKeyboardButton(f"✏️ {k}", callback_data=f"editkey_{k}"))
        bot.edit_message_text("Какую секцию текста изменить?", chat_id, m_id, reply_markup=markup)
    elif call.data == "adm_img_list":
        markup = types.InlineKeyboardMarkup()
        keys = ["img_start", "img_profile", "img_wallet", "img_games_menu", "img_slots", "img_crash", "img_dice"]
        for k in keys: markup.add(types.InlineKeyboardButton(f"🖼 {k}", callback_data=f"editphoto_{k}"))
        bot.edit_message_text("Для какого меню загрузить фото?", chat_id, m_id, reply_markup=markup)
    elif call.data.startswith("editkey_"):
        key = call.data.split("_")[1]
        msg = bot.send_message(chat_id, f"📝 Текст для {key}:")
        bot.register_next_step_handler(msg, process_save_setting, key)
    elif call.data.startswith("editphoto_"):
        key = call.data.split("_")[1]
        admin_states[user_id] = key
        bot.send_message(chat_id, f"🖼 Прикрепите и отправьте фото для {key}.")
    elif call.data == "adm_change_bal":
        msg = bot.send_message(chat_id, "Введите `[ID] [СУММА]`:")
        bot.register_next_step_handler(msg, process_admin_balance)
    elif call.data == "adm_create_voucher":
        msg = bot.send_message(chat_id, "Введите `[КОД] [СУММА] [АКТИВАЦИИ]`:")
        bot.register_next_step_handler(msg, process_admin_voucher)
    elif call.data == "adm_broadcast":
        msg = bot.send_message(chat_id, "Введите текст рассылки:")
        bot.register_next_step_handler(msg, process_admin_broadcast)

@bot.message_handler(content_types=['photo', 'text'])
def handle_admin_media(message):
    user_id = message.from_user.id
    if user_id == ADMIN_ID and user_id in admin_states:
        key = admin_states[user_id]
        if message.content_type == 'photo':
            file_id = message.photo[-1].file_id
            set_set(key, file_id)
            bot.send_message(message.chat.id, f"✅ Фотография для {key} успешно сохранена!")
            del admin_states[user_id]
        elif message.content_type == 'text' and message.text.lower() == 'убрать':
            set_set(key, "")
            bot.send_message(message.chat.id, "Фото удалено.")
            del admin_states[user_id]

def process_get_bet(message, game_type):
    try:
        bet = int(message.text.strip())
        u = get_user(message.from_user.id)
        if bet <= 0 or bet > u['balance']:
            bot.send_message(message.chat.id, "❌ Ставка некорректна.")
            return
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔥 ИГРАТЬ 🔥", callback_data=f"startgame_{game_type}_{bet}"), types.InlineKeyboardButton("❌ Отмена", callback_data="menu_games"))
        send_or_edit(message.chat.id, f"{get_set(f'txt_{game_type}_info')}\n\nСтавка: <b>{bet}$</b>", markup, img_key=f"img_{game_type}")
    except Exception: bot.send_message(message.chat.id, "Введите число.")

def process_deposit_amount(message):
    try:
        amount = int(message.text.strip())
        pay_url, invoice_id = create_crypto_invoice(amount, message.from_user.id)
        if not pay_url:
            bot.send_message(message.chat.id, "❌ Ошибка генерации счета. Проверьте токен CryptoBot.")
            return
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💳 Оплатить", url=pay_url))
        markup.add(types.InlineKeyboardButton("🔄 Проверить", callback_data=f"check_{invoice_id}_{amount}"))
        bot.send_message(message.chat.id, f"Счет на {amount}$ создан:", reply_markup=markup)
    except Exception: bot.send_message(message.chat.id, "Ошибка ввода")

@bot.callback_query_handler(func=lambda call: call.data.startswith("check_"))
def check_payment(call):
    _, invoice_id, amount = call.data.split("_")
    if check_crypto_invoice(invoice_id):
        update_balance(call.from_user.id, int(amount))
        update_stats(call.from_user.id, deposit=int(amount))
        bot.answer_callback_query(call.id, "🎉 Пополнено!", show_alert=True)
    else: bot.answer_callback_query(call.id, "❌ Не оплачено.", show_alert=True)

def process_withdraw_request(message):
    try:
        parts = message.text.split()
        address, amount = parts[0], int(parts[1])
        u = get_user(message.from_user.id)
        if amount < 5 or amount > u['balance']:
            bot.send_message(message.chat.id, "❌ Ошибка вывода (мин. 5$).")
            return
        update_balance(message.from_user.id, -amount)
        update_stats(message.from_user.id, withdraw=amount)
        bot.send_message(message.chat.id, "✅ Заявка создана!")
        bot.send_message(ADMIN_ID, f"📥 Вывод @{message.from_user.username}: {amount}$\n<code>{address}</code>", parse_mode="HTML")
    except Exception: bot.send_message(message.chat.id, "Неверный формат.")

def process_save_setting(message, key):
    set_set(key, message.text)
    bot.send_message(message.chat.id, "Сохранено.")

def process_admin_balance(message):
    try:
        i, s = map(int, message.text.split())
        update_balance(i, s)
        bot.send_message(message.chat.id, "Готово")
    except Exception: bot.send_message(message.chat.id, "Ошибка")

def process_admin_voucher(message):
    try:
        c, a, u = message.text.split()
        a, u = int(a), int(u)
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO vouchers VALUES (?,?,?)", (c,a,u))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "Создан")
    except Exception: bot.send_message(message.chat.id, "Ошибка")

def process_admin_broadcast(message):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    ids = cursor.fetchall()
    conn.close()
    for r in ids:
        try: 
            bot.send_message(r[0], message.text, parse_mode="HTML")
            time.sleep(0.05)
        except Exception: pass
    bot.send_message(message.chat.id, "Готово")

if __name__ == '__main__':
    init_db()
    print("Казино V8.1 успешно запущено! Все ошибки синтаксиса устранены.")
    bot.infinity_polling()