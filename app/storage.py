import os
import uuid
from pathlib import Path

from storage3.exceptions import StorageApiError
from supabase import Client, create_client

BUCKET = "documents"

_client: Client = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_KEY"],   # server-side only
)


def upload_pdf(user_id: uuid.UUID, doc_id: uuid.UUID, data: bytes) -> str:
    path = f"{user_id}/{doc_id}.pdf"
    _client.storage.from_(BUCKET).upload(
        path, data, {"content-type": "application/pdf"}
    )
    return path


def download_to_temp(storage_path: str) -> Path:
    data = _client.storage.from_(BUCKET).download(storage_path)
    tmp = Path("/tmp") / Path(storage_path).name
    tmp.write_bytes(data)
    return tmp


def signed_url(
    storage_path: str, expires_seconds: int = 300
) -> tuple[str | None, Exception | None]:
    """Return (url, None) on success, or (None, error) on any failure."""
    try:
        res = _client.storage.from_(BUCKET).create_signed_url(
            storage_path, expires_seconds
        )
        return res["signedURL"], None
    except StorageApiError as e:
        # e.status is 404 for a missing object, 400 for a bad request, etc.
        # (it can be a str like "404" — the router normalizes it)
        return None, e
    except Exception as e:  # noqa: BLE001 - surface any failure instead of a 500
        # httpx network errors, JSON parse failures, unexpected stuff
        return None, e


def delete_object(storage_path: str) -> None:
    _client.storage.from_(BUCKET).remove([storage_path])