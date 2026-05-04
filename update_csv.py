# update_csv.py - Обновление CSV с ценами и фото

import os
import re
import time
import random
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# =====================================================================
# СПИСОК ССЫЛОК
# =====================================================================

ALL_LINKS_WITH_MODELS = [
    ("Т-34-85",
     "https://zvezda.org.ru/catalog/sbornye_modeli/tekhnika/vtoraya_mirovaya_voyna_vehicles/geroi_pobedy_sovetskiy_sredniy_tank_t_34_85/"),
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
    ("Т-90",
     "https://zvezda.org.ru/catalog/sbornye_modeli/tekhnika/poslevoennaya_i_sovremennaya_vehicles/rossiyskiy_osnovnoy_tank_t_90ms__38645/"),
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


# =====================================================================
# ФУНКЦИИ ПАРСИНГА
# =====================================================================

def extract_price(text):
    """Извлекает цену из текста"""
    if not text:
        return ""
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


def parse_kit_details(url, driver, wait):
    """Парсит детальную информацию о наборе с ценой и фото"""
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

    # ЦЕНА
    price = ""
    price_selectors = [".product-price", ".price", ".cost", ".product__price"]
    for selector in price_selectors:
        price_text = safe_text(selector)
        if price_text:
            price = extract_price(price_text)
            if price:
                break

    if not price:
        page_text = driver.find_element(By.TAG_NAME, "body").text
        price = extract_price(page_text)

    # ФОТО
    photos = driver.find_elements(By.CSS_SELECTOR,
                                  ".product-gallery__image img, .product-gallery-big__img, .product-slider__slide img")
    photo_links = []
    for p in photos:
        src = p.get_attribute("src")
        if src and src.startswith("http") and 'no-photo' not in src and 'blank' not in src:
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
        "Фото": ", ".join(photo_links[:3]),
        "PDF файлы": ", ".join(pdf_links[:3]),
        "Модель": "",
        "URL": url
    }


def parse_all_kits():
    """Парсит все наборы и возвращает DataFrame"""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )
    wait = WebDriverWait(driver, 20)

    results = []

    for model, url in ALL_LINKS_WITH_MODELS:
        print(f"   Парсинг: {model}...")
        kit_data = parse_kit_details(url, driver, wait)
        if kit_data and kit_data["Название"]:
            kit_data["Модель"] = model
            results.append(kit_data)
            print(
                f"      ✅ {kit_data['Название'][:40]}... | Цена: {kit_data['Цена']} | Фото: {len(kit_data['Фото'].split(',')) if kit_data['Фото'] else 0}")
        else:
            print(f"      ❌ Ошибка: {url}")
        time.sleep(random.uniform(0.5, 1))

    driver.quit()

    if results:
        return pd.DataFrame(results)
    return pd.DataFrame()


# =====================================================================
# ЗАПУСК
# =====================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 ОБНОВЛЕНИЕ CSV С ЦЕНАМИ И ФОТО")
    print("=" * 60)

    df = parse_all_kits()

    if not df.empty:
        # Сохраняем в файл
        df.to_csv("zvezda_cached.csv", sep=";", encoding="utf-8-sig", index=False)
        print(f"\n✅ Сохранено {len(df)} наборов в zvezda_cached.csv")
        print(f"\n📋 Колонки: {list(df.columns)}")
        print("\n📊 Пример данных:")
        print(df[["Модель", "Название", "Цена", "Фото"]].head(10).to_string())
    else:
        print("❌ Не удалось собрать данные")