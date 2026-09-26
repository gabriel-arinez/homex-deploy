# HOMEX Deploy

Infraestructura versionada para ensamblar, verificar y operar HOMEX. No contiene reglas
comerciales, lógica NLP ni componentes Vue de dominio.

## Estado

- D00 — baseline y contrato: cerrada.
- D01 — runtime integrado backend + NLP: cerrada y verificada con CI remoto verde.
- D02+ — pendientes según `docs/PLAN_MAESTRO.md`.

## Runtime D01

D01 ejecuta PostgreSQL, Redis, migración one-shot, aplicación de privilegios, API Django,
worker Celery y jobs operativos de publicación, reconciliación y limpieza. API y worker comparten
la misma imagen; el wheel NLP y el modelo ASR están fijados por versión/hash.

```bash
cp .env.example .env
# Editar contraseñas y ASR_MODEL_SOURCE antes de continuar.
docker compose --env-file .env build backend
docker compose --env-file .env up -d postgres redis
docker compose --env-file .env run --rm migrate
docker compose --env-file .env run --rm grant-runtime
docker compose --env-file .env up -d api worker
```

Jobs independientes:

```bash
docker compose --env-file .env run --rm publisher
docker compose --env-file .env run --rm reconciler
docker compose --env-file .env run --rm cleanup
```

Gate integral aislado:

```bash
ASR_MODEL_SOURCE=/ruta/absoluta/faster-whisper-small \
POSTGRES_USER=postgres POSTGRES_DB=homex \
sh scripts/test_d01_runtime.sh
```

El gate usa el proyecto Compose exclusivo `homex-d01-gate` y elimina sólo sus recursos
efímeros. Producción no debe usar los marcadores de `.env.example`.

## Estructura

```text
.github/workflows/ci.yml       config, build, integración y secretos
docker/backend.Dockerfile      imagen común API/worker
docker/postgres/init/          bootstrap de roles PostgreSQL
docker-compose.yml             runtime integrado D01
docs/ARQUITECTURA_DEPLOY.md    arquitectura y fronteras
docs/implementacion/           evidencia por fase
releases/manifest.yaml         componentes exactos
scripts/                       gates y operación
```
