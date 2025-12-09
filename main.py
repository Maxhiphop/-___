import telebot
from telebot import types
import json
import time
import threading
import os
import random

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = '8361675894:AAHGtLc7SqcMof2CpyWXkrPfX79fKBZ_wj8'
DATA_FILE = 'users.json'

# Новый и расширенный список предметов с их характеристиками
ITEMS = {
    # --- ЕДА (Восстанавливает Голод, тратит Энергию) ---
    'berry':    {'name': 'Ягода 🍓',    'price': 10, 'hunger': 15, 'energy_cost': 0},
    'fish':     {'name': 'Рыба 🐟',     'price': 30, 'hunger': 35, 'energy_cost': 5},
    'steak':    {'name': 'Стейк 🥩',    'price': 60, 'hunger': 60, 'energy_cost': 15},
    
    # --- ИГРУШКИ (Восстанавливают Счастье, тратит Энергию и Голод) ---
    'ball':     {'name': 'Мячик ⚽',    'price': 15, 'mood': 20, 'energy_cost': 5, 'hunger_cost': 5},
    'laser':    {'name': 'Лазер 🔦',    'price': 40, 'mood': 45, 'energy_cost': 10, 'hunger_cost': 10},
    'quest':    {'name': 'Квест 🗺️',    'price': 80, 'mood': 70, 'energy_cost': 20, 'hunger_cost': 15},
    
    # --- БОНУСЫ (Восстанавливают Энергию) ---
    'coffee':   {'name': 'Кофе ☕',    'price': 35, 'energy': 40, 'mood_cost': 10},  # Эффект: -10 Настроение
    'vitamins': {'name': 'Витамины 💊', 'price': 70, 'energy': 65, 'mood_cost': 0},   # Нет побочных эффектов
    'elixir':   {'name': 'Эликсир ✨',  'price': 150, 'energy': 100, 'hunger': 100, 'mood': 100, 'mood_cost': 0} # Полное восстановление
}

# Категории для магазина
SHOP_CATEGORIES = {
    'food':     {'emoji': '🍖', 'title': 'Еда (Голод)'},
    'toys':     {'emoji': '⚽', 'title': 'Игрушки (Счастье)'},
    'boosts':   {'emoji': '⚡', 'title': 'Бонусы (Энергия)'},
}

DUEL_COOLDOWN = 300 # 5 минут
WIN_REWARD = 50

bot = telebot.TeleBot(API_TOKEN)
users = {}
captcha_storage = {}

# --- РАБОТА С ДАННЫМИ ---
def load_data():
    global users
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            try:
                users = json.load(f)
                users = {int(k): v for k, k in users.items()}
            except:
                users = {}

def save_data():
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

def ensure_user_data(user_id):
    """Обновляет данные старых пользователей, добавляя новые поля и предметы"""
    if user_id not in users: return
    
    defaults = {
        "coins": 100,
        # Заменяем инвентарь на новый, чтобы не было конфликтов со старыми ключами
        "inventory": {'berry': 3, 'ball': 1, 'coffee': 0},
        "last_duel": 0
    }
    
    for key, val in defaults.items():
        if key not in users[user_id]:
            users[user_id][key] = val
        elif key == "inventory" and isinstance(users[user_id][key], dict):
             # Добавляем новые предметы, если их нет
            for item_key in ITEMS.keys():
                if item_key not in users[user_id]['inventory']:
                    users[user_id]['inventory'][item_key] = 0

load_data()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def get_progress_bar(value, length=8):
    filled = int(length * value / 100)
    bar = '■' * filled + '□' * (length - filled)
    return f"[{bar}]"

def get_pet_status_text(user_id):
    """Генерирует текст состояния питомца"""
    ensure_user_data(user_id)
    u = users[user_id]
    s = u['stats']
    inv = u['inventory']
    
    text = f"🐱 **{u['name']}** | 💰 {u.get('coins', 0)}\n" \
           f"━━━━━━━━━━━━━━━━━━\n" \
           f"🍖 Голод:      {get_progress_bar(s['hunger'])} {int(s['hunger'])}%\n" \
           f"⚽ Счастье:    {get_progress_bar(s['mood'])} {int(s['mood'])}%\n" \
           f"⚡ Энергия:    {get_progress_bar(s['energy'])} {int(s['energy'])}%\n" \
           f"━━━━━━━━━━━━━━━━━━\n" \
           f"🎒 **В сумке:**\n"
           
    # Отображаем инвентарь только с купленными предметами
    inv_lines = []
    for item_key, count in inv.items():
        if count > 0:
            inv_lines.append(f"{ITEMS[item_key]['name']}: {count}")
            
    if inv_lines:
        text += '\n'.join(inv_lines)
    else:
        text += "Пусто! Купи что-нибудь."
        
    if s['hunger'] <= 0 or s['mood'] <= 0 or s['energy'] <= 0:
        text += "\n\n💀 Питомец слишком слаб..."
        
    return text

def get_main_keyboard():
    """Создает клавиатуру главного меню"""
    markup = types.InlineKeyboardMarkup(row_width=3)
    
    # Действия теперь используют callback_data с item_key
    btn_feed = types.InlineKeyboardButton("Покормить 🍖", callback_data='menu_use_food')
    btn_play = types.InlineKeyboardButton("Поиграть ⚽", callback_data='menu_use_toys')
    btn_boost = types.InlineKeyboardButton("Бонусы ⚡", callback_data='menu_use_boosts')

    # Меню и Служебные
    btn_shop = types.InlineKeyboardButton("🛒 Магазин", callback_data='menu_shop_cat')
    btn_duel = types.InlineKeyboardButton("⚔️ Дуэль", callback_data='menu_duel')
    btn_delete = types.InlineKeyboardButton("🗑️ Удалить", callback_data='menu_delete') 
    btn_ref = types.InlineKeyboardButton("🔄 Обновить", callback_data='refresh')
    
    markup.add(btn_feed, btn_play, btn_boost)
    markup.add(btn_shop, btn_duel, btn_delete)
    markup.add(btn_ref)
    return markup

def get_shop_categories_keyboard():
    """Клавиатура для выбора категории магазина"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    for cat_key, cat_data in SHOP_CATEGORIES.items():
        markup.add(types.InlineKeyboardButton(f"{cat_data['emoji']} {cat_data['title']}", callback_data=f'shop_{cat_key}'))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data='menu_main'))
    return markup

def get_shop_items_keyboard(category_key):
    """Клавиатура с товарами внутри категории"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    # Фильтруем предметы по категории
    if category_key == 'food': item_keys = ['berry', 'fish', 'steak']
    elif category_key == 'toys': item_keys = ['ball', 'laser', 'quest']
    elif category_key == 'boosts': item_keys = ['coffee', 'vitamins', 'elixir']
    else: item_keys = []

    for item_key in item_keys:
        item = ITEMS[item_key]
        markup.add(types.InlineKeyboardButton(
            f"Купить {item['name']} ({item['price']} 💰)", 
            callback_data=f'buy_{item_key}'
        ))
        
    markup.add(types.InlineKeyboardButton("🔙 К категориям", callback_data='menu_shop_cat'))
    return markup

def get_use_item_keyboard(category_key, user_inventory):
    """Клавиатура для выбора предмета ИЗ ИНВЕНТАРЯ для использования"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    # Фильтруем предметы по категории и наличию
    if category_key == 'food': item_keys = ['berry', 'fish', 'steak']
    elif category_key == 'toys': item_keys = ['ball', 'laser', 'quest']
    elif category_key == 'boosts': item_keys = ['coffee', 'vitamins', 'elixir']
    else: item_keys = []
    
    has_items = False
    for item_key in item_keys:
        if user_inventory.get(item_key, 0) > 0:
            has_items = True
            item = ITEMS[item_key]
            markup.add(types.InlineKeyboardButton(
                f"Использовать {item['name']} ({user_inventory[item_key]} шт.)", 
                callback_data=f'use_{item_key}'
            ))
            
    if not has_items:
        markup.add(types.InlineKeyboardButton("В сумке пусто 😔", callback_data='ignore'))

    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data='menu_main'))
    return markup

# --- ФОНОВЫЙ ПОТОК (Жизнь) ---
def live_cycle():
    while True:
        time.sleep(60)
        changed = False
        for uid in list(users.keys()):
            if 'stats' in users[uid]:
                s = users[uid]['stats']
                s['hunger'] = max(0, s['hunger'] - 2)
                s['mood'] = max(0, s['mood'] - 2)
                s['energy'] = max(0, s['energy'] - 1)
                changed = True
        if changed:
            save_data()

threading.Thread(target=live_cycle, daemon=True).start()

# --- РЕГИСТРАЦИЯ И СТАРТ (БЕЗ ИЗМЕНЕНИЙ) ---

@bot.message_handler(commands=['start'])
def start_game(message):
    uid = message.chat.id
    if uid not in users:
        msg = bot.send_message(uid, "Привет! Придумай имя питомцу:")
        bot.register_next_step_handler(msg, set_name)
    else:
        ensure_user_data(uid)
        send_new_main_menu(uid)

def set_name(message):
    uid = message.chat.id
    name = message.text
    users[uid] = {
        "name": name, 
        "stats": {"hunger": 80, "mood": 80, "energy": 80},
        "coins": 100,
        "inventory": {'berry': 3, 'ball': 1, 'coffee': 0}, # Начальный инвентарь
        "last_duel": 0
    }
    msg = bot.send_message(uid, f"{name} родился! Теперь пришли фото (картинку).")
    bot.register_next_step_handler(msg, set_photo)

def set_photo(message):
    if not message.photo:
        msg = bot.send_message(message.chat.id, "Пришли именно фото!")
        bot.register_next_step_handler(msg, set_photo)
        return
    users[message.chat.id]['photo'] = message.photo[-1].file_id
    save_data()
    send_new_main_menu(message.chat.id)

def send_new_main_menu(uid):
    if uid not in users: return
    text = get_pet_status_text(uid)
    markup = get_main_keyboard()
    photo = users[uid].get('photo')

    if photo:
        bot.send_photo(uid, photo, caption=text, reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(uid, text, reply_markup=markup, parse_mode="Markdown")

# --- ЛОГИКА УДАЛЕНИЯ С КАПЧЕЙ (БЕЗ ИЗМЕНЕНИЙ) ---

def process_delete_captcha(message):
    uid = message.chat.id
    user_input = message.text
    if uid not in captcha_storage:
        bot.send_message(uid, "Ошибка: процесс удаления не был запущен корректно. Нажми /start.")
        return

    correct_answer = captcha_storage.pop(uid)

    try:
        if int(user_input.strip()) == correct_answer:
            if uid in users:
                del users[uid]
                save_data()
                bot.send_message(uid, "✅ **Питомец успешно удален.**\nТвои данные стерты. Нажми /start, чтобы начать заново.", parse_mode="Markdown")
            else:
                 bot.send_message(uid, "Ошибка: Питомец уже удален. Нажми /start.")
        else:
            bot.send_message(uid, "❌ **Неверный ответ!** Удаление отменено. Твой питомец спасен! Возврат в главное меню.")
            send_new_main_menu(uid)
            
    except ValueError:
        bot.send_message(uid, "❌ **Неверный формат ввода!** Удаление отменено. Введи только число.")
        send_new_main_menu(uid)

# --- ГЛАВНАЯ ЛОГИКА: ОБРАБОТКА КНОПОК ---

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    uid = call.message.chat.id
    if uid not in users: return

    ensure_user_data(uid)
    u = users[uid]
    data = call.data
    
    # --- ЛОГИКА ИСПОЛЬЗОВАНИЯ ПРЕДМЕТОВ ---
    if data.startswith('menu_use_'):
        category = data.split('_')[-1] # food, toys, boosts
        text = f"🎒 **ИСПОЛЬЗОВАТЬ {SHOP_CATEGORIES[category]['title'].upper()}**\n\n"
        bot.edit_message_caption(
            caption=text + get_pet_status_text(uid), 
            chat_id=uid, message_id=call.message.message_id, 
            reply_markup=get_use_item_keyboard(category, u['inventory']), 
            parse_mode="Markdown"
        )
        return

    elif data.startswith('use_'):
        item_key = data.split('_')[1]
        item = ITEMS[item_key]
        category = next(k for k, v in SHOP_CATEGORIES.items() if item_key in ['berry', 'fish', 'steak'] if k == 'food' or item_key in ['ball', 'laser', 'quest'] if k == 'toys' or item_key in ['coffee', 'vitamins', 'elixir'] if k == 'boosts') # Определяем категорию для возврата
        
        if u['inventory'].get(item_key, 0) > 0:
            u['inventory'][item_key] -= 1
            s = u['stats']
            
            # Применяем эффекты
            s['hunger'] = min(100, s['hunger'] + item.get('hunger', 0))
            s['mood'] = min(100, s['mood'] + item.get('mood', 0))
            s['energy'] = min(100, s['energy'] + item.get('energy', 0))
            
            # Побочные эффекты
            s['energy'] = max(0, s['energy'] - item.get('energy_cost', 0))
            s['hunger'] = max(0, s['hunger'] - item.get('hunger_cost', 0))
            s['mood'] = max(0, s['mood'] - item.get('mood_cost', 0))
            
            bot.answer_callback_query(call.id, f"Использовано: {item['name']}! Эффекты применены.")
            
            # Обновляем меню использования
            text = f"🎒 **ИСПОЛЬЗОВАТЬ {SHOP_CATEGORIES[category]['title'].upper()}**\n\n"
            bot.edit_message_caption(
                caption=text + get_pet_status_text(uid), 
                chat_id=uid, message_id=call.message.message_id, 
                reply_markup=get_use_item_keyboard(category, u['inventory']), 
                parse_mode="Markdown"
            )
            save_data()
            return

        else:
            bot.answer_callback_query(call.id, "Этого предмета нет в инвентаре!", show_alert=True)
            return

    # --- ЛОГИКА ПОКУПОК ---
    elif data == 'menu_shop_cat':
        text = f"🛒 **МАГАЗИН**\nТвои монеты: 💰 {u['coins']}\n\nВыберите категорию:"
        bot.edit_message_caption(caption=text, chat_id=uid, message_id=call.message.message_id, reply_markup=get_shop_categories_keyboard(), parse_mode="Markdown")
        return

    elif data.startswith('shop_'):
        category = data.split('_')[1]
        text = f"🛒 **{SHOP_CATEGORIES[category]['title'].upper()}**\nТвои монеты: 💰 {u['coins']}\n\nВыберите предмет:"
        bot.edit_message_caption(caption=text, chat_id=uid, message_id=call.message.message_id, reply_markup=get_shop_items_keyboard(category), parse_mode="Markdown")
        return

    elif data.startswith('buy_'):
        item_key = data.split('_')[1]
        item = ITEMS[item_key]
        price = item['price']
        
        # Определяем категорию для возврата в меню
        if item_key in ['berry', 'fish', 'steak']: category = 'food'
        elif item_key in ['ball', 'laser', 'quest']: category = 'toys'
        else: category = 'boosts'
        
        if u['coins'] >= price:
            u['coins'] -= price
            u['inventory'][item_key] = u['inventory'].get(item_key, 0) + 1
            bot.answer_callback_query(call.id, f"Куплено: {item['name']}!")
            
            # Обновляем текст магазина (чтобы обновился баланс монет)
            text = f"🛒 **{SHOP_CATEGORIES[category]['title'].upper()}**\nТвои монеты: 💰 {u['coins']}\n\nВыберите предмет:"
            bot.edit_message_caption(caption=text, chat_id=uid, message_id=call.message.message_id, reply_markup=get_shop_items_keyboard(category), parse_mode="Markdown")
            save_data()
            return
        else:
            bot.answer_callback_query(call.id, "Недостаточно монет!", show_alert=True)
            return

    # --- ЛОГИКА ДУЭЛИ И УДАЛЕНИЯ (БЕЗ ИЗМЕНЕНИЙ В ЛОГИКЕ) ---
    elif data == 'menu_duel':
        current_time = time.time()
        if current_time - u.get('last_duel', 0) < DUEL_COOLDOWN:
            left = int(DUEL_COOLDOWN - (current_time - u['last_duel']))
            bot.answer_callback_query(call.id, f"Питомец отдыхает. Ждать: {left} сек.", show_alert=True)
            return

        enemy_ids = [k for k in users.keys() if k != uid]
        if not enemy_ids:
            bot.answer_callback_query(call.id, "Нет других игроков :(", show_alert=True)
            return
        
        enemy_id = random.choice(enemy_ids)
        enemy = users[enemy_id]
        
        my_power = sum(u['stats'].values()) + random.randint(-20, 20)
        enemy_power = sum(enemy['stats'].values()) + random.randint(-20, 20)
        
        u['last_duel'] = current_time
        
        if my_power > enemy_power:
            u['coins'] += WIN_REWARD
            res = f"🏆 Победа над {enemy['name']}!\nПолучено {WIN_REWARD} монет."
        else:
            res = f"🤕 Поражение от {enemy['name']}...\nТренируйся лучше."
            
        bot.answer_callback_query(call.id, res, show_alert=True)

    elif data == 'menu_delete':
        # Логика капчи и удаления перенесена в отдельную функцию выше
        num1 = random.randint(3, 15)
        num2 = random.randint(3, 15)
        if num1 < num2: num1, num2 = num2, num1 
            
        operator = random.choice(['+', '-'])
        correct_answer = num1 + num2 if operator == '+' else num1 - num2
        captcha_text = f"{num1} {operator} {num2}"
        
        captcha_storage[uid] = correct_answer
        bot.answer_callback_query(call.id, "Запущено удаление. Смотри следующее сообщение.", show_alert=True)
        
        msg = bot.send_message(uid, 
                               f"⚠️ **Внимание!** Ты собираешься удалить питомца {u['name']} и все данные.\n\n"
                               f"Для подтверждения реши капчу:\n**Сколько будет {captcha_text}?**\n\n"
                               f"Отправь *только число* в ответ.",
                               parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_delete_captcha)
        
        try:
            bot.delete_message(uid, call.message.message_id)
        except:
            pass
        return

    elif data == 'menu_main':
        pass # Просто переходим к обновлению главного меню
    
    elif data == 'refresh' or data == 'ignore':
        bot.answer_callback_query(call.id, "Обновлено")
        # Переходим к финальному обновлению сообщения

    # -- ФИНАЛЬНОЕ ОБНОВЛЕНИЕ СООБЩЕНИЯ (редактирование) --
    save_data()
    try:
        bot.edit_message_caption(
            caption=get_pet_status_text(uid),
            chat_id=uid, 
            message_id=call.message.message_id, 
            reply_markup=get_main_keyboard(),
            parse_mode="Markdown"
        )
    except:
        pass

if __name__ == '__main__':
    print("Бот v4.0 запущен...")
    bot.infinity_polling()