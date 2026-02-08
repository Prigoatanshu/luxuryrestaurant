import os
import smtplib
import sqlite3
import urllib.parse
from email.message import EmailMessage

from flask import Flask, render_template, request, redirect, url_for, flash, session

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "luxurydine-dev-key")
DB_PATH = os.path.join(os.path.dirname(__file__), "luxurydine.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS menu_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            price TEXT NOT NULL,
            image_url TEXT NOT NULL
        )
        """
    )
    conn.commit()

    count = conn.execute("SELECT COUNT(*) FROM menu_items").fetchone()[0]
    if count == 0:
        seed_items = [
            (
                "Starters",
                "Seared Scallops",
                "Citrus beurre blanc, fennel pollen",
                "$16",
                "https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=800&q=80",
            ),
            (
                "Starters",
                "Heirloom Salad",
                "Burrata, basil oil, aged balsamic",
                "$12",
                "https://images.unsplash.com/photo-1540189549336-e6e99c3679fe?auto=format&fit=crop&w=800&q=80",
            ),
            (
                "Starters",
                "Truffle Tagliolini",
                "Black truffle, parmesan crema",
                "$18",
                "https://images.unsplash.com/photo-1504754524776-8f4f37790ca0?auto=format&fit=crop&w=800&q=80",
            ),
            (
                "Main Course",
                "Butter-Poached Chicken",
                "Wild mushroom jus, thyme",
                "$24",
                "https://images.unsplash.com/photo-1600891964599-f61ba0e24092?auto=format&fit=crop&w=800&q=80",
            ),
            (
                "Main Course",
                "Pan-Seared Sea Bass",
                "Saffron risotto, lemon zest",
                "$29",
                "https://images.unsplash.com/photo-1553621042-f6e147245754?auto=format&fit=crop&w=800&q=80",
            ),
            (
                "Main Course",
                "Wagyu Steak",
                "Truffle potato puree, jus",
                "$38",
                "https://images.unsplash.com/photo-1604908554149-6d5f6a1d1b94?auto=format&fit=crop&w=800&q=80",
            ),
            (
                "Main Course",
                "Braised Short Rib",
                "Celery root, red wine glaze",
                "$32",
                "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=800&q=80",
            ),
            (
                "Main Course",
                "Wild Mushroom Risotto",
                "Porcini, aged pecorino",
                "$22",
                "https://images.unsplash.com/photo-1473093295043-cdd812d0e601?auto=format&fit=crop&w=800&q=80",
            ),
            (
                "Desserts",
                "Chocolate Souffle",
                "Madagascar vanilla, cacao nibs",
                "$12",
                "https://images.unsplash.com/photo-1488477181946-6428a0291777?auto=format&fit=crop&w=800&q=80",
            ),
            (
                "Desserts",
                "Citrus Tart",
                "Lemon curd, candied peel",
                "$11",
                "https://images.unsplash.com/photo-1481931098730-318b6f776db0?auto=format&fit=crop&w=800&q=80",
            ),
            (
                "Desserts",
                "Berry Parfait",
                "Mascarpone, mint, berry compote",
                "$10",
                "https://images.unsplash.com/photo-1505253758473-96b7015fcd40?auto=format&fit=crop&w=800&q=80",
            ),
        ]
        conn.executemany(
            """
            INSERT INTO menu_items (category, name, description, price, image_url)
            VALUES (?, ?, ?, ?, ?)
            """,
            seed_items,
        )
        conn.commit()
    conn.close()


def fetch_menu_items():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, category, name, description, price, image_url FROM menu_items ORDER BY id ASC"
    ).fetchall()
    conn.close()
    return rows


def group_menu_items(rows):
    categories = ["Starters", "Main Course", "Desserts"]
    grouped = {category: [] for category in categories}
    for row in rows:
        grouped.setdefault(row["category"], []).append(row)
    return grouped, categories


def whatsapp_link(item):
    number = os.environ.get("WHATSAPP_NUMBER", "15550162419")
    message = (
        f"Hello LuxuryDine, I'd like to order {item['name']} "
        f"({item['price']})."
    )
    text = urllib.parse.quote_plus(message)
    return f"https://wa.me/{number}?text={text}"


def require_admin():
    return session.get("is_admin") is True


@app.context_processor
def inject_globals():
    return {"whatsapp_link": whatsapp_link}


init_db()

@app.route("/")
def home():
    return render_template("home.html", title="Home")

@app.route("/menu")
def menu():
    items = fetch_menu_items()
    grouped_items, categories = group_menu_items(items)
    return render_template(
        "menu.html",
        title="Menu",
        grouped_items=grouped_items,
        categories=categories,
    )

@app.route("/contact")
def contact():
    return render_template("contact.html", title="Contact")

@app.route("/about")
def about():
    return render_template("about.html", title="About")

@app.route("/gallery")
def gallery():
    return render_template("gallery.html", title="Gallery")

@app.route("/events")
def events():
    return render_template("events.html", title="Events")

@app.route("/private-dining")
def private_dining():
    return render_template("private_dining.html", title="Private Dining")

@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password", "")
        expected = os.environ.get("ADMIN_PASSWORD")
        if expected and password == expected:
            session["is_admin"] = True
            return redirect(url_for("admin_menu"))
        flash("Invalid admin password.")
    return render_template("admin_login.html", title="Admin Login")


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    flash("Logged out.")
    return redirect(url_for("admin_login"))


@app.route("/admin/menu", methods=["GET", "POST"])
def admin_menu():
    if not require_admin():
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        action = request.form.get("action")
        conn = get_db()
        if action == "add":
            conn.execute(
                """
                INSERT INTO menu_items (category, name, description, price, image_url)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    request.form.get("category", "Starters").strip(),
                    request.form.get("name", "").strip(),
                    request.form.get("description", "").strip(),
                    request.form.get("price", "").strip(),
                    request.form.get("image_url", "").strip(),
                ),
            )
            conn.commit()
            flash("Menu item added.")
        elif action == "update":
            conn.execute(
                """
                UPDATE menu_items
                SET category = ?, name = ?, description = ?, price = ?, image_url = ?
                WHERE id = ?
                """,
                (
                    request.form.get("category", "").strip(),
                    request.form.get("name", "").strip(),
                    request.form.get("description", "").strip(),
                    request.form.get("price", "").strip(),
                    request.form.get("image_url", "").strip(),
                    request.form.get("id"),
                ),
            )
            conn.commit()
            flash("Menu item updated.")
        elif action == "delete":
            conn.execute("DELETE FROM menu_items WHERE id = ?", (request.form.get("id"),))
            conn.commit()
            flash("Menu item deleted.")
        conn.close()
        return redirect(url_for("admin_menu"))

    items = fetch_menu_items()
    grouped_items, categories = group_menu_items(items)
    return render_template(
        "admin_menu.html",
        title="Admin Menu",
        items=items,
        categories=categories,
        grouped_items=grouped_items,
    )

@app.route("/reserve", methods=["POST"])
def reserve():
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    date = request.form.get("date", "").strip()
    time = request.form.get("time", "").strip()

    if not all([name, phone, date, time]):
        flash("Please fill in all reservation fields.")
        return redirect(url_for("home"))

    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    to_email = os.environ.get("SMTP_TO", "jhapriyanshu107@gmail.com")

    if not smtp_user or not smtp_pass:
        flash("Reservation email is not configured. Please set SMTP_USER and SMTP_PASS.")
        return redirect(url_for("home"))

    msg = EmailMessage()
    msg["Subject"] = f"New Reservation — {name}"
    msg["From"] = smtp_user
    msg["To"] = to_email
    msg.set_content(
        "LuxuryDine Reservation\n"
        f"Name: {name}\n"
        f"Phone: {phone}\n"
        f"Date: {date}\n"
        f"Time: {time}\n"
    )

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(smtp_user, smtp_pass)
            smtp.send_message(msg)
        flash("Reservation sent successfully. We'll confirm shortly.")
    except Exception:
        flash("Something went wrong while sending your reservation. Please try again.")

    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(debug=True)
