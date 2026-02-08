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


def persist_email_status(path: Path, record_id: int, sent: bool, error: str) -> None:
    with write_lock:
        records = read_json(path, [])
        updated = False
        for row in records:
            try:
                current_id = int(row.get("id", 0))
            except (TypeError, ValueError):
                continue

            if current_id == record_id:
                row["email_notification"] = {
                    "sent": sent,
                    "error": "" if sent else error,
                    "updated_at": utc_now_iso(),
                }
                updated = True
                break

        if updated:
            write_json(path, records)


def parse_env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def smtp_config() -> tuple[dict[str, str | int | bool], list[str], str | None]:
    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    smtp_to = os.getenv("NOTIFY_TO_EMAIL", "").strip()
    smtp_from = os.getenv("NOTIFY_FROM_EMAIL", smtp_user).strip()
    smtp_use_ssl = parse_env_bool("SMTP_USE_SSL", False)
    smtp_use_tls = parse_env_bool("SMTP_USE_TLS", not smtp_use_ssl)

    raw_port = os.getenv("SMTP_PORT", "587").strip()
    try:
        smtp_port = int(raw_port)
    except ValueError:
        return {}, [], f"Invalid SMTP_PORT value: {raw_port!r}"

    config = {
        "host": smtp_host,
        "user": smtp_user,
        "password": smtp_password,
        "to": smtp_to,
        "from": smtp_from,
        "port": smtp_port,
        "use_ssl": smtp_use_ssl,
        "use_tls": smtp_use_tls,
    }

    missing = []
    if not smtp_host:
        missing.append("SMTP_HOST")
    if not smtp_user:
        missing.append("SMTP_USER")
    if not smtp_password:
        missing.append("SMTP_PASSWORD")
    if not smtp_to:
        missing.append("NOTIFY_TO_EMAIL")
    if not smtp_from:
        missing.append("NOTIFY_FROM_EMAIL")

    return config, missing, None


def log_smtp_diagnostics() -> None:
    config, missing, config_error = smtp_config()
    if config_error:
        app.logger.warning("Email notifications disabled: %s", config_error)
        return

    if missing:
        app.logger.warning(
            "Email notifications disabled. Missing env vars: %s",
            ", ".join(missing),
        )
        return

    mode = "SSL" if config["use_ssl"] else ("TLS" if config["use_tls"] else "plain")
    app.logger.info(
        "Email notifications enabled. host=%s port=%s mode=%s to=%s from=%s",
        config["host"],
        config["port"],
        mode,
        config["to"],
        config["from"],
    )


def send_notification_email(subject: str, body: str) -> tuple[bool, str]:
    config, missing, config_error = smtp_config()
    if config_error:
        return False, config_error

    if missing:
        return False, f"Missing SMTP config environment variables: {', '.join(missing)}"

    try:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = str(config["from"])
        message["To"] = str(config["to"])
        message.set_content(body)

        if config["use_ssl"]:
            with smtplib.SMTP_SSL(str(config["host"]), int(config["port"]), timeout=20) as smtp:
                smtp.ehlo()
                smtp.login(str(config["user"]), str(config["password"]))
                smtp.send_message(message)
        else:
            with smtplib.SMTP(str(config["host"]), int(config["port"]), timeout=20) as smtp:
                smtp.ehlo()
                if config["use_tls"]:
                    smtp.starttls()
                    smtp.ehlo()
                smtp.login(str(config["user"]), str(config["password"]))
                smtp.send_message(message)
    except Exception as error:
        app.logger.exception("Failed to send notification email")
        return False, str(error)

    return True, ""


def email_config_diagnostics() -> tuple[bool, list[str]]:
    required = ["SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "NOTIFY_TO_EMAIL"]
    missing = [name for name in required if not os.getenv(name)]
    return (len(missing) == 0, missing)


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


def parse_int(value, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def build_content_from_form(form_data) -> dict:
    menu_count = max(0, min(parse_int(form_data.get("menu_count", "0")), 100))
    video_count = max(0, min(parse_int(form_data.get("video_count", "0")), 50))

    hero_stats = []
    for index in range(3):
        value = form_data.get(f"hero_stat_value_{index}", "").strip()
        label = form_data.get(f"hero_stat_label_{index}", "").strip()
        if value or label:
            hero_stats.append({"value": value, "label": label})

    menu_items = []
    for index in range(menu_count):
        name = form_data.get(f"menu_name_{index}", "").strip()
        description = form_data.get(f"menu_description_{index}", "").strip()
        tag = form_data.get(f"menu_tag_{index}", "").strip()
        price = form_data.get(f"menu_price_{index}", "").strip()
        image = form_data.get(f"menu_image_{index}", "").strip()
        alt = form_data.get(f"menu_alt_{index}", "").strip()
        if not any([name, description, tag, price, image, alt]):
            continue

        menu_items.append(
            {
                "name": name,
                "description": description,
                "tag": tag,
                "price": price,
                "image": image,
                "alt": alt or name,
            }
        )

    videos = []
    for index in range(video_count):
        title = form_data.get(f"video_title_{index}", "").strip()
        description = form_data.get(f"video_description_{index}", "").strip()
        video = form_data.get(f"video_file_{index}", "").strip()
        poster = form_data.get(f"video_poster_{index}", "").strip()
        if not any([title, description, video, poster]):
            continue
        videos.append(
            {
                "title": title,
                "description": description,
                "video": video,
                "poster": poster,
            }
        )

    footer_hours = []
    hour_1 = form_data.get("footer_hours_1", "").strip()
    hour_2 = form_data.get("footer_hours_2", "").strip()
    if hour_1:
        footer_hours.append(hour_1)
    if hour_2:
        footer_hours.append(hour_2)

    return {
        "brand": {
            "name": form_data.get("brand_name", "").strip(),
            "email": form_data.get("brand_email", "").strip(),
            "phone": form_data.get("brand_phone", "").strip(),
            "address": form_data.get("brand_address", "").strip(),
        },
        "hero": {
            "eyebrow": form_data.get("hero_eyebrow", "").strip(),
            "title": form_data.get("hero_title", "").strip(),
            "description": form_data.get("hero_description", "").strip(),
            "video": form_data.get("hero_video", "").strip(),
            "poster": form_data.get("hero_poster", "").strip(),
            "caption": form_data.get("hero_caption", "").strip(),
            "stats": hero_stats,
        },
        "about": {
            "eyebrow": form_data.get("about_eyebrow", "").strip(),
            "title": form_data.get("about_title", "").strip(),
            "description": form_data.get("about_description", "").strip(),
            "image": form_data.get("about_image", "").strip(),
            "badge": form_data.get("about_badge", "").strip(),
        },
        "menu": {
            "eyebrow": form_data.get("menu_eyebrow", "").strip(),
            "title": form_data.get("menu_title", "").strip(),
            "items": menu_items,
        },
        "videos": videos,
        "booking": {
            "title": form_data.get("booking_title", "").strip(),
            "description": form_data.get("booking_description", "").strip(),
        },
        "ordering": {
            "title": form_data.get("ordering_title", "").strip(),
            "description": form_data.get("ordering_description", "").strip(),
        },
        "footer": {
            "tagline": form_data.get("footer_tagline", "").strip(),
            "hours": footer_hours,
            "social": form_data.get("footer_social", "").strip(),
        },
    }


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

    try:
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
                "email_notification": {
                    "sent": None,
                    "error": "",
                    "updated_at": utc_now_iso(),
                },
            }
            reservations.append(reservation)
            write_json(RESERVATIONS_PATH, reservations)
    except OSError:
        return jsonify({"ok": False, "message": "Unable to save reservation right now. Please try again."}), 500

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
    email_sent, email_error = send_notification_email("New reservation request", email_body)
    try:
        persist_email_status(RESERVATIONS_PATH, reservation["id"], email_sent, email_error)
    except OSError:
        app.logger.exception("Failed updating reservation email notification status")

    if email_sent:
        return jsonify({"ok": True, "message": "Reservation request received."}), 201

    app.logger.warning("Reservation email delivery failed for id=%s: %s", reservation["id"], email_error)
    return jsonify(
        {
            "ok": True,
            "message": "Reservation saved, but email notification failed. Check admin panel inbox.",
            "email_sent": False,
        }
    ), 201


@app.post("/api/orders")
def api_create_order() -> tuple:
    payload = parse_request_payload()

    required_fields = ["full_name", "phone", "pickup_time", "order_details"]
    for field in required_fields:
        if not str(payload.get(field, "")).strip():
            return jsonify({"ok": False, "message": f"Missing required field: {field}"}), 400

    try:
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
                "email_notification": {
                    "sent": None,
                    "error": "",
                    "updated_at": utc_now_iso(),
                },
            }
            orders.append(order)
            write_json(ORDERS_PATH, orders)
    except OSError:
        return jsonify({"ok": False, "message": "Unable to save order right now. Please try again."}), 500

    email_body = (
        "New order request\n\n"
        f"Name: {order['full_name']}\n"
        f"Email: {order['email']}\n"
        f"Phone: {order['phone']}\n"
        f"Pickup time: {order['pickup_time']}\n"
        f"Order details: {order['order_details']}\n"
        f"Notes: {order['notes']}\n"
    )
    email_sent, email_error = send_notification_email("New pickup order", email_body)
    try:
        persist_email_status(ORDERS_PATH, order["id"], email_sent, email_error)
    except OSError:
        app.logger.exception("Failed updating order email notification status")

    if email_sent:
        return jsonify({"ok": True, "message": "Order request received."}), 201

    app.logger.warning("Order email delivery failed for id=%s: %s", order["id"], email_error)
    return jsonify(
        {
            "ok": True,
            "message": "Order saved, but email notification failed. Check admin panel inbox.",
            "email_sent": False,
        }
    ), 201


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
    content = get_site_content()
    reservations = sorted(load_reservations(), key=lambda row: row.get("created_at", ""), reverse=True)[:200]
    orders = sorted(load_orders(), key=lambda row: row.get("created_at", ""), reverse=True)[:200]
    email_ok, email_missing = email_config_diagnostics()

    return render_template(
        "admin_panel.html",
        content=content,
        reservations=reservations,
        orders=orders,
        email_ok=email_ok,
        email_missing=email_missing,
    )


@app.post("/admin/content-form")
@admin_required
def admin_update_content_form():
    parsed_content = build_content_from_form(request.form)

    is_valid, message = validate_content(parsed_content)
    if not is_valid:
        flash(message, "error")
        return redirect(url_for("admin_panel"))

    with write_lock:
        write_json(CONTENT_PATH, parsed_content)

    flash("Website content updated", "success")
    return redirect(url_for("admin_panel"))


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


@app.post("/admin/email-test")
@admin_required
def admin_email_test():
    email_ok, email_missing = email_config_diagnostics()
    if not email_ok:
        flash(f"Missing SMTP env vars: {', '.join(email_missing)}", "error")
        return redirect(url_for("admin_panel"))

    sent, error = send_notification_email(
        "Luxurydine SMTP Test",
        "This is a test email from Luxurydine admin panel.",
    )
    if sent:
        flash("Test email sent successfully.", "success")
    else:
        flash(f"SMTP test failed: {error}", "error")

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


@app.after_request
def set_cache_headers(response):
    if request.path == "/" or request.path.endswith("index.html") or request.path.endswith("main.js"):
        response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


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


@app.errorhandler(404)
def handle_404(_error):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "message": "API endpoint not found"}), 404
    return ("Not Found", 404)


@app.errorhandler(405)
def handle_405(_error):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "message": "Method not allowed"}), 405
    return ("Method Not Allowed", 405)


@app.errorhandler(500)
def handle_500(_error):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "message": "Internal server error"}), 500
    return ("Internal Server Error", 500)


init_storage()
log_smtp_diagnostics()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
