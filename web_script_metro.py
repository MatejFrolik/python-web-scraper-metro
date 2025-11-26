import csv
import re
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# Seznam prodejen METRO SK – uprav podle reality
STORES = [
    "Devínska Nová Ves",
    "Ivanka pri Dunaji",
    "Košice",
    "Nitra",
    "Zvolen",
    "Žilina",
]

INPUT_CSV = "produkty.csv"              # vstupní seznam produktů
OUTPUT_CSV = "metro_sklady_vystup.csv"  # výstupní tabulka

def create_driver(headless: bool = True) -> webdriver.Chrome:
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    # DŮLEŽITÉ: vypneme SSL ověřování certifikátu pro webdriver_manager
    service = Service(ChromeDriverManager(ssl_verify=False).install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_window_size(1400, 900)
    return driver



def accept_cookies_if_any(driver, wait: WebDriverWait):
    try:
        btn = wait.until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "//*[contains(., 'Súhlasím') or contains(., 'Akceptovať') or contains(., 'Akceptovať všetko')]",
                )
            )
        )
        btn.click()
        time.sleep(1)
    except Exception:
        pass


def switch_store(driver, wait: WebDriverWait, store_name: str):
    # Otevřít dialog na změnu predajne – text XPATH si případně uprav podle reálné stránky
    switch_btn = wait.until(
        EC.element_to_be_clickable(
            (By.XPATH, "//*[contains(text(),'Vybrať inú predajňu')]")
        )
    )
    switch_btn.click()
    time.sleep(0.5)

    # Kliknout na konkrétní predajnu
    store_elem = wait.until(
        EC.element_to_be_clickable(
            (By.XPATH, f"//*[contains(text(), '{store_name}')]")
        )
    )
    store_elem.click()

    # Počkat na přepnutí – když to nepůjde poznat textem, necháme pauzu
    try:
        wait.until(
            EC.text_to_be_present_in_element(
                (By.XPATH, "//*[contains(text(),'Vybraná predajňa')]"),
                store_name,
            )
        )
    except Exception:
        time.sleep(2)


def get_stock_for_current_store(driver, wait: WebDriverWait) -> int | None:
    # Najít text „Na predajni: xx bal.“ – případně uprav podle skutečného textu
    stock_elem = wait.until(
        EC.presence_of_element_located(
            (By.XPATH, "//*[contains(text(),'Na predajni:')]")
        )
    )
    text = stock_elem.text
    m = re.search(r"Na predajni:\s*([\d\s\xa0]+)", text)
    if not m:
        return None
    num_str = m.group(1).replace("\xa0", "").replace(" ", "")
    try:
        return int(num_str)
    except ValueError:
        return None


def load_products(path: str):
    products = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("product_name") or row.get("name") or ""
            url = row.get("product_url") or row.get("url") or ""
            if url:
                products.append({"name": name, "url": url})
    return products


def main():
    if not Path(INPUT_CSV).exists():
        print(f"Chybí vstupní soubor {INPUT_CSV}. Vytvoř si ho ve formátu:")
        print("product_name,product_url")
        return

    products = load_products(INPUT_CSV)
    if not products:
        print("Ve vstupním CSV nejsou žádné produkty.")
        return

    driver = create_driver(headless=True)
    wait = WebDriverWait(driver, 15)

    results = []

    try:
        first_page = True

        for prod in products:
            name = prod["name"]
            url = prod["url"]
            print(f"\n=== Produkt: {name or '(bez názvu)'} ===")
            print(f"URL: {url}")

            driver.get(url)
            if first_page:
                accept_cookies_if_any(driver, wait)
                first_page = False

            for store in STORES:
                print(f"  Predajňa: {store} ...")
                try:
                    switch_store(driver, wait, store)
                    stock = get_stock_for_current_store(driver, wait)
                    print(f"    Na predajni {store}: {stock} bal.")
                except Exception as e:
                    print(f"    Chyba u predajne {store}: {e}")
                    stock = None

                results.append(
                    {
                        "product_name": name,
                        "product_url": url,
                        "predajna": store,
                        "baleni_na_sklade": stock,
                    }
                )

        # Zápis výsledků
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "product_name",
                    "product_url",
                    "predajna",
                    "baleni_na_sklade",
                ],
            )
            writer.writeheader()
            writer.writerows(results)

        print(f"\nHotovo. Výsledek je v souboru: {OUTPUT_CSV}")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
