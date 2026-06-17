"""Authentication and role-based authorization for the gateway."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import logging
import secrets as secrets_lib
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from fastapi import Depends, HTTPException, Request, Response, WebSocket
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from src.config import settings

logger = logging.getLogger(__name__)
http_basic = HTTPBasic(auto_error=False)

UserRole = Literal["viewer", "investor", "admin"]

AUTH_COOKIE_NAME = "ia_gateway_auth"
AUTH_COOKIE_MAX_AGE_SECONDS = 12 * 60 * 60

ROLE_PERMISSIONS: dict[UserRole, frozenset[str]] = {
    "viewer": frozenset({"chat", "news"}),
    "investor": frozenset({"chat", "news", "market", "forex", "simulation", "reports"}),
    "admin": frozenset(
        {
            "chat",
            "news",
            "market",
            "forex",
            "simulation",
            "reports",
            "portfolio",
            "trading",
            "admin",
        }
    ),
}

TOOL_PERMISSIONS: dict[str, str] = {
    "get_stock_data": "market",
    "get_crypto_data": "market",
    "get_market_overview": "market",
    "get_technical_indicators": "market",
    "get_options_chain": "market",
    "search_ticker": "market",
    "get_earnings_calendar": "market",
    "get_forex_data": "forex",
    "get_forex_rates": "forex",
    "get_central_bank_rates": "forex",
    "search_market_news": "news",
    "search_stored_news": "news",
    "get_latest_news": "news",
    "get_portfolio_summary": "portfolio",
    "get_account_info": "portfolio",
    "get_trade_history": "portfolio",
    "run_simulation": "simulation",
    "generate_report": "reports",
    "execute_trade": "trading",
    "confirm_trade": "trading",
    "cancel_order": "trading",
    "set_trading_mode": "trading",
}


@dataclass(frozen=True)
class AuthContext:
    subject: str
    username: str
    email: str
    role: UserRole
    groups: tuple[str, ...]
    auth_method: str
    permissions: frozenset[str]
    internal: bool = False

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions or "admin" in self.permissions

    def to_public_dict(self) -> dict:
        return {
            "subject": self.subject,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "groups": list(self.groups),
            "auth_method": self.auth_method,
            "permissions": sorted(self.permissions),
            "internal": self.internal,
        }


class WebSocketAuthError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def client_ip(req: Request | WebSocket) -> str:
    headers = req.headers
    client = req.client
    xff = headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[-1].strip()
    return client.host if client else "0.0.0.0"


def require_permission(permission: str):
    def dependency(auth: AuthContext = Depends(require_access)) -> AuthContext:
        if not auth.has_permission(permission):
            raise HTTPException(
                status_code=403,
                detail=(f"Permission denied: role '{auth.role}' cannot access '{permission}'."),
            )
        return auth

    return dependency


def require_access(
    request: Request,
    response: Response,
    credentials: HTTPBasicCredentials | None = Depends(http_basic),
) -> AuthContext:
    ip = client_ip(request)
    if settings.is_development:
        return _context_for_role("admin", "development", "development", internal=True)

    if settings.is_internal_ip(ip):
        return _context_for_role("admin", "internal", ip, internal=True)

    if not settings.is_ip_allowed(ip):
        logger.warning("Blocked %s", ip)
        raise HTTPException(status_code=403, detail="Access denied")

    context = _authenticate_external(
        headers=request.headers,
        cookies=request.cookies,
        credentials=credentials,
        response=response,
        request=request,
    )
    if context:
        return context

    if settings.auth_mode == "cognito":
        raise HTTPException(status_code=401, detail="Cognito authentication required")

    raise _basic_auth_challenge()


def authenticate_websocket(websocket: WebSocket) -> AuthContext:
    ip = client_ip(websocket)
    if settings.is_development:
        return _context_for_role("admin", "development", "development", internal=True)

    if settings.is_internal_ip(ip):
        return _context_for_role("admin", "internal", ip, internal=True)

    if not settings.is_ip_allowed(ip):
        raise WebSocketAuthError("Access denied")

    credentials = None
    parsed_basic = _parse_basic_authorization(websocket.headers.get("Authorization"))
    if parsed_basic:
        credentials = HTTPBasicCredentials(
            username=parsed_basic[0],
            password=parsed_basic[1],
        )

    context = _authenticate_external(
        headers=websocket.headers,
        cookies=websocket.cookies,
        credentials=credentials,
    )
    if context:
        return context

    if settings.auth_mode == "cognito":
        raise WebSocketAuthError("Cognito authentication required")

    raise WebSocketAuthError("Authentication required")


def can_call_tool(auth_context: AuthContext | None, tool_name: str) -> bool:
    if auth_context is None:
        return True
    permission = TOOL_PERMISSIONS.get(tool_name, "admin")
    return auth_context.has_permission(permission)


def allowed_tool_definitions(tools: list[dict], auth_context: AuthContext | None) -> list[dict]:
    if auth_context is None:
        return tools
    return [tool for tool in tools if can_call_tool(auth_context, tool["name"])]


def authorization_prompt(auth_context: AuthContext | None) -> str:
    if auth_context is None:
        return ""
    capabilities = ", ".join(sorted(auth_context.permissions))
    return (
        "\n\n## Current User Authorization\n"
        f"- Role: {auth_context.role}\n"
        f"- Groups: {', '.join(auth_context.groups) or 'none'}\n"
        f"- Allowed capabilities: {capabilities}\n"
        "- Do not request or infer data from tools outside those capabilities. "
        "If the user asks for restricted data or actions, explain that their role "
        "does not permit it."
    )


def _authenticate_external(
    *,
    headers,
    cookies,
    credentials: HTTPBasicCredentials | None,
    response: Response | None = None,
    request: Request | None = None,
) -> AuthContext | None:
    if settings.auth_mode in ("cognito", "hybrid"):
        context = _context_from_cognito(headers)
        if context:
            return context

    if settings.auth_mode in ("basic", "hybrid"):
        if _is_auth_cookie_valid(cookies.get(AUTH_COOKIE_NAME)):
            return _context_for_role(
                settings.basic_auth_role,
                settings.ui_auth_username,
                settings.ui_auth_username,
                auth_method="basic-cookie",
            )
        if _is_basic_credentials_valid(credentials):
            if response is not None and request is not None:
                _set_auth_cookie(response, request)
            return _context_for_role(
                settings.basic_auth_role,
                settings.ui_auth_username,
                settings.ui_auth_username,
                auth_method="basic",
            )
    return None


def _context_from_cognito(headers) -> AuthContext | None:
    token = headers.get("x-amzn-oidc-accesstoken")
    if not token:
        authorization = headers.get("Authorization", "")
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer":
            token = value
    if not token:
        return None

    claims = _validate_cognito_token(token)
    if not claims:
        return None

    groups = _normalise_groups(claims.get(settings.cognito_groups_claim, []))
    role = _role_from_groups(groups)
    username = (
        claims.get("cognito:username")
        or claims.get("username")
        or claims.get("email")
        or claims.get("sub")
        or "cognito-user"
    )
    email = claims.get("email", "")
    subject = claims.get("sub", username)
    return AuthContext(
        subject=subject,
        username=username,
        email=email,
        role=role,
        groups=tuple(groups),
        auth_method="cognito",
        permissions=ROLE_PERMISSIONS[role],
    )


def _validate_cognito_token(token: str) -> dict | None:
    if not settings.cognito_user_pool_id or not settings.cognito_app_client_id:
        logger.warning("Cognito auth requested but Cognito settings are incomplete")
        return None

    try:
        import jwt
    except ImportError:
        logger.error("PyJWT is required for Cognito authentication")
        return None

    issuer = (
        f"https://cognito-idp.{settings.aws_region}.amazonaws.com/{settings.cognito_user_pool_id}"
    )
    try:
        signing_key = _jwks_client(issuer).get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            issuer=issuer,
            options={"verify_aud": False},
        )
    except Exception as exc:
        logger.warning("Invalid Cognito token: %s", exc)
        return None

    if not _claim_matches_client(claims):
        logger.warning("Cognito token client id did not match configured app client")
        return None
    return claims


@lru_cache(maxsize=8)
def _jwks_client(issuer: str):
    from jwt import PyJWKClient

    return PyJWKClient(f"{issuer}/.well-known/jwks.json")


def _claim_matches_client(claims: dict) -> bool:
    expected = settings.cognito_app_client_id
    audience = claims.get("aud")
    client_id = claims.get("client_id")
    if client_id == expected:
        return True
    if audience == expected:
        return True
    if isinstance(audience, list) and expected in audience:
        return True
    return False


def _normalise_groups(raw_groups) -> list[str]:
    if isinstance(raw_groups, str):
        groups = [entry.strip() for entry in raw_groups.split(",")]
    elif isinstance(raw_groups, list):
        groups = [str(entry).strip() for entry in raw_groups]
    else:
        groups = []
    return [group for group in groups if group]


def _role_from_groups(groups: list[str]) -> UserRole:
    normalised = {group.lower() for group in groups}
    if normalised & _configured_groups(settings.auth_admin_groups):
        return "admin"
    if normalised & _configured_groups(settings.auth_investor_groups):
        return "investor"
    if normalised & _configured_groups(settings.auth_viewer_groups):
        return "viewer"
    return "viewer"


def _configured_groups(value: str) -> set[str]:
    return {entry.strip().lower() for entry in value.split(",") if entry.strip()}


def _context_for_role(
    role: UserRole,
    username: str,
    subject: str,
    *,
    auth_method: str = "internal",
    internal: bool = False,
) -> AuthContext:
    return AuthContext(
        subject=subject,
        username=username,
        email="",
        role=role,
        groups=(role,),
        auth_method=auth_method,
        permissions=ROLE_PERMISSIONS[role],
        internal=internal,
    )


def _is_basic_credentials_valid(credentials: HTTPBasicCredentials | None) -> bool:
    if credentials is None:
        return False
    return _is_basic_auth_valid(credentials.username, credentials.password)


def _is_basic_auth_valid(username: str, password: str) -> bool:
    configured_username = settings.ui_auth_username
    configured_password = settings.ui_auth_password
    if not configured_username or not configured_password:
        return False
    return secrets_lib.compare_digest(
        username.encode("utf-8"), configured_username.encode("utf-8")
    ) and secrets_lib.compare_digest(password.encode("utf-8"), configured_password.encode("utf-8"))


def _auth_cookie_signature() -> str:
    if not settings.ui_auth_password:
        return ""
    message = f"{settings.ui_auth_username}:gateway-ui".encode()
    return hmac.new(settings.ui_auth_password.encode("utf-8"), message, hashlib.sha256).hexdigest()


def _is_auth_cookie_valid(cookie_value: str | None) -> bool:
    signature = _auth_cookie_signature()
    if not cookie_value or not signature:
        return False
    return secrets_lib.compare_digest(cookie_value, signature)


def _set_auth_cookie(response: Response, request: Request) -> None:
    signature = _auth_cookie_signature()
    if not signature:
        return
    forwarded_proto = request.headers.get("X-Forwarded-Proto", "")
    secure = request.url.scheme == "https" or forwarded_proto.split(",")[-1].strip() == "https"
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=signature,
        max_age=AUTH_COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        samesite="strict",
        secure=secure,
    )


def _basic_auth_challenge() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="Authentication required",
        headers={"WWW-Authenticate": 'Basic realm="investments-assistant"'},
    )


def _parse_basic_authorization(header_value: str | None) -> tuple[str, str] | None:
    if not header_value:
        return None
    scheme, _, token = header_value.partition(" ")
    if scheme.lower() != "basic" or not token:
        return None
    try:
        decoded = base64.b64decode(token, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return None
    username, separator, password = decoded.partition(":")
    if not separator:
        return None
    return username, password
