

rom flask import Flask, redirect, url_for, request
import sqlite3, hashlib, feedparser, os
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
DB = "navarra_te_ve.db"
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "static", "audiencia")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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
c.execute("""CREATE TABLE IF NOT EXISTS audiencia(
id INTEGER PRIMARY KEY,
nombre TEXT, pueblo TEXT, texto TEXT,
filename TEXT, status TEXT DEFAULT 'pending',
created_at TEXT)""")
c.commit()
c.close()

def classify(title):
t = title.lower()
if any(x in t for x in ["incendio", "accidente", "policía", "emergencia"]):
return "Sucesos", "alta"
if any(x in t for x in ["ayuntamiento", "pleno", "obras", "urbanismo"]):
return "Municipios", "media"
return "Navarra", "normal"

BASE_STYLE = """
body{font-family:Arial;margin:0;background:#f4f5f8;color:#182033}
header{background:linear-gradient(110deg,#6338b7,#3e69c7,#25aeb3);color:white;padding:25px}
main{max-width:1100px;margin:auto;padding:25px}
.btn{padding:12px 16px;border:0;border-radius:7px;background:#6338b7;color:white;font-weight:bold;cursor:pointer;text-decoration:none;display:inline-block}
.btn-pub{background:#2E8C86}
.btn-desc{background:#999}
article{background:white;padding:18px;margin:12px 0;border-radius:10px}
.src{color:#6338b7;font-size:12px;font-weight:bold}
.title{font-size:18px;font-weight:bold;margin:7px 0}
.acciones{margin-top:10px;display:flex;gap:8px}
.acciones form{display:inline}
.aud-item{display:flex;gap:14px;align-items:flex-start}
.aud-item img, .aud-item video{width:140px;border-radius:8px}
input,textarea{width:100%;padding:10px;margin:6px 0;border:1px solid #ccc;border-radius:6px;box-sizing:border-box}
label{font-weight:bold;font-size:13px}
"""

@app.route("/")
def index():
c = db()
items = c.execute("SELECT * FROM items WHERE status='pending' ORDER BY id DESC").fetchall()
aud = c.execute("SELECT * FROM audiencia WHERE status='pending' ORDER BY id DESC").fetchall()
c.close()

html = f"""<!doctype html><html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Navarra Te Ve · Panel</title><style>{BASE_STYLE}</style></head><body>
<header><b>📱 NAVARRA TE VE</b><br>Panel de administración</header>
<main>
<form method="post" action="/collect">
<button class="btn">🤖 BUSCAR NOVEDADES DE TUDELA</button>
</form>

<h2>Noticias pendientes: {len(items)}</h2>"""

for x in items:
html += f'<article><div class="src">{x["source"]} · {x["locality"]}</div>'
html += f'<div class="title">{x["title"]}</div>'
html += f'<small>{x["published_at"]} · {x["category"]} · prioridad {x["priority"]} · <a href="{x["url"]}">fuente</a></small>'
html += f'''<div class="acciones">
<form method="post" action="/publish/{x["id"]}"><button class="btn btn-pub">✅ Publicar</button></form>
<form method="post" action="/discard/{x["id"]}"><button class="btn btn-desc">🗑️ Descartar</button></form>
</div></article>'''

html += f'<h2>📸 De la audiencia pendientes: {len(aud)}</h2>'
for a in aud:
ext = a["filename"].rsplit(".", 1)[-1].lower() if a["filename"] else ""
preview = f'<video src="/static/audiencia/{a["filename"]}" controls></video>' if ext in ("mp4","mov","webm") else f'<img src="/static/audiencia/{a["filename"]}">'
html += f'''<article class="aud-item">{preview}
<div>
<div class="src">{a["nombre"]} · {a["pueblo"]}</div>
<div class="title">{a["texto"] or "(sin descripción)"}</div>
<small>{a["created_at"]}</small>
<div class="acciones">
<form method="post" action="/audiencia/publish/{a["id"]}"><button class="btn btn-pub">✅ Publicar</button></form>
<form method="post" action="/audiencia/discard/{a["id"]}"><button class="btn btn-desc">🗑️ Descartar</button></form>
</div>
</div></article>'''

html += f'<p><a class="btn" href="/enviar">📤 Ver formulario de envío</a> &nbsp; <a class="btn" href="/audiencia" style="background:#25aeb3">👀 Ver publicado</a></p>'
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

@app.post("/publish/<int:item_id>")
def publish(item_id):
c = db()
c.execute("UPDATE items SET status='published' WHERE id=?", (item_id,))
c.commit()
c.close()
return redirect(url_for("index"))

@app.post("/discard/<int:item_id>")
def discard(item_id):
c = db()
c.execute("UPDATE items SET status='discarded' WHERE id=?", (item_id,))
c.commit()
c.close()
return redirect(url_for("index"))

@app.route("/enviar", methods=["GET", "POST"])
def enviar():
if request.method == "POST":
nombre = request.form.get("nombre", "").strip()
pueblo = request.form.get("pueblo", "").strip()
texto = request.form.get("texto", "").strip()
file = request.files.get("archivo")
filename = ""
if file and file.filename:
filename = secure_filename(f"{datetime.now().timestamp()}_{file.filename}")
file.save(os.path.join(UPLOAD_FOLDER, filename))

c = db()
c.execute("""INSERT INTO audiencia (nombre, pueblo, texto, filename, created_at)
VALUES (?,?,?,?,?)""",
(nombre, pueblo, texto, filename, datetime.now().isoformat(timespec="minutes")))
c.commit()
c.close()
return """<!doctype html><html lang="es"><body style="font-family:Arial;text-align:center;padding:60px">
<h2>¡Gracias! 🎉</h2><p>Hemos recibido tu foto o vídeo. Lo revisaremos antes de publicarlo.</p>
<a href="/enviar">Enviar otro</a></body></html>"""

return f"""<!doctype html><html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Envía tu vídeo o foto · Navarra Te Ve</title><style>{BASE_STYLE}</style></head><body>
<header><b>📱 NAVARRA TE VE</b><br>Envía tu foto o vídeo</header>
<main>
<form method="post" enctype="multipart/form-data">
<label>Tu nombre</label><input name="nombre" required>
<label>Tu pueblo</label><input name="pueblo" required>
<label>Cuéntanos qué es (opcional)</label><textarea name="texto" rows="3"></textarea>
<label>Foto o vídeo</label><input type="file" name="archivo" accept="image/*,video/*" required>
<br><br><button class="btn">📤 Enviar</button>
</form>
</main></body></html>"""

@app.post("/audiencia/publish/<int:item_id>")
def audiencia_publish(item_id):
c = db()
c.execute("UPDATE audiencia SET status='published' WHERE id=?", (item_id,))
c.commit()
c.close()
return redirect(url_for("index"))

@app.post("/audiencia/discard/<int:item_id>")
def audiencia_discard(item_id):
c = db()
c.execute("UPDATE audiencia SET status='discarded' WHERE id=?", (item_id,))
c.commit()
c.close()
return redirect(url_for("index"))

@app.route("/audiencia")
def audiencia_publica():
c = db()
aud = c.execute("SELECT * FROM audiencia WHERE status='published' ORDER BY id DESC").fetchall()
c.close()
html = f"""<!doctype html><html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>De la audiencia · Navarra Te Ve</title><style>{BASE_STYLE}</style></head><body>
<header><b>📱 NAVARRA TE VE</b><br>De la audiencia</header><main>"""
for a in aud:
ext = a["filename"].rsplit(".", 1)[-1].lower() if a["filename"] else ""
preview = f'<video src="/static/audiencia/{a["filename"]}" controls style="width:100%"></video>' if ext in ("mp4","mov","webm") else f'<img src="/static/audiencia/{a["filename"]}" style="width:100%">'
html += f'''<article>{preview}
<div class="title">{a["texto"] or ""}</div>
<small>📷 {a["nombre"]}, {a["pueblo"]}</small></article>'''
html += '</main></body></html>'
return html

init()
