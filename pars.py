import pandas as pd
import time
import random
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# =====================================================================
# ПОЛНЫЙ СПИСОК ССЫЛОК ДЛЯ ВСЕХ 12 МОДЕЛЕЙ
# =====================================================================

ALL_LINKS_WITH_MODELS = [
    # ========== ТАНКИ ==========
    ("Т-34-85",
     "https://zvezda.org.ru/catalog/sbornye_modeli/tekhnika/vtoraya_mirovaya_voyna_vehicles/geroi_pobedy_sovetskiy_sredniy_tank_t_34_85/"),
    ("Т-34-85",
     "https://zvezda.org.ru/catalog/sbornye_modeli/tekhnika/vtoraya_mirovaya_voyna_vehicles/geroi_pobedy_sovetskiy_sredniy_tank_t_34_76_obr_19/"),
    ("Tiger I",
     "https://zvezda.org.ru/catalog/sbornye_modeli/tekhnika/vtoraya_mirovaya_voyna_vehicles/nemetskiy_tyazhelyy_tank_t_vi_tigr/"),
    ("Panther",
     "https://zvezda.org.ru/catalog/sbornye_modeli/tekhnika/vtoraya_mirovaya_voyna_vehicles/nemetskiy_sredniy_tank_t_v_pantera/"),
    ("M4 Sherman",
     "https://zvezda.org.ru/catalog/sbornye_modeli/tekhnika/vtoraya_mirovaya_voyna_vehicles/geroi_pobedy_amerikanskiy_sredniy_tank_m4a2_76_w_sherman/"),
    ("M4 Sherman",
     "https://zvezda.org.ru/catalog/sbornye_modeli/tekhnika/vtoraya_mirovaya_voyna_vehicles/amerikanskiy_sredniy_tank_sherman_m4a2_76/"),
    ("M4 Sherman",
     "https://zvezda.org.ru/catalog/sbornye_modeli/tekhnika/vtoraya_mirovaya_voyna_vehicles/amerikanskiy_sredniy_tank_sherman_m4a2_31431/"),
    ("КВ-1",
     "https://zvezda.org.ru/catalog/sbornye_modeli/tekhnika/vtoraya_mirovaya_voyna_vehicles/sovetskiy_tyazhelyy_tank_kv_1/"),
    ("КВ-1",
     "https://zvezda.org.ru/catalog/sbornye_modeli/tekhnika/vtoraya_mirovaya_voyna_vehicles/kv_1_ekranirovannyy/"),
    ("Т-90",
     "https://zvezda.org.ru/catalog/sbornye_modeli/tekhnika/poslevoennaya_i_sovremennaya_vehicles/rossiyskiy_osnovnoy_tank_t_90ms__38645/"),

    # ========== САМОЛЕТЫ ==========
    ("Ил-2",
     "https://zvezda.org.ru/catalog/sbornye_modeli/aviatsiya/vtoraya_mirovaya_voyna_aviation/geroi_pobedy_sovetskiy_dvukhmestnyy_shturmovik_il_2_obr_1943g/"),
    ("Ил-2",
     "https://zvezda.org.ru/catalog/sbornye_modeli/aviatsiya/vtoraya_mirovaya_voyna_aviation/sovetskiy_dvukhmestnyy_shturmovik_il_2_obr_1943g/"),
    ("Bf-109",
     "https://zvezda.org.ru/catalog/sbornye_modeli/aviatsiya/vtoraya_mirovaya_voyna_aviation/nemetskiy_istrebitel_messershmitt_bf_109_f2_11383/"),
    ("Fw-190",
     "https://zvezda.org.ru/catalog/sbornye_modeli/aviatsiya/vtoraya_mirovaya_voyna_aviation/nemetskiy_istrebitel_fokke_vulf_fw_190_a4/"),
    ("Spitfire",
     "https://zvezda.org.ru/catalog/sbornye_modeli/aviatsiya/vtoraya_mirovaya_voyna_aviation/2804it-spitfire-mk-ix_36484/"),
    ("P-51 Mustang",
     "https://zvezda.org.ru/catalog/sbornye_modeli/aviatsiya/vtoraya_mirovaya_voyna_aviation/1423it-r-51a-mustang_36712/"),
    ("Су-25",
     "https://zvezda.org.ru/catalog/sbornye_modeli/aviatsiya/poslevoennaya_i_sovremennaya_aviation/sovetskiy_shturmovik_su_25_40371/"),
    ("Су-25",
     "https://zvezda.org.ru/catalog/sbornye_modeli/aviatsiya/poslevoennaya_i_sovremennaya_aviation/sovetskiy_shturmovik_su_25_37443/"),
    ("Су-25",
     "https://zvezda.org.ru/catalog/sbornye_modeli/aviatsiya/poslevoennaya_i_sovremennaya_aviation/sovetskiy_shturmovik_su_25-2/"),
]

print("=" * 80)
print("📊 СТАТИСТИКА ССЫЛОК ПО МОДЕЛЯМ")
print("=" * 80)

model_count = {}
for model, _ in ALL_LINKS_WITH_MODELS:
    model_count[model] = model_count.get(model, 0) + 1

for model, count in model_count.items():
    print(f"   {model}: {count} наборов")

print(f"\n   Всего ссылок: {len(ALL_LINKS_WITH_MODELS)}")


# =====================================================================
# ФУНКЦИЯ ДЛЯ ИЗВЛЕЧЕНИЯ ЦЕНЫ
# =====================================================================

def extract_price(text):
    """Извлекает цену из текста"""
    if not text:
        return ""
    # Ищем числа с пробелами и ₽
    patterns = [
        r'(\d[\d\s]*\d)\s*₽',
        r'(\d[\d\s]*\d)\s*руб',
        r'(\d+)\s*₽',
        r'(\d+)\s*руб'
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            price = match.group(1).replace(' ', '')
            return f"{price} ₽"
    return ""


# =====================================================================
# ПАРСИНГ ДЕТАЛЬНОЙ ИНФОРМАЦИИ С ЦЕНОЙ
# =====================================================================

def parse_kit_details(url, driver, wait):
    """Парсит детальную информацию о наборе с ценой"""

    driver.get(url)

    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1")))
    except:
        return None

    time.sleep(2)

    def safe_text(selector):
        try:
            elem = driver.find_element(By.CSS_SELECTOR, selector)
            return elem.text.strip()
        except:
            return ""

    # Название
    title = safe_text("h1")
    if not title or title == "404 Not Found":
        return None

    # Артикул
    article = ""
    article_text = safe_text(".product__article, .article, .product-article")
    match = re.search(r'(\d+)', article_text)
    if match:
        article = match.group(1)
    if not article:
        match = re.search(r'_(\d+)/?$', url)
        if match:
            article = match.group(1)

    # Масштаб
    scale = ""
    desc = safe_text(".product-description__text, .product-desc")
    scale_match = re.search(r'Масштаб\s*\n\s*(\d+:\d+)', desc)
    if scale_match:
        scale = scale_match.group(1)

    # ЦЕНА - ищем в разных местах
    price = ""

    # Пробуем найти цену в блоке с ценой
    price_selectors = [
        ".product-price",
        ".price",
        ".cost",
        ".product__price",
        ".price-value"
    ]
    for selector in price_selectors:
        price_text = safe_text(selector)
        if price_text:
            price = extract_price(price_text)
            if price:
                break

    # Если не нашли, ищем во всем тексте страницы
    if not price:
        page_text = driver.find_element(By.TAG_NAME, "body").text
        price = extract_price(page_text)

    # Фото
    photos = driver.find_elements(By.CSS_SELECTOR, ".product-gallery__image img, .product-gallery-big__img")
    photo_links = []
    for p in photos:
        src = p.get_attribute("src")
        if src and src.startswith("http") and 'no-photo' not in src:
            photo_links.append(src)

    # PDF инструкции
    pdf_links = []
    pdf_elements = driver.find_elements(By.CSS_SELECTOR, "a[href$='.pdf']")
    for pdf in pdf_elements:
        href = pdf.get_attribute("href")
        if href:
            pdf_links.append(href)

    return {
        "Название": title,
        "Артикул": article,
        "Масштаб": scale,
        "Цена": price,
        "Описание": desc[:500] if desc else "",
        "Фото": ", ".join(photo_links[:3]),
        "PDF файлы": ", ".join(pdf_links[:3]),
        "URL": url
    }


# =====================================================================
# ОСНОВНАЯ ФУНКЦИЯ
# =====================================================================

def main():
    print("\n" + "=" * 80)
    print("🚀 ПАРСЕР КАТАЛОГА ЗВЕЗДЫ (С ЦЕНАМИ)")
    print("=" * 80)

    print("\n📁 Начинаем парсинг...")

    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    # Добавляем User-Agent для обхода блокировок
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    wait = WebDriverWait(driver, 20)

    results = []
    failed = []

    for i, (model, url) in enumerate(ALL_LINKS_WITH_MODELS, 1):
        print(f"\n   [{i}/{len(ALL_LINKS_WITH_MODELS)}] {model}: {url.split('/')[-2]}")

        kit_data = parse_kit_details(url, driver, wait)

        if kit_data and kit_data["Название"]:
            kit_data["Модель"] = model
            results.append(kit_data)
            print(f"       ✅ {kit_data['Название'][:50]}...")
            print(f"       📦 Артикул: {kit_data['Артикул']}, Масштаб: {kit_data['Масштаб']}, Цена: {kit_data['Цена']}")
        else:
            print(f"       ❌ Ошибка при парсинге")
            failed.append((model, url))

        time.sleep(random.uniform(1.5, 3))

    driver.quit()

    # Сохранение
    print("\n📁 Сохранение результатов...")

    df = pd.DataFrame(results)
    df.to_csv("zvezda_with_prices.csv", sep=";", encoding="utf-8-sig", index=False)

    print(f"\n{'=' * 80}")
    print(f"🎉 ГОТОВО!")
    print(f"   Успешно собрано: {len(results)} наборов")
    print(f"   Не удалось: {len(failed)}")
    print(f"   Файл: zvezda_with_prices.csv")
    print(f"{'=' * 80}")

    # Статистика
    print("\n📊 СТАТИСТИКА ПО МОДЕЛЯМ:")
    if results:
        model_counts = {}
        for kit in results:
            model = kit.get("Модель", "Неизвестно")
            model_counts[model] = model_counts.get(model, 0) + 1

        for model, count in sorted(model_counts.items()):
            print(f"   {model}: {count} наборов")

        # Статистика по ценам
        prices_found = sum(1 for kit in results if kit.get("Цена"))
        print(f"\n💰 Цены найдены для {prices_found}/{len(results)} наборов")

    if failed:
        print("\n⚠️ НЕ УДАЛОСЬ СПАРСИТЬ:")
        for model, url in failed:
            print(f"   {model}: {url}")

    return df


if __name__ == "__main__":
    df = main()

    if len(df) > 0:
        print("\n📋 РЕЗУЛЬТАТ (первые 10):")
        print(df[["Модель", "Название", "Артикул", "Масштаб", "Цена"]].head(10).to_string())