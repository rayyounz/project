from flask import Flask, render_template, request, g, redirect, url_for
import sqlite3
import os

tables = [
    """CREATE TABLE events(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        date DATE
    )""",
    """CREATE TABLE articles(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        categorie TEXT,
        prix INTEGER,
        quantite_initiale INTEGER
    )""",
    """CREATE TABLE transactions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        article_id INTEGER,
        type TEXT,
        quantity INTEGER,
        event_id INTEGER,
        date DATE,
        FOREIGN KEY(article_id) REFERENCES articles(id) ON DELETE CASCADE,
        FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
    )""",
    """CREATE TABLE todos(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        description TEXT,
        event_id INTEGER,
        FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
    )"""
]

app = Flask("app.py")

if not os.path.exists('bd.db'):
    bd = sqlite3.connect('bd.db')
    curs = bd.cursor()
    for table in tables:
        curs.execute(table)
    bd.commit()
    bd.close()

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect("bd.db")
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

def get_articles_with_stock():
    bd = get_db()
    cur = bd.cursor()
    cur.execute("""
        SELECT
            a.id,
            a.name,
            a.categorie,
            a.prix,
            (
                a.quantite_initiale +
                IFNULL((
                    SELECT SUM(CASE WHEN type='buy' THEN quantity WHEN type='sell' THEN -quantity END)
                    FROM transactions
                    WHERE article_id = a.id
                ), 0)
            ) AS stock
        FROM articles a
        ORDER BY a.id
    """)
    return cur.fetchall()

def edit_article(article_id, new_name, new_categorie, new_prix, new_quantite_initiale):
    bd = get_db()
    curs = bd.cursor()
    curs.execute("SELECT id FROM articles WHERE id = ?", (article_id,))
    if curs.fetchone():
        curs.execute("UPDATE articles SET name = ?, categorie = ?, prix = ?, quantite_initiale = ? WHERE id = ?",
                     (new_name, new_categorie, new_prix, new_quantite_initiale, article_id))
        bd.commit()

@app.route('/')
def index():
    bd = get_db()
    curs = bd.cursor()
    curs.execute("SELECT * FROM events")
    events = curs.fetchall()
    todos = curs.execute("""
        SELECT t.id, t.description, e.name
        FROM todos t
        LEFT JOIN events e ON t.event_id = e.id
    """).fetchall()
    return render_template('index.html', events=events, articles=get_articles_with_stock(), todos=todos)

@app.route('/addtask', methods=['POST'])
def addtask():
    bd = get_db()
    curs = bd.cursor()
    description = request.form['description']
    event_id = request.form['event_id']
    curs.execute("SELECT id FROM events WHERE id = ?", (event_id,))
    if curs.fetchone():
        curs.execute("INSERT INTO todos (description, event_id) VALUES (?, ?)", (description, event_id))
        bd.commit()
    return redirect(url_for('index'))

@app.route('/done_task', methods=['POST'])
def done_task():
    bd = get_db()
    curs = bd.cursor()
    task_id = request.form['id']
    curs.execute("SELECT id FROM todos WHERE id = ?", (task_id,))
    if curs.fetchone():
        curs.execute("DELETE FROM todos WHERE id = ?", (task_id,))
        bd.commit()
    return redirect(url_for('index'))

@app.route('/editarticle', methods=['POST'])
def editarticle():
    article_id = request.form['id']
    new_name = request.form['name']
    new_categorie = request.form['categorie']
    try:
        new_prix = int(request.form['prix'])
        new_quantite_initiale = int(request.form['quantite_initiale'])
    except ValueError:
        return redirect(url_for('index'))
    edit_article(article_id, new_name, new_categorie, new_prix, new_quantite_initiale)
    return redirect(url_for('index'))

@app.route('/addevent', methods=['POST'])
def addevent():
    bd = get_db()
    curs = bd.cursor()
    name = request.form['name']
    date = request.form['date']
    curs.execute("INSERT INTO events (name, date) VALUES (?, ?)", (name, date))
    bd.commit()
    return redirect(url_for('index'))

@app.route('/deleteevent', methods=['POST'])
def deleteevent():
    bd = get_db()
    curs = bd.cursor()
    id = request.form['id']
    curs.execute("SELECT id FROM events WHERE id = ?", (id,))
    if curs.fetchone():
        curs.execute("DELETE FROM events WHERE id = ?", (id,))
        bd.commit()
    return redirect(url_for('index'))

@app.route('/addarticle', methods=['POST'])
def addarticle():
    bd = get_db()
    curs = bd.cursor()
    name = request.form['name']
    categorie = request.form['categorie']
    try:
        prix = int(request.form['prix'])
        quantite_initiale = int(request.form['quantite_initiale'])
    except ValueError:
        return redirect(url_for('index'))
    curs.execute("INSERT INTO articles (name, categorie, prix, quantite_initiale) VALUES (?, ?, ?, ?)",
                 (name, categorie, prix, quantite_initiale))
    bd.commit()
    return redirect(url_for('index'))

@app.route('/deletearticle', methods=['POST'])
def deletearticle():
    bd = get_db()
    curs = bd.cursor()
    id = request.form['id']
    curs.execute("SELECT id FROM articles WHERE id = ?", (id,))
    if curs.fetchone():
        curs.execute("DELETE FROM articles WHERE id = ?", (id,))
        bd.commit()
    return redirect(url_for('index'))

@app.route("/addtransaction", methods=['POST'])
def addtransaction():
    db = get_db()
    cur = db.cursor()
    article_id = request.form.get("article_id")
    type_ = request.form.get("type")
    quantity = request.form.get("quantity")
    event_id = request.form.get("event_id")
    if not article_id or not type_ or not quantity or not event_id:
        return redirect(url_for("index"))
    try:
        article_id = int(article_id)
        event_id = int(event_id)
        quantity = int(quantity)
    except ValueError:
        return redirect(url_for("index"))
    cur.execute("SELECT id FROM articles WHERE id = ?", (article_id,))
    if not cur.fetchone():
        return redirect(url_for("index"))
    cur.execute("SELECT id FROM events WHERE id = ?", (event_id,))
    if not cur.fetchone():
        return redirect(url_for("index"))
    if type_ == "sell":
        cur.execute("""
            SELECT IFNULL(a.quantite_initiale + SUM(CASE WHEN t.type='buy' THEN t.quantity WHEN t.type='sell' THEN -t.quantity END), a.quantite_initiale)
            FROM articles a LEFT JOIN transactions t ON a.id=t.article_id
            WHERE a.id=?
        """, (article_id,))
        stock = cur.fetchone()[0] or 0
        if quantity > stock:
            return redirect(url_for("index"))
    cur.execute("INSERT INTO transactions (article_id, type, quantity, event_id, date) VALUES (?, ?, ?, ?, DATE('now'))",
                (article_id, type_, quantity, event_id))
    db.commit()
    return redirect(url_for("index"))

@app.route('/getstatsforevent', methods=['POST'])
def getstatsforevent():
    event_id = request.form['event_id']
    db = get_db()
    cur = db.cursor()
    try:
        event_id = int(event_id)
    except ValueError:
        return redirect(url_for('index'))
    cur.execute("SELECT name, date FROM events WHERE id = ?", (event_id,))
    event = cur.fetchone()
    if not event:
        return redirect(url_for('index'))
    cur.execute("""
        SELECT SUM(CASE WHEN type='sell' THEN quantity ELSE 0 END),
               SUM(CASE WHEN type='buy' THEN quantity ELSE 0 END)
        FROM transactions WHERE event_id = ?
    """, (event_id,))
    total_sold, total_bought = cur.fetchone()
    cur.execute("""
        SELECT SUM(CASE WHEN t.type='sell' THEN t.quantity * a.prix ELSE 0 END) -
               SUM(CASE WHEN t.type='buy' THEN t.quantity * a.prix ELSE 0 END)
        FROM transactions t JOIN articles a ON a.id = t.article_id
        WHERE t.event_id = ?
    """, (event_id,))
    profit = cur.fetchone()[0] or 0
    cur.execute("""
        SELECT a.id, a.name, SUM(t.quantity) AS quantity_sold
        FROM transactions t JOIN articles a ON a.id = t.article_id
        WHERE t.event_id = ? AND t.type='sell'
        GROUP BY a.id
        ORDER BY quantity_sold DESC
    """, (event_id,))
    bestproducts = cur.fetchall()
    events = db.cursor().execute("SELECT * FROM events").fetchall()
    return render_template("index.html",
                           events=events,
                           articles=get_articles_with_stock(),
                           stats={"event_name": event[0], "event_date": event[1],
                                  "total_sold": total_sold or 0, "total_bought": total_bought or 0},
                           profit=profit,
                           bestproducts=[{"id": r[0], "name": r[1], "quantity_sold": r[2]} for r in bestproducts])

@app.teardown_appcontext
def close_db(error):
    db = g.pop("db", None)
    if db:
        db.close()

app.run()
