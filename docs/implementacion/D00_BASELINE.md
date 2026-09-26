# D00 — Baseline de infraestructura y contrato de despliegue

**Fecha:** 25 de septiembre de 2026  
**Rama:** `feat/d00-baseline`  
**Commit base deploy:** `a6b4b27` (`docs: add HOMEX deploy master plan`)  
**Estado:** implementación local completa; cierre pendiente de CI remoto verde.

## Precondiciones verificadas

| Repositorio | Revisión verificada | Gate requerido | Estado |
| --- | --- | --- | --- |
| homex-backend | `adb949268277da4361f37c96b786c5cdd0265750` | F08.4 | cerrado en `main` |
| homex-nlp | `b5fe2921320c9031f6d44dc5c91a18411daa393e` | F06 | cerrado en `main` |
| homex-frontend | `db969c00b06fbdc22bd30937f40ebf8d0a045505` | FE02 | cerrado en `main` |

FE03 no fue usada como precondición. Su rama de trabajo estaba activa, pero la revisión registrada
por D00 es el `main` actual.

## Auditoría

Se leyeron `.env.example`, configuración de runtime, locks, documentación de implementación y
comandos de los tres repositorios. El inventario resultante está en
`docs/ARQUITECTURA_DEPLOY.md`.

Hallazgos principales:

- NLP se consume como wheel dentro del worker y no expone puerto ni servicio HTTP.
- El backend tiene liveness en `/api/v1/health/`, pero no readiness de dependencias.
- Los comandos de publicación, reconciliación y limpieza existen como comandos Django reales.
- El backend no tiene todavía un servidor WSGI/ASGI productivo en su lock.
- Beat agenda publicación, reconciliación y limpieza, pero D01 debe aislar la limpieza del worker
  de inferencia conforme al plan.
- El frontend requiere `VITE_API_BASE_URL`; es configuración pública de build, nunca secreto.

## Archivos modificados

- `.env.example`: contrato consolidado y eliminación de nombres inventados.
- `.github/workflows/ci.yml`: jobs independientes para Compose, YAML, release y secretos.
- `.yamllint.yml`: política YAML.
- `docker-compose.yml`: PostgreSQL/Redis fijados, checks reales, loopback y red interna.
- `releases/manifest.yaml`: baseline con revisiones exactas y hash del wheel NLP.
- `releases/manifest.schema.json`: esquema verificable de release.
- `scripts/validate_env_contract.py`: gate de variables únicas y autorizadas.
- `docs/ARQUITECTURA_DEPLOY.md`: contrato técnico y faltantes propietarios.
- `README.md`: operación y estructura D00.

## Imágenes y versiones

- PostgreSQL: `postgres:17.6-alpine3.22`.
- Redis: `redis:8.2.1-alpine3.22`.
- homex-nlp: wheel `0.1.0`, SHA-256
  `cfacc3a987f6158f43934cb64304fa50ea3e577cfa576f3db1e6d2a9576d19e6`.
- Imágenes API/worker/frontend: explícitamente `pending-d01`/`pending-d02`; D00 no las inventa.
- Modelo ASR: explícitamente pendiente de versión y hash en D01.

## Variables

Se retiraron `BACKEND_PORT`, `FRONTEND_PORT`, `NLP_PORT` y `APP_ENV`, que no pertenecían a los
contratos fuente. Se conservaron los nombres exactos de backend y frontend, más seis variables
propias de orquestación local: `COMPOSE_PROJECT_NAME`, `POSTGRES_DB`, `POSTGRES_USER`,
`POSTGRES_PASSWORD`, `POSTGRES_PORT` y `REDIS_PORT`.

## Gates y evidencia local

| Gate | Resultado |
| --- | --- |
| variables únicas/autorizadas | `env-contract-ok: 25 variables únicas` |
| sintaxis YAML | correcta mediante `yaml.safe_load` |
| sintaxis JSON Schema | correcta mediante `json.loads` |
| manifest contra JSON Schema | correcto con `jsonschema` Draft 2020-12 |
| SHA-256 del wheel | coincide con manifiesto |
| `docker compose config` | pendiente: el host tiene Docker 29.1.3 sin plugin Compose |
| CI remoto | pendiente de push/PR |

CI ejecutará `docker compose --env-file .env.example config --quiet`, `yamllint`,
`check-jsonschema` y Gitleaks sin credenciales productivas.

## Riesgos y bloqueos

1. D00 no puede cerrarse formalmente hasta observar CI remoto verde.
2. D01 necesita una decisión/cambio backend para servidor productivo y readiness real.
3. D01 debe elegir y fijar el artefacto ASR con versión y hash.
4. La separación migrador/runtime PostgreSQL debe materializarse en D01; el usuario de bootstrap
   de la imagen oficial no debe convertirse en el runtime productivo final.

## Comandos de operación D00

```bash
cp .env.example .env
python3 scripts/validate_env_contract.py
docker compose --env-file .env config --quiet
docker compose --env-file .env up -d postgres redis
docker compose --env-file .env ps
docker compose --env-file .env down
```

## Commit final

Pendiente hasta completar revisión local y crear el commit de fase.
