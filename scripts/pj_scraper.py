# -----------------------------------------------------------------------------
# pj_scraper.py
# -----------------------------------------------------------------------------
"""Scrapes PagesJaunes.fr search results for professionals **without** a website.
Outputs one JSON object per line with (name, phone, address, pj_url, source).
"""

import json, os, re, sys, asyncio
from typing import Dict, Any, Generator
from playwright.async_api import async_playwright, Page

BASE_URL = "https://www.pagesjaunes.fr/search/"  # ?quoiqui=...&ou=...


def _proxy_config():
    username = os.getenv("WEBSHARE_USERNAME")
    password = os.getenv("WEBSHARE_PASS")
    host = os.getenv("WEBSHARE_HOST", "proxy.webshare.io")
    port = os.getenv("WEBSHARE_PORT", "80")
    return {
        "server": f"http://{host}:{port}",
        "username": username,
        "password": password,
    }


async def _get_cards(page: Page) -> Generator[Dict[str, Any], None, None]:
    items = await page.query_selector_all("article.bi-listing")
    for item in items:
        # skip if website link exists
        has_web = await item.query_selector("a[href*='http'][target='_blank']")
        if has_web:
            continue
        name = await item.eval_on_selector("h3", "e=>e.textContent")
        phone = await item.eval_on_selector("a.num-tel", "e=>e.textContent")
        addr = await item.eval_on_selector("a.adresse", "e=>e.textContent")
        link = await item.eval_on_selector("a.denomination-links", "e=>e.href")
        yield {
            "name": name.strip() if name else "",
            "phone": re.sub(r"\s+", "", phone) if phone else None,
            "address": addr.strip() if addr else None,
            "pj_url": link,
            "source": "pagesjaunes",
        }


async def scrape(activity: str, city: str | None = None):
    query = f"quoiqui={activity.replace(' ', '+')}"
    if city:
        query += f"&ou={city.replace(' ', '+')}"
    url = f"{BASE_URL}?{query}"

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, proxy=_proxy_config())
        ctx = await browser.new_context()
        page = await ctx.new_page()
        await page.goto(url, timeout=60000)
        await page.wait_for_selector("article.bi-listing")
        async for card in _get_cards(page):
            print(json.dumps(card, ensure_ascii=False))
        await browser.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("activity")
    parser.add_argument("--city")
    args = parser.parse_args()

    asyncio.run(scrape(args.activity, args.city))
