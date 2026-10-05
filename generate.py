import html
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# Add or remove comics here. Selectors may need updates as sites change.
COMICS = [
    ("Questionable Content", "https://www.questionablecontent.net/",
     "img#strip"),
    ("Girls with Slingshots", "https://www.girlswithslingshots.com/",
     "img#cc-comic"),
    ("SMBC", "https://www.smbc-comics.com/",
     "img#cc-comic"),
    ("SMBC Bonus", "https://www.smbc-comics.com/",
     "#aftercomic img, #mobaftercomic img"),
    ("XKCD", "https://xkcd.com/",
     "#comic img"),
	("Joy of Tech", "https://www.joyoftech.com/joyoftech/",
     "img[src*='joyimages/'][src$='.png']:not([src*='thumb']):not([src*='/JoTnav/']):not([src*='/joystuff/'])"),
	("Penny Arcade", "https://www.penny-arcade.com/comic",
	"meta[property='og:image']"),
    ("Buttersafe", "https://buttersafe.com/",
     "#comic img"),
    ("Dumbing of Age", "https://www.dumbingofage.com/",
     "#comic img[title]"),
    ("Something Positive", "https://somethingpositive.net/",
     "article .post-thumbnail img"),
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
            "title": data.get("title", ""),
            "caption": data.get("alt", ""),
            "link": f"https://xkcd.com/{data['num']}/",
        }

    response = session.get(url, timeout=30)
    if name == "Dumbing of Age" and response.status_code == 426:
        # This host requires a protocol upgrade that requests cannot negotiate.
        result = subprocess.run(
            ["curl", "--fail", "--silent", "--show-error", "--location",
             "--max-time", "30", url],
            capture_output=True, text=True, timeout=35, check=True,
        )
        markup = result.stdout
    else:
        response.raise_for_status()
        markup = response.text
    soup = BeautifulSoup(markup, "html.parser")
    image = soup.select_one(selector)
    if image is None:
        raise ValueError("Comic image not found")

    if image.name == "meta":
        source = image.get("content")
    else:
        source = image.get("data-src") or image.get("src")
    if not source:
        raise ValueError("Image URL not found")

    comic = {
        "image": web_url(response.url, source),
        "alt": image.get("alt", ""),
        "caption": image.get("title", ""),
        "link": response.url,
    }
    if name == "Questionable Content":
        newspost = soup.select_one("#newspost")
        if newspost:
            comic["caption"] = newspost.get_text(" ", strip=True)
    elif name in ("SMBC", "SMBC Bonus", "Girls with Slingshots"):
        heading = soup.select_one(".cc-newsheader a")
        if heading:
            comic["title"] = heading.get_text(" ", strip=True)
            comic["link"] = web_url(response.url, heading["href"])
    elif name in ("Dumbing of Age", "Something Positive"):
        article = image.find_parent("article")
        heading = (article or soup).select_one(".entry-title a")
        if heading:
            comic["title"] = heading.get_text(" ", strip=True)
            comic["link"] = web_url(response.url, heading["href"])
    return comic


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
        details = ""
        if comic:
            if comic.get("title"):
                details += f'<h3>{escape(comic["title"])}</h3>'
            picture = (
                f'<a href="{escape(link, quote=True)}" target="_blank" rel="noopener noreferrer">'
                f'<img src="{escape(comic["image"], quote=True)}" '
                f'alt="{escape(comic["alt"], quote=True)}" '
                f'title="{escape(comic.get("caption", ""), quote=True)}" '
                'loading="lazy"></a>'
            )
            if comic.get("caption"):
                picture += f'<p class="caption">{escape(comic["caption"])}</p>'

        cards.append(
            f'<article><h2><a href="{escape(link, quote=True)}" target="_blank" rel="noopener noreferrer">'
            f'{escape(name)}</a></h2>{details}{picture}'
            f'<p class="notice">{escape(notice)}</p>'
            f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">Visit original site ↗</a>'
            '</article>'
        )

    updated = datetime.now(timezone.utc).strftime("%B %d, %Y · %H:%M UTC")
    page = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Daily Comics</title>
<style>
body { margin:0; background:#f5f1e8; color:#26231e; font-family:Georgia,serif }
main { max-width:1100px; margin:auto; padding:24px }
header { text-align:center; border-bottom:4px double; margin-bottom:28px }
h1 { font-size:clamp(2.5rem,7vw,4.5rem); margin:18px 0 }
article { padding:20px 0 30px; border-bottom:1px solid #aaa }
h2 { font-size:1.6rem }
h3 { font-size:1.2rem; font-weight:normal }
.caption { white-space:pre-line; font:16px/1.5 system-ui,sans-serif }
a { color:inherit }
img { display:block; max-width:100%; height:auto; margin:16px auto }
.notice, header p { color:#655f55; font:14px/1.5 system-ui,sans-serif }
</style>
</head>
<body><main>
<header><h1>Daily Comics</h1><p>Updated: UPDATED</p></header>
CARDS
</main></body></html>"""
    page = page.replace("UPDATED", escape(updated))
    page = page.replace("CARDS", "\n".join(cards))
    (OUTPUT / "index.html").write_text(page, encoding="utf-8")
    CACHE.write_text(json.dumps(cache, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
