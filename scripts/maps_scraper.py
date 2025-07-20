# ========================
# maps_scraper.py
# ------------------------
# Scrapes Google Maps for businesses of a given activity that do **not** have a
# "Website" button on their listing. Outputs one JSON object per line to STDOUT.
#
# Usage:
#   python maps_scraper.py "plombier" [--city "Lyon"]
#
# Environment variables required:
#   WEBSHARE_USERNAME / WEBSHARE_PASS  – credentials for the rotating proxy
#   WEBSHARE_HOST      (optional)      – host (default: proxy.webshare.io)
#   WEBSHARE_PORT      (optional)      – port (default: 80)
#
# Notes:
# - Uses Playwright in headless mode with the Webshare rotating proxy.
# - Stops scrolling when no new results have appeared for three consecutive scrolls.
# - Filters out every card containing a "Website" button before yielding.
# - Prints minimal lead information (name, phone, plusCode, mapsUrl, source).
# ========================

import asyncio, json, os, sys, time
from pathlib import Path
from typing import Generator, Dict, Any
from playwright.async_api import async_playwright, Page

SCROLL_PAUSE_SEC = 1.0
MAX_IDLE = 3  # consecutive scrolls without new cards before break


def _proxy_config() -> Dict[str, str]:
    username = os.getenv("WEBSHARE_USERNAME")
    password = os.getenv("WEBSHARE_PASS")
    if not username or not password:
        raise RuntimeError("WEBSHARE credentials missing in env vars")
    host = os.getenv("WEBSHARE_HOST", "proxy.webshare.io")
    port = os.getenv("WEBSHARE_PORT", "80")
    return {
        "server": f"http://{host}:{port}",
        "username": username,
        "password": password,
    }


def _build_query(activity: str, city: str | None) -> str:
    return f"{activity} {city}" if city else activity


async def _scroll_results(page: Page) -> None:
    idle = 0
    last_count = 0
    while True:
        await page.mouse.wheel(0, 4000)
        await page.wait_for_timeout(SCROLL_PAUSE_SEC * 1000)
        cards = await page.query_selector_all("div[role='article']")
        count = len(cards)
        if count == last_count:
            idle += 1
            if idle >= MAX_IDLE:
                break
        else:
            idle = 0
            last_count = count


def _has_website(card_html: str) -> bool:
    return "Website" in card_html or "Site Web" in card_html


async def _extract_cards(page: Page) -> Generator[Dict[str, Any], None, None]:
    cards = await page.query_selector_all("div[role='article']")
    for card in cards:
        html = await card.inner_html()
        if _has_website(html):
            continue
        name = await card.get_attribute("aria-label") or ""
        maps_url = await card.eval_on_selector("a", "e=>e.href")
        plus_code = await card.eval_on_selector("a", "e=>e.getAttribute('data-result-id')")
        yield {
            "name": name.strip(),
            "phone": None,
            "plus_code": plus_code,
            "maps_url": maps_url,
            "source": "google_maps",
        }


async def scrape(activity: str, city: str | None = None):
    query = _build_query(activity, city)
    url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}"

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, proxy=_proxy_config())
        ctx = await browser.new_context()
        page = await ctx.new_page()
        await page.goto(url, timeout=60000)
        await _scroll_results(page)
        async for card in _extract_cards(page):
            print(json.dumps(card, ensure_ascii=False))
        await browser.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("activity", help="Activité à rechercher, ex.: plombier")
    parser.add_argument("--city", help="Ville (facultatif)")
    args = parser.parse_args()

    asyncio.run(scrape(args.activity, args.city))
