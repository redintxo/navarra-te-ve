from flask import Flask, redirect, url_for
import sqlite3, hashlib, feedparser
from datetime import datetime

app = Flask(__name__)
DB = "navarra_te_ve.db"

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init():
    c = db()
    c.execute("""CREATE TABLE IF NOT EXISTS items(
        id INTEGER PRIMARY KEY,
        source TEXT, locality TEXT, title TEXT, url TEXT UNIQUE,
        summary TEXT, category TEXT, priority TEXT,
        published_at TEXT, status TEXT DEFAULT 'pending',
        fingerprint TEXT, created_at TEXT)""")
    c.commit()
    c.close()

def classify(title):
    t = title.lower()
    if any(x in t for x in ["incendio", "accidente", "policía", "emergencia"]):
        return "Sucesos", "alta"
    if any(x in t for x in ["ayuntamiento", "pleno", "obras", "urbanismo"]):
        return "Municipios", "media"
    return "Navarra", "normal"

@app.route("/")
def index():
    c = db()
    items = c.execute(
        "SELECT * FROM items WHERE status='pending' ORDER BY id DESC"
    ).fetchall()
    c.close()

    html = """<!doctype html><html lang="es"><head>
    <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Navarra Te Ve</title>
    <style>
    body{font-family:Arial;margin:0;background:#f4f5f8;color:#182033}
    header{background:linear-gradient(110deg,#6338b7,#3e69c7,#25aeb3);color:white;padding:25px}
    main{max-width:1100px;margin:auto;padding:25px}
    .btn{padding:12px 16px;border:0;border-radius:7px;background:#6338b7;color:white;font-weight:bold}
    article{background:white;padding:18px;margin:12px 0;border-radius:10px}
    .src{color:#6338b7;font-size:12px;font-weight:bold}
    .title{font-size:18px;font-weight:bold;margin:7px 0}
    </style></head><body>
    <header><b>📱 NAVARRA TE VE</b><br>Motor editorial</header>
    <main>
    <form method="post" action="/collect">
    <button class="btn">🤖 BUSCAR NOVEDADES DE TUDELA</button>
    </form>
    <h2>Pendientes: %d</h2>""" % len(items)

    for x in items:
        html += '<article><div class="src">%s · %s</div>' % (x["source"], x["locality"])
        html += '<div class="title">%s</div>' % x["title"]
        html += '<small>%s · %s · prioridad %s · <a href="%s">fuente</a></small>' % (
            x["published_at"], x["category"], x["priority"], x["url"])
        html += '</article>'

    html += "</main></body></html>"
    return html

@app.post("/collect")
def collect():
    feed = feedparser.parse("https://tudela.es/noticias/todas/1.rss")
    c = db()
    for e in feed.entries[:50]:
        title = e.get("title", "").strip()
        link = e.get("link", "").strip()
        if not title or not link:
            continue
        try:
            category, priority = classify(title)
            c.execute("""INSERT INTO items
            (source, locality, title, url, summary, category, priority,
             published_at, fingerprint, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            ("Tudela · RSS", "Tudela", title, link,
             e.get("summary", ""), category, priority,
             e.get("published", ""),
             hashlib.sha256((title + link).encode()).hexdigest(),
             datetime.now().isoformat(timespec="minutes")))
        except sqlite3.IntegrityError:
            pass
    c.commit()
    c.close()
    return redirect(url_for("index"))

init()
