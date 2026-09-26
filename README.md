# HOMEX Deploy

Infraestructura versionada para ensamblar, verificar y operar HOMEX. Este repositorio no
contiene reglas comerciales, lógica NLP ni componentes Vue de dominio.

## Estado

La fase **D00 — baseline de infraestructura** está en desarrollo. El Compose actual levanta
únicamente PostgreSQL y Redis con versiones fijadas; las imágenes de aplicación comienzan en
D01 y el frontend/proxy en D02.

## Validación local

```bash
cp .env.example .env
docker compose config --quiet
docker compose up -d postgres redis
docker compose ps
```

Los valores de `.env.example` son marcadores locales, no secretos productivos. Antes de usar el
entorno se debe cambiar `POSTGRES_PASSWORD`, mantener sincronizado `DATABASE_URL` y sustituir
cualquier credencial marcada con `replace-with-...`.

## Estructura

```text
.github/workflows/ci.yml       CI de configuración y contratos
docker-compose.yml             baseline local, no producción
docs/ARQUITECTURA_DEPLOY.md    topología, fronteras y contratos auditados
docs/implementacion/           evidencia de cierre por fase
nginx/                         reservado para D02
releases/manifest.yaml         componentes exactos de la release
releases/manifest.schema.json  contrato verificable del manifiesto
scripts/                       validadores y operación versionada
```

El orden rector, los gates y las prohibiciones están en
[`docs/PLAN_MAESTRO.md`](docs/PLAN_MAESTRO.md).
