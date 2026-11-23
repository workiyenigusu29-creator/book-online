import os
import sqlite3
from flask import Flask, g, redirect, render_template_string, request, session, url_for
import fitz  # PyMuPDF

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-this-to-a-strong-random-secret")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "bookstore.db")

BOOKS = {
    "book_1": {
        "title": "ሀገር በቀል እፅዋትና የህክምና ጥቅማቸው",
        "price_etb": 100,
        "file": os.path.join(BASE_DIR, "medcine book.pdf"),
    },
    "book_2": {
        "title": "የትምህርት ሙያዊ ብቃትና ተግባራዊ አፈጻጸም",
        "price_etb": 150,
        "file": os.path.join(BASE_DIR, "የትምህርት ሙያዊ ብቃት.pdf"),
    },
    "book_3": {
        "title": "Professional competence and practical performance in education",
        "price_etb": 150,
        "file": os.path.join(BASE_DIR, "Educational competency.pdf"),
    },
    "book_4": {
        "title": "የመሪነት ጥበብ",
        "price_etb": 200,
        "file": os.path.join(BASE_DIR, "የመሪነት ጥበብ.pdf"),
    },
    "book_5": {
        "title": "የስኬት ምስጢር",
        "price_etb": 200,
        "file": os.path.join(BASE_DIR, "የስኬት ምስጢር.pdf"),
    },
    "book_6": {
        "title": "የሲቭል ሰርቭስ የብቃት ምዘና ጥያቄዎች 457 በላይ",
        "price_etb": 200,
        "file": os.path.join(BASE_DIR, "civil service exam.pdf"),
    },
}

PAGE_TEXT_CACHE = {}


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_key TEXT NOT NULL,
            book_id TEXT NOT NULL,
            tx_ref TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_key, book_id)
        )
        """
    )
    conn.commit()
    conn.close()


def get_user_key() -> str:
    if "user_key" not in session:
        session["user_key"] = os.urandom(12).hex()
    return session["user_key"]


def get_user_searches(book_id: str) -> list[str]:
    all_searches = session.get("user_searches", {})
    return all_searches.get(book_id, [])


def add_user_search(book_id: str, term: str):
    term = term.strip().lower()
    if not term:
        return
    all_searches = session.get("user_searches", {})
    book_list = all_searches.get(book_id, [])
    if term not in book_list:
        book_list.append(term)
    all_searches[book_id] = book_list
    session["user_searches"] = all_searches
    session.modified = True


def has_purchased(user_key: str, book_id: str) -> bool:
    row = (
        get_db()
        .execute(
            "SELECT 1 FROM purchases WHERE user_key = ? AND book_id = ?",
            (user_key, book_id),
        )
        .fetchone()
    )
    return row is not None


def get_pages_text(book_id: str) -> list[str]:
    if book_id in PAGE_TEXT_CACHE:
        return PAGE_TEXT_CACHE[book_id]
    book = BOOKS.get(book_id)
    if not book or not os.path.exists(book["file"]):
        return []
    doc = fitz.open(book["file"])
    pages = [p.get_text("text") or "" for p in doc]
    doc.close()
    PAGE_TEXT_CACHE[book_id] = pages
    return pages


def page_matches_user_searches(page_text: str, terms: list[str]) -> list[str]:
    low = page_text.lower()
    return [t for t in terms if t in low]


def is_bot_or_crawler(user_agent: str) -> bool:
    ua = (user_agent or "").lower()
    return any(
        bot_name in ua
        for bot_name in ("googlebot", "bingbot", "yandex", "duckduckbot", "crawler", "spider")
    )


INDEX_TEMPLATE = """
<!doctype html>
<html lang="am">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>የመጻሕፍት መደብር — ፍለጋ እና ንባብ</title>
  <meta name="description" content="በመጻሕፍት ውስጥ ይፈልጉ፣ በፍለጋ የሚዛመዱ ገጾችን ይክፈቱ እና ሙሉ መጽሐፍ ይግዙ።" />
</head>
<body>
  <h1>የመጻሕፍት መደብር</h1>
  <ul>
    {% for bid, b in books.items() %}
      <li>
        <a href="{{ url_for('book_page', book_id=bid, page_num=1) }}">{{ b.title }}</a>
        — {{ b.price_etb }} ብር
      </li>
    {% endfor %}
  </ul>
</body>
</html>
"""

PAGE_TEMPLATE = """
<!doctype html>
<html lang="am">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{{ book.title }} — ገጽ {{ page_num }}</title>
  <meta name="description" content="{{ meta_description }}" />
  <style>
    body { font-family: Arial, sans-serif; max-width: 900px; margin: 24px auto; padding: 0 16px; }
    .box { border: 1px solid #ddd; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
    .locked { background: #f8f8f8; color: #555; }
    button { padding: 8px 14px; cursor: pointer; }
  </style>
</head>
<body>
  <p><a href="{{ url_for('home') }}">← ወደ መጻሕፍት ዝርዝር</a></p>
  <h1>{{ book.title }} ({{ book.price_etb }} ብር)</h1>
  <h2>ገጽ {{ page_num }} ከ {{ total_pages }}</h2>

  <div class="box">
    <h3>በግል ፍለጋ የሚዛመዱ ገጾችን ይክፈቱ</h3>
    <form method="get" action="{{ url_for('search_book', book_id=book_id) }}">
      <input type="text" name="q" value="{{ query }}" placeholder="የሚፈልጉትን ቃል ያስገቡ..." required />
      <button type="submit">ፈልግ እና የሚዛመዱትን ክፈት</button>
    </form>

    {% if user_searches %}
      <p><strong>የፈለጉት ቃላት፡</strong> {{ user_searches | join(", ") }}</p>
    {% endif %}

    {% if matches is not none %}
      <h4>የተገኙ ገጾች ({{ matches | length }})፡</h4>
      {% if matches %}
        <ul>
          {% for m in matches %}
            <li>
              <a href="{{ url_for('book_page', book_id=book_id, page_num=m.page) }}">ገጽ {{ m.page }}</a>:
              ...{{ m.snippet }}...
            </li>
          {% endfor %}
        </ul>
      {% else %}
        <p>"{{ query }}" የሚል ቃል በየትኛውም ገጽ አልተገኘም።</p>
      {% endif %}
    {% endif %}
  </div>

  <div class="box">
    {% if page_num > 1 %}
      <a href="{{ url_for('book_page', book_id=book_id, page_num=page_num - 1) }}">← ቀዳሚ ገጽ</a>
    {% endif %}
    {% if page_num < total_pages %}
      <a href="{{ url_for('book_page', book_id=book_id, page_num=page_num + 1) }}" style="margin-left: 12px;">ቀጣይ ገጽ →</a>
    {% endif %}
  </div>

  {% if allowed %}
    <div class="box">
      {% if matched_terms %}
        <p><strong>በፍለጋዎ የተከፈተ ገጽ (ቃላት)፡</strong> {{ matched_terms | join(", ") }}</p>
      {% elif has_paid %}
        <p><strong>ሁኔታ፡</strong> ሙሉ መጽሐፉ ተገዝቷል</p>
      {% elif crawler_view %}
        <p><strong>ሁኔታ፡</strong> ለSearch Engine የተዘጋጀ ገጽ</p>
      {% endif %}
      <pre style="white-space: pre-wrap; font-family: inherit;">{{ page_text }}</pre>
    </div>
  {% else %}
    <div class="box locked">
      <h3>ገጽ {{ page_num }} ተቆልፏል</h3>
      <p>ይህ ገጽ በግል ፍለጋዎ ውስጥ አልተገኘም ወይም መጽሐፉን ገና አልገዙም።</p>
      <form method="post" action="{{ url_for('unlock_book', book_id=book_id, page_num=page_num) }}">
        <button type="submit">ሙሉ መጽሐፉን ይግዙ ({{ book.price_etb }} ብር)</button>
      </form>
    </div>
  {% endif %}
</body>
</html>
"""


@app.route("/")
def home():
    get_user_key()
    return render_template_string(INDEX_TEMPLATE, books=BOOKS)


@app.route("/book/<book_id>/page/<int:page_num>")
def book_page(book_id: str, page_num: int):
    book = BOOKS.get(book_id)
    pages = get_pages_text(book_id)
    if not book or not pages or page_num < 1 or page_num > len(pages):
        return "ገጹ አልተገኘም", 404

    user_key = get_user_key()
    paid = has_purchased(user_key, book_id)
    searches = get_user_searches(book_id)
    page_text = pages[page_num - 1]
    matched_terms = page_matches_user_searches(page_text, searches)
    crawler = is_bot_or_crawler(request.headers.get("User-Agent", ""))

    allowed = paid or bool(matched_terms) or crawler

    snippet_source = " ".join(page_text.split())
    meta_desc = (snippet_source[:155] + "...") if len(snippet_source) > 155 else snippet_source

    return render_template_string(
        PAGE_TEMPLATE,
        book_id=book_id,
        book=book,
        page_num=page_num,
        total_pages=len(pages),
        page_text=page_text if allowed else "",
        allowed=allowed,
        has_paid=paid,
        matched_terms=matched_terms,
        crawler_view=crawler,
        user_searches=searches,
        matches=None,
        query="",
        meta_description=meta_desc or f"{book['title']} - ገጽ {page_num}",
    )


@app.route("/book/<book_id>/search")
def search_book(book_id: str):
    book = BOOKS.get(book_id)
    pages = get_pages_text(book_id)
    if not book or not pages:
        return "መጽሐፉ አልተገኘም", 404

    q = (request.args.get("q") or "").strip()
    if q:
        add_user_search(book_id, q)

    user_key = get_user_key()
    paid = has_purchased(user_key, book_id)
    searches = get_user_searches(book_id)

    matches = []
    q_low = q.lower()
    if q_low:
        for idx, text in enumerate(pages, start=1):
            pos = text.lower().find(q_low)
            if pos != -1:
                start = max(0, pos - 60)
                end = min(len(text), pos + len(q_low) + 60)
                snippet = " ".join(text[start:end].split())
                matches.append({"page": idx, "snippet": snippet})

    first_page_text = pages[0]
    first_matched = page_matches_user_searches(first_page_text, searches)
    crawler = is_bot_or_crawler(request.headers.get("User-Agent", ""))
    allowed = paid or bool(first_matched) or crawler
    snippet_source = " ".join(first_page_text.split())
    meta_desc = (snippet_source[:155] + "...") if len(snippet_source) > 155 else snippet_source

    return render_template_string(
        PAGE_TEMPLATE,
        book_id=book_id,
        book=book,
        page_num=1,
        total_pages=len(pages),
        page_text=first_page_text if allowed else "",
        allowed=allowed,
        has_paid=paid,
        matched_terms=first_matched,
        crawler_view=crawler,
        user_searches=searches,
        matches=matches,
        query=q,
        meta_description=meta_desc or book["title"],
    )


@app.route("/book/<book_id>/unlock", methods=["POST"])
def unlock_book(book_id: str):
    if book_id not in BOOKS:
        return "መጽሐፉ አልተገኘም", 404

    page_num = int(request.args.get("page_num", "1"))
    user_key = get_user_key()
    tx_ref = f"WEB-{os.urandom(4).hex().upper()}"

    db = get_db()
    db.execute(
        "INSERT OR IGNORE INTO purchases (user_key, book_id, tx_ref) VALUES (?, ?, ?)",
        (user_key, book_id, tx_ref),
    )
    db.commit()
    return redirect(url_for("book_page", book_id=book_id, page_num=page_num))


@app.route("/robots.txt")
def robots_txt():
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /book/*/unlock",
    ]
    return "\n".join(lines), 200, {"Content-Type": "text/plain; charset=utf-8"}


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
