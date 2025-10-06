from __future__ import annotations

import os
import time
import logging
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, WebDriverException


OKX_SWAP_BASE = "https://www.okx.com/ru/trade-swap/"


def format_pair_for_url(pair: str) -> str:
    """Insert '-' before 'USDT' suffix: e.g., 'DOTUSDT' -> 'DOT-USDT'."""
    pair = pair.strip().upper()
    if pair.endswith("USDT") and "-" not in pair:
        return f"{pair[:-4]}-USDT"
    return pair


def build_okx_swap_url(formatted_pair: str) -> str:
    # OKX swap URLs are lowercase and end with '-swap', e.g. eth-usdt-swap
    return f"{OKX_SWAP_BASE}{formatted_pair.lower()}-swap"


def ensure_dir(path: str) -> None:
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def download_file(url: str, dest_path: str, timeout: int = 20) -> None:
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    with open(dest_path, "wb") as f:
        f.write(resp.content)


def create_webdriver(headless: bool = True) -> webdriver.Chrome:
    options = ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,1200")
    # Reduce automation flags to avoid potential anti-bot friction
    options.add_experimental_option("excludeSwitches", ["enable-automation"]) 
    options.add_experimental_option("useAutomationExtension", False)
    service = ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver


def find_icon_src_for_pair(driver: webdriver.Chrome, url: str, wait_seconds: int = 20) -> Optional[str]:
    try:
        driver.get(url)

        wait = WebDriverWait(driver, wait_seconds)
        # Wait for the <picture class="okui-picture okui-picture-font"> to appear
        picture = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "picture.okui-picture okui-picture-font".replace(" ", ".")))
        )

        # Within picture, find nested img and get src
        try:
            img = picture.find_element(By.CSS_SELECTOR, "img[src]")
            src = img.get_attribute("src")
            return src
        except Exception:
            return None
    except TimeoutException:
        return None
    except WebDriverException:
        return None


def scrape_and_download_icons(pairs: Iterable[str], output_dir: str) -> Tuple[List[str], List[str]]:
    ensure_dir(output_dir)

    driver = create_webdriver(headless=True)
    saved: List[str] = []
    failed: List[str] = []
    try:
        for pair in pairs:
            original_pair = pair.strip().upper()
            formatted = format_pair_for_url(original_pair)
            url = build_okx_swap_url(formatted)

            logging.info("Processing %s -> %s", original_pair, url)
            icon_src = find_icon_src_for_pair(driver, url)
            if not icon_src:
                logging.warning("Icon not found for %s", original_pair)
                failed.append(original_pair)
                continue

            # Choose extension from URL; default to .png
            ext = ".png"
            for candidate in (".png", ".svg", ".webp", ".jpg", ".jpeg"):
                if candidate in icon_src.lower():
                    ext = candidate
                    break

            dest_path = os.path.join(output_dir, f"{original_pair}{ext}")
            try:
                download_file(icon_src, dest_path)
                saved.append(dest_path)
                logging.info("Saved %s", dest_path)
            except Exception as e:
                logging.exception("Failed to download %s: %s", icon_src, e)
                failed.append(original_pair)
                continue
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    return saved, failed


DEFAULT_PAIRS = [
    "BTCUSDT",
    "ETHUSDT",
    "AAVEUSDT",
    "DOTUSDT",
    "AGLDUSDT",
    "APEUSDT",
    "FILUSDT",
    "GRASSUSDT",
    "BNBUSDT",
    "BERAUSDT",
    "SUSDT",
    "SOLUSDT",
    "POPCATUSDT",
    "JUPUSDT",
    "LPTUSDT",
    "SEIUSDT",
    "TAOUSDT",
    "ADAUSDT",
    "JTOUSDT",
    "LDOUSDT",
    "LINKUSDT",
    "BERAUSDT",
    "PNUTUSDT",
    "ORDIUSDT",
    "ICPUSDT",
    "UNIUSDT",
    "OPUSDT",
    "ZROUSDT",
    "ENAUSDT",
    "ATOMUSDT",
    "WUSDT",
    "XRPUSDT",
    "TRBUSDT",
    "APTUSDT",
    "TONUSDT",
    "BATUSDT",
    "GOATUSDT",
    "KAVAUSDT",
    "GASUSDT",
    "LTCUSDT",
    "AVAXUSDT",
    "TIAUSDT",
    "BOMEUSDT",
    "PEPEUSDT",
    "TURBOUSDT",
    "WIFUSDT",
    "RENDERUSDT",
    "HBARUSDT",
    "UXLINKUSDT",
    "BRETTUSDT",
    "SANDUSDT",
    "MOVEUSDT",
    "BAKEUSDT",
]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_dir = os.path.join(project_root, "tradehtml", "icons")
    saved, failed = scrape_and_download_icons(DEFAULT_PAIRS, output_dir)
    logging.info("Total saved: %d", len(saved))
    if failed:
        logging.warning("Failed to download for pairs: %s", ", ".join(failed))
    else:
        logging.info("All pairs processed successfully; no failures.")


if __name__ == "__main__":
    main()


