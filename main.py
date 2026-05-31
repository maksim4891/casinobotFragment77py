import random
import time
import sqlite3
import urllib.request
import urllib.error
import json
import telebot
from telebot import types
import socks
import socket

# === НАСТРОЙКИ ПРОКСИ (ДЛЯ BOTHOST) ===
PROXY_HOST = "5.78.217.202"
PROXY_PORT = 42341
PROXY_PASSWORD = "dd104462821249bd7ac519130220c25d09"

def setup_proxy():
    try:
        # Настройка SOCKS5 прокси
        socks.set_default_proxy(
            socks.SOCKS5,
            PROXY_HOST,
            PROXY_PORT,
            password=PROXY_PASSWORD
        )
        socket.socket = socks.socksocket
        
        # Настройка для urllib
        proxy_handler = urllib.request.ProxyHandler({
            'http': f'socks5://:{PROXY_PASSWORD}@{PROXY_HOST}:{PROXY_PORT}',
            'https': f'socks5://:{PROXY_PASSWORD}@{PROXY_HOST}:{PROXY_PORT}'
        })
        opener = urllib.request.build_opener(proxy_handler)
        urllib.request.install_opener(opener)
        
        print("✅ Прокси успешно настроен!")
        return True
    except Exception as e:
        print(f"❌ Ошибка настройки прокси: {e}")
        print("Убедитесь, что PySocks установлен: pip install PySocks")
        return False

# Запускаем настройку прокси
setup_proxy()

# === НАСТРОЙКИ БОТА ===
TOKEN = '8742929536:AAGX-oAF4CZktcfxNwAHPnavt-sUZk-JY1Y'
ADMIN_ID = 1178979444
CRYPTO_BOT_TOKEN = '586791:AAYuv27u6bqo0uF2zeuQ7GRzYbc1H7rnRqz'

bot = telebot.TeleBot(TOKEN)
DB_NAME = 'casino.db'

admin_states = {}
active_crash_games = {}

# Список смайликов для анимации слотов
SLOT_EMOJIS = ["🍒", "🍋", "💎", "🍇", "🍊", "🔔", "7️⃣"]

# --- ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ---
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
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE vouchers ADD COLUMN percent INTEGER")
    except sqlite3.OperationalError:
        pass
    
    default_settings = {
        "txt_start": "👑 <b>Добро пожаловать в VIP Casino!</b> 👑\n\nТвой баланс: <b>{balance}$</b>\nИспытай свою удачу прямо сейчас!",
        "img_start": "",
        "txt_profile": "👤 <b>Ваш профиль:</b>\n\n💰 Баланс: <b>{balance}$</b>\n📊 Сыграно игр: {games_played}\n📥 Пополнений: {deposited}$\n📤 Выведено: {withdrawn}$",
        "img_profile": "",
        "txt_wallet": "💳 <b>Кошелек / Касса</b>\n\nПополнение через CryptoBot USDT (TON).\nМинимальный вывод: <b>5$</b>",
        "img_wallet": "",
        "txt_games_menu": "🎮 <b>Выберите игровой режим:</b>\n\nПомни: фортуна любит смелых!",
        "img_games_menu": "",
        "txt_voucher_menu": "🎫 <b>Введите секретный ваучер:</b>\n\nВаучер дает бонусный % к твоему следующему пополнению счета!",
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
        try:
            text = text.format(**kwargs)
        except Exception:
            pass
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

# --- СИСТЕМА ПОПОЛНЕНИЯ (РАБОЧАЯ) ---
def create_crypto_invoice(amount, user_id):
    urls = [
        "https://pay.crypt.bot/api/createInvoice",
    ]
    
    payload = {
        "asset": "USDT",
        "amount": str(amount),
        "description": f"Пополнение баланса ID{user_id}",
        "payload": str(user_id),
        "expires_in": 3600
    }
    
    data = json.dumps(payload).encode('utf-8')
    
    for url in urls:
        try:
            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Crypto-Pay-API-Token", CRYPTO_BOT_TOKEN)
            req.add_header("Content-Type", "application/json")
            req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            
            with urllib.request.urlopen(req, timeout=15) as response:
                response_data = response.read().decode()
                res_json = json.loads(response_data)
                
                if res_json.get("ok") and res_json.get("result"):
                    result = res_json["result"]
                    print(f"[CryptoBot Success]: Счет создан")
                    return result["pay_url"], result["invoice_id"]
                else:
                    print(f"[CryptoBot Error]: {res_json.get('error', 'Unknown error')}")
                    
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else "No body"
            print(f"[CryptoBot HTTP Error] Код: {e.code} | Ответ: {error_body[:200]}")
        except Exception as e:
            print(f"[CryptoBot Error] {e}")
    
    return None, None

def check_crypto_invoice(invoice_id):
    urls = [
        "https://pay.crypt.bot/api/getInvoices",
    ]
    
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
        except Exception as e:
            print(f"[Check Error] {e}")
            continue
    
    return False

def send_or_edit(chat_id, text, markup, msg_id=None, img_key=None):
    img_val = get_set(img_key) if img_key else ""
    if img_val and img_val.strip():
        if msg_id:
            try:
                bot.delete_message(chat_id, msg_id)
            except Exception:
                pass
        return bot.send_photo(chat_id, img_val, caption=text, parse_mode="HTML", reply_markup=markup)
    else:
        if msg_id:
            try:
                return bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text, parse_mode="HTML", reply_markup=markup)
            except Exception:
                pass
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

# --- ДИАГНОСТИКА ПРОКСИ ---
@bot.message_handler(commands=['check_proxy'])
def check_proxy(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    bot.send_message(message.chat.id, "🔄 Проверяю работу прокси и API...")
    
    try:
        req = urllib.request.Request("https://pay.crypt.bot/api/getMe", method="GET")
        req.add_header("Crypto-Pay-API-Token", CRYPTO_BOT_TOKEN)
        response = urllib.request.urlopen(req, timeout=10)
        bot.send_message(message.chat.id, "✅ Прокси работает! CryptoBot API доступен!")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {str(e)[:300]}")

@bot.message_handler(commands=['start'])
def start_cmd(message):
    u = get_user(message.from_user.id, message.from_user.first_name)
    t = get_set("txt_start", balance=u['balance'])
    send_or_edit(message.chat.id, t, main_menu(), img_key="img_start")

@bot.message_handler(commands=['admin'])
def admin_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📝 Изменить Текст", callback_data="adm_text_list"),
        types.InlineKeyboardButton("🖼 Изменить Фото", callback_data="adm_img_list"),
        types.InlineKeyboardButton("💰 Изменить баланс", callback_data="adm_change_bal"),
        types.InlineKeyboardButton("🎫 Создать ваучер", callback_data="adm_create_voucher"),
        types.InlineKeyboardButton("📢 Сделать рассылку", callback_data="adm_broadcast"),
        types.InlineKeyboardButton("🔧 Проверить прокси", callback_data="adm_check_proxy")
    )
    bot.send_message(message.chat.id, "🛠 <b>Панель администратора V10.0</b>", parse_mode="HTML", reply_markup=markup)

# Глобальный обработчик кнопки проверки платежа
@bot.callback_query_handler(func=lambda call: call.data.startswith("check_"))
def check_payment(call):
    _, invoice_id, amount = call.data.split("_")
    user_id = call.from_user.id
    amount = int(amount)
    
    if check_crypto_invoice(invoice_id):
        percent = get_user_voucher_percent(user_id)
        bonus = 0
        voucher_text = ""
        
        if percent > 0:
            bonus = int(amount * (percent / 100))
            voucher_text = f" (включая бонус +{percent}% по ваучеру!)"
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET active_voucher = NULL WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()

        total_credit = amount + bonus
        update_balance(user_id, total_credit)
        update_stats(user_id, deposit=amount)
        
        bot.answer_callback_query(call.id, f"🎉 Баланс пополнен на {total_credit}$!", show_alert=True)
        bot.send_message(user_id, f"✅ Оплата подтверждена! На ваш баланс зачислено <b>{total_credit}$</b>{voucher_text}.", parse_mode="HTML")
    else:
        bot.answer_callback_query(call.id, "❌ Счет еще не оплачен.", show_alert=True)

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
        v_status = f"\n🎫 Активный бонус: <b>+{get_user_voucher_percent(user_id)}% к депозиту</b>" if u['active_voucher'] else ""
        t = get_set("txt_profile", balance=u['balance'], games_played=u['games_played'], deposited=u['deposited'], withdrawn=u['withdrawn']) + v_status
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

    elif call.data == "menu_voucher":
        msg = bot.send_message(chat_id, get_set("txt_voucher_menu"), parse_mode="HTML")
        bot.register_next_step_handler(msg, process_activate_voucher)

    elif call.data == "wallet_deposit":
        msg = bot.send_message(chat_id, "💵 <b>Введите сумму пополнения ($):</b>\n\nМинимальная сумма: 1$", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_deposit_amount)
        
    elif call.data == "wallet_withdraw":
        msg = bot.send_message(chat_id, "📤 <b>Вывод средств (Минимум 5$)</b>\n\nВведите адрес и сумму через пробел:", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_withdraw_request)

    elif call.data == "adm_check_proxy":
        check_proxy(call.message)

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
                        f"🎰 <b>БАРАБАНЫ КРУТЯТСЯ...</b>\n\n[ {fake_1} | {fake_2} | {fake_3} ]",
                        chat_id, m_id, parse_mode="HTML"
                    )
                except Exception:
                    pass
                time.sleep(0.2)

            if is_win:
                win = bet * 3
                update_balance(user_id, win)
                t = f"🎰 РЕЗУЛЬТАТ: [ {final_res[0]} | {final_res[1]} | {final_res[2]} ]\n\n" + get_set("txt_win", win=win)
            else:
                t = f"🎰 РЕЗУЛЬТАТ: [ {final_res[0]} | {final_res[1]} | {final_res[2]} ]\n\n" + get_set("txt_lose")
                
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🎰 Еще раз", callback_data="bet_slots"), types.InlineKeyboardButton("⬅️ Меню", callback_data="main_menu"))
            bot.send_message(chat_id, t, parse_mode="HTML", reply_markup=markup)

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
            markup.add(types.InlineKeyboardButton("💰 ЗАБРАТЬ ВЫИГРЫШ!", callback_data="claim_crash"))
            
            while current_x < crash_limit:
                if active_crash_games.get(user_id, {}).get("status") == "claimed":
                    break
                try:
                    bot.edit_message_text(
                        f"🚀 <b>Ракета летит!</b>\n\n📈 Множитель: <b>{round(current_x, 2)}x</b>\n💰 Выигрыш: {int(bet * current_x)}$\n\nУспей забрать!",
                        chat_id, m_id, parse_mode="HTML", reply_markup=markup
                    )
                except Exception:
                    pass
                
                time.sleep(1)
                current_x += step + random.uniform(0.005, 0.015)

            if active_crash_games.get(user_id, {}).get("status") == "claimed":
                final_x = active_crash_games[user_id]["final_x"]
                win = int(bet * final_x)
                update_balance(user_id, win)
                t = f"🚀 Вы забрали на {round(final_x, 2)}x!\n\n" + get_set("txt_win", win=win)
            else:
                t = f"💥 <b>ВЗРЫВ на {round(crash_limit, 2)}x!</b>\n\n" + get_set("txt_lose")
                
            if user_id in active_crash_games:
                del active_crash_games[user_id]
            
            end_markup = types.InlineKeyboardMarkup()
            end_markup.add(types.InlineKeyboardButton("🚀 Еще раз", callback_data="bet_crash"), types.InlineKeyboardButton("⬅️ Меню", callback_data="main_menu"))
            bot.send_message(chat_id, t, parse_mode="HTML", reply_markup=end_markup)

        elif game_type == "dice":
            c_score = random.randint(7, 11)
            t = f"🤵 <b>Дилер бросает...</b>\n\n🎲 Результат: <b>{c_score}</b>\n\nТвоя очередь!"
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🎲 Бросить кости", callback_data=f"playerdice_{bet}_{c_score}"))
            bot.edit_message_text(t, chat_id, m_id, parse_mode="HTML", reply_markup=markup)

    elif call.data == "claim_crash":
        if user_id in active_crash_games and active_crash_games[user_id]["status"] == "flying":
            try:
                text = call.message.text
                parsed_x = float(text.split("множитель: ")[1].split("x")[0])
            except Exception:
                parsed_x = 1.05
            
            active_crash_games[user_id]["status"] = "claimed"
            active_crash_games[user_id]["final_x"] = parsed_x
            bot.answer_callback_query(call.id, "✅ Выигрыш зафиксирован!")

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
        for k in keys:
            markup.add(types.InlineKeyboardButton(f"✏️ {k}", callback_data=f"editkey_{k}"))
        bot.edit_message_text("✏️ <b>Выберите текст для изменения:</b>", chat_id, m_id, parse_mode="HTML", reply_markup=markup)
    
    elif call.data == "adm_img_list":
        markup = types.InlineKeyboardMarkup()
        keys = ["img_start", "img_profile", "img_wallet", "img_games_menu", "img_slots", "img_crash", "img_dice"]
        for k in keys:
            markup.add(types.InlineKeyboardButton(f"🖼 {k}", callback_data=f"editphoto_{k}"))
        bot.edit_message_text("🖼 <b>Для какого меню загрузить фото?</b>", chat_id, m_id, parse_mode="HTML", reply_markup=markup)
    
    elif call.data.startswith("editkey_"):
        key = call.data.split("_")[1]
        msg = bot.send_message(chat_id, f"📝 Новый текст для <code>{key}</code>:", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_save_setting, key)
    
    elif call.data.startswith("editphoto_"):
        key = call.data.split("_")[1]
        admin_states[user_id] = key
        bot.send_message(chat_id, f"🖼 Отправьте фото для {key}\n\nИли «убрать» чтобы удалить")
    
    elif call.data == "adm_change_bal":
        msg = bot.send_message(chat_id, "Введите <code>ID СУММА</code>", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_admin_balance)
    
    elif call.data == "adm_create_voucher":
        msg = bot.send_message(chat_id, "Введите <code>КОД ПРОЦЕНТ АКТИВАЦИЙ</code>\n\nПример: <code>BONUS50 50 100</code>", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_admin_voucher)
    
    elif call.data == "adm_broadcast":
        msg = bot.send_message(chat_id, "📢 Введите текст рассылки:", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_admin_broadcast)

@bot.message_handler(content_types=['photo', 'text'])
def handle_admin_media(message):
    user_id = message.from_user.id
    if user_id == ADMIN_ID and user_id in admin_states:
        key = admin_states[user_id]
        if message.content_type == 'photo':
            file_id = message.photo[-1].file_id
            set_set(key, file_id)
            bot.send_message(message.chat.id, f"✅ Фото для {key} сохранено!")
            del admin_states[user_id]
        elif message.content_type == 'text' and message.text.lower() == 'убрать':
            set_set(key, "")
            bot.send_message(message.chat.id, "✅ Фото удалено!")
            del admin_states[user_id]

def process_get_bet(message, game_type):
    try:
        bet = int(message.text.strip())
        u = get_user(message.from_user.id)
        if bet <= 0 or bet > u['balance']:
            bot.send_message(message.chat.id, "❌ Некорректная ставка")
            return
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🔥 ИГРАТЬ", callback_data=f"startgame_{game_type}_{bet}"),
            types.InlineKeyboardButton("❌ Отмена", callback_data="menu_games")
        )
        send_or_edit(message.chat.id, f"{get_set(f'txt_{game_type}_info')}\n\nСтавка: <b>{bet}$</b>", markup, img_key=f"img_{game_type}")
    except Exception:
        bot.send_message(message.chat.id, "❌ Введите число")

def process_deposit_amount(message):
    try:
        amount = int(message.text.strip())
        
        if amount <= 0:
            bot.send_message(message.chat.id, "❌ Сумма должна быть больше 0")
            return
        
        pay_url, invoice_id = create_crypto_invoice(amount, message.from_user.id)
        
        if not pay_url:
            bot.send_message(message.chat.id, "❌ Ошибка создания счета. Проверьте /check_proxy")
            return
            
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("💳 Оплатить USDT", url=pay_url),
            types.InlineKeyboardButton("🔄 Проверить оплату", callback_data=f"check_{invoice_id}_{amount}")
        )
        bot.send_message(message.chat.id, f"💰 Счет на <b>{amount}$</b> создан!\n\nПосле оплаты нажмите «Проверить оплату»", parse_mode="HTML", reply_markup=markup)
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Введите число")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {str(e)[:100]}")

# --- ЛОГИКА ВАУЧЕРОВ ---
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

def process_activate_voucher(message):
    code = message.text.strip()
    user_id = message.from_user.id
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT percent, uses_left FROM vouchers WHERE code = ?", (code,))
    voucher = cursor.fetchone()
    
    if not voucher:
        bot.send_message(message.chat.id, "❌ Неверный код ваучера")
        conn.close()
        return
        
    percent, uses_left = voucher[0], voucher[1]
    
    cursor.execute("SELECT 1 FROM voucher_history WHERE user_id = ? AND code = ?", (user_id, code))
    already_used = cursor.fetchone()
    
    if already_used:
        bot.send_message(message.chat.id, "❌ Вы уже использовали этот ваучер")
        conn.close()
        return
        
    if uses_left <= 0:
        bot.send_message(message.chat.id, "❌ Ваучер больше не активен")
        conn.close()
        return
        
    cursor.execute("UPDATE users SET active_voucher = ? WHERE user_id = ?", (code, user_id))
    cursor.execute("UPDATE vouchers SET uses_left = uses_left - 1 WHERE code = ?", (code,))
    cursor.execute("INSERT INTO voucher_history VALUES (?, ?)", (user_id, code))
    conn.commit()
    conn.close()
    
    bot.send_message(
        message.chat.id, 
        f"🎫 <b>Ваучер активирован!</b>\n\n+{percent}% к следующему пополнению!", 
        parse_mode="HTML"
    )

def process_withdraw_request(message):
    try:
        parts = message.text.split()
        address, amount = parts[0], int(parts[1])
        u = get_user(message.from_user.id)
        if amount < 5 or amount > u['balance']:
            bot.send_message(message.chat.id, "❌ Ошибка (мин 5$ или недостаточно средств)")
            return
        update_balance(message.from_user.id, -amount)
        update_stats(message.from_user.id, withdraw=amount)
        bot.send_message(message.chat.id, "✅ Заявка на вывод принята!")
        bot.send_message(ADMIN_ID, f"📥 Вывод @{message.from_user.username}: {amount}$\n{address}", parse_mode="HTML")
    except Exception:
        bot.send_message(message.chat.id, "❌ Формат: АДРЕС СУММА")

def process_save_setting(message, key):
    set_set(key, message.text)
    bot.send_message(message.chat.id, f"✅ {key} сохранен!")

def process_admin_balance(message):
    try:
        user_id, amount = map(int, message.text.split())
        update_balance(user_id, amount)
        bot.send_message(message.chat.id, f"✅ Баланс {user_id} изменен на {amount}$")
    except Exception:
        bot.send_message(message.chat.id, "❌ Формат: ID СУММА")

def process_admin_voucher(message):
    try:
        code, percent, uses = message.text.split()
        percent, uses = int(percent), int(uses)
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO vouchers (code, percent, uses_left) VALUES (?,?,?)", (code.upper(), percent, uses))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"✅ Ваучер {code} создан! +{percent}%, {uses} активаций")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

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
        except:
            pass
    
    bot.send_message(message.chat.id, f"✅ Рассылка завершена! Отправлено: {count}")

if __name__ == '__main__':
    init_db()
    print("🎰 КАЗИНО V10.0 ЗАПУЩЕНО!")
    print(f"🤖 Бот: @{bot.get_me().username}")
    print(f"👑 Админ: {ADMIN_ID}")
    print(f"🌐 Прокси: {PROXY_HOST}:{PROXY_PORT}")
    bot.infinity_polling()