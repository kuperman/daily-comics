import html
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# Add or remove comics here. Selectors may need updates as sites change.
COMICS = [
    ("Questionable Content", "https://www.questionablecontent.net/",
     "img#strip"),
    ("SMBC", "https://www.smbc-comics.com/",
     "img#cc-comic"),
    ("XKCD", "https://xkcd.com/",
     "#comic img"),
	("Joy of Tech", "https://www.joyoftech.com/joyoftech/",
     "img[src*='joyimages/'][src$='.png']:not([src*='thumb']):not([src*='/JoTnav/']):not([src*='/joystuff/'])"),
	("Penny Arcade", "https://www.penny-arcade.com/comic",
	"meta[property='og:image']"),
    ("Buttersafe", "https://buttersafe.com/",
     "#comic img"),
]

OUTPUT = Path("public")
CACHE = Path("comic-cache.json")
session = requests.Session()
session.headers["User-Agent"] = "PersonalComicsReader/1.0"


def web_url(base, value):
    result = urljoin(base, value)
    if urlparse(result).scheme not in ("http", "https"):
        raise ValueError("Unsupported image URL")
    return result


def fetch_comic(name, url, selector):
    if name == "XKCD":
        response = session.get(
            "https://xkcd.com/info.0.json", timeout=30
        )
        response.raise_for_status()
        data = response.json()
        return {
            "image": web_url(url, data["img"]),
            "alt": data.get("alt", ""),
            "link": f"https://xkcd.com/{data['num']}/",
        }

    response = session.get(url, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    image = soup.select_one(selector)
    if image is None:
        raise ValueError("Comic image not found")

    # source = image.get("data-src") or image.get("src")
    if image.name == "meta":
        source = image.get("content")
    else:
        source = image.get("data-src") or image.get("src")
    if not source:
        raise ValueError("Image URL not found")

    return {
        "image": web_url(response.url, source),
        "alt": image.get("alt", ""),
        "link": response.url,
    }


def main():
    OUTPUT.mkdir(exist_ok=True)
    try:
        cache = json.loads(CACHE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        cache = {}

    cards = []
    escape = html.escape

    for name, url, selector in COMICS:
        notice = ""
        try:
            comic = fetch_comic(name, url, selector)
            comic["retrieved"] = datetime.now(timezone.utc).isoformat()
            cache[name] = comic
        except Exception as error:
            print(f"{name}: {error}")
            comic = cache.get(name)
            if comic:
                notice = (
                    "Latest check failed; showing the image last retrieved "
                    + comic["retrieved"][:10] + "."
                )
            else:
                notice = "Image unavailable. Open the original site to read."

        link = comic["link"] if comic else url
        picture = ""
        if comic:
            picture = (
                f'<a href="{escape(link, quote=True)}">'
                f'<img src="{escape(comic["image"], quote=True)}" '
                f'alt="{escape(comic["alt"], quote=True)}" '
                'loading="lazy"></a>'
            )

        cards.append(
            f'<article><h2><a href="{escape(link, quote=True)}">'
            f'{escape(name)}</a></h2>{picture}'
            f'<p class="notice">{escape(notice)}</p>'
            f'<a href="{escape(url, quote=True)}">Visit original site ↗</a>'
            '</article>'
        )

    updated = datetime.now(timezone.utc).strftime("%B %d, %Y · %H:%M UTC")
    page = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Daily Comics</title>
<style>
body { margin:0; background:#f5f1e8; color:#26231e; font-family:Georgia,serif }
main { max-width:1100px; margin:auto; padding:24px }
header { text-align:center; border-bottom:4px double; margin-bottom:28px }
h1 { font-size:clamp(2.5rem,7vw,4.5rem); margin:18px 0 }
article { padding:20px 0 30px; border-bottom:1px solid #aaa }
h2 { font-size:1.6rem }
a { color:inherit }
img { display:block; max-width:100%; height:auto; margin:16px auto }
.notice, header p { color:#655f55; font:14px/1.5 system-ui,sans-serif }
</style>
</head>
<body><main>
<header><h1>The Daily Comics</h1><p>Updated: UPDATED</p></header>
CARDS
</main></body></html>"""
    page = page.replace("UPDATED", escape(updated))
    page = page.replace("CARDS", "\n".join(cards))
    (OUTPUT / "index.html").write_text(page, encoding="utf-8")
    CACHE.write_text(json.dumps(cache, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
