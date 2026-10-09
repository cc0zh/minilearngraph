"""ASGI boundary: check local provenance before parsing or invoking routes."""

import json
import math
import sqlite3
from typing import Any

from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from mini_learngraph.api.settings import valid_host

MAX_BODY_BYTES = 512 * 1024
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def error_body(
    code: str, message: str, *, retryable: bool = False, issues: list | None = None
) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "details": {
            "resource_type": None,
            "resource_id": None,
            "expected_revision": None,
            "current_revision": None,
            "failure_reason": None,
            "issues": issues or [],
        },
        "retryable": retryable,
    }


def issue(path: list[str | int], code: str, message: str) -> dict[str, Any]:
    return {
        "path": path,
        "code": code,
        "message": message,
        "node_ids": [],
        "edge_indexes": [],
    }


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _invalid_constant(_: str) -> Any:
    raise ValueError("invalid number")


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("invalid number")
    return number


def validate_json(body: bytes) -> None:
    # Decode explicitly: json.loads(bytes) would also accept UTF-16/32.
    value = json.loads(
        body.decode("utf-8"),
        object_pairs_hook=_unique_object,
        parse_constant=_invalid_constant,
        parse_float=_finite_float,
    )
    # Escaped unpaired surrogates are accepted by Python's JSON decoder, but
    # cannot be encoded as UTF-8 or safely stored/returned as contract text.
    def check_text(item: Any) -> None:
        if isinstance(item, str):
            item.encode("utf-8")
        elif isinstance(item, dict):
            for key, child in item.items():
                key.encode("utf-8")
                check_text(child)
        elif isinstance(item, list):
            for child in item:
                check_text(child)
    check_text(value)


def storage_busy(exc: sqlite3.Error) -> bool:
    code = getattr(exc, "sqlite_errorcode", None)
    return isinstance(code, int) and code & 0xFF in {
        sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED
    }


class SecurityBoundary:
    """Buffer bounded bodies once; check every chunk, not just Content-Length.

    This wrapper sits outside Starlette's exception middleware so safe internal
    errors are returned without an exception re-raise or traceback disclosure.
    """

    def __init__(self, app: ASGIApp, allowed_origins: list[str]):
        self.app = app
        self.allowed_origins = frozenset(allowed_origins)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = scope.get("headers", [])
        hosts = [v.decode("latin-1") for k, v in headers if k.lower() == b"host"]
        origins = [v.decode("latin-1") for k, v in headers if k.lower() == b"origin"]
        origin = origins[0] if len(origins) == 1 else None
        host_ok = len(hosts) == 1 and valid_host(hosts[0])
        same_origin = f"{scope.get('scheme', 'http')}://{hosts[0]}" if host_ok else None
        origin_ok = len(origins) <= 1 and (
            origin is None or origin in self.allowed_origins or origin == same_origin
        )
        started = False

        async def cors_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                response_headers = list(message.get("headers", []))
                if origin is not None and origin_ok and host_ok:
                    response_headers.extend([
                        (b"access-control-allow-origin", origin.encode("latin-1")),
                        (b"vary", b"Origin"),
                    ])
                message = {**message, "headers": response_headers}
            await send(message)

        async def reject(status: int, code: str, message: str) -> None:
            await JSONResponse(error_body(code, message), status)(scope, receive, cors_send)

        if not host_ok:
            await reject(403, "host_not_allowed", "Only local server hosts are allowed.")
            return
        if not origin_ok:
            await reject(403, "origin_not_allowed", "Origin is not allowed.")
            return

        method = scope["method"]
        preflight_methods = [
            v for k, v in headers if k.lower() == b"access-control-request-method"
        ]
        if method == "OPTIONS" and origins and preflight_methods:
            if len(preflight_methods) != 1 or preflight_methods[0] not in {
                b"GET", b"POST", b"PUT"
            }:
                await reject(405, "method_not_allowed", "Method is not allowed.")
                return
            requested = [
                v.decode("latin-1") for k, v in headers
                if k.lower() == b"access-control-request-headers"
            ]
            if len(requested) > 1 or any(
                name.strip().lower() != "content-type"
                for value in requested for name in value.split(",") if name.strip()
            ):
                await reject(403, "origin_not_allowed", "CORS headers are not allowed.")
                return
            await Response(status_code=200, headers={
                "Access-Control-Allow-Methods": "GET, POST, PUT",
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Max-Age": "600",
            })(scope, receive, cors_send)
            return

        if method in WRITE_METHODS:
            media = [v for k, v in headers if k.lower() == b"content-type"]
            if len(media) != 1 or media[0].split(b";", 1)[0].strip().lower() != b"application/json":
                await reject(415, "unsupported_media_type", "Content-Type must be application/json.")
                return

        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = await receive()
            if chunk["type"] == "http.disconnect":
                return
            data = chunk.get("body", b"")
            total += len(data)
            if total > MAX_BODY_BYTES:
                await reject(413, "payload_too_large", "Request body exceeds 512 KiB.")
                return
            if method == "GET" and data:
                payload = error_body("validation_failed", "GET requests must not have a body.",
                                     issues=[issue(["body"], "constraint", "Body is not allowed.")])
                await JSONResponse(payload, 422)(scope, receive, cors_send)
                return
            chunks.append(data)
            if not chunk.get("more_body", False):
                break
        body = b"".join(chunks)
        if method in WRITE_METHODS:
            try:
                validate_json(body)
            except (ValueError, UnicodeError, RecursionError, OverflowError):
                await reject(400, "invalid_json", "Body must be valid strict UTF-8 JSON.")
                return

        delivered = False

        async def replay() -> Message:
            nonlocal delivered
            if delivered:
                return await receive()
            delivered = True
            return {"type": "http.request", "body": body, "more_body": False}

        try:
            await self.app(scope, replay, cors_send)
        except Exception as exc:  # noqa: BLE001 -- HTTP boundary sanitizes defects; cancellation and exit propagate.
            if started:
                # A response cannot be replaced once headers have been sent.
                return
            if isinstance(exc, sqlite3.Error) and storage_busy(exc):
                payload = error_body("storage_busy", "Storage is temporarily busy.", retryable=True)
                status = 503
            else:
                payload = error_body("internal_error", "An internal error occurred.")
                status = 500
            await JSONResponse(payload, status)(scope, replay, cors_send)
