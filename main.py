"""
Books to Scrape - Full Scraper
Phases:
  1. Scrape a single book product page → single_book.csv
  2. Scrape all books in one category  → category_<name>.csv
  3. Scrape every book across all categories → one CSV per category
  4. Download cover images for every book scraped
"""

from csv import DictWriter
import os
import re
import time
import requests
from bs4 import BeautifulSoup

# ── Constants ────────────────────────────────────────────────────────────────
BASE_URL   = "https://books.toscrape.com/"
CAT_URL    = BASE_URL + "catalogue/"
OUTPUT_DIR = "output"
IMG_DIR    = os.path.join(OUTPUT_DIR, "images")
HEADERS    = {"User-Agent": "Mozilla/5.0 (books-scraper/1.0)"}
RATING_MAP = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}
CSV_FIELDS = [
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

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(IMG_DIR, exist_ok=True)


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_soup(url: str) -> BeautifulSoup:
    """Fetch a URL and return a BeautifulSoup object."""
    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def clean_price(raw: str) -> str:
    """Strip currency symbol and whitespace from a price string."""
    return raw.replace("Â", "").replace("£", "").strip()


def parse_quantity(raw: str) -> int:
    """Extract the integer from 'In stock (22 available)'."""
    match = re.search(r"\d+", raw)
    return int(match.group()) if match else 0


def resolve_image_url(img_src: str) -> str:
    """Turn the relative ../../media/cache/... path into an absolute URL."""
    # img_src always starts with ../../
    relative = img_src.replace("../../", "")
    return BASE_URL + relative


def safe_filename(name: str) -> str:
    """Make a string safe to use as a filename."""
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', name.lower())


# ── Phase 1: scrape a single product page ────────────────────────────────────

def scrape_book(url: str) -> dict:
    """
    Visit one book product page and return a dict with all required fields.
    Also downloads the cover image to IMG_DIR.
    """
    soup = get_soup(url)

    # Table rows: UPC, Price (excl. tax), Price (incl. tax), Availability
    table = {
        row.find("th").text.strip(): row.find("td").text.strip()
        for row in soup.select("table.table tr")
    }

    # Description (may be absent on some books)
    desc_tag = soup.select_one("#product_description ~ p")
    description = desc_tag.text.strip() if desc_tag else ""

    # Category: second-to-last breadcrumb item
    breadcrumbs = soup.select("ul.breadcrumb li")
    category = breadcrumbs[-2].text.strip() if len(breadcrumbs) >= 2 else ""

    # Star rating: class list looks like ['star-rating', 'Three']
    rating_classes = soup.select_one("p.star-rating")["class"]
    rating_word = rating_classes[1] if len(rating_classes) > 1 else "Zero"
    review_rating = RATING_MAP.get(rating_word, 0)

    # Absolute image URL
    img_src = soup.select_one("#product_gallery img")["src"]
    image_url = resolve_image_url(img_src)

    # Download image
    download_image(image_url, category)

    return {
        "product_page_url":     url,
        "universal_product_code": table.get("UPC", ""),
        "book_title":           soup.select_one("h1").text.strip(),
        "price_including_tax":  clean_price(table.get("Price (incl. tax)", "")),
        "price_excluding_tax":  clean_price(table.get("Price (excl. tax)", "")),
        "quantity_available":   parse_quantity(table.get("Availability", "")),
        "product_description":  description,
        "category":             category,
        "review_rating":        review_rating,
        "image_url":            image_url,
    }


def download_image(image_url: str, category: str) -> None:
    """Download a cover image and save it under IMG_DIR/<category>/."""
    cat_dir = os.path.join(IMG_DIR, safe_filename(category))
    os.makedirs(cat_dir, exist_ok=True)
    filename = image_url.split("/")[-1]
    filepath = os.path.join(cat_dir, filename)
    if not os.path.exists(filepath):          # skip if already saved
        response = requests.get(image_url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        with open(filepath, "wb") as f:
            f.write(response.content)


# ── Phase 2: scrape all book URLs from one category (with pagination) ─────────

def get_book_urls_from_category(category_url: str) -> list[str]:
    """
    Walk every page of a category listing and return all product-page URLs.
    Handles pagination automatically.
    """
    urls = []
    page_url = category_url

    while page_url:
        soup = get_soup(page_url)

        for article in soup.select("article.product_pod"):
            href = article.select_one("h3 a")["href"]
            # href is relative to the catalogue/ directory
            # e.g. "../../../catalogue/book-title_123/index.html"
            # Strip leading "../" segments and prepend CAT_URL
            clean_href = href.replace("../", "")
            urls.append(CAT_URL + clean_href)

        # Check for a "next" page button
        next_btn = soup.select_one("li.next a")
        if next_btn:
            next_href = next_btn["href"]
            # next_href is relative to the current page directory
            page_dir = page_url.rsplit("/", 1)[0] + "/"
            page_url = page_dir + next_href
        else:
            page_url = None

    return urls


def scrape_category(category_url: str, category_name: str) -> list[dict]:
    """Scrape every book in a category and return a list of book dicts."""
    print(f"  → Collecting book URLs for '{category_name}' ...")
    book_urls = get_book_urls_from_category(category_url)
    print(f"     Found {len(book_urls)} books.")

    books = []
    for i, url in enumerate(book_urls, 1):
        print(f"     Scraping book {i}/{len(book_urls)}: {url.split('/')[-2]}")
        try:
            books.append(scrape_book(url))
            time.sleep(0.2)   # be polite
        except Exception as exc:
            print(f"     WARNING: Failed to scrape {url}: {exc}")

    return books


# ── CSV writer ────────────────────────────────────────────────────────────────

def write_csv(books: list[dict], filepath: str) -> None:
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(books)
    print(f"  ✓ Saved {len(books)} records → {filepath}")


# ── Phase 3: discover all categories ─────────────────────────────────────────

def get_all_categories() -> list[tuple[str, str]]:
    """
    Return a list of (category_name, category_url) tuples for every category
    listed on the Books to Scrape homepage.
    """
    soup = get_soup(BASE_URL)
    categories = []
    for link in soup.select("ul.nav-list ul li a"):
        name = link.text.strip()
        href = link["href"]                   # e.g. "catalogue/travel_2/index.html"
        url  = BASE_URL + href
        categories.append((name, url))
    return categories


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    # ── Phase 1: Single book ─────────────────────────────────────────────────
    print("\n=== Phase 1: Single book ===")
    SINGLE_BOOK_URL = (
        "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"
    )
    book_data = scrape_book(SINGLE_BOOK_URL)
    write_csv([book_data], os.path.join(OUTPUT_DIR, "single_book.csv"))
    print(f"  Title  : {book_data['book_title']}")
    print(f"  UPC    : {book_data['universal_product_code']}")
    print(f"  Price  : £{book_data['price_including_tax']} (incl. tax)")
    print(f"  Rating : {book_data['review_rating']} / 5")
    print(f"  Image  : {book_data['image_url']}")

    # ── Phase 2: One category (Mystery) ──────────────────────────────────────
    print("\n=== Phase 2: One category (Mystery) ===")
    MYSTERY_URL = "https://books.toscrape.com/catalogue/category/books/mystery_3/index.html"
    mystery_books = scrape_category(MYSTERY_URL, "Mystery")
    write_csv(mystery_books, os.path.join(OUTPUT_DIR, "category_mystery.csv"))

    # ── Phase 3+4: All categories → separate CSV + images ────────────────────
    print("\n=== Phase 3+4: All categories ===")
    categories = get_all_categories()
    print(f"  Discovered {len(categories)} categories.\n")

    for cat_name, cat_url in categories:
        print(f"[{cat_name}]")
        books = scrape_category(cat_url, cat_name)
        csv_path = os.path.join(
            OUTPUT_DIR, f"category_{safe_filename(cat_name)}.csv"
        )
        write_csv(books, csv_path)

    print("\n✅ All done!")
    print(f"   CSV files  → {OUTPUT_DIR}/")
    print(f"   Images     → {IMG_DIR}/")
