from slowapi import Limiter
from slowapi.util import get_remote_address


def user_or_ip(request) -> str:
    """Limit per user, not per IP.

    Behind Railway's proxy every request arrives from the proxy's address, so
    an IP key would make all users share one limit. Every limited route needs
    a login, and FastAPI runs get_current_user (which sets request.state.user_id)
    before the @limiter.limit check, so the id here is a verified one.
    """
    user_id = getattr(request.state, "user_id", None)
    return str(user_id) if user_id else get_remote_address(request)


limiter = Limiter(key_func=user_or_ip, default_limits=[])
