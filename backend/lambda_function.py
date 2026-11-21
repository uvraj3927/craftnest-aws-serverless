import json
import traceback
import uuid

from app.handlers import ApiError, create_order, get_orders, login, register
from app.logging_utils import log_event, set_request_id
from app.responses import response


def _route(event):
    # HTTP API payload v2 uses rawPath/requestContext.http.method.
    # REST API / HTTP API v1 commonly uses path/httpMethod.
    path = event.get("rawPath") or event.get("path") or "/"
    method = (
        (event.get("requestContext", {}).get("http", {}) or {}).get("method")
        or event.get("httpMethod")
        or "GET"
    )
    return method.upper(), path.rstrip("/") or "/"


def lambda_handler(event, context):
    request_id = (
        getattr(context, "aws_request_id", None)
        or event.get("requestContext", {}).get("requestId")
        or str(uuid.uuid4())
    )
    set_request_id(request_id)
    method, path = _route(event)

    if method == "OPTIONS":
        return response(204, {})

    try:
        routes = {
            ("POST", "/register"): register,
            ("POST", "/login"): login,
            ("POST", "/orders"): create_order,
            ("GET", "/orders"): get_orders,
        }
        handler = routes.get((method, path))
        if not handler:
            return response(404, {"message": "Route not found."})
        return handler(event)
    except ApiError as exc:
        return response(exc.status_code, {"message": exc.message})
    except Exception as exc:
        log_event("ERROR", "UNHANDLED_EXCEPTION", {
            "error": str(exc),
            "stack_trace": traceback.format_exc(),
            "method": method,
            "path": path,
        })
        return response(500, {"message": "An unexpected server error occurred."})
