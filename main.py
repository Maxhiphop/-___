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

# --- ПРЕДМЕТЫ ---
ITEMS = {
    'berry':    {'name': 'Ягода 🍓',    'price': 10, 'hunger': 15, 'energy_cost': 0},
    'fish':     {'name': 'Рыба 🐟',     'price': 30, 'hunger': 35, 'energy_cost': 5},
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

# --- СОПОСТАВЛЕНИЕ ПРЕДМЕТОВ И КАТЕГОРИЙ ---
ITEM_CATEGORY = {
    'berry':'food','fish':'food','steak':'food',
    'ball':'toys','laser':'toys','quest':'toys',
    'coffee':'boosts','vitamins':'boosts','elixir':'boosts'
}

DUEL_COOLDOWN = 300
WIN_REWARD = 50

bot = telebot.TeleBot(API_TOKEN)
users = {}
captcha_storage = {}

# --- ДАННЫЕ ---
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
    if uid not in users:
        return
    u = users[uid]
    # stats
    if 'stats' not in u:
        u['stats'] = {'hunger':80,'mood':80,'energy':80}
    # coins
    if 'coins' not in u:
        u['coins'] = 100
    # inventory
    if 'inventory' not in u:
        u['inventory'] = {key:0 for key in ITEMS.keys()}
    else:
        for key in ITEMS.keys():
            if key not in u['inventory']:
                u['inventory'][key]=0
    # last duel
    if 'last_duel' not in u:
        u['last_duel']=0

load_data()

# --- ВСПОМОГАТЕЛЬНЫЕ ---
def get_progress_bar(val,length=8):
    filled = int(length * val / 100)
    return f"[{'■'*filled}{'□'*(length-filled)}]"

def get_pet_status_text(uid):
    ensure_user_data(uid)
    u = users[uid]
    s = u['stats']
    inv = u['inventory']
    text = f"🐱 **{u['name']}** | 💰 {u.get('coins',0)}\n"\
           f"━━━━━━━━━━━━━━━━━━\n"\
           f"🍖 Голод: {get_progress_bar(s['hunger'])} {int(s['hunger'])}%\n"\
           f"⚽ Счастье: {get_progress_bar(s['mood'])} {int(s['mood'])}%\n"\
           f"⚡ Энергия: {get_progress_bar(s['energy'])} {int(s['energy'])}%\n"\
           f"━━━━━━━━━━━━━━━━━━\n🎒 **В сумке:**\n"
    lines=[f"{ITEMS[k]['name']}: {v}" for k,v in inv.items() if v>0]
    text += '\n'.join(lines) if lines else "Пусто! Купи что-нибудь."
    if s['hunger']<=0 or s['mood']<=0 or s['energy']<=0:
        text+="\n\n💀 Питомец слишком слаб..."
    return text

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
    kb=types.InlineKeyboardMarkup(row_width=1)
    for k,v in SHOP_CATEGORIES.items():
        kb.add(types.InlineKeyboardButton(f"{v['emoji']} {v['title']}",callback_data=f'shop_{k}'))
    kb.add(types.InlineKeyboardButton("🔙 Назад",callback_data='menu_main'))
    return kb

def get_shop_items_keyboard(cat):
    kb=types.InlineKeyboardMarkup(row_width=1)
    items = [k for k,v in ITEM_CATEGORY.items() if v==cat]
    for key in items:
        kb.add(types.InlineKeyboardButton(f"Купить {ITEMS[key]['name']} ({ITEMS[key]['price']} 💰)", callback_data=f'buy_{key}'))
    kb.add(types.InlineKeyboardButton("🔙 К категориям", callback_data='menu_shop_cat'))
    return kb

def get_use_item_keyboard(cat, inv):
    kb=types.InlineKeyboardMarkup(row_width=1)
    items=[k for k,v in ITEM_CATEGORY.items() if v==cat and inv.get(k,0)>0]
    if items:
        for key in items:
            kb.add(types.InlineKeyboardButton(f"Использовать {ITEMS[key]['name']} ({inv[key]} шт.)", callback_data=f'use_{key}'))
    else:
        kb.add(types.InlineKeyboardButton("В сумке пусто 😔", callback_data='ignore'))
    kb.add(types.InlineKeyboardButton("🔙 Назад",callback_data='menu_main'))
    return kb

# --- ФОНОВЫЙ ПОТОК ---
def live_cycle():
    while True:
        time.sleep(60)
        changed=False
        for uid,u in users.items():
            if 'stats' in u:
                s=u['stats']
                s['hunger']=max(0,s['hunger']-2)
                s['mood']=max(0,s['mood']-2)
                s['energy']=max(0,s['energy']-1)
                changed=True
        if changed:
            save_data()
threading.Thread(target=live_cycle, daemon=True).start()

# --- СТАРТ ---
@bot.message_handler(commands=['start'])
def start_game(msg):
    uid=msg.chat.id
    if uid not in users:
        m=bot.send_message(uid,"Привет! Придумай имя питомцу:")
        bot.register_next_step_handler(m,set_name)
    else:
        ensure_user_data(uid)
        send_new_main_menu(uid)

def set_name(msg):
    uid=msg.chat.id
    name=msg.text
    users[uid]={"name":name,"stats":{"hunger":80,"mood":80,"energy":80},"coins":100,"inventory":{'berry':3,'ball':1,'coffee':0},"last_duel":0}
    m=bot.send_message(uid,f"{name} родился! Пришли фото питомца.")
    bot.register_next_step_handler(m,set_photo)

def set_photo(msg):
    uid=msg.chat.id
    if not msg.photo:
        m=bot.send_message(uid,"Пришли именно фото!")
        bot.register_next_step_handler(m,set_photo)
        return
    users[uid]['photo']=msg.photo[-1].file_id
    save_data()
    send_new_main_menu(uid)

def send_new_main_menu(uid):
    if uid not in users: return
    text=get_pet_status_text(uid)
    kb=get_main_keyboard()
    photo=users[uid].get('photo')
    try:
        if photo:
            bot.send_photo(uid,photo,caption=text,reply_markup=kb,parse_mode="Markdown")
        else:
            bot.send_message(uid,text,reply_markup=kb,parse_mode="Markdown")
    except:
        pass

# --- УДАЛЕНИЕ ---
def process_delete_captcha(msg):
    uid=msg.chat.id
    ans=captcha_storage.pop(uid, None)
    if ans is None:
        bot.send_message(uid,"Ошибка: процесс удаления не запущен корректно. /start")
        return
    try:
        if int(msg.text.strip())==ans:
            users.pop(uid,None)
            save_data()
            bot.send_message(uid,"✅ Питомец удален. /start",parse_mode="Markdown")
        else:
            bot.send_message(uid,"❌ Неверно! Возврат в меню.")
            send_new_main_menu(uid)
    except:
        bot.send_message(uid,"❌ Неверный формат! Возврат в меню.")
        send_new_main_menu(uid)

# --- CALLBACK ---
@bot.callback_query_handler(func=lambda c:True)
def callback_handler(call):
    uid=call.message.chat.id
    if uid not in users: return
    u=users[uid]
    ensure_user_data(uid)
    data=call.data

    # Использование предметов
    if data.startswith('menu_use_'):
        cat=data.split('_')[-1]
        text=f"🎒 **ИСПОЛЬЗОВАТЬ {SHOP_CATEGORIES[cat]['title'].upper()}**\n\n"
        try:
            bot.edit_message_caption(text+get_pet_status_text(uid),uid,call.message.message_id,reply_markup=get_use_item_keyboard(cat,u['inventory']),parse_mode="Markdown")
        except:
            bot.edit_message_text(text+get_pet_status_text(uid),uid,call.message.message_id,reply_markup=get_use_item_keyboard(cat,u['inventory']),parse_mode="Markdown")
        return

    elif data.startswith('use_'):
        key=data.split('_')[1]
        if u['inventory'].get(key,0)>0:
            u['inventory'][key]-=1
            s=u['stats']
            item=ITEMS[key]
            s['hunger']=min(100,s['hunger']+item.get('hunger',0))
            s['mood']=min(100,s['mood']+item.get('mood',0))
            s['energy']=min(100,s['energy']+item.get('energy',0))
            s['energy']=max(0,s['energy']-item.get('energy_cost',0))
            s['hunger']=max(0,s['hunger']-item.get('hunger_cost',0))
            s['mood']=max(0,s['mood']-item.get('mood_cost',0))
            bot.answer_callback_query(call.id,f"Использовано: {item['name']}!")
            cat=ITEM_CATEGORY[key]
            try:
                bot.edit_message_caption(f"🎒 **ИСПОЛЬЗОВАТЬ {SHOP_CATEGORIES[cat]['title'].upper()}**\n\n"+get_pet_status_text(uid),uid,call.message.message_id,reply_markup=get_use_item_keyboard(cat,u['inventory']),parse_mode="Markdown")
            except:
                bot.edit_message_text(f"🎒 **ИСПОЛЬЗОВАТЬ {SHOP_CATEGORIES[cat]['title'].upper()}**\n\n"+get_pet_status_text(uid),uid,call.message.message_id,reply_markup=get_use_item_keyboard(cat,u['inventory']),parse_mode="Markdown")
            save_data()
        else:
            bot.answer_callback_query(call.id,"Этого предмета нет в инвентаре!",show_alert=True)
        return

    # Магазин
    if data=='menu_shop_cat':
        text=f"🛒 **МАГАЗИН**\nТвои монеты: 💰 {u['coins']}\n\nВыбери категорию:"
        try:
            bot.edit_message_caption(text,uid,call.message.message_id,reply_markup=get_shop_categories_keyboard(),parse_mode="Markdown")
        except:
            bot.edit_message_text(text,uid,call.message.message_id,reply_markup=get_shop_categories_keyboard(),parse_mode="Markdown")
        return

    elif data.startswith('shop_'):
        cat=data.split('_')[1]
        text=f"🛒 **{SHOP_CATEGORIES[cat]['title'].upper()}**\nТвои монеты: 💰 {u['coins']}\n\nВыберите предмет:"
        try:
            bot.edit_message_caption(text,uid,call.message.message_id,reply_markup=get_shop_items_keyboard(cat),parse_mode="Markdown")
        except:
            bot.edit_message_text(text,uid,call.message.message_id,reply_markup=get_shop_items_keyboard(cat),parse_mode="Markdown")
        return

    elif data.startswith('buy_'):
        key=data.split('_')[1]
        price=ITEMS[key]['price']
        cat=ITEM_CATEGORY[key]
        if u['coins']>=price:
            u['coins']-=price
            u['inventory'][key]=u['inventory'].get(key,0)+1
            bot.answer_callback_query(call.id,f"Куплено: {ITEMS[key]['name']}!")
        else:
            bot.answer_callback_query(call.id,"Недостаточно монет!",show_alert=True)
        text=f"🛒 **{SHOP_CATEGORIES[cat]['title'].upper()}**\nТвои монеты: 💰 {u['coins']}\n\nВыберите предмет:"
        try:
            bot.edit_message_caption(text,uid,call.message.message_id,reply_markup=get_shop_items_keyboard(cat),parse_mode="Markdown")
        except:
            bot.edit_message_text(text,uid,call.message.message_id,reply_markup=get_shop_items_keyboard(cat),parse_mode="Markdown")
        save_data()
        return

    # Дуэль
    if data=='menu_duel':
        now=time.time()
        if now-u.get('last_duel',0)<DUEL_COOLDOWN:
            bot.answer_callback_query(call.id,f"Питомец отдыхает. Ждать {int(DUEL_COOLDOWN-(now-u['last_duel']))} сек.",show_alert=True)
            return
        enemies=[k for k in users.keys() if k!=uid]
        if not enemies:
            bot.answer_callback_query(call.id,"Нет других игроков :(",show_alert=True)
            return
        enemy=users[random.choice(enemies)]
        my_power=sum(u['stats'].values())+random.randint(-20,20)
        enemy_power=sum(enemy['stats'].values())+random.randint(-20,20)
        u['last_duel']=now
        if my_power>enemy_power:
            u['coins']+=WIN_REWARD
            res=f"🏆 Победа над {enemy['name']}!\nПолучено {WIN_REWARD} монет."
        else:
            res=f"🤕 Поражение от {enemy['name']}..."
        bot.answer_callback_query(call.id,res,show_alert=True)
        save_data()
        return

    # Удаление
    if data=='menu_delete':
        n1,n2=random.randint(3,15),random.randint(3,15)
        if n1<n2:n1,n2=n2,n1
        op=random.choice(['+','-'])
        ans=n1+n2 if op=='+' else n1-n2
        captcha_storage[uid]=ans
        bot.answer_callback_query(call.id,"Запущено удаление. Следующее сообщение.",show_alert=True)
        msg=bot.send_message(uid,f"⚠️ Ты собираешься удалить {u['name']}.\nРеши капчу: {n1}{op}{n2}=",parse_mode="Markdown")
        bot.register_next_step_handler(msg,process_delete_captcha)
        try: bot.delete_message(uid,call.message.message_id)
        except: pass
        return

    # Обновление
    bot.answer_callback_query(call.id,"Обновлено")
    try:
        bot.edit_message_caption(get_pet_status_text(uid),uid,call.message.message_id,reply_markup=get_main_keyboard(),parse_mode="Markdown")
    except:
        try: bot.edit_message_text(get_pet_status_text(uid),uid,call.message.message_id,reply_markup=get_main_keyboard(),parse_mode="Markdown")
        except: pass
    save_data()

if __name__=='__main__':
    print("Бот v5.0 запущен...")
    bot.infinity_polling()
