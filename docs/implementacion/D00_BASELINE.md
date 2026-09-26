# D00 — Baseline de infraestructura y contrato de despliegue

**Fecha:** 26 de septiembre de 2026  
**Rama:** `feat/d00-baseline`  
**Commit base deploy:** `a6b4b27` (`docs: add HOMEX deploy master plan`)  
**Estado:** correcciones de auditoría aplicadas; cierre condicionado al CI remoto del commit correctivo.

## Precondiciones verificadas

| Repositorio | Revisión verificada | Gate requerido | Estado |
| --- | --- | --- | --- |
| homex-backend | `9fac22ecc4f471237e6611b5a226532ab2a037ab` | F08.4 | cerrado en `main`; contratos FE03/FE04 ya integrados |
| homex-nlp | `b5fe2921320c9031f6d44dc5c91a18411daa393e` | F06 | cerrado en `main` |
| homex-frontend | `9374c2f73b5496dc79fd70dbb250ac4f645f8ec5` | FE02 | satisfecha; FE04 ya fusionada en `main` |

D00 exige FE02 como mínimo. La revisión frontend auditada ya contiene FE03 y FE04, por lo que no
se rebaja ni se sustituye el gate: simplemente se fija el `main` vigente y probado.

## Reauditoría de fuentes

Se releyeron los contratos de entorno y runtime vigentes después de detectar que la primera
implementación había fijado revisiones antiguas.

Resultado:

- backend `main` conserva los mismos nombres de configuración necesarios para deploy;
- frontend `main` conserva `VITE_API_BASE_URL` y `npm run build`;
- NLP continúa en F06 con wheel `0.1.0` y contrato v1;
- los comandos Django `publicar_outbox_capturas`, `reconciliar_outbox_capturas` y
  `limpiar_audio_temporal` siguen existiendo;
- `GET /api/v1/health/` sigue siendo liveness y no readiness;
- backend sigue sin declarar Gunicorn/Uvicorn u otro servidor WSGI/ASGI productivo en su lock.

El inventario consolidado está en `docs/ARQUITECTURA_DEPLOY.md`.

## Archivos de D00

- `.env.example`: contrato consolidado y eliminación de nombres inventados.
- `.github/workflows/ci.yml`: jobs independientes para Compose, YAML, release y secretos.
- `.yamllint.yml`: política YAML.
- `docker-compose.yml`: PostgreSQL/Redis fijados, checks reales, loopback y red interna.
- `releases/manifest.yaml`: baseline con revisiones exactas, migraciones hoja y hash del wheel NLP.
- `releases/manifest.schema.json`: contrato de release con invariantes por estado.
- `scripts/validate_env_contract.py`: gate de variables únicas y autorizadas.
- `scripts/test_release_manifest_schema.py`: pruebas positivas/negativas del contrato de release.
- `docs/ARQUITECTURA_DEPLOY.md`: topología, contratos auditados y faltantes propietarios.
- `README.md`: operación y estructura D00.

## Imágenes y versiones

- PostgreSQL: `postgres:17.6-alpine3.22`.
- Redis: `redis:8.2.1-alpine3.22`.
- homex-nlp: wheel `0.1.0`, SHA-256
  `cfacc3a987f6158f43934cb64304fa50ea3e577cfa576f3db1e6d2a9576d19e6`.
- Imágenes API/worker/frontend: `pending-d01`/`pending-d02` únicamente porque la release está
  en estado `baseline`.
- Modelo ASR: pendiente de versión y hash en D01.

## Estado esperado de migraciones

D00 deja de usar un SHA Git bajo el nombre ambiguo `expected_migration`.
`runtime.expected_migrations` registra las migraciones hoja del backend auditado:

| App | Migración hoja |
| --- | --- |
| accounts | `0001_initial` |
| capturas | `0007_cierre_hitl_f083` |
| catalogo | `0007_media_dimensiones_f077` |
| clientes | `0001_initial` |
| documentos | `0005_integridad_adjunto_f077` |
| movimientos_stock | `0003_carga_inicial_unica_f075` |
| notas_entrega | `0001_initial` |
| ordenes_trabajo | `0001_initial` |
| pedidos | `0001_initial` |
| proformas | `0004_cierre_reglas_f072` |
| recibos | `0003_cierre_reglas_f074` |

D01 deberá comprobar este mapa contra Django/PostgreSQL; un commit de código no se presenta como
si fuera una migración.

## Contrato de releases

El schema admite `pending-d01`/`pending-d02` sólo en `baseline`.

Para `candidate`, `released` o `superseded` exige:

- versión ASR no pendiente;
- SHA-256 real del modelo;
- imágenes API, worker y frontend/proxy con `tag@sha256:digest`;
- mapa de migraciones Django con formato válido.

La prueba `scripts/test_release_manifest_schema.py` verifica que:

1. baseline con pendientes es válida;
2. candidate/released/superseded con pendientes son rechazados;
3. candidate completa e inmutable es válida;
4. una imagen candidate sin digest es rechazada;
5. un SHA Git usado como supuesto nombre de migración es rechazado.

## Variables

Se retiraron `BACKEND_PORT`, `FRONTEND_PORT`, `NLP_PORT` y `APP_ENV`.

El contrato actual contiene 25 variables únicas: variables reales de backend/frontend más
configuración propia de orquestación local y `DJANGO_SETTINGS_MODULE` para seleccionar settings
de producción. No contiene secretos reales.

## Gates y evidencia

El primer commit de D00 (`6aa447f037ce52f0c668d5b288af8bccd25c0d47`) ejecutó GitHub Actions
`36222249907` con **4/4 jobs verdes**:

- `compose-config`;
- `yaml`;
- `release-contract`;
- `secrets`.

Ese resultado confirmó el baseline inicial, pero la auditoría posterior detectó revisiones fuente
obsoletas y dos debilidades del contrato de release; por ello D00 no se declara cerrada hasta que
el commit correctivo ejecute nuevamente todos los gates.

Gates del commit correctivo:

| Gate | Resultado exigido |
| --- | --- |
| variables únicas/autorizadas | `env-contract-ok: 25 variables únicas` |
| `docker compose config` | verde |
| YAML | verde |
| manifest actual contra JSON Schema | verde |
| pruebas de estados del manifest | `release-contract-tests-ok` |
| Gitleaks | verde |
| CI remoto | 4/4 verde |

## Riesgos y bloqueos para D01

1. Backend necesita fijar un servidor WSGI/ASGI productivo antes de construir la imagen API.
2. Backend debe definir readiness real de dependencias; deploy no lo falsificará.
3. D01 debe elegir y fijar el artefacto ASR con versión y hash.
4. La separación migrador/runtime PostgreSQL debe materializarse sin convertir al usuario runtime
   en propietario del esquema.
5. D01 debe comparar `expected_migrations` con el estado real de Django/PostgreSQL.

## Comandos de operación D00

```bash
cp .env.example .env
python3 scripts/validate_env_contract.py
python3 scripts/test_release_manifest_schema.py
docker compose --env-file .env config --quiet
docker compose --env-file .env up -d postgres redis
docker compose --env-file .env ps
docker compose --env-file .env down
```

## Cierre

El commit funcional inicial de D00 es
`6aa447f037ce52f0c668d5b288af8bccd25c0d47`. El commit correctivo y su CI se registrarán en el
cierre documental después de observar todos los jobs verdes.
