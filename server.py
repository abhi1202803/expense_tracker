import argparse
import hashlib
import json
import threading
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import uuid4


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DEFAULT_DB_PATH = BASE_DIR / "expenses.json"


class ValidationError(Exception):
    pass


class IdempotencyConflict(Exception):
    pass


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_amount_to_cents(raw_amount: Any) -> int:
    if raw_amount is None:
        raise ValidationError("Amount is required.")

    try:
        amount = Decimal(str(raw_amount))
    except (InvalidOperation, ValueError):
        raise ValidationError("Amount must be a valid number.") from None

    if amount <= 0:
        raise ValidationError("Amount must be greater than zero.")

    quantized = amount.quantize(Decimal("0.01"))
    if quantized != amount:
        raise ValidationError("Amount can have at most two decimal places.")

    return int(quantized * 100)


def format_cents(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    absolute = abs(cents)
    whole, fraction = divmod(absolute, 100)
    return f"{sign}{whole}.{fraction:02d}"


def normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValidationError("Request body must be a JSON object.")

    category = str(payload.get("category", "")).strip()
    description = str(payload.get("description", "")).strip()
    raw_date = str(payload.get("date", "")).strip()

    if not category:
        raise ValidationError("Category is required.")
    if not raw_date:
        raise ValidationError("Date is required.")

    try:
        parsed_date = date.fromisoformat(raw_date)
    except ValueError:
        raise ValidationError("Date must use YYYY-MM-DD format.") from None

    return {
        "amount_cents": parse_amount_to_cents(payload.get("amount")),
        "category": category,
        "description": description,
        "date": parsed_date.isoformat(),
    }


def fingerprint_payload(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class CreateExpenseResult:
    expense: dict[str, Any]
    created: bool


class ExpenseStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self._initialize()

    def _initialize(self) -> None:
        if self.db_path.exists():
            return

        self._write_data({"expenses": []})

    def _read_data(self) -> dict[str, Any]:
        if not self.db_path.exists():
            return {"expenses": []}

        raw = self.db_path.read_text(encoding="utf-8")
        if not raw.strip():
            return {"expenses": []}

        return json.loads(raw)

    def _write_data(self, data: dict[str, Any]) -> None:
        self.db_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def create_expense(self, payload: dict[str, Any], idempotency_key: str) -> CreateExpenseResult:
        key = (idempotency_key or "").strip()
        if not key:
            raise ValidationError("Idempotency-Key header or idempotency_key field is required.")

        normalized = normalize_payload(payload)
        request_fingerprint = fingerprint_payload(normalized)
        created_at = utc_now_iso()

        with self.lock:
            data = self._read_data()
            expenses = data["expenses"]

            existing = next((expense for expense in expenses if expense["idempotency_key"] == key), None)
            if existing:
                if existing["request_fingerprint"] != request_fingerprint:
                    raise IdempotencyConflict("This idempotency key was already used for a different expense.")
                return CreateExpenseResult(expense=self._public_expense(existing), created=False)

            stored_expense = {
                "id": str(uuid4()),
                "amount_cents": normalized["amount_cents"],
                "category": normalized["category"],
                "description": normalized["description"],
                "date": normalized["date"],
                "created_at": created_at,
                "idempotency_key": key,
                "request_fingerprint": request_fingerprint,
            }
            expenses.append(stored_expense)
            self._write_data(data)

        return CreateExpenseResult(expense=self._public_expense(stored_expense), created=True)

    def list_expenses(self, category: str | None = None, sort: str | None = None) -> list[dict[str, Any]]:
        with self.lock:
            expenses = [expense.copy() for expense in self._read_data()["expenses"]]

        if category:
            normalized_category = category.strip().lower()
            expenses = [expense for expense in expenses if expense["category"].lower() == normalized_category]

        if sort == "date_desc":
            expenses.sort(key=lambda expense: (expense["date"], expense["created_at"]), reverse=True)
        else:
            expenses.sort(key=lambda expense: expense["created_at"], reverse=True)

        return [self._public_expense(expense) for expense in expenses]

    @staticmethod
    def _public_expense(expense: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": expense["id"],
            "amount": format_cents(expense["amount_cents"]),
            "category": expense["category"],
            "description": expense["description"],
            "date": expense["date"],
            "created_at": expense["created_at"],
        }


class ExpenseTrackerHandler(BaseHTTPRequestHandler):
    server_version = "ExpenseTracker/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/api/expenses":
            self.handle_list_expenses(parsed)
            return

        if parsed.path == "/health":
            self.send_json(HTTPStatus.OK, {"status": "ok"})
            return

        self.serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path != "/api/expenses":
            self.send_error_json(HTTPStatus.NOT_FOUND, "Route not found.")
            return

        raw_body = self.read_json_body()
        if raw_body is None:
            return

        idempotency_key = self.headers.get("Idempotency-Key") or raw_body.get("idempotency_key")

        try:
            result = self.server.store.create_expense(raw_body, idempotency_key)
        except ValidationError as error:
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(error))
            return
        except IdempotencyConflict as error:
            self.send_error_json(HTTPStatus.CONFLICT, str(error))
            return

        status = HTTPStatus.CREATED if result.created else HTTPStatus.OK
        self.send_json(
            status,
            {
                "expense": result.expense,
                "idempotency_replay": not result.created,
            },
        )

    def handle_list_expenses(self, parsed) -> None:
        query = parse_qs(parsed.query)
        category = query.get("category", [None])[0]
        sort = query.get("sort", [None])[0]

        if sort not in (None, "date_desc"):
            self.send_error_json(HTTPStatus.BAD_REQUEST, "Unsupported sort value.")
            return

        expenses = self.server.store.list_expenses(category=category, sort=sort)
        self.send_json(HTTPStatus.OK, {"expenses": expenses})

    def read_json_body(self) -> dict[str, Any] | None:
        content_length = self.headers.get("Content-Length")
        if not content_length:
            self.send_error_json(HTTPStatus.BAD_REQUEST, "Request body is required.")
            return None

        try:
            length = int(content_length)
        except ValueError:
            self.send_error_json(HTTPStatus.BAD_REQUEST, "Invalid Content-Length header.")
            return None

        try:
            raw_body = self.rfile.read(length)
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_error_json(HTTPStatus.BAD_REQUEST, "Request body must be valid JSON.")
            return None

        if not isinstance(payload, dict):
            self.send_error_json(HTTPStatus.BAD_REQUEST, "Request body must be a JSON object.")
            return None

        return payload

    def serve_static(self, raw_path: str) -> None:
        relative_path = "index.html" if raw_path == "/" else raw_path.lstrip("/")
        candidate = (self.server.static_dir / relative_path).resolve()

        try:
            candidate.relative_to(self.server.static_dir.resolve())
        except ValueError:
            self.send_error_json(HTTPStatus.NOT_FOUND, "File not found.")
            return

        if not candidate.exists() or not candidate.is_file():
            self.send_error_json(HTTPStatus.NOT_FOUND, "File not found.")
            return

        content_type = self.guess_content_type(candidate.suffix)
        body = candidate.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    @staticmethod
    def guess_content_type(suffix: str) -> str:
        return {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".json": "application/json; charset=utf-8",
        }.get(suffix.lower(), "application/octet-stream")

    def send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, status: HTTPStatus, message: str) -> None:
        self.send_json(status, {"error": message})

    def log_message(self, format: str, *args: Any) -> None:
        return


class ExpenseTrackerServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], handler_class, store: ExpenseStore, static_dir: Path):
        super().__init__(server_address, handler_class)
        self.store = store
        self.static_dir = static_dir


def build_server(host: str, port: int, db_path: Path) -> ExpenseTrackerServer:
    store = ExpenseStore(db_path)
    return ExpenseTrackerServer((host, port), ExpenseTrackerHandler, store=store, static_dir=STATIC_DIR)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Expense Tracker app.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = build_server(args.host, args.port, Path(args.db))
    print(f"Expense Tracker running on http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
