import json
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import os

API_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN'
ADMIN_ID = 123456789  # Твой Telegram ID для админ команд

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

DATA_FILE = 'store_data.json'

# Загрузка данных из файла или инициализация
def load_data():
    if not os.path.exists(DATA_FILE):
        return {
            "categories": {},  # структура магазина
            "users": {},       # {user_id: {"referrer": user_id or None, "referrals": []}}
        }
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

# Сохранение данных
def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

data = load_data()

# --- Админ проверки
def is_admin(user_id):
    return user_id == ADMIN_ID

# --- Команда /start с реферальным кодом
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = str(message.from_user.id)
    args = message.get_args()
    if user_id not in data["users"]:
        referrer = args if args in data["users"] else None
        data["users"][user_id] = {"referrer": referrer, "referrals": []}
        if referrer:
            data["users"][referrer]["referrals"].append(user_id)
        save_data(data)
    await message.answer(f"Привет! Добро пожаловать в наш магазин.\n"
                         f"Твой реферальный код: {user_id}\n"
                         f"Пригласи друзей, чтобы получить бонусы!\n"
                         f"Используй /catalog чтобы начать просмотр товаров.")

# --- Команда /referals показать количество приглашённых
@dp.message_handler(commands=['referals'])
async def cmd_referals(message: types.Message):
    user_id = str(message.from_user.id)
    user = data["users"].get(user_id)
    if not user:
        await message.answer("Ты ещё не зарегистрирован.")
        return
    count = len(user["referrals"])
    await message.answer(f"Ты пригласил(а) {count} пользователей:\n" + "\n".join(user["referrals"]) if count else "Пока никого не пригласил.")

# --- Команда /catalog — начать навигацию по категориям
@dp.message_handler(commands=['catalog'])
async def cmd_catalog(message: types.Message):
    categories = data["categories"]
    if not categories:
        await message.answer("Каталог пуст.")
        return
    keyboard = InlineKeyboardMarkup(row_width=1)
    for cat in categories.keys():
        keyboard.add(InlineKeyboardButton(cat, callback_data=f"cat|{cat}"))
    await message.answer("Выберите категорию:", reply_markup=keyboard)

# --- Обработчик inline кнопок (категории, подкатегории, товары)
@dp.callback_query_handler(lambda c: True)
async def process_callback(callback_query: types.CallbackQuery):
    data_store = data  # для удобства
    user_id = str(callback_query.from_user.id)
    parts = callback_query.data.split('|')

    if parts[0] == 'cat':
        cat = parts[1]
        subcats = data_store["categories"].get(cat)
        if not subcats:
            await bot.answer_callback_query(callback_query.id, text="Подкатегории отсутствуют.")
            return
        keyboard = InlineKeyboardMarkup(row_width=1)
        # подкатегории или товары?
        if isinstance(subcats, dict):
            for subcat in subcats.keys():
                keyboard.add(InlineKeyboardButton(subcat, callback_data=f"subcat|{cat}|{subcat}"))
            await bot.send_message(user_id, f"Подкатегории категории '{cat}':", reply_markup=keyboard)
        else:
            await bot.send_message(user_id, f"Товары в категории '{cat}':")
            # здесь можно добавить логику для списка товаров если сразу идут товары
        await bot.answer_callback_query(callback_query.id)

    elif parts[0] == 'subcat':
        cat = parts[1]
        subcat = parts[2]
        subsubcats_or_products = data_store["categories"][cat][subcat]
        keyboard = InlineKeyboardMarkup(row_width=1)
        if isinstance(subsubcats_or_products, dict):
            for ssc in subsubcats_or_products.keys():
                keyboard.add(InlineKeyboardButton(ssc, callback_data=f"subsubcat|{cat}|{subcat}|{ssc}"))
            await bot.send_message(user_id, f"Подкатегории '{subcat}':", reply_markup=keyboard)
        else:
            # список товаров
            for product in subsubcats_or_products:
                keyboard.add(InlineKeyboardButton(product["title"], callback_data=f"product|{cat}|{subcat}|{product['title']}"))
            await bot.send_message(user_id, f"Товары в '{subcat}':", reply_markup=keyboard)
        await bot.answer_callback_query(callback_query.id)

    elif parts[0] == 'subsubcat':
        cat, subcat, subsubcat = parts[1], parts[2], parts[3]
        products = data_store["categories"][cat][subcat][subsubcat]
        keyboard = InlineKeyboardMarkup(row_width=1)
        for product in products:
            keyboard.add(InlineKeyboardButton(product["title"], callback_data=f"product|{cat}|{subcat}|{subsubcat}|{product['title']}"))
        await bot.send_message(user_id, f"Товары в '{subsubcat}':", reply_markup=keyboard)
        await bot.answer_callback_query(callback_query.id)

    elif parts[0] == 'product':
        # получение информации о товаре
        # структура: product|cat|subcat|product_title
        # или product|cat|subcat|subsubcat|product_title
        keys = parts[1:]
        # ищем товар по названию в нужном месте
        node = data_store["categories"]
        try:
            for key in keys[:-1]:
                node = node[key]
            product_title = keys[-1]
            product_list = node if isinstance(node, list) else []
            product = next((p for p in product_list if p["title"] == product_title), None)
            if not product:
                await bot.send_message(user_id, "Товар не найден.")
                return
            text = f"Название: {product['title']}\nОписание: {product['description']}\nЦена: {product['price']}"
            if product.get("image"):
                await bot.send_photo(user_id, product["image"], caption=text)
            else:
                await bot.send_message(user_id, text)
            await bot.answer_callback_query(callback_query.id)
        except Exception as e:
            await bot.send_message(user_id, "Ошибка при получении товара.")
            await bot.answer_callback_query(callback_query.id)

# --- Пример админ команды: добавить категорию
@dp.message_handler(commands=['add_category'])
async def add_category(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("Только админ может использовать эту команду.")
        return
    args = message.get_args()
    if not args:
        await message.answer("Использование: /add_category <название категории>")
        return
    category = args.strip()
    if category in data["categories"]:
        await message.answer("Категория уже существует.")
        return
    data["categories"][category] = {}
    save_data(data)
    await message.answer(f"Категория '{category}' добавлена.")

# --- Добавление подкатегории
@dp.message_handler(commands=['add_subcategory'])
async def add_subcategory(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("Только админ может использовать эту команду.")
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Использование: /add_subcategory <категория> <название подкатегории>")
        return
    category = parts[1]
    subcategory = parts[2]
    if category not in data["categories"]:
        await message.answer("Категория не найдена.")
        return
    if subcategory in data["categories"][category]:
        await message.answer("Подкатегория уже существует.")
        return
    data["categories"][category][subcategory] = {}
    save_data(data)
    await message.answer(f"Подкатегория '{subcategory}' добавлена в категорию '{category}'.")

# --- Добавление под-подкатегории
@dp.message_handler(commands=['add_subsubcategory'])
async def add_subsubcategory(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("Только админ может использовать эту команду.")
        return
    parts = message.text.split(maxsplit=3)
    if len(parts) < 4:
        await message.answer("Использование: /add_subsubcategory <категория> <подкатегория> <название под-подкатегории>")
        return
    category = parts[1]
    subcategory = parts[2]
    subsubcategory = parts[3]
    if category not in data["categories"]:
        await message.answer("Категория не найдена.")
        return
    if subcategory not in data["categories"][category]:
        await message.answer("Подкатегория не найдена.")
        return
    if subsubcategory in data["categories"][category][subcategory]:
        await message.answer("Под-подкатегория уже существует.")
        return
    data["categories"][category][subcategory][subsubcategory] = []
    save_data(data)
    await message.answer(f"Под-подкатегория '{subsubcategory}' добавлена в '{subcategory}'.")

# --- Добавление товара
@dp.message_handler(commands=['add_product'])
async def add_product(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("Только админ может использовать эту команду.")
        return
    # Пример: /add_product Категория Подкатегория Под-подкатегория Название Цена Описание Картинка
    # Для упрощения здесь используем упрощённый формат через разделитель '|'
    args = message.get_args()
    if not args:
        await message.answer("Использование:\n/add_product <Категория>|<Подкатегория>|<Под-подкатегория>|<Название>|<Цена>|<Описание>|<URL картинки>\n" \
                             "Если под-подкатегории нет, оставьте пустым, например: Категория|Подкатегория||Название|Цена|Описание|URL")
        return
    parts = args.split('|')
    if len(parts) !=7:
        await message.answer("Неверное количество параметров. Используйте формат:\n" \
                             "<Категория>|<Подкатегория>|<Под-подкатегория>|<Название>|<Цена>|<Описание>|<URL картинки>")
        return
    category, subcategory, subsubcategory, title, price, description, image_url = parts
    if category not in data["categories"]:
        await message.answer("Категория не найдена.")
        return
    if subcategory not in data["categories"][category]:
        await message.answer("Подкатегория не найдена.")
        return

    # Определяем куда добавлять товар
    if subsubcategory:
        if subsubcategory not in data["categories"][category][subcategory]:
            await message.answer("Под-подкатегория не найдена.")
            return
        data["categories"][category][subcategory][subsubcategory].append({
            "title": title,
            "price": price,
            "description": description,
            "image": image_url
        })
    else:
        # Если нет под-подкатегории, товар хранится в списке подкатегории
        if isinstance(data["categories"][category][subcategory], dict):
            # Если в подкатегории пока нет списка товаров, создаём
            data["categories"][category][subcategory] = []
        data["categories"][category][subcategory].append({
            "title": title,
            "price": price,
            "description": description,
            "image": image_url
        })
    save_data(data)
    await message.answer(f"Товар '{title}' добавлен.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
