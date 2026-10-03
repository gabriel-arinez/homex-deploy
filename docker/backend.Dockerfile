# syntax=docker/dockerfile:1.7
FROM ghcr.io/astral-sh/uv:0.8.22-python3.11-bookworm-slim@sha256:2c4b9b297693b09abc2286fb3c1df78e0de9d48d371abc3e83f9b1913037801a

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1 \
    PATH="/app/.venv/bin:$PATH"

RUN groupadd --gid 10001 homex \
    && useradd --uid 10001 --gid homex --create-home --shell /usr/sbin/nologin homex

WORKDIR /app

COPY --from=backend pyproject.toml uv.lock ./
COPY --from=backend vendor/ ./vendor/
COPY docker/requirements-deploy.lock /tmp/requirements-deploy.lock
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --extra worker --no-install-project

COPY --from=backend manage.py ./
COPY --from=backend apps/ ./apps/
COPY --from=backend config/ ./config/
COPY --from=backend docs/sql/ ./docs/sql/
COPY --from=backend scripts/ ./scripts/
COPY scripts/apply_runtime_privileges.py /opt/homex-deploy/apply_runtime_privileges.py
COPY scripts/verify_expected_migrations.py /opt/homex-deploy/verify_expected_migrations.py
COPY scripts/verify_media_integrity.py /opt/homex-deploy/verify_media_integrity.py

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --extra worker \
    && uv pip install --python /app/.venv/bin/python --no-deps --require-hashes \
        --requirements /tmp/requirements-deploy.lock \
    && install -d -o homex -g homex -m 0700 /var/lib/homex/audio-temporal \
    && install -d -o homex -g homex -m 0755 /var/lib/homex/media \
    && chown -R homex:homex /app

USER 10001:10001

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
