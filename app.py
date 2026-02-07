import json
import os
import smtplib
import threading
from datetime import datetime, timezone
from email.message import EmailMessage
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)

BASE_DIR = Path(__file__).resolve().parent
SITE_DIR = BASE_DIR / "site"
DATA_DIR = BASE_DIR / "data"
DEFAULT_CONTENT_PATH = SITE_DIR / "content-default.json"
CONTENT_PATH = DATA_DIR / "content.json"
RESERVATIONS_PATH = DATA_DIR / "reservations.json"
ORDERS_PATH = DATA_DIR / "orders.json"

app = Flask(__name__, static_folder=str(SITE_DIR), static_url_path="")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-this-secret-key")
write_lock = threading.Lock()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path, default):
    if not path.exists():
        return default

    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def write_json(path: Path, payload) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)


def load_default_content() -> dict:
    with DEFAULT_CONTENT_PATH.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def init_storage() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not CONTENT_PATH.exists():
        write_json(CONTENT_PATH, load_default_content())

    if not RESERVATIONS_PATH.exists():
        write_json(RESERVATIONS_PATH, [])

    if not ORDERS_PATH.exists():
        write_json(ORDERS_PATH, [])


def validate_content(content: dict) -> tuple[bool, str]:
    required_sections = ["brand", "hero", "menu", "footer"]
    for section in required_sections:
        if section not in content:
            return False, f"Missing section: {section}"

    menu_items = content.get("menu", {}).get("items", [])
    if not isinstance(menu_items, list) or len(menu_items) == 0:
        return False, "Menu must include at least one item"

    for item in menu_items:
        if not item.get("name"):
            return False, "Each menu item requires a name"
        if not item.get("price"):
            return False, "Each menu item requires a price"

    return True, "ok"


def get_site_content() -> dict:
    return read_json(CONTENT_PATH, load_default_content())


def load_reservations() -> list:
    return read_json(RESERVATIONS_PATH, [])


def load_orders() -> list:
    return read_json(ORDERS_PATH, [])


def next_id(records: list) -> int:
    if not records:
        return 1
    return max(int(record.get("id", 0)) for record in records) + 1


def send_notification_email(subject: str, body: str) -> None:
    smtp_host = os.getenv("SMTP_HOST")
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_to = os.getenv("NOTIFY_TO_EMAIL")
    smtp_from = os.getenv("NOTIFY_FROM_EMAIL", smtp_user or "")

    if not all([smtp_host, smtp_user, smtp_password, smtp_to, smtp_from]):
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = smtp_from
    message["To"] = smtp_to
    message.set_content(body)

    with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as smtp:
        smtp.starttls()
        smtp.login(smtp_user, smtp_password)
        smtp.send_message(message)


def is_admin_authenticated() -> bool:
    return bool(session.get("admin_authenticated"))


def admin_required(route_handler):
    @wraps(route_handler)
    def wrapped(*args, **kwargs):
        if not is_admin_authenticated():
            return redirect(url_for("admin_login"))
        return route_handler(*args, **kwargs)

    return wrapped


def parse_request_payload() -> dict:
    if request.is_json:
        return request.get_json(silent=True) or {}
    return request.form.to_dict()


@app.get("/api/content")
def api_content() -> tuple:
    return jsonify(get_site_content()), 200


@app.post("/api/reservations")
def api_create_reservation() -> tuple:
    payload = parse_request_payload()

    required_fields = ["full_name", "email", "phone", "reservation_date", "reservation_time", "guests"]
    for field in required_fields:
        if not str(payload.get(field, "")).strip():
            return jsonify({"ok": False, "message": f"Missing required field: {field}"}), 400

    with write_lock:
        reservations = load_reservations()
        reservation = {
            "id": next_id(reservations),
            "full_name": payload["full_name"].strip(),
            "email": payload["email"].strip(),
            "phone": payload["phone"].strip(),
            "reservation_date": payload["reservation_date"].strip(),
            "reservation_time": payload["reservation_time"].strip(),
            "guests": str(payload["guests"]).strip(),
            "occasion": payload.get("occasion", "").strip(),
            "notes": payload.get("notes", "").strip(),
            "status": "new",
            "created_at": utc_now_iso(),
        }
        reservations.append(reservation)
        write_json(RESERVATIONS_PATH, reservations)

    email_body = (
        "New reservation request\n\n"
        f"Name: {reservation['full_name']}\n"
        f"Email: {reservation['email']}\n"
        f"Phone: {reservation['phone']}\n"
        f"Date: {reservation['reservation_date']}\n"
        f"Time: {reservation['reservation_time']}\n"
        f"Guests: {reservation['guests']}\n"
        f"Occasion: {reservation['occasion']}\n"
        f"Notes: {reservation['notes']}\n"
    )
    send_notification_email("New reservation request", email_body)

    return jsonify({"ok": True, "message": "Reservation request received."}), 201


@app.post("/api/orders")
def api_create_order() -> tuple:
    payload = parse_request_payload()

    required_fields = ["full_name", "phone", "pickup_time", "order_details"]
    for field in required_fields:
        if not str(payload.get(field, "")).strip():
            return jsonify({"ok": False, "message": f"Missing required field: {field}"}), 400

    with write_lock:
        orders = load_orders()
        order = {
            "id": next_id(orders),
            "full_name": payload["full_name"].strip(),
            "email": payload.get("email", "").strip(),
            "phone": payload["phone"].strip(),
            "pickup_time": payload["pickup_time"].strip(),
            "order_details": payload["order_details"].strip(),
            "notes": payload.get("notes", "").strip(),
            "status": "new",
            "created_at": utc_now_iso(),
        }
        orders.append(order)
        write_json(ORDERS_PATH, orders)

    email_body = (
        "New order request\n\n"
        f"Name: {order['full_name']}\n"
        f"Email: {order['email']}\n"
        f"Phone: {order['phone']}\n"
        f"Pickup time: {order['pickup_time']}\n"
        f"Order details: {order['order_details']}\n"
        f"Notes: {order['notes']}\n"
    )
    send_notification_email("New pickup order", email_body)

    return jsonify({"ok": True, "message": "Order request received."}), 201


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if is_admin_authenticated():
        return redirect(url_for("admin_panel"))

    if request.method == "POST":
        submitted_password = request.form.get("password", "")
        expected_password = os.getenv("ADMIN_PASSWORD", "change-this-admin-password")

        if submitted_password and submitted_password == expected_password:
            session["admin_authenticated"] = True
            return redirect(url_for("admin_panel"))

        flash("Invalid password", "error")

    return render_template("admin_login.html")


@app.get("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.get("/admin")
@admin_required
def admin_panel():
    reservations = sorted(load_reservations(), key=lambda row: row.get("created_at", ""), reverse=True)[:200]
    orders = sorted(load_orders(), key=lambda row: row.get("created_at", ""), reverse=True)[:200]

    return render_template(
        "admin_panel.html",
        content_json=json.dumps(get_site_content(), indent=2),
        reservations=reservations,
        orders=orders,
    )


@app.post("/admin/content")
@admin_required
def admin_update_content():
    content_raw = request.form.get("content_json", "")
    if not content_raw.strip():
        flash("Content JSON cannot be empty", "error")
        return redirect(url_for("admin_panel"))

    try:
        parsed_content = json.loads(content_raw)
    except json.JSONDecodeError as error:
        flash(f"Invalid JSON: {error.msg}", "error")
        return redirect(url_for("admin_panel"))

    is_valid, message = validate_content(parsed_content)
    if not is_valid:
        flash(message, "error")
        return redirect(url_for("admin_panel"))

    with write_lock:
        write_json(CONTENT_PATH, parsed_content)

    flash("Website content updated", "success")
    return redirect(url_for("admin_panel"))


@app.post("/admin/reservations/<int:reservation_id>/status")
@admin_required
def admin_update_reservation_status(reservation_id: int):
    status = request.form.get("status", "new").strip().lower()
    allowed = {"new", "confirmed", "completed", "cancelled"}
    if status not in allowed:
        flash("Invalid reservation status", "error")
        return redirect(url_for("admin_panel"))

    updated = False
    with write_lock:
        reservations = load_reservations()
        for row in reservations:
            if int(row.get("id", 0)) == reservation_id:
                row["status"] = status
                updated = True
                break
        if updated:
            write_json(RESERVATIONS_PATH, reservations)

    if updated:
        flash("Reservation status updated", "success")
    else:
        flash("Reservation not found", "error")

    return redirect(url_for("admin_panel"))


@app.post("/admin/orders/<int:order_id>/status")
@admin_required
def admin_update_order_status(order_id: int):
    status = request.form.get("status", "new").strip().lower()
    allowed = {"new", "accepted", "preparing", "ready", "completed", "cancelled"}
    if status not in allowed:
        flash("Invalid order status", "error")
        return redirect(url_for("admin_panel"))

    updated = False
    with write_lock:
        orders = load_orders()
        for row in orders:
            if int(row.get("id", 0)) == order_id:
                row["status"] = status
                updated = True
                break
        if updated:
            write_json(ORDERS_PATH, orders)

    if updated:
        flash("Order status updated", "success")
    else:
        flash("Order not found", "error")

    return redirect(url_for("admin_panel"))


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/<path:path>")
def static_files(path: str):
    candidate = (SITE_DIR / path).resolve()
    if SITE_DIR not in candidate.parents and candidate != SITE_DIR:
        abort(404)

    if candidate.is_file():
        return send_from_directory(app.static_folder, path)

    abort(404)


init_storage()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
