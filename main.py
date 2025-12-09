import telebot
from telebot import types
import json
import time
import threading
import os
import random

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = '8361675894:AAHGtLcSqcMof2CpyWXkrPf79fKBZ_wj8' # ЗАМЕНИТЕ НА ВАШ РЕАЛЬНЫЙ ТОКЕН!
DATA_FILE = 'users.json'
PARSE_MODE = 'MarkdownV2'

# --- ПРЕДМЕТЫ ---
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

# --- КАТЕГОРИИ ---
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
# ❗️ НОВОЕ: Временное хранилище для имен во время регистрации
temp_storage = {} 

# --- УТИЛИТЫ ---
def escape_markdown(text):
    """Экранирует символы, которые могут сломать парсинг MarkdownV2."""
    special_chars = r'_*[]()~`>#+-=|{}.!'
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

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

def ensure_user_data(uid):
    """Инициализирует недостающие данные для существующего пользователя."""
    if uid not in users: return False
    u = users[uid]
    u.setdefault('stats', {'hunger':80,'mood':80,'energy':80})
    u.setdefault('coins', 100)
    u.setdefault('inventory', {k:0 for k in ITEMS.keys()})
    u.setdefault('last_duel', 0)
    u.setdefault('photo', None)
    u.setdefault('name', 'Питомец')
    return True

load_data()

# --- ТЕКСТ СТАТУСА ПИТОМЦА ---
def get_progress_bar(val,length=8):
    filled = int(length * val / 100)
    return f"[{'■'*filled}{'□'*(length-filled)}]"

def get_pet_status_text(uid):
    if uid not in users:
        return "👋 Привет! Твой питомец еще не создан\\. Нажми /start\\."

    u = users[uid]
    s = u.get('stats', {}) # Используем .get() на случай, если регистрация не завершена
    inv = u.get('inventory', {})
    
    pet_name = escape_markdown(u.get('name', 'Питомец'))
    
    # Проверяем, есть ли stats, чтобы избежать ошибки при незавершенной регистрации
    if not s:
        return f"🐱 {pet_name} \\| 💰 {u.get('coins', 0)}\\n\nПродолжи регистрацию, чтобы увидеть его статус\\."
        
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

# --- ФУНКЦИЯ ОТПРАВКИ/РЕДАКТИРОВАНИЯ ---
def edit_or_send_menu(uid, msg=None, text=None, kb=None):
    """Универсальная функция для отправки нового или редактирования существующего сообщения."""
    if uid not in users: return
    
    text = text if text else get_pet_status_text(uid)
    kb = kb if kb else get_main_keyboard()
    photo = users[uid].get('photo')
    
    try:
        if msg:
            if msg.caption is not None or photo: 
                bot.edit_message_caption(text, uid, msg.message_id, reply_markup=kb, parse_mode=PARSE_MODE)
            else:
                bot.edit_message_text(text, uid, msg.message_id, reply_markup=kb, parse_mode=PARSE_MODE)
        else:
            if photo:
                bot.send_photo(uid, photo, caption=text, reply_markup=kb, parse_mode=PARSE_MODE)
            else:
                bot.send_message(uid, text, reply_markup=kb, parse_mode=PARSE_MODE)
    except telebot.apihelper.ApiTelegramException as e:
        if "message is not modified" not in str(e):
             print(f"Ошибка при обновлении меню для {uid}: {e}")
        pass

# --- КЛАВИАТУРЫ (без изменений) ---
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
    if uid not in users or 'name' not in users[uid] or 'stats' not in users[uid]:
        m = bot.send_message(uid, "Привет! Придумай имя питомцу:")
        # ❗️ Обновляем users[uid] и temp_storage[uid] для фикса бага
        users[uid] = {'coins': 100, 'inventory': {'berry':3,'ball':1,'coffee':0}}
        temp_storage[uid] = {'step': 'name_pending'}
        bot.register_next_step_handler(m, set_name)
    else:
        ensure_user_data(uid)
        edit_or_send_menu(uid)

def set_name(msg):
    uid = msg.chat.id
    name = msg.text.strip()
    
    # ❗️ Проверяем, что это тот пользователь, который должен был ввести имя
    if uid not in temp_storage or temp_storage[uid].get('step') != 'name_pending':
        bot.send_message(uid, "Ошибка регистрации или тайм-аут. Нажми /start еще раз.")
        return

    # Сохраняем имя во временное хранилище
    temp_storage[uid]['name'] = name
    temp_storage[uid]['step'] = 'photo_pending'
    
    m = bot.send_message(uid, f"{name} родился! Теперь пришли фото (картинку).")
    bot.register_next_step_handler(m, set_photo)

def set_photo(msg):
    uid = msg.chat.id
    
    # ❗️ Проверяем состояние и пользователя
    if uid not in temp_storage or temp_storage[uid].get('step') != 'photo_pending':
        bot.send_message(uid, "Ошибка регистрации или тайм-аут. Нажми /start еще раз.")
        return

    if not msg.photo:
        m = bot.send_message(uid, "Это не фото! Пришли *только* фото питомца\\.", parse_mode=PARSE_MODE)
        bot.register_next_step_handler(m, set_photo)
        return
        
    # Собираем все финальные данные
    pet_name = temp_storage.pop(uid)['name'] 
    
    users[uid].update({
        "name": pet_name,
        "stats": {"hunger":80,"mood":80,"energy":80},
        "photo": msg.photo[-1].file_id
    })
    
    save_data()
    edit_or_send_menu(uid)

# --- УДАЛЕНИЕ (без изменений) ---
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
            edit_or_send_menu(uid)
    except:
        bot.send_message(uid, "❌ Неверный формат! Возврат в меню.")
        edit_or_send_menu(uid)

# --- CALLBACK (без изменений в логике, кроме вызовов функций) ---
@bot.callback_query_handler(func=lambda c: True)
def callback_handler(call):
    uid = call.message.chat.id
    data = call.data
    msg = call.message
    
    if uid not in users or 'name' not in users[uid] or 'stats' not in users.get(uid, {}): 
        bot.answer_callback_query(call.id, "Сначала создай своего питомца! Нажми /start", show_alert=True)
        return
        
    u = users[uid]
    ensure_user_data(uid)

    # --- 1. ИСПОЛЬЗОВАНИЕ ПРЕДМЕТОВ ---
    if data.startswith('menu_use_'):
        cat = data.split('_')[-1]
        text = f"🎒 Использовать {SHOP_CATEGORIES[cat]['title']}\n\n" + get_pet_status_text(uid)
        kb = get_use_item_keyboard(cat, u['inventory'])
        edit_or_send_menu(uid, msg=msg, text=text, kb=kb)
        return

    elif data.startswith('use_'):
        key = data.split('_')[1]
        cat = ITEM_CATEGORY.get(key)
        item = ITEMS[key]
        
        if u['inventory'].get(key,0)>0:
            u['inventory'][key]-=1
            s=u['stats']
            
            # Применение эффектов
            s['hunger']=min(100,s['hunger']+item.get('hunger',0))
            s['mood']=min(100,s['mood']+item.get('mood',0))
            s['energy']=min(100,s['energy']+item.get('energy',0))
            s['energy']=max(0,s['energy']-item.get('energy_cost',0))
            s['hunger']=max(0,s['hunger']-item.get('hunger_cost',0))
            s['mood']=max(0,s['mood']-item.get('mood_cost',0))
            
            bot.answer_callback_query(call.id,f"Использовано: {item['name']}!")
            save_data()

            text = f"🎒 Использовать {SHOP_CATEGORIES[cat]['title']}\n\n" + get_pet_status_text(uid)
            kb = get_use_item_keyboard(cat,u['inventory'])
            edit_or_send_menu(uid, msg=msg, text=text, kb=kb)
        else:
            bot.answer_callback_query(call.id,"Этого предмета нет!", show_alert=True)
        return

    # --- 2. МАГАЗИН ---
    elif data=='menu_shop_cat':
        text=f"🛒 Магазин\nМонеты: {u['coins']}\nВыбери категорию:"
        kb = get_shop_categories_keyboard()
        edit_or_send_menu(uid, msg=msg, text=text, kb=kb)
        return

    elif data.startswith('shop_'):
        cat = data.split('_')[1]
        text=f"🛒 {SHOP_CATEGORIES[cat]['title']}\nМонеты: {u['coins']}\nВыберите предмет:"
        kb = get_shop_items_keyboard(cat)
        edit_or_send_menu(uid, msg=msg, text=text, kb=kb)
        return

    elif data.startswith('buy_'):
        key = data.split('_')[1]
        item = ITEMS[key]
        cat = ITEM_CATEGORY.get(key)
        
        if u['coins'] >= item['price']:
            u['coins'] -= item['price']
            u['inventory'][key] = u['inventory'].get(key,0)+1
            bot.answer_callback_query(call.id,f"Куплено: {item['name']}!")
            save_data()
        else:
            bot.answer_callback_query(call.id,"Недостаточно монет!", show_alert=True)
            
        text=f"🛒 {SHOP_CATEGORIES[cat]['title']}\nМонеты: {u['coins']}\nВыберите предмет:"
        kb = get_shop_items_keyboard(cat)
        edit_or_send_menu(uid, msg=msg, text=text, kb=kb)
        return

    # --- 3. ДУЭЛЬ ---
    elif data=='menu_duel':
        now = time.time()
        if now-u.get('last_duel',0)<DUEL_COOLDOWN:
            bot.answer_callback_query(call.id,f"Питомец отдыхает. Ждать {int(DUEL_COOLDOWN-(now-u['last_duel']))} сек.", show_alert=True)
            return
            
        enemies = [k for k in users.keys() if k!=uid and 'name' in users.get(k, {}) and 'stats' in users.get(k, {})]
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

    # --- 4. УДАЛЕНИЕ ---
    elif data=='menu_delete':
        n1,n2=random.randint(3,15),random.randint(3,15)
        if n1<n2:n1,n2=n2,n1
        op=random.choice(['+','-'])
        ans = n1+n2 if op=='+' else n1-n2
        captcha_storage[uid] = ans
        
        bot.answer_callback_query(call.id,"Запущено удаление. Следующее сообщение.", show_alert=True)
        msg_delete = bot.send_message(uid,f"⚠️ Ты собираешься удалить {u['name']}.\\nРеши капчу: {n1}{op}{n2}=")
        bot.register_next_step_handler(msg_delete, process_delete_captcha)
        try: bot.delete_message(uid, call.message.message_id)
        except: pass
        return

    # --- 5. ОБНОВЛЕНИЕ / ВОЗВРАТ ---
    elif data in ['refresh', 'menu_main', 'ignore']:
        bot.answer_callback_query(call.id,"Обновлено")
        edit_or_send_menu(uid, msg=msg)
        return

if __name__=='__main__':
    print("Бот v7.0 запущен...")
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"Критическая ошибка при запуске бота: {e}")
