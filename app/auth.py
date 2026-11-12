import uuid

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

security = HTTPBearer()
_issuer = f"{settings.supabase_url}/auth/v1"
_jwks_client = jwt.PyJWKClient(f"{_issuer}/.well-known/jwks.json")


async def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials = Depends(security),
) -> uuid.UUID:
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(creds.credentials)
        payload = jwt.decode(
            creds.credentials,
            signing_key.key,
            algorithms=["ES256"],
            audience="authenticated",
            issuer=_issuer,
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token expired")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"invalid token: {exc}")

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token has no subject")
    user_id = uuid.UUID(sub)
    request.state.user_id = user_id     # the rate limit key, see app/limiter.py
    return user_id