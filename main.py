import telebot
from telebot import types
import json
import time
import threading
import os
import random

# --- КОНФИГУРАЦИЯ ---
# ВНИМАНИЕ: Если вы используете replit с переменными окружения,
# используйте os.environ.get('TELEGRAM_BOT_TOKEN')
API_TOKEN = '8361675894:AAHGtLc7SqcMof2CpyWXkrPf79fKBZ_wj8' # ЗАМЕНИТЕ НА ВАШ РЕАЛЬНЫЙ ТОКЕН!
DATA_FILE = 'users.json'

# --- ПРЕДМЕТЫ (без изменений) ---
ITEMS = {
    'berry':    {'name': 'Ягода 🍓',    'price': 10, 'hunger': 15, 'energy_cost': 0},
    'fish':     {'name': 'Рыба 🐟',    'price': 30, 'hunger': 35, 'energy_cost': 5},
    'steak':    {'name': 'Стейк 🥩',    'price': 60, 'hunger': 60, 'energy_cost': 15},
    'ball':     {'name': 'Мячик ⚽',    'price': 15, 'mood': 20, 'energy_cost': 5, 'hunger_cost': 5},
    'laser':    {'name': 'Лазер 🔦',    'price': 40, 'mood': 45, 'energy_cost': 10, 'hunger_cost': 10},
    'quest':    {'name': 'Квест 🗺️',    'price': 80, 'mood': 70, 'energy_cost': 20, 'hunger_cost': 15},
    'coffee':   {'name': 'Кофе ☕',    'price': 35, 'energy': 40, 'mood_cost': 10},
    'vitamins': {'name': 'Витамины 💊', 'price': 70, 'energy': 65, 'mood_cost': 0},
    'elixir':   {'name': 'Эликсир ✨',  'price': 150, 'energy': 100, 'hunger': 100, 'mood': 100, 'mood_cost': 0}
}

# --- КАТЕГОРИИ (без изменений) ---
SHOP_CATEGORIES = {
    'food':     {'emoji': '🍖', 'title': 'Еда (Голод)'},
    'toys':     {'emoji': '⚽', 'title': 'Игрушки (Счастье)'},
    'boosts':   {'emoji': '⚡', 'title': 'Бонусы (Энергия)'},
}

ITEM_CATEGORY = {
    'berry':'food','fish':'food','steak':'food',
    'ball':'toys','laser':'toys','quest':'toys',
    'coffee':'boosts','vitamins':'boosts','elixir':'boosts'
}

DUEL_COOLDOWN = 300
WIN_REWARD = 50

# --- ИНИЦИАЛИЗАЦИЯ ---
bot = telebot.TeleBot(API_TOKEN)
users = {}
captcha_storage = {}

# --- УТИЛИТЫ ДЛЯ MARKDOWNV2 ---
def escape_markdown(text):
    """Экранирует символы, которые могут сломать парсинг MarkdownV2."""
    special_chars = r'_*[]()~`>#+-=|{}.!'
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

# --- ЗАГРУЗКА/СОХРАНЕНИЕ (без изменений) ---
def load_data():
    global users
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            try:
                users = {int(k): v for k, v in json.load(f).items()}
            except:
                users = {}

def save_data():
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

# --- ИНИЦИАЛИЗАЦИЯ ПОЛЬЗОВАТЕЛЯ ---
def ensure_user_data(uid):
    """Проверяет и инициализирует данные пользователя, если они неполные."""
    if uid not in users:
        # Если пользователя нет вообще, то его надо регистрировать через /start
        return False
    
    u = users[uid]
    # Инициализация недостающих ключей, если они отсутствуют
    u.setdefault('stats', {'hunger':80,'mood':80,'energy':80})
    u.setdefault('coins', 100)
    u.setdefault('inventory', {k:0 for k in ITEMS.keys()})
    u.setdefault('last_duel', 0)
    u.setdefault('photo', None)
    u.setdefault('name', 'Питомец') # Обеспечиваем наличие имени
    return True

load_data()

# --- ПРОГРЕСС БАР ---
def get_progress_bar(val,length=8):
    filled = int(length * val / 100)
    return f"[{'■'*filled}{'□'*(length-filled)}]"

# --- ТЕКСТ СТАТУСА ПИТОМЦА ---
def get_pet_status_text(uid):
    if uid not in users:
        # Это для случаев, когда пользователь нажимает кнопку, но его нет в базе
        return "👋 Привет! Твой питомец еще не создан. Нажми /start."

    u = users[uid]
    s = u['stats']
    inv = u['inventory']
    
    # ❗️ Экранируем специальные символы
    pet_name = escape_markdown(u.get('name', 'Питомец'))
    
    text = f"🐱 {pet_name} \\| 💰 {u.get('coins',0)}\n"\
           "━━━━━━━━━━━━━━━━━━\n"\
           f"🍖 Голод: {escape_markdown(get_progress_bar(s['hunger']))} {int(s['hunger'])}%\n"\
           f"⚽ Счастье: {escape_markdown(get_progress_bar(s['mood']))} {int(s['mood'])}%\n"\
           f"⚡ Энергия: {escape_markdown(get_progress_bar(s['energy']))} {int(s['energy'])}%\n"\
           "━━━━━━━━━━━━━━━━━━\n🎒 В сумке:\n"
           
    lines = [f"{escape_markdown(ITEMS[k]['name'])}: {v}" for k,v in inv.items() if v>0]
    
    text += '\n'.join(lines) if lines else "Пусто\\! Купи что\\-нибудь\\."
    if s['hunger']<=0 or s['mood']<=0 or s['energy']<=0:
        text += "\n\n💀 Питомец слишком слаб\\.\\.\\. Покорми и поиграй с ним!"
    return text

# --- КНОПКИ (без изменений) ---
def get_main_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(
        types.InlineKeyboardButton("Покормить 🍖", callback_data='menu_use_food'),
        types.InlineKeyboardButton("Поиграть ⚽", callback_data='menu_use_toys'),
        types.InlineKeyboardButton("Бонусы ⚡", callback_data='menu_use_boosts')
    )
    kb.add(
        types.InlineKeyboardButton("🛒 Магазин", callback_data='menu_shop_cat'),
        types.InlineKeyboardButton("⚔️ Дуэль", callback_data='menu_duel'),
        types.InlineKeyboardButton("🗑️ Удалить", callback_data='menu_delete')
    )
    kb.add(types.InlineKeyboardButton("🔄 Обновить", callback_data='refresh'))
    return kb

def get_shop_categories_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=1)
    for k,v in SHOP_CATEGORIES.items():
        kb.add(types.InlineKeyboardButton(f"{v['emoji']} {v['title']}", callback_data=f'shop_{k}'))
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data='menu_main'))
    return kb

def get_shop_items_keyboard(cat):
    kb = types.InlineKeyboardMarkup(row_width=1)
    for key, category in ITEM_CATEGORY.items():
        if category == cat:
            kb.add(types.InlineKeyboardButton(f"Купить {ITEMS[key]['name']} ({ITEMS[key]['price']} 💰)", callback_data=f'buy_{key}'))
    kb.add(types.InlineKeyboardButton("🔙 К категориям", callback_data='menu_shop_cat'))
    return kb

def get_use_item_keyboard(cat, inv):
    kb = types.InlineKeyboardMarkup(row_width=1)
    items = [k for k,v in ITEM_CATEGORY.items() if v==cat and inv.get(k,0)>0]
    if items:
        for key in items:
            kb.add(types.InlineKeyboardButton(f"Использовать {ITEMS[key]['name']} ({inv[key]} шт.)", callback_data=f'use_{key}'))
    else:
        kb.add(types.InlineKeyboardButton("В сумке пусто 😔", callback_data='ignore'))
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data='menu_main'))
    return kb

# --- ФОНОВЫЙ ПОТОК (без изменений) ---
def live_cycle():
    while True:
        time.sleep(60)
        changed = False
        for uid, u in users.items():
            # Пропускаем, если пользователь еще не зарегистрирован полностью
            if 'stats' not in u: continue 
            
            s = u['stats']
            s['hunger'] = max(0, s['hunger']-2)
            s['mood'] = max(0, s['mood']-2)
            s['energy'] = max(0, s['energy']-1)
            changed = True
        if changed:
            save_data()

threading.Thread(target=live_cycle, daemon=True).start()

# --- СТАРТ ---
@bot.message_handler(commands=['start'])
def start_game(msg):
    uid = msg.chat.id
    # ❗️ ИСПРАВЛЕНИЕ 3: Всегда проверяем наличие пользователя
    if uid not in users or 'name' not in users[uid]:
        m = bot.send_message(uid, "Привет! Придумай имя питомцу:")
        # Инициализируем минимальные данные, чтобы избежать ошибок
        users[uid] = {} 
        bot.register_next_step_handler(m, set_name)
    else:
        ensure_user_data(uid)
        send_new_main_menu(uid)

def set_name(msg):
    uid = msg.chat.id
    name = msg.text.strip()
    users[uid] = {
        "name": name,
        "stats": {"hunger":80,"mood":80,"energy":80},
        "coins": 100,
        "inventory": {'berry':3,'ball':1,'coffee':0},
        "last_duel": 0,
        "photo": None
    }
    m = bot.send_message(uid, f"{name} родился! Пришли фото питомца.")
    bot.register_next_step_handler(m, set_photo)

# --- ФУНКЦИЯ ОТПРАВКИ/РЕДАКТИРОВАНИЯ ---
def send_new_main_menu(uid, msg_id=None, kb=None):
    if uid not in users: return
    text = get_pet_status_text(uid)
    kb = kb if kb else get_main_keyboard()
    photo = users[uid].get('photo')
    
    try:
        if msg_id:
            # Редактирование существующего сообщения
            if photo:
                bot.edit_message_caption(text, uid, msg_id, reply_markup=kb, parse_mode='MarkdownV2')
            else:
                bot.edit_message_text(text, uid, msg_id, reply_markup=kb, parse_mode='MarkdownV2')
        else:
            # Отправка нового сообщения
            if photo:
                bot.send_photo(uid, photo, caption=text, reply_markup=kb, parse_mode='MarkdownV2')
            else:
                bot.send_message(uid, text, reply_markup=kb, parse_mode='MarkdownV2')
    except telebot.apihelper.ApiTelegramException as e:
        # Игнорируем ошибку "Message is not modified"
        if "message is not modified" not in str(e):
             # Если ошибка парсинга или другая критическая, отправляем новое сообщение
             if "can't parse entities" in str(e) or "Bad Request" in str(e):
                 print(f"Парсинг ошибка! Попытка отправить новое сообщение. Ошибка: {e}")
                 bot.send_message(uid, text, reply_markup=kb, parse_mode='MarkdownV2')
             else:
                 print(f"Ошибка при редактировании сообщения для {uid}: {e}")
        pass

# --- УДАЛЕНИЕ (без изменений) ---
# ... (оставлен код process_delete_captcha без изменений) ...
def process_delete_captcha(msg):
    uid = msg.chat.id
    ans = captcha_storage.pop(uid, None)
    if ans is None:
        bot.send_message(uid, "Ошибка: процесс удаления не запущен. /start")
        return
    try:
        if int(msg.text.strip()) == ans:
            users.pop(uid, None)
            save_data()
            bot.send_message(uid, "✅ Питомец удален. /start")
        else:
            bot.send_message(uid, "❌ Неверно! Возврат в меню.")
            send_new_main_menu(uid)
    except:
        bot.send_message(uid, "❌ Неверный формат! Возврат в меню.")
        send_new_main_menu(uid)


# --- CALLBACK ---
@bot.callback_query_handler(func=lambda c: True)
def callback_handler(call):
    uid = call.message.chat.id
    
    # ❗️ ИСПРАВЛЕНИЕ 3: Если нет данных, просим запустить /start
    if uid not in users or 'name' not in users[uid]: 
        bot.answer_callback_query(call.id, "Сначала создай своего питомца! Нажми /start", show_alert=True)
        return
        
    u = users[uid]
    ensure_user_data(uid)
    data = call.data
    
    # --- Логика редактирования меню ---
    # Используем одну функцию send_new_main_menu для обновления всего меню
    def update_menu_edit(new_text, new_kb):
        try:
            has_photo = call.message.caption is not None # Проверяем, было ли сообщение с фото
            if has_photo:
                bot.edit_message_caption(new_text, uid, call.message.message_id, reply_markup=new_kb, parse_mode='MarkdownV2')
            else:
                bot.edit_message_text(new_text, uid, call.message.message_id, reply_markup=new_kb, parse_mode='MarkdownV2')
        except telebot.apihelper.ApiTelegramException as e:
            if "message is not modified" not in str(e):
                print(f"Ошибка при редактировании (update_menu_edit): {e}")
            pass

    # Использование предметов
    if data.startswith('menu_use_'):
        cat = data.split('_')[-1]
        text = f"🎒 Использовать {SHOP_CATEGORIES[cat]['title']}\n\n" + get_pet_status_text(uid)
        update_menu_edit(text, get_use_item_keyboard(cat,u['inventory']))
        return

    elif data.startswith('use_'):
        key = data.split('_')[1]
        cat = ITEM_CATEGORY.get(key) # ❗️ ИСПРАВЛЕНИЕ 2: Получаем категорию предмета
        
        if u['inventory'].get(key,0)>0:
            u['inventory'][key]-=1
            s=u['stats']
            item=ITEMS[key]
            
            # Обновление характеристик
            s['hunger']=min(100,s['hunger']+item.get('hunger',0))
            s['mood']=min(100,s['mood']+item.get('mood',0))
            s['energy']=min(100,s['energy']+item.get('energy',0))
            s['energy']=max(0,s['energy']-item.get('energy_cost',0))
            s['hunger']=max(0,s['hunger']-item.get('hunger_cost',0))
            s['mood']=max(0,s['mood']-item.get('mood_cost',0))
            
            bot.answer_callback_query(call.id,f"Использовано: {item['name']}!")
            
            # Обновляем меню использования (food/toys/boosts)
            text = f"🎒 Использовать {SHOP_CATEGORIES[cat]['title']}\n\n" + get_pet_status_text(uid)
            update_menu_edit(text, get_use_item_keyboard(cat,u['inventory']))
            save_data()
        else:
            bot.answer_callback_query(call.id,"Этого предмета нет!", show_alert=True)
        return

    # Магазин
    if data=='menu_shop_cat':
        text=f"🛒 Магазин\nМонеты: {u['coins']}\nВыбери категорию:"
        update_menu_edit(text, get_shop_categories_keyboard())
        return

    elif data.startswith('shop_'):
        cat = data.split('_')[1]
        text=f"🛒 {SHOP_CATEGORIES[cat]['title']}\nМонеты: {u['coins']}\nВыберите предмет:"
        update_menu_edit(text, get_shop_items_keyboard(cat))
        return

    elif data.startswith('buy_'):
        key = data.split('_')[1]
        price = ITEMS[key]['price']
        cat = ITEM_CATEGORY.get(key) # ❗️ ИСПРАВЛЕНИЕ 2: Получаем категорию предмета
        
        if u['coins'] >= price:
            u['coins'] -= price
            u['inventory'][key] = u['inventory'].get(key,0)+1
            bot.answer_callback_query(call.id,f"Куплено: {ITEMS[key]['name']}!")
        else:
            bot.answer_callback_query(call.id,"Недостаточно монет!", show_alert=True)
            
        text=f"🛒 {SHOP_CATEGORIES[cat]['title']}\nМонеты: {u['coins']}\nВыберите предмет:"
        update_menu_edit(text, get_shop_items_keyboard(cat))
        save_data()
        return

    # Дуэль (без изменений)
    if data=='menu_duel':
        now = time.time()
        if now-u.get('last_duel',0)<DUEL_COOLDOWN:
            bot.answer_callback_query(call.id,f"Питомец отдыхает. Ждать {int(DUEL_COOLDOWN-(now-u['last_duel']))} сек.", show_alert=True)
            return
        # ... (оставлена логика дуэли) ...
        enemies = [k for k in users.keys() if k!=uid and 'name' in users[k]]
        if not enemies:
            bot.answer_callback_query(call.id,"Нет других игроков :(", show_alert=True)
            return
        enemy = users[random.choice(enemies)]
        my_power = sum(u['stats'].values()) + random.randint(-20,20)
        enemy_power = sum(enemy['stats'].values()) + random.randint(-20,20)
        u['last_duel'] = now
        if my_power>enemy_power:
            u['coins'] += WIN_REWARD
            res=f"🏆 Победа над {enemy['name']}!\nПолучено {WIN_REWARD} монет."
        else:
            res=f"🤕 Поражение от {enemy['name']}..."
        bot.answer_callback_query(call.id,res, show_alert=True)
        save_data()
        return

    # Удаление (без изменений)
    if data=='menu_delete':
        n1,n2=random.randint(3,15),random.randint(3,15)
        if n1<n2:n1,n2=n2,n1
        op=random.choice(['+','-'])
        ans = n1+n2 if op=='+' else n1-n2
        captcha_storage[uid] = ans
        bot.answer_callback_query(call.id,"Запущено удаление. Следующее сообщение.", show_alert=True)
        msg = bot.send_message(uid,f"⚠️ Ты собираешься удалить {u['name']}.\nРеши капчу: {n1}{op}{n2}=")
        bot.register_next_step_handler(msg, process_delete_captcha)
        try: bot.delete_message(uid, call.message.message_id)
        except: pass
        return

    # Обновление / Возврат в главное меню
    if data=='refresh' or data=='menu_main' or data=='ignore':
        bot.answer_callback_query(call.id,"Обновлено")
        update_menu_edit(get_pet_status_text(uid), get_main_keyboard())
        save_data()
        return

if __name__=='__main__':
    print("Бот v5.0 запущен...")
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"Ошибка при запуске бота: {e}")
