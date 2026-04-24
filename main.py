
# Press ⌃R to execute it or replace it with your code.
# Press Double ⇧ to search everywhere for classes, files, tool windows, actions, and settings.


"""
Scrapes a single book page from Books to Scrape (https://books.toscrape.com)
and writes the extracted data to a CSV file.
"""

"""
Books to Scrape – Category Scraper
===================================
Scrapes every book in a chosen category (handling pagination automatically)
and writes all product data to a single CSV file.

Usage:
    python scrape_category.py

Configuration:
    Change CATEGORY_URL and OUTPUT_CSV near the top of the file to target a
    different category or output path.
"""

import csv
import time
import urllib.parse
import requests
from bs4 import BeautifulSoup

# ── Configuration ─────────────────────────────────────────────────────────────
BASE_URL     = "https://books.toscrape.com/"
CATEGORY_URL = "https://books.toscrape.com/catalogue/category/books/mystery_3/index.html"
OUTPUT_CSV   = "mystery_books.csv"
DELAY        = 0.5   # polite delay (seconds) between requests

RATING_MAP   = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}

CSV_FIELDS   = [
    "product_page_url",
    "universal_product_code",
    "book_title",
    "price_including_tax",
    "price_excluding_tax",
    "quantity_available",
    "product_description",
    "category",
    "review_rating",
    "image_url",
]

# ── HTTP helper ───────────────────────────────────────────────────────────────

def get_soup(url: str) -> BeautifulSoup:
    """Fetch *url* and return a parsed BeautifulSoup object."""
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    response.encoding = "utf-8"
    return BeautifulSoup(response.text, "html.parser")


# ── Phase 2 – Category crawler (with pagination) ──────────────────────────────

def get_book_urls_from_category(category_url: str) -> list[str]:
    """
    Walk every page of *category_url* and return a list of absolute
    product-page URLs for every book found.

    Pagination is detected via the ``<li class="next">`` element; the loop
    stops when that element is absent (i.e. we're on the last page).
    """
    book_urls: list[str] = []
    page_url  = category_url
    page_num  = 1

    while page_url:
        print(f"  Crawling category page {page_num}: {page_url}")
        soup = get_soup(page_url)

        # Every book card has an <h3><a href="..."> with a relative path like
        # "../../../a-light-in-the-attic_1000/index.html"
        for anchor in soup.select("article.product_pod h3 a"):
            relative_href = anchor["href"]           # e.g. "../../some-book_123/index.html"
            # Resolve relative to the *current page URL* so pagination works correctly
            absolute_url  = urllib.parse.urljoin(page_url, relative_href)
            book_urls.append(absolute_url)

        # Check for a "next" button
        next_btn = soup.select_one("li.next a")
        if next_btn:
            # href is relative to the current page (e.g. "page-2.html")
            page_url = urllib.parse.urljoin(page_url, next_btn["href"])
            page_num += 1
            time.sleep(DELAY)
        else:
            page_url = None     # no more pages – exit the loop

    print(f"  Found {len(book_urls)} books across {page_num} page(s).\n")
    return book_urls


# ── Phase 1 – Individual book scraper ─────────────────────────────────────────

def scrape_book(url: str) -> dict:
    """
    Visit a single book product page and return a dict with all required fields.
    """
    soup = get_soup(url)

    # Title
    book_title = soup.find("h1").get_text(strip=True)

    # Product information table (UPC, prices, availability)
    table_rows = soup.select("table.table-striped tr")
    table_data = {
        row.find("th").get_text(strip=True): row.find("td").get_text(strip=True)
        for row in table_rows
    }

    upc            = table_data.get("UPC", "")
    price_excl_tax = table_data.get("Price (excl. tax)", "")
    price_incl_tax = table_data.get("Price (incl. tax)", "")
    availability_raw = table_data.get("Availability", "")

    # Parse integer from "In stock (22 available)"
    if "(" in availability_raw:
        quantity_available = availability_raw.split("(")[1].split(" ")[0]
    else:
        quantity_available = "0"

    # Description (the <p> sibling that immediately follows #product_description)
    desc_tag = soup.select_one("#product_description ~ p")
    product_description = desc_tag.get_text(strip=True) if desc_tag else ""

    # Category – second-to-last breadcrumb: Home > Category > Book title
    breadcrumbs = soup.select("ul.breadcrumb li")
    category = breadcrumbs[-2].get_text(strip=True) if len(breadcrumbs) >= 3 else ""

    # Star rating – CSS class on <p class="star-rating Three">
    rating_tag    = soup.select_one("p.star-rating")
    rating_word   = rating_tag["class"][1] if rating_tag else "Zero"
    review_rating = RATING_MAP.get(rating_word, 0)

    # Thumbnail image – resolve relative src to absolute URL
    img_tag = soup.select_one("#product_gallery img")
    img_src = img_tag["src"] if img_tag else ""
    if img_src.startswith("../"):
        image_url = BASE_URL + img_src.replace("../../", "")
    else:
        image_url = img_src

    return {
        "product_page_url":       url,
        "universal_product_code": upc,
        "book_title":             book_title,
        "price_including_tax":    price_incl_tax,
        "price_excluding_tax":    price_excl_tax,
        "quantity_available":     quantity_available,
        "product_description":    product_description,
        "category":               category,
        "review_rating":          review_rating,
        "image_url":              image_url,
    }


# ── CSV writer ────────────────────────────────────────────────────────────────

def write_csv(records: list[dict], filepath: str) -> None:
    """Write *records* to a CSV file at *filepath*."""
    with open(filepath, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(records)
    print(f"\nSaved {len(records)} records → {filepath}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"Category : {CATEGORY_URL}")
    print(f"Output   : {OUTPUT_CSV}\n")

    # Step 1 – collect every book URL in the category (all pages)
    print("Step 1 – Collecting book URLs …")
    book_urls = get_book_urls_from_category(CATEGORY_URL)

    # Step 2 – scrape each product page
    print("Step 2 – Scraping individual book pages …")
    records: list[dict] = []
    for idx, url in enumerate(book_urls, start=1):
        print(f"  [{idx:>3}/{len(book_urls)}] {url.split('/')[-2]}")
        try:
            records.append(scrape_book(url))
        except Exception as exc:
            print(f"         ERROR: {exc} – skipping")
        time.sleep(DELAY)

    # Step 3 – write results to CSV
    print("\nStep 3 – Writing CSV …")
    write_csv(records, OUTPUT_CSV)
    print("Done.")


if __name__ == "__main__":
    main()
