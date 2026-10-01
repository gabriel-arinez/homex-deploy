# HOMEX Deploy

Infraestructura versionada para ensamblar, verificar y operar HOMEX. No contiene reglas
comerciales, lógica NLP ni componentes Vue de dominio.

## Estado

- D00 — baseline y contrato: cerrada.
- D01 — runtime integrado backend + NLP: cerrada y verificada con CI remoto verde.
- D02 — staging integrado y reverse proxy: cerrada y fusionada.
- D03 — media persistente local: cerrada y validada.
- D04 — release candidate integrada + HTTPS/acceso privado: en curso; automatización implementada, validación real de Cloudflare/dispositivos pendiente.
- D05+ — recuperación, resiliencia, release y piloto pendientes.

## Staging D02

D02 añade el build reproducible de Vue, Gunicorn y Nginx unprivileged como único punto HTTP.
Vue y `/api` comparten origen; las rutas profundas usan fallback SPA y los uploads atraviesan el
proxy sin ampliar CORS/CSRF. Consulte `docs/implementacion/D02_STAGING_PROXY.md`.

```bash
docker compose --env-file .env build backend frontend-proxy
docker compose --env-file .env up -d postgres redis
docker compose --env-file .env run --rm migrate
docker compose --env-file .env run --rm grant-runtime
docker compose --env-file .env up -d api frontend-proxy worker
```

Gate navegador/API: `sh scripts/test_d02_staging.sh`.

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
docker/backend.Dockerfile      imagen común API/worker con Gunicorn
docker/frontend.Dockerfile     build Vue + runtime Nginx
docker/postgres/init/          bootstrap de roles PostgreSQL
docker-compose.yml             runtime integrado D01/D02
docs/ARQUITECTURA_DEPLOY.md    arquitectura y fronteras
docs/implementacion/           evidencia por fase
releases/manifest.yaml         componentes exactos
scripts/                       gates y operación
```


## Arquitectura productiva vigente

La release inicial de HOMEX usa media persistente local servida por Nginx HTTPS y acceso remoto
privado mediante Cloudflare Zero Trust/Tunnel. `homex.internal` usa una CA privada HOMEX para que
PC, tablet y móvil dispongan de contexto seguro sin comprar dominio ni provisionar R2.

La rama histórica `feat/d03-r2-media` no fue fusionada y no representa el plan vigente. D03 ya está
fusionada; el trabajo actual continúa en `feat/d04-private-release-candidate`.
