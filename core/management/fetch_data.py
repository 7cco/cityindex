import os
import sys
import time
import logging
import re
import requests
import pandas as pd
import django
from dotenv import load_dotenv


BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cityindex.settings')
django.setup()

from core.models import Locality, EconomicData, InfrastructureData
from django.db import transaction


OVERPASS_API_URL = "https://overpass-api.de/api/interpreter"
NOMINATIM_API_URL = "https://nominatim.openstreetmap.org/search"

load_dotenv()

EMAIL = os.getenv('GORODINDEX_EMAIL', 'contact@gorodindex.local')
HEADERS = {
    'User-Agent': f'GorodIndex/1.0 ({EMAIL})',
    'Accept-Language': 'ru'
}

DATA_DIR = os.path.join(BASE_DIR, "data", "data_clean")
NDLF_FILE = os.path.join(DATA_DIR, "ndfl.xlsx")
POPULATION_FILE = os.path.join(DATA_DIR, "population.xlsx")
UNEMPLOYMENT_FILE = os.path.join(DATA_DIR, "unemployment.xlsx")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def ndfl(input_file):
    """Обработка данных НДФЛ и населения"""
    ndfl = pd.read_excel(input_file)
    ndfl['Название'] = ndfl['Название'].astype(str).str.strip()
    valid_names = set(ndfl['Название'].dropna())

    logger.info(f"Загружено {len(valid_names)} городов из ndfl.xlsx")

    df = pd.read_excel(POPULATION_FILE)

    df['Население'] = df['Население'].astype(str).str.replace(r'[^\d.,]', '', regex=True)
    df['Население'] = df['Население'].str.replace(',', '.')
    df['Население'] = pd.to_numeric(df['Население'], errors='coerce')

    # Функция: извлечь все подстроки вида "г. ..." из строки и проверить, есть ли среди них валидное название
    def extract_valid_city_name(text):
        if pd.isna(text):
            return None
        text = str(text)
        matches = re.findall(r'г\.\s*[А-ЯЁа-яё][А-ЯЁа-яё\s\-]*', text)
        for match in matches:
            # Нормализуем: убираем лишние пробелы после точки
            normalized = re.sub(r'г\.\s*', 'г. ', match)
            if normalized in valid_names:
                return normalized
        return None

    df['Чистое_название'] = df['Название'].apply(extract_valid_city_name)
    filtered_df = df[
        (df['Население'] >= 12000) &
        (df['Население'] <= 100000) &
        (df['Чистое_название'].notna())
    ]

    result = filtered_df[['Чистое_название', 'Население']].rename(columns={'Чистое_название': 'Название'})

    final = pd.merge(
        result,
        ndfl[['Название', 'ОКТМО', 'НДФЛ']],
        on='Название',
        how='inner'  # только те, что есть в обоих файлах
    )

    final = final.reset_index(drop=True)
    final_clean = final.sort_values(by=['Название', 'Население'])
    final_clean = final_clean.drop_duplicates(subset=['Название'], keep='first')
    return final_clean.reset_index(drop=True)


def get_city_coordinates(city_name, region_name=None):
    try:
        query = f"{city_name}, {region_name}" if region_name else city_name
        params = {'q': query, 'format': 'json', 'limit': 1, 'addressdetails': 1}
        logger.info(f"Запрос координат для: {query}")
        response = requests.get(NOMINATIM_API_URL, params=params, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        if not data:
            logger.warning(f"Не найдены координаты для: {query}")
            return None
        place = data[0]
        display_name = place.get('display_name', 'Unknown')
        bbox = place.get('boundingbox')
        if bbox:
            return {
                'type': 'bbox',
                'min_lat': float(bbox[0]),
                'max_lat': float(bbox[1]),
                'min_lon': float(bbox[2]),
                'max_lon': float(bbox[3]),
                'display_name': display_name
            }
        return {
            'type': 'center',
            'lat': float(place['lat']),
            'lon': float(place['lon']),
            'display_name': display_name
        }
    except Exception as e:
        logger.error(f"Ошибка при получении координат для {city_name}: {e}")
        return None


def query_count_with_retry(element_type, tag_key, tag_value, area_clause, max_retries=5):
    """
    Запрос к Overpass с таймаутами и паузами.
    Возвращает число или None при полном провале.
    """
    for attempt in range(max_retries):
        try:
            if element_type:
                query = f'[out:json][timeout:60];{element_type}["{tag_key}"="{tag_value}"]({area_clause});out ids;'
            else:
                query = f'[out:json][timeout:60];(' \
                        f'node["{tag_key}"="{tag_value}"]({area_clause});' \
                        f'way["{tag_key}"="{tag_value}"]({area_clause});' \
                        f');out ids;'

            logger.debug(f"Отправка запроса: {query[:100]}...")

            response = requests.post(
                OVERPASS_API_URL,
                data={'data': query},
                headers=HEADERS,
                timeout=70
            )
            response.raise_for_status()
            data = response.json()
            count = len(data.get('elements', []))
            logger.info(f"  → {tag_value}: {count} объектов")
            return count

        except requests.exceptions.HTTPError as e:
            status = e.response.status_code
            if status == 429:
                wait = 10 + 5 * attempt
                logger.warning(f"  ⚠️ 429 Too Many Requests. Повтор через {wait} сек...")
                time.sleep(wait)
            elif status >= 500:
                wait = 15 + 5 * attempt
                logger.warning(f"  ⚠️ Серверная ошибка {status}. Повтор через {wait} сек...")
                time.sleep(wait)
            else:
                logger.error(f"  ❌ Ошибка HTTP {status}")
                break
        except requests.exceptions.Timeout:
            wait = 20
            logger.warning(f"  ⚠️ Таймаут. Повтор через {wait} сек...")
            time.sleep(wait)
        except Exception as e:
            logger.error(f"  ❌ Неизвестная ошибка: {e}")
            break

    logger.error(f"  ❌ Все {max_retries} попыток исчерпаны для '{tag_value}'")
    return None


def get_infrastructure_data(coords):
    if coords['type'] == 'bbox':
        area = f"{coords['min_lat']},{coords['min_lon']},{coords['max_lat']},{coords['max_lon']}"
    else:
        area = f"around:5000,{coords['lat']},{coords['lon']}"

    schools = query_count_with_retry('', 'amenity', 'school', area) or 0
    gas_stations = query_count_with_retry('', 'amenity', 'fuel', area) or 0
    bus_stops = query_count_with_retry('node', 'highway', 'bus_stop', area) or 0

    return {
        'schools': schools,
        'gas_stations': gas_stations,
        'bus_stops': bus_stops
    }


def extract_region_from_osm(display_name):
    """
    Извлекает регион из строки Nominatim.
    Ищет последнюю часть, которая выглядит как субъект РФ
    """
    if not isinstance(display_name, str):
        return None

    parts = [p.strip() for p in display_name.split(',') if p.strip()]
    if parts and parts[-1] in ('Россия'):
        parts = parts[:-1]

    region_keywords = [
        'область', 'край', 'республика', 'автономный округ', 
        'г.', 'город', 'Хакасия', 'Башкирия', 'Адыгея', 'Татарстан',
        'Коми', 'Карелия', 'Мордовия', 'Удмуртия', 'Чувашия', 'Марий Эл',
        'Северная Осетия', 'Дагестан', 'Ингушетия', 'Кабардино-Балкария',
        'Карачаево-Черкесия', 'Тыва', 'Алтай', 'Бурятия', 'Якутия',
        'Крым', 'Севастополь', 'Москва', 'Санкт-Петербург'
    ]

    # Идём с конца — ищем первый элемент, похожий на регион
    for part in reversed(parts):
        part_lower = part.lower()
        # Пропускаем мелкие муниципальные образования
        if any(x in part_lower for x in ['городской округ', 'муниципальный округ', 'район', 'поселение']):
            continue
        # Если содержит ключевые слова — это регион
        if any(kw in part_lower for kw in [k.lower() for k in region_keywords]):
            return part.replace('—', '-')
        # Или если это короткое название республики
        if part in ['Адыгея', 'Хакасия', 'Башкирия', 'Татарстан', 'Коми', 'Карелия',
                    'Мордовия', 'Удмуртия', 'Чувашия', 'Марий Эл', 'Тыва', 'Алтай',
                    'Бурятия', 'Якутия', 'Крым']:
            return part
    return parts[-1] if parts else None


def get_unemployment_data():
    """Загружает и обрабатывает данные о безработице"""
    logger.info("Загрузка данных о безработице...")
    df_unemp = pd.read_excel(UNEMPLOYMENT_FILE)

    if 'Unnamed: 0' not in df_unemp.columns or 2023 not in df_unemp.columns:
        raise ValueError("В файле unemployment.xlsx должны быть колонки 'Unnamed: 0' и 2023")

    # Создаём словарь: регион: безработица
    unemployment_dict = dict(zip(df_unemp['Unnamed: 0'], df_unemp[2023]))
    logger.info(f"Загружено {len(unemployment_dict)} регионов с данными о безработице.")
    
    # Маппинг алиасов (краткие названия: полные)
    REGION_ALIAS = {
        # Республики
        'Хакасия': 'Республика Хакасия',
        'Башкирия': 'Республика Башкортостан',
        'Адыгея': 'Республика Адыгея',
        'Татарстан': 'Республика Татарстан',
        'Коми': 'Республика Коми',
        'Карелия': 'Республика Карелия',
        'Мордовия': 'Республика Мордовия',
        'Удмуртия': 'Удмуртская Республика',
        'Чувашия': 'Чувашская Республика',
        'Марий Эл': 'Республика Марий Эл',
        'Северная Осетия': 'Республика Северная Осетия - Алания',
        'Северная Осетия - Алания': 'Республика Северная Осетия - Алания',
        'Дагестан': 'Республика Дагестан',
        'Ингушетия': 'Республика Ингушетия',
        'Кабардино-Балкария': 'Кабардино-Балкарская Республика',
        'Карачаево-Черкесия': 'Карачаево-Черкесская Республика',
        'Тыва': 'Республика Тыва',
        'Алтай': 'Республика Алтай',
        'Бурятия': 'Республика Бурятия',
        'Якутия': 'Республика Саха (Якутия)',
        # Города федерального значения
        'Москва': 'г. Москва',
        'Санкт-Петербург': 'г.Санкт-Петербург',
        'Севастополь': 'г. Севастополь',
        'Крым': 'Республика Крым',
        # Области/края
        'Ростовская': 'Ростовская область',
        'Воронежская': 'Воронежская область',
    }
    
    return unemployment_dict, REGION_ALIAS


def find_unemployment_rate(region_raw, unemp_dict, alias_map):
    if not region_raw:
        return None
    if region_raw in unemp_dict:
        return unemp_dict[region_raw]
    if region_raw in alias_map:
        full_name = alias_map[region_raw]
        if full_name in unemp_dict:
            return unemp_dict[full_name]
    region_clean = region_raw.replace(' ', '').lower()
    for key in unemp_dict:
        if isinstance(key, str):
            key_clean = key.replace(' ', '').lower()
            if region_clean in key_clean or key_clean in region_clean:
                return unemp_dict[key]
    return None


def fetch_and_save_data():
    """Основная функция для загрузки и сохранения данных"""
    logger.info("Загрузка и обработка данных НДФЛ и населения...")
    
    for file_path in [NDLF_FILE, POPULATION_FILE, UNEMPLOYMENT_FILE]:
        if not os.path.exists(file_path):
            logger.error(f"Файл не найден: {file_path}")
            sys.exit(1)
    
    cities_data = ndfl(NDLF_FILE)
    logger.info(f"Отобрано {len(cities_data)} городов для обработки")
    
    unemp_dict, region_aliases = get_unemployment_data()
    
    results = []
    for idx, row in cities_data.iterrows():
        raw_name = row['Название']
        city_clean = raw_name[3:].strip()
        logger.info(f"[{idx+1}/{len(cities_data)}] Обработка: {raw_name} → '{city_clean}'")

        coords = get_city_coordinates(city_clean)
        if not coords:
            logger.warning(f"  ❌ Не найден: {city_clean}")
            continue

        infra = get_infrastructure_data(coords)
        logger.info(f"  ✅ Результат: школы={infra['schools']}, АЗС={infra['gas_stations']}, остановки={infra['bus_stops']}")

        region_name = extract_region_from_osm(coords['display_name'])
        unemp_rate = find_unemployment_rate(region_name, unemp_dict, region_aliases)
        
        results.append({
            'city_name': city_clean,
            'region': region_name,
            'population': row['Население'],
            'oktmo_code': row['ОКТМО'],
            'ndfl': row['НДФЛ'],
            'unemployment_rate': unemp_rate,
            'infrastructure': infra,
            'osm_display_name': coords['display_name']
        })

        # Пауза между городами
        time.sleep(2)

    logger.info("Сохранение данных в базу Django...")
    with transaction.atomic():
        for item in results:
            # Создаем или обновляем запись о городе
            locality, _ = Locality.objects.update_or_create(
                oktmo_code=item['oktmo_code'],
                defaults={
                    'city': item['city_name'],
                    'region': item['region'],
                    'population': item['population'],
                    'is_active': True
                }
            )
            
            # Создаем или обновляем экономические данные
            EconomicData.objects.update_or_create(
                locality=locality,
                year=2023,
                defaults={
                    'ndfl_total': item['ndfl'],
                    'unemployment_rate': item['unemployment_rate']
                }
            )
            
            # Создаем или обновляем данные об инфраструктуре
            InfrastructureData.objects.update_or_create(
                locality=locality,
                defaults={
                    'schools': item['infrastructure']['schools'],
                    'gas_stations': item['infrastructure']['gas_stations'],
                    'bus_stops': item['infrastructure']['bus_stops']
                }
            )
            
            logger.info(f"Сохранен город: {locality.city} ({locality.region})")
    
    logger.info(f"Всего сохранено городов: {len(results)}")
    return results


if __name__ == "__main__":
    logger.info("Запуск скрипта загрузки данных...")
    fetch_and_save_data()
    logger.info("Скрипт завершен")