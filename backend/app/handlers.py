import json
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from botocore.exceptions import ClientError

from . import repository
from .logging_utils import log_event
from .responses import response
from .security import create_session_token, hash_password, verify_password, verify_session_token

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ApiError(Exception):
    def __init__(self, status_code, message):
        self.status_code = status_code
        self.message = message


def _body(event):
    raw = event.get("body")
    if not raw:
        return {}
    if event.get("isBase64Encoded"):
        import base64
        raw = base64.b64decode(raw).decode("utf-8")
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        raise ApiError(400, "Request body must be valid JSON.")
    if not isinstance(parsed, dict):
        raise ApiError(400, "Request body must be a JSON object.")
    return parsed


def _normalise_email(value):
    if not isinstance(value, str):
        raise ApiError(400, "A valid email address is required.")
    email = value.strip().lower()
    if len(email) > 254 or not _EMAIL_RE.match(email):
        raise ApiError(400, "A valid email address is required.")
    return email


def _auth_claims(event):
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    authorization = headers.get("authorization", "")
    if not authorization.lower().startswith("bearer "):
        raise ApiError(401, "Authentication is required.")
    claims = verify_session_token(authorization[7:].strip())
    if not claims:
        raise ApiError(401, "Session is invalid or expired.")
    return claims


def register(event):
    data = _body(event)
    name = data.get("name")
    email = _normalise_email(data.get("email"))
    password = data.get("password")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100:
        raise ApiError(400, "Name is required (maximum 100 characters).")
    if not isinstance(password, str) or len(password) < 8 or len(password) > 128:
        raise ApiError(400, "Password must be between 8 and 128 characters.")
    user = {
        "user_id": str(uuid.uuid4()),
        "name": name.strip(),
        "email": email,
        "password_hash": hash_password(password),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        repository.create_user(user)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            raise ApiError(409, "An account with this email already exists.")
        raise
    log_event("INFO", "USER_REGISTERED", {"user_id": user["user_id"], "email": email})
    return response(201, {
        "message": "Registration successful.",
        "user": {"user_id": user["user_id"], "name": user["name"], "email": email},
    })


def login(event):
    data = _body(event)
    email = _normalise_email(data.get("email"))
    password = data.get("password")
    if not isinstance(password, str) or not password:
        raise ApiError(400, "Password is required.")
    user = repository.get_user(email)
    if not user:
        log_event("WARNING", "LOGIN_FAILED", {
            "email": email, "reason": "USER_NOT_FOUND",
        })
        raise ApiError(401, "Invalid email or password.")
    if not verify_password(password, user.get("password_hash", "")):
        log_event("WARNING", "LOGIN_FAILED", {
            "email": email, "reason": "INVALID_PASSWORD",
        })
        raise ApiError(401, "Invalid email or password.")
    token = create_session_token(user)
    log_event("INFO", "LOGIN_SUCCESS", {"user_id": user["user_id"], "email": email})
    return response(200, {
        "message": "Login successful.",
        "token": token,
        "user": {"user_id": user["user_id"], "name": user["name"], "email": email},
    })


def _validated_order_items(raw_items):
    if not isinstance(raw_items, list) or not raw_items:
        raise ApiError(400, "Your cart is empty.")
    if len(raw_items) > 50:
        raise ApiError(400, "An order cannot contain more than 50 line items.")
    items, total = [], Decimal("0.00")
    for entry in raw_items:
        if not isinstance(entry, dict):
            raise ApiError(400, "Each order item must be an object.")
        product_id = entry.get("product_id") or entry.get("productId")
        quantity = entry.get("quantity")
        if not isinstance(product_id, (str, int)) or not str(product_id).strip():
            raise ApiError(400, "Each item needs a product_id.")
        if isinstance(quantity, bool) or not isinstance(quantity, int) or not 1 <= quantity <= 99:
            raise ApiError(400, "Item quantity must be an integer from 1 to 99.")
        # Client-supplied price is accepted for this schema-only starter.
        # Production must look up price/discount from a trusted product catalog.
        try:
            unit_price = Decimal(str(entry.get("unit_price", entry.get("unitPrice"))))
        except (InvalidOperation, TypeError):
            raise ApiError(400, "Each item needs a valid unit_price.")
        if not unit_price.is_finite() or unit_price <= 0 or unit_price > Decimal("1000000"):
            raise ApiError(400, "Item unit_price is outside the allowed range.")
        line_total = (unit_price * quantity).quantize(Decimal("0.01"))
        total += line_total
        items.append({
            "product_id": str(product_id),
            "quantity": quantity,
            "unit_price": unit_price,
            "line_total": line_total,
        })
    return items, total.quantize(Decimal("0.01"))


def create_order(event):
    claims = _auth_claims(event)
    data = _body(event)
    items, total = _validated_order_items(data.get("items"))
    address = data.get("shipping_address") or data.get("shippingAddress")
    if not isinstance(address, dict):
        raise ApiError(400, "A shipping_address object is required.")
    required = ("name", "phone", "address")
    if any(not isinstance(address.get(k), str) or not address[k].strip() for k in required):
        raise ApiError(400, "Shipping name, phone and address are required.")
    order = {
        "order_id": str(uuid.uuid4()),
        "user_email": claims["email"],
        "items": items,
        "total_amount": total,
        "shipping_address": {k: address[k].strip() for k in required},
        "status": "CONFIRMED",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        repository.create_order(order)
    except Exception:
        log_event("ERROR", "ORDER_FAILED", {
            "reason": "DYNAMODB_FAILURE", "user_email": claims["email"],
        })
        raise

    try:
        repository.publish_order_confirmation(order)
    except Exception:
        # The order is already durable in DynamoDB. Return a clear partial-success
        # response rather than pretending the order write was rolled back.
        log_event("ERROR", "ORDER_FAILED", {
            "reason": "SNS_FAILURE", "order_id": order["order_id"],
            "user_email": claims["email"],
        })
        return response(202, {
            "message": "Order was saved, but confirmation notification could not be sent.",
            "order_id": order["order_id"],
            "notification_status": "PENDING",
        })

    log_event("INFO", "ORDER_CREATED", {
        "order_id": order["order_id"],
        "total_amount": str(total),
        "user_email": claims["email"],
    })
    return response(201, {
        "message": "Order created successfully.",
        "order_id": order["order_id"],
        "total_amount": str(total),
        "status": order["status"],
    })


def get_orders(event):
    claims = _auth_claims(event)
    orders = repository.list_user_orders(claims["email"])
    safe_orders = []
    for order in orders:
        safe_orders.append({
            "order_id": order.get("order_id"),
            "user_email": order.get("user_email"),
            "items": order.get("items", []),
            "total_amount": str(order.get("total_amount", "0")),
            "shipping_address": order.get("shipping_address", {}),
            "status": order.get("status"),
            "created_at": order.get("created_at"),
        })
    return response(200, {"orders": safe_orders})
