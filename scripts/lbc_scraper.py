# -----------------------------------------------------------------------------
# lbc_scraper.py
# -----------------------------------------------------------------------------
"""Scrapes professional ads on LeBonCoin that lack the "website" field.
Outputs one JSON object per line (title, phone, lbc_id, url, source).
Requires the undocumented LeBonCoin JSON API accessible from the listing pages.
"""

import asyncio, json, os, re, sys
from typing import Dict, Any, Generator
from urllib.parse import urlencode
from playwright.async_api import async_playwright

API_BASE = "https://api.leboncoin.fr/api/utils/search"
CATEGORY_PRO = "services"  # adapt if necessary


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


async def _query_api(activity: str, city: str | None = None, limit: int = 200):
    params = {
        "filters": {
            "category": CATEGORY_PRO,
            "keywords": {"text": activity},
            "owner_type": "pro",
        },
        "limit": limit,
    }
    if city:
        params["filters"]["location_zipcodes"] = [city]

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, proxy=_proxy_config())
        page = await browser.new_page()
        # We cannot call API directly due to CORS/proxy; use page.evaluate fetch
        js = f"""
        fetch('{API_BASE}', {{
            method: 'POST',
            headers: {{'Content-Type':'application/json'}},
            body: JSON.stringify({json.dumps(params)})
        }}).then(r=>r.json())
        """
        data = await page.evaluate(js)
        await browser.close()
    return data


def _extract_leads(data: Dict[str, Any]):
    for ad in data.get("ads", []):
        if ad.get("website"):
            continue
        yield {
            "title": ad.get("title"),
            "phone": ad.get("attributes", {}).get("phone"),
            "lbc_id": ad.get("id"),
            "url": ad.get("url"),
            "source": "leboncoin",
        }


async def scrape(activity: str, city: str | None = None):
    data = await _query_api(activity, city)
    for lead in _extract_leads(data):
        print(json.dumps(lead, ensure_ascii=False))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("activity")
    parser.add_argument("--city")
    args = parser.parse_args()

    asyncio.run(scrape(args.activity, args.city))
