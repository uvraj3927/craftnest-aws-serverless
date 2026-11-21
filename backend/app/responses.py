import json

from .config import CORS_ALLOW_ORIGIN


def response(status_code: int, body: dict, headers: dict | None = None):
    base_headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": CORS_ALLOW_ORIGIN,
        "Access-Control-Allow-Headers": "Content-Type,Authorization",
        "Access-Control-Allow-Methods": "OPTIONS,GET,POST",
        "Access-Control-Max-Age": "86400",
        "Vary": "Origin",
    }
    if headers:
        base_headers.update(headers)
    return {
        "statusCode": status_code,
        "headers": base_headers,
        "body": json.dumps(body, default=str),
        "isBase64Encoded": False,
    }
