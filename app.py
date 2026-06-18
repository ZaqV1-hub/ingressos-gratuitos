from __future__ import annotations

import base64
import io
import json
import os
from abc import ABC, abstractmethod
from functools import wraps
from datetime import datetime
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

EVENT_DATE_LABEL = "17 de junho de 2025"
PANEL_TITLE = "Painel de Reservas"
RESERVATION_TITLE = "Reserva de Ingressos"
RESERVATION_SUBTITLE = "Preencha os dados para reservar seus ingressos"
PANEL_USERNAME = os.getenv("PANEL_USERNAME", "operador5979")
PANEL_PASSWORD = os.getenv("PANEL_PASSWORD", "reservas10")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "reserva-local-simples")


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
        holder_phone: str,
        companions: list[dict[str, str]],
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
        holder_phone: str,
        companions: list[dict[str, str]],
    ) -> dict[str, Any]:
        data = self.load_data()
        reservation = {
            "id": data["next_id"],
            "holder_name": holder_name,
            "holder_phone": holder_phone,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
                    "holder_phone": data.get("holder_phone", ""),
                    "created_at": data["created_at"],
                    "companions": data.get("companions", []),
                }
            )
        return sorted(reservations, key=lambda row: row["id"], reverse=True)

    def create_reservation(
        self,
        holder_name: str,
        holder_phone: str,
        companions: list[dict[str, str]],
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
                "holder_phone": holder_phone,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
    if STORAGE_BACKEND == "firebase":
        return FirestoreStore()
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
                "holder_phone": item.get("holder_phone", ""),
                "created_at": item["created_at"],
                "created_at_display": format_datetime(item["created_at"]),
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
    holder_phone = request.form.get("holder_phone", "").strip()
    companion_names = request.form.getlist("companion_name[]")
    companion_phones = request.form.getlist("companion_phone[]")

    if not holder_name:
        flash("O nome do titular é obrigatório.", "error")
        return redirect(url_for("reservation_page"))

    if not holder_phone:
        flash("O telefone do titular é obrigatório.", "error")
        return redirect(url_for("reservation_page"))

    companions = []
    for name, phone in zip(companion_names, companion_phones):
        cleaned_name = name.strip()
        cleaned_phone = phone.strip()
        if cleaned_name:
            companions.append({"name": cleaned_name, "phone": cleaned_phone})

    store.create_reservation(holder_name, holder_phone, companions)
    flash("Reserva salva com sucesso.", "success")
    return redirect(url_for("reservation_page"))


@app.route("/export.xlsx", methods=["GET"])
@require_panel_login
def export_excel():
    reservations = list(reversed(get_reservations()))

    workbook = Workbook()
    reservation_sheet = workbook.active
    reservation_sheet.title = "Titulares"
    reservation_sheet.append(["Reserva", "Nome do titular", "Telefone", "Criado em"])

    for row in reservations:
        reservation_sheet.append(
            [row["id"], row["holder_name"], row["holder_phone"], row["created_at"]]
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
    app.run(debug=False, port=APP_PORT)
