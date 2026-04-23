
# Press ⌃R to execute it or replace it with your code.
# Press Double ⇧ to search everywhere for classes, files, tool windows, actions, and settings.


"""
Scrapes a single book page from Books to Scrape (https://books.toscrape.com)
and writes the extracted data to a CSV file.
"""

import csv
import requests
from bs4 import BeautifulSoup

# ── Configuration ────────────────────────────────────────────────────────────
BASE_URL = "https://books.toscrape.com/"
BOOK_URL = "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"
OUTPUT_CSV = "book_data.csv"

# Maps written-out rating words to digits
RATING_MAP = {
    "One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_soup(url: str) -> BeautifulSoup:
    """Fetch a URL and return a BeautifulSoup object."""
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    response.encoding = "utf-8"          # site serves UTF-8; ensure correct decode
    return BeautifulSoup(response.text, "html.parser")


def extract_book_data(url: str) -> dict:
    """Visit a single book page and extract the required fields."""
    soup = get_soup(url)

    # ── Title ────────────────────────────────────────────────────────────────
    book_title = soup.find("h1").get_text(strip=True)

    # ── Product information table ─────────────────────────────────────────────
    table_rows = soup.select("table.table-striped tr")
    table_data = {
        row.find("th").get_text(strip=True): row.find("td").get_text(strip=True)
        for row in table_rows
    }

    upc                 = table_data.get("UPC", "")
    price_excl_tax      = table_data.get("Price (excl. tax)", "")
    price_incl_tax      = table_data.get("Price (incl. tax)", "")
    availability_raw    = table_data.get("Availability", "")

    # Extract the number from e.g. "In stock (22 available)"
    quantity_available = ""
    if "(" in availability_raw:
        quantity_available = availability_raw.split("(")[1].split(" ")[0]

    # ── Description ───────────────────────────────────────────────────────────
    desc_tag = soup.select_one("#product_description ~ p")
    product_description = desc_tag.get_text(strip=True) if desc_tag else ""

    # ── Category ──────────────────────────────────────────────────────────────
    breadcrumbs = soup.select("ul.breadcrumb li")
    # Breadcrumb order: Home > Category > Book title
    category = breadcrumbs[-2].get_text(strip=True) if len(breadcrumbs) >= 3 else ""

    # ── Star rating ───────────────────────────────────────────────────────────
    rating_tag = soup.select_one("p.star-rating")
    rating_word = rating_tag["class"][1] if rating_tag else "Zero"
    review_rating = RATING_MAP.get(rating_word, 0)

    # ── Image URL ─────────────────────────────────────────────────────────────
    img_tag = soup.select_one("#product_gallery img")
    img_src = img_tag["src"] if img_tag else ""
    # src looks like "../../media/cache/.../cover.jpg" – make it absolute
    image_url = BASE_URL + img_src.replace("../../", "") if img_src.startswith("../") else img_src

    return {
        "product_page_url":     url,
        "universal_product_code": upc,
        "book_title":           book_title,
        "price_including_tax":  price_incl_tax,
        "price_excluding_tax":  price_excl_tax,
        "quantity_available":   quantity_available,
        "product_description":  product_description,
        "category":             category,
        "review_rating":        review_rating,
        "image_url":            image_url,
    }


def write_to_csv(data: dict, filepath: str) -> None:
    """Write a single book record to a CSV file."""
    fieldnames = [
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
    with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(data)
    print(f"Data written to: {filepath}")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Scraping: {BOOK_URL}")
    book_data = extract_book_data(BOOK_URL)

    print("\nExtracted data:")
    for key, value in book_data.items():
        display_val = (value[:80] + "...") if isinstance(value, str) and len(value) > 80 else value
        print(f"  {key}: {display_val}")

    write_to_csv(book_data, OUTPUT_CSV)



# Press the green button in the gutter to run the script.


# See PyCharm help at https://www.jetbrains.com/help/pycharm/
