FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.6 /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /srv

COPY pyproject.toml uv.lock README.md ./
COPY app ./app
# alembic.ini and alembic/ ship too, so migrations can be run from the image.
COPY alembic.ini ./
COPY alembic ./alembic
# --no-dev: uv sync installs the dev group by default, which we don't want here.
RUN uv sync --frozen --no-editable --no-dev

ENV PATH="/opt/venv/bin:$PATH"

# Railway injects PORT at runtime, so the shell form is needed to expand it.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
