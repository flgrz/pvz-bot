import requests
import json
import time
import os
from datetime import datetime
from bs4 import BeautifulSoup
from telegram import Bot
from telegram.error import TelegramError
import asyncio

# ============================================
# ⚠️ ВАШИ НАСТРОЙКИ (ВСТАВЬТЕ СВОИ ДАННЫЕ)
# ============================================

# ТОКЕН БОТА - получили у @BotFather
BOT_TOKEN = "8427915511:AAGbVbZGSuFPY7ZnlHpPf1nBbZ8g4zwc0lU"

# CHAT ID - узнали через getUpdates
CHAT_ID = 8219291620  # ВСТАВЬТЕ СВОЙ ID (ТОЛЬКО ЦИФРЫ)

# ============================================
# 🔗 ССЫЛКИ ДЛЯ ПОИСКА (уже с вашими фильтрами)
# ============================================
# ✅ Город: СПб и ЛО
# ✅ Цена: до 100 000 ₽
# ✅ Площадь: 20-100 м²

# АВИТО (коммерческая + свободного назначения)
AVITO_URL = "https://www.avito.ru/sankt-peterburg/kommercheskaya_nedvizhimost/sdam/drugoe-ASgBAgICAkSwCNRWnsMNhtk5?cd=1&f=ASgBAgECA0SwCNRW9BKk2gGeww2G2TkCRbYTFHsiZnJvbSI6MjAsInRvIjoxMDB9xpoMFnsiZnJvbSI6MCwidG8iOjEwMDAwMH0&localPriority=0&s=104"

# ЦИАН - замените на свою ссылку после настройки фильтров
CIAN_URL = "https://spb.cian.ru/cat.php?currency=2&deal_type=rent&engine_version=2&maxarea=100&maxprice=100000&minarea=20&offer_type=offices&office_type%5B0%5D=1&office_type%5B1%5D=2&office_type%5B2%5D=5&region=2"

# ЯНДЕКС - замените на свою ссылку после настройки фильтров
YANDEX_URL = "https://realty.yandex.ru/sankt-peterburg/snyat/kommercheskaya-nedvizhimost/torgovoe-pomeshchenie/?priceMax=100000&areaMin=20&areaMax=100"

# ============================================
# 📁 ФАЙЛ ДЛЯ ПРОСМОТРЕННЫХ ОБЪЯВЛЕНИЙ
# ============================================
SEEN_FILE = "seen_ads.json"

# ============================================
# 🔧 СЛУЖЕБНЫЕ ФУНКЦИИ (НЕ МЕНЯТЬ!)
# ============================================

bot = Bot(token=BOT_TOKEN)

def load_seen_ads():
    """Загружает список просмотренных объявлений"""
    try:
        with open(SEEN_FILE, 'r', encoding='utf-8') as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()

def save_seen_ads(seen_ads):
    """Сохраняет список просмотренных объявлений"""
    with open(SEEN_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(seen_ads), f, ensure_ascii=False, indent=2)

async def send_to_telegram(item, source):
    """Отправляет объявление в Telegram"""
    
    # Эмодзи для разных площадок
    source_emoji = {
        'avito': '📦',
        'cian': '🏢',
        'yandex': '📱'
    }.get(source, '🔍')
    
    # Название источника
    source_name = {
        'avito': 'Авито',
        'cian': 'ЦИАН',
        'yandex': 'Яндекс'
    }.get(source, source)
    
    # Формируем сообщение
    message = (
        f"{source_emoji} <b>{item['title']}</b>\n"
        f"📌 <b>Источник:</b> {source_name}\n"
        f"💰 <b>Цена:</b> {item['price']}\n"
        f"📍 <b>Адрес:</b> {item['address']}\n"
        f"📐 <b>Площадь:</b> {item.get('area', 'не указано')}\n"
        f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        f"🔗 <a href='{item['url']}'>ОТКРЫТЬ ОБЪЯВЛЕНИЕ</a>"
    )
    
    try:
        if item.get('photo'):
            await bot.send_photo(
                chat_id=CHAT_ID,
                photo=item['photo'],
                caption=message,
                parse_mode='HTML'
            )
        else:
            await bot.send_message(
                chat_id=CHAT_ID,
                text=message,
                parse_mode='HTML'
            )
        print(f"✅ [{source_name}] Отправлено: {item['title'][:30]}...")
        return True
    except TelegramError as e:
        print(f"❌ Ошибка отправки: {e}")
        return False

# ============================================
# 📦 ПАРСЕР АВИТО
# ============================================

def parse_avito():
    """Парсит страницу Авито и возвращает список объявлений"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(AVITO_URL, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"Авито: ошибка загрузки {response.status_code}")
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        items = []
        
        for item in soup.find_all('div', {'data-marker': 'item'}):
            try:
                item_id = item.get('data-item-id', '')
                if not item_id:
                    continue
                
                title_elem = item.find('meta', {'itemprop': 'name'})
                title = title_elem.get('content', 'Без названия') if title_elem else 'Без названия'
                
                price_elem = item.find('meta', {'itemprop': 'price'})
                price = price_elem.get('content', 'Цена не указана') if price_elem else 'Цена не указана'
                if price and price.isdigit():
                    price = f"{int(price):,} ₽".replace(',', ' ')
                
                link_elem = item.find('a', {'data-marker': 'item-title'})
                link = 'https://www.avito.ru' + link_elem.get('href', '') if link_elem else ''
                
                address_elem = item.find('span', {'class': 'address'})
                address = address_elem.text.strip() if address_elem else 'Адрес не указан'
                
                img_elem = item.find('img', {'itemprop': 'image'})
                photo = img_elem.get('src', '') if img_elem else ''
                
                # Площадь
                area = "не указано"
                if 'м²' in title.lower():
                    import re
                    area_match = re.search(r'(\d+(?:[.,]\d+)?)\s*м[²2]', title)
                    if area_match:
                        area = area_match.group(1) + ' м²'
                
                items.append({
                    'id': f"avito_{item_id}",
                    'title': title,
                    'price': price,
                    'url': link,
                    'address': address,
                    'photo': photo,
                    'area': area
                })
                
            except Exception as e:
                print(f"Авито: ошибка парсинга элемента: {e}")
                continue
        
        print(f"Авито: найдено {len(items)} объявлений")
        return items
        
    except Exception as e:
        print(f"Авито: ошибка запроса: {e}")
        return []

# ============================================
# 📦 ПАРСЕР ЦИАН (упрощённый)
# ============================================

def parse_cian():
    """Парсит страницу ЦИАН (может работать нестабильно)"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(CIAN_URL, headers=headers, timeout=10)
        if response.status_code != 200:
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        items = []
        
        for item in soup.find_all('article', {'data-name': 'CardComponent'}):
            try:
                link_elem = item.find('a', {'data-name': 'CardLink'})
                if not link_elem:
                    continue
                
                href = link_elem.get('href', '')
                item_id = href.split('/')[-2] if '/' in href else str(hash(href))
                
                title_elem = item.find('span', {'data-mark': 'OfferTitle'})
                title = title_elem.text.strip() if title_elem else 'Без названия'
                
                price_elem = item.find('span', {'data-mark': 'MainPrice'})
                price = price_elem.text.strip() if price_elem else 'Цена не указана'
                
                address_elem = item.find('span', {'data-mark': 'Address'})
                address = address_elem.text.strip() if address_elem else 'Адрес не указан'
                
                if href.startswith('/'):
                    link = 'https://www.cian.ru' + href
                else:
                    link = href
                
                img_elem = item.find('img')
                photo = img_elem.get('src', '') if img_elem else ''
                
                items.append({
                    'id': f"cian_{item_id}",
                    'title': title,
                    'price': price,
                    'url': link,
                    'address': address,
                    'photo': photo,
                    'area': 'не указано'
                })
                
            except:
                continue
        
        return items
        
    except:
        return []

# ============================================
# 📦 ПАРСЕР ЯНДЕКС (упрощённый)
# ============================================

def parse_yandex():
    """Парсит страницу Яндекса (может работать нестабильно)"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(YANDEX_URL, headers=headers, timeout=10)
        if response.status_code != 200:
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        items = []
        
        for item in soup.find_all('div', {'data-testid': 'offer-card'}):
            try:
                item_id = item.get('data-offer-id', str(hash(str(item))))
                
                title_elem = item.find('h3')
                title = title_elem.text.strip() if title_elem else 'Без названия'
                
                price_elem = item.find('span', {'data-testid': 'offer-price'})
                price = price_elem.text.strip() if price_elem else 'Цена не указана'
                
                address_elem = item.find('span', {'data-testid': 'offer-address'})
                address = address_elem.text.strip() if address_elem else 'Адрес не указан'
                
                link_elem = item.find('a', {'data-testid': 'offer-link'})
                link = 'https://realty.yandex.ru' + link_elem.get('href', '') if link_elem else ''
                
                img_elem = item.find('img')
                photo = img_elem.get('src', '') if img_elem else ''
                
                items.append({
                    'id': f"yandex_{item_id}",
                    'title': title,
                    'price': price,
                    'url': link,
                    'address': address,
                    'photo': photo,
                    'area': 'не указано'
                })
                
            except:
                continue
        
        return items
        
    except:
        return []

# ============================================
# 🔁 ОСНОВНАЯ ФУНКЦИЯ ПРОВЕРКИ
# ============================================

async def check_all_sources():
    """Проверяет все источники и отправляет новые объявления"""
    print(f"\n{'='*50}")
    print(f"🔍 Проверка в {datetime.now().strftime('%H:%M:%S')}")
    
    seen_ads = load_seen_ads()
    all_items = []
    
    # Авито
    avito_items = parse_avito()
    for item in avito_items:
        item['source'] = 'avito'
    all_items.extend(avito_items)
    
    # ЦИАН (если нужно)
    if CIAN_URL != "https://spb.cian.ru/cat.php?currency=2&deal_type=rent&engine_version=2&maxarea=100&maxprice=100000&minarea=20&offer_type=offices&office_type%5B0%5D=1&office_type%5B1%5D=2&office_type%5B2%5D=5&region=2":
        cian_items = parse_cian()
        for item in cian_items:
            item['source'] = 'cian'
        all_items.extend(cian_items)
    
    # Яндекс (если нужно)
    if YANDEX_URL != "https://realty.yandex.ru/sankt-peterburg/snyat/kommercheskaya-nedvizhimost/torgovoe-pomeshchenie/?priceMax=100000&areaMin=20&areaMax=100":
        yandex_items = parse_yandex()
        for item in yandex_items:
            item['source'] = 'yandex'
        all_items.extend(yandex_items)
    
    print(f"Всего найдено: {len(all_items)} объявлений")
    
    new_items = [item for item in all_items if item['id'] not in seen_ads]
    print(f"Новых: {len(new_items)}")
    
    sent_count = 0
    for item in new_items:
        if await send_to_telegram(item, item['source']):
            seen_ads.add(item['id'])
            sent_count += 1
            await asyncio.sleep(1)
    
    if sent_count > 0:
        save_seen_ads(seen_ads)
    
    print(f"✅ Отправлено: {sent_count}")

# ============================================
# 🚀 ЗАПУСК БОТА
# ============================================

async def main():
    print("="*50)
    print("🤖 БОТ ДЛЯ ПОИСКА ПОМЕЩЕНИЙ")
    print("="*50)
    print(f"Токен: {BOT_TOKEN[:10]}...")
    print(f"Интервал проверки: 5 минут")
    print("="*50)
    
    # Проверяем токен
    if BOT_TOKEN == "8427915511:AAGbVbZGSuFPY7ZnlHpPf1nBbZ8g4zwc0lU":
        print("\n❌ ОШИБКА: Не вставлен токен бота!")
        print("Вставьте свой токен в строку BOT_TOKEN")
        return
    
    # Отправляем приветствие
    try:
        await bot.send_message(
            chat_id=304705375,
            text="🚀 <b>Бот запущен на Render.com!</b>\n\n"
                 "Буду присылать новые объявления каждые 5 минут.\n\n"
                 "🔍 <b>Параметры поиска:</b>\n"
                 "• Площадь: 20-100 м²\n"
                 "• Цена: до 100 000 ₽\n"
                 "• Город: СПб и ЛО\n"
                 "• Площадка: Авито (основная)",
            parse_mode='HTML'
        )
        print("✅ Приветственное сообщение отправлено")
    except Exception as e:
        print(f"❌ Ошибка приветствия: {e}")
        print("Проверьте CHAT_ID и токен")
        return
    
    # Бесконечный цикл
    while True:
        try:
            await check_all_sources()
            print("⏳ Следующая проверка через 5 минут...")
            await asyncio.sleep(300)
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())