from __future__ import annotations

import base64
import io
import json
import os
import smtplib
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from functools import wraps
from pathlib import Path
from typing import Any

from flask import Flask, flash, redirect, render_template, request, send_file, session, url_for
from openpyxl import Workbook

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
except ImportError:
    firebase_admin = None
    credentials = None
    firestore = None


def load_dotenv_file(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


BASE_DIR = Path(__file__).resolve().parent
load_dotenv_file(BASE_DIR / ".env")
DATA_DIR = BASE_DIR / "work" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATA_FILE = DATA_DIR / "reservas.json"
APP_PORT = int(os.getenv("PORT", os.getenv("APP_PORT", "5001")))
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local").strip().lower()
APP_UTC_OFFSET_HOURS = float(os.getenv("APP_UTC_OFFSET_HOURS", "-3"))

EVENT_DATE_LABEL = "19 de julho de 2026"
PANEL_TITLE = "Painel de Reservas"
RESERVATION_TITLE = "Reserva de Ingressos"
RESERVATION_SUBTITLE = "Preencha os dados para reservar seus ingressos"
PANEL_USERNAME = os.getenv("PANEL_USERNAME", "admin")
PANEL_PASSWORD = os.getenv("PANEL_PASSWORD", "troque-essa-senha")
ZOHO_SMTP_HOST = os.getenv("ZOHO_SMTP_HOST", "smtp.zoho.com")
ZOHO_SMTP_PORT = int(os.getenv("ZOHO_SMTP_PORT", "465"))
ZOHO_SMTP_USERNAME = os.getenv("ZOHO_SMTP_USERNAME", "").strip()
ZOHO_SMTP_PASSWORD = os.getenv("ZOHO_SMTP_PASSWORD", "").strip()
ZOHO_SMTP_FROM_EMAIL = os.getenv("ZOHO_SMTP_FROM_EMAIL", ZOHO_SMTP_USERNAME).strip()
ZOHO_SMTP_FROM_NAME = os.getenv(
    "ZOHO_SMTP_FROM_NAME",
    "Estância Parque Ecológico das Águas",
).strip()
ZOHO_SMTP_USE_SSL = os.getenv("ZOHO_SMTP_USE_SSL", "true").strip().lower() in {
    "1",
    "true",
    "yes",
}
EMAIL_SEND_TIMEOUT_SECONDS = int(os.getenv("EMAIL_SEND_TIMEOUT_SECONDS", "20"))
IS_RENDER_ENV = bool(os.getenv("RENDER") or os.getenv("RENDER_EXTERNAL_URL"))

TERMS_TEXT = """
Os termos de uso do evento do Estância Parque Ecológico das Águas serão atualizados aqui em breve.

Data do evento: 19/07/2026

Assim que o Lucas enviar a versão final dos termos, este texto será substituído.
""".strip()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "reserva-local-simples")
STORE_MODE = "local"


def current_timestamp() -> str:
    app_timezone = timezone(timedelta(hours=APP_UTC_OFFSET_HOURS))
    return datetime.now(app_timezone).strftime("%Y-%m-%d %H:%M:%S")


def format_datetime(value: str) -> str:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return value
    return parsed.strftime("%d/%m/%Y %H:%M")


class ReservationStore(ABC):
    @abstractmethod
    def list_reservations(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def create_reservation(
        self,
        holder_name: str,
        holder_email: str,
        holder_phone: str,
        companions: list[dict[str, str]],
        terms_accepted_at: str,
    ) -> dict[str, Any]:
        raise NotImplementedError


class LocalJsonStore(ReservationStore):
    def __init__(self, data_file: Path) -> None:
        self.data_file = data_file
        self.ensure_data_file()

    def ensure_data_file(self) -> None:
        if not self.data_file.exists():
            self.save_data({"next_id": 1, "reservations": []})

    def load_data(self) -> dict[str, Any]:
        self.ensure_data_file()
        return json.loads(self.data_file.read_text(encoding="utf-8"))

    def save_data(self, data: dict[str, Any]) -> None:
        self.data_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def list_reservations(self) -> list[dict[str, Any]]:
        data = self.load_data()
        return sorted(data["reservations"], key=lambda row: row["id"], reverse=True)

    def create_reservation(
        self,
        holder_name: str,
        holder_email: str,
        holder_phone: str,
        companions: list[dict[str, str]],
        terms_accepted_at: str,
    ) -> dict[str, Any]:
        data = self.load_data()
        reservation = {
            "id": data["next_id"],
            "holder_name": holder_name,
            "holder_email": holder_email,
            "holder_phone": holder_phone,
            "created_at": current_timestamp(),
            "terms_accepted_at": terms_accepted_at,
            "companions": companions,
        }
        data["reservations"].append(reservation)
        data["next_id"] += 1
        self.save_data(data)
        return reservation


class FirestoreStore(ReservationStore):
    def __init__(self) -> None:
        if firebase_admin is None or credentials is None or firestore is None:
            raise RuntimeError(
                "firebase-admin não está instalado. Rode pip install -r requirements.txt."
            )
        self.db = self._init_firestore()

    def _init_firestore(self):
        try:
            firebase_admin.get_app()
        except ValueError:
            service_account_file = os.getenv("FIREBASE_SERVICE_ACCOUNT_FILE", "").strip()
            encoded_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON_BASE64", "").strip()
            raw_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
            if service_account_file:
                credential = credentials.Certificate(service_account_file)
                firebase_admin.initialize_app(credential)
            elif encoded_json:
                service_account = json.loads(base64.b64decode(encoded_json).decode("utf-8"))
                credential = credentials.Certificate(service_account)
                firebase_admin.initialize_app(credential)
            elif raw_json:
                credential = credentials.Certificate(json.loads(raw_json))
                firebase_admin.initialize_app(credential)
            else:
                firebase_admin.initialize_app()
        return firestore.client()

    def list_reservations(self) -> list[dict[str, Any]]:
        docs = self.db.collection("reservations").stream()
        reservations = []
        for doc in docs:
            data = doc.to_dict()
            reservations.append(
                {
                    "id": data["id"],
                    "holder_name": data["holder_name"],
                    "holder_email": data.get("holder_email", ""),
                    "holder_phone": data.get("holder_phone", ""),
                    "created_at": data["created_at"],
                    "terms_accepted_at": data.get("terms_accepted_at", ""),
                    "companions": data.get("companions", []),
                }
            )
        return sorted(reservations, key=lambda row: row["id"], reverse=True)

    def create_reservation(
        self,
        holder_name: str,
        holder_email: str,
        holder_phone: str,
        companions: list[dict[str, str]],
        terms_accepted_at: str,
    ) -> dict[str, Any]:
        counter_ref = self.db.collection("meta").document("counters")

        @firestore.transactional
        def create_in_transaction(transaction, ref):
            snapshot = ref.get(transaction=transaction)
            next_id = 1
            if snapshot.exists:
                next_id = snapshot.to_dict().get("next_id", 1)
            reservation = {
                "id": next_id,
                "holder_name": holder_name,
                "holder_email": holder_email,
                "holder_phone": holder_phone,
                "created_at": current_timestamp(),
                "terms_accepted_at": terms_accepted_at,
                "companions": companions,
            }
            transaction.set(ref, {"next_id": next_id + 1}, merge=True)
            transaction.set(
                self.db.collection("reservations").document(str(next_id)),
                reservation,
            )
            return reservation

        return create_in_transaction(self.db.transaction(), counter_ref)


def create_store() -> ReservationStore:
    global STORE_MODE
    if STORAGE_BACKEND == "firebase":
        try:
            STORE_MODE = "firebase"
            return FirestoreStore()
        except Exception:
            if IS_RENDER_ENV:
                raise
            STORE_MODE = "local"
            return LocalJsonStore(DATA_FILE)
    STORE_MODE = "local"
    return LocalJsonStore(DATA_FILE)


store = create_store()


def get_reservations() -> list[dict[str, Any]]:
    reservations = []
    for item in store.list_reservations():
        companions = item.get("companions", [])
        reservations.append(
            {
                "id": item["id"],
                "holder_name": item["holder_name"],
                "holder_email": item.get("holder_email", ""),
                "holder_phone": item.get("holder_phone", ""),
                "created_at": item["created_at"],
                "created_at_display": format_datetime(item["created_at"]),
                "terms_accepted_at": item.get("terms_accepted_at", ""),
                "companions": companions,
                "total_people": 1 + len(companions),
            }
        )
    return reservations


def build_dashboard_data(reservations: list[dict[str, Any]]) -> dict[str, int]:
    holder_count = len(reservations)
    companion_count = sum(len(item["companions"]) for item in reservations)
    total_people = holder_count + companion_count
    return {
        "holder_count": holder_count,
        "companion_count": companion_count,
        "total_people": total_people,
    }


def is_panel_authenticated() -> bool:
    return session.get("panel_authenticated") is True


def require_panel_login(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if not is_panel_authenticated():
            return redirect(url_for("panel_login", next=request.path))
        return view_func(*args, **kwargs)

    return wrapped_view


def send_confirmation_email(reservation: dict[str, Any]) -> None:
    if not (
        ZOHO_SMTP_USERNAME
        and ZOHO_SMTP_PASSWORD
        and ZOHO_SMTP_FROM_EMAIL
        and reservation.get("holder_email")
    ):
        return

    total_people = 1 + len(reservation.get("companions", []))
    companion_lines = []
    for companion in reservation.get("companions", []):
        phone = companion.get("phone") or "Não informado"
        companion_lines.append(f"- {companion.get('name', '')} | {phone}")

    companion_text = "\n".join(companion_lines) if companion_lines else "- Nenhum acompanhante"
    body = f"""Olá, {reservation['holder_name']}!

Sua reserva para o evento do Estância Parque Ecológico das Águas foi confirmada.

Data da reserva: 19/07/2026
Titular: {reservation['holder_name']}
E-mail: {reservation['holder_email']}
Telefone: {reservation['holder_phone']}
Total de pessoas: {total_people}

Acompanhantes:
{companion_text}

Regras importantes:
- Este agendamento vale somente para o dia 19/07/2026.
- Os termos finais do evento ainda serão atualizados pela equipe responsável.

Dúvidas ou esclarecimentos:
Consulte a equipe do Estância Parque Ecológico das Águas.
"""

    message = EmailMessage()
    message["Subject"] = "Confirmação da sua reserva - Estância Parque Ecológico das Águas"
    message["From"] = (
        f"{ZOHO_SMTP_FROM_NAME} <{ZOHO_SMTP_FROM_EMAIL}>"
        if ZOHO_SMTP_FROM_NAME
        else ZOHO_SMTP_FROM_EMAIL
    )
    message["To"] = reservation["holder_email"]
    message["Reply-To"] = ZOHO_SMTP_FROM_EMAIL
    if ZOHO_SMTP_FROM_EMAIL and ZOHO_SMTP_FROM_EMAIL != reservation["holder_email"]:
        message["Bcc"] = ZOHO_SMTP_FROM_EMAIL
    message.set_content(body)

    attempts: list[tuple[str, int, bool]] = []
    attempts.append((ZOHO_SMTP_HOST, ZOHO_SMTP_PORT, ZOHO_SMTP_USE_SSL))
    if (ZOHO_SMTP_HOST, 587, False) not in attempts:
        attempts.append((ZOHO_SMTP_HOST, 587, False))
    if (ZOHO_SMTP_HOST, 465, True) not in attempts:
        attempts.append((ZOHO_SMTP_HOST, 465, True))

    last_error: Exception | None = None
    for host, port, use_ssl in attempts:
        try:
            if use_ssl:
                with smtplib.SMTP_SSL(host, port, timeout=EMAIL_SEND_TIMEOUT_SECONDS) as smtp:
                    smtp.login(ZOHO_SMTP_USERNAME, ZOHO_SMTP_PASSWORD)
                    smtp.send_message(message)
                    return
            else:
                with smtplib.SMTP(host, port, timeout=EMAIL_SEND_TIMEOUT_SECONDS) as smtp:
                    smtp.ehlo()
                    smtp.starttls()
                    smtp.ehlo()
                    smtp.login(ZOHO_SMTP_USERNAME, ZOHO_SMTP_PASSWORD)
                    smtp.send_message(message)
                    return
        except Exception as exc:
            last_error = exc

    if last_error is not None:
        raise last_error


@app.route("/", methods=["GET"])
def home():
    return redirect(url_for("reservation_page"))


@app.route("/reserva", methods=["GET"])
def reservation_page():
    return render_template(
        "reserva.html",
        page_title=RESERVATION_TITLE,
        reservation_title=RESERVATION_TITLE,
        reservation_subtitle=RESERVATION_SUBTITLE,
        event_date_label=EVENT_DATE_LABEL,
        terms_text=TERMS_TEXT,
    )


@app.route("/painel", methods=["GET"])
@require_panel_login
def panel_page():
    reservations = get_reservations()
    return render_template(
        "painel.html",
        page_title=PANEL_TITLE,
        event_date_label=EVENT_DATE_LABEL,
        reservations=reservations,
        stats=build_dashboard_data(reservations),
    )


@app.route("/painel/login", methods=["GET", "POST"])
def panel_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if username == PANEL_USERNAME and password == PANEL_PASSWORD:
            session["panel_authenticated"] = True
            next_url = request.form.get("next") or url_for("panel_page")
            return redirect(next_url)
        flash("Usuário ou senha inválidos.", "error")

    if is_panel_authenticated():
        return redirect(url_for("panel_page"))

    return render_template(
        "painel_login.html",
        page_title="Login do Painel",
        next_url=request.args.get("next", url_for("panel_page")),
    )


@app.route("/painel/logout", methods=["POST"])
def panel_logout():
    session.pop("panel_authenticated", None)
    return redirect(url_for("panel_login"))


@app.route("/reservations", methods=["POST"])
def create_reservation():
    holder_name = request.form.get("holder_name", "").strip()
    holder_email = request.form.get("holder_email", "").strip()
    holder_phone = request.form.get("holder_phone", "").strip()
    companion_names = request.form.getlist("companion_name[]")
    companion_phones = request.form.getlist("companion_phone[]")
    terms_accepted = request.form.get("terms_accepted", "").strip()

    if not holder_name:
        flash("O nome do titular é obrigatório.", "error")
        return redirect(url_for("reservation_page"))

    if not holder_email:
        flash("O e-mail do titular é obrigatório.", "error")
        return redirect(url_for("reservation_page"))

    if not holder_phone:
        flash("O telefone do titular é obrigatório.", "error")
        return redirect(url_for("reservation_page"))

    if terms_accepted != "yes":
        flash("É necessário aceitar os termos antes de confirmar.", "error")
        return redirect(url_for("reservation_page"))

    companions = []
    for name, phone in zip(companion_names, companion_phones):
        cleaned_name = name.strip()
        cleaned_phone = phone.strip()
        if cleaned_name:
            companions.append({"name": cleaned_name, "phone": cleaned_phone})

    reservation = store.create_reservation(
        holder_name,
        holder_email,
        holder_phone,
        companions,
        current_timestamp(),
    )

    email_sent = True
    try:
        send_confirmation_email(reservation)
    except Exception:
        email_sent = False
        app.logger.exception("Falha ao enviar e-mail de confirmação.")

    if email_sent:
        flash("Reserva salva com sucesso. O e-mail de confirmação foi enviado.", "success")
    else:
        flash("Reserva salva com sucesso, mas o e-mail de confirmação não pôde ser enviado agora.", "error")
    return redirect(url_for("reservation_page"))


@app.route("/export.xlsx", methods=["GET"])
@require_panel_login
def export_excel():
    reservations = list(reversed(get_reservations()))

    workbook = Workbook()
    reservation_sheet = workbook.active
    reservation_sheet.title = "Titulares"
    reservation_sheet.append(
        ["Reserva", "Nome do titular", "E-mail", "Telefone", "Criado em", "Termos aceitos em"]
    )

    for row in reservations:
        reservation_sheet.append(
            [
                row["id"],
                row["holder_name"],
                row["holder_email"],
                row["holder_phone"],
                row["created_at"],
                row["terms_accepted_at"],
            ]
        )

    companion_sheet = workbook.create_sheet("Acompanhantes")
    companion_sheet.append(["Reserva", "Nome", "Telefone"])
    for row in reservations:
        for companion in row["companions"]:
            companion_sheet.append([row["id"], companion["name"], companion["phone"]])

    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="reservas_ingresso.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=APP_PORT)
