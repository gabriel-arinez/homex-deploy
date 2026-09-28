# D02 — Staging integrado y reverse proxy

**Fecha:** 28 de septiembre de 2026  
**Rama:** `feat/d02-staging-proxy`  
**Commit base:** `812569224094483f7cffc6d5573580fd72aab872`  
**Estado:** implementación y gates locales completos; CI remoto se ejecutará al publicar la rama.

## Componentes fijados

| Componente | Revisión o artefacto |
| --- | --- |
| backend | `0659dc553af15b2125fad9b4ac0579669916e77b` |
| frontend | `57c32d3aa2c2e46fbcc7136f6a90995b67c664ea` |
| NLP, evidencia integrada | `55236655956c2f488af645aafa657db39af66b60` |
| wheel NLP consumido por backend | `homex-nlp==0.1.0`, SHA-256 `cfacc3a987f6158f43934cb64304fa50ea3e577cfa576f3db1e6d2a9576d19e6` |
| Node build | `24.15.0-bookworm-slim` fijado por digest |
| Nginx runtime | `1.29.3-alpine3.22` unprivileged, fijado por digest |
| Gunicorn | `23.0.0`, wheel verificado por SHA-256 |

Los tags `d02-*` siguen siendo tags de una release `baseline`. D04 deberá promover imágenes de
registry mediante `tag@sha256`; D02 no presenta IDs locales como digests distribuibles.

## Implementación

`docker/frontend.Dockerfile` realiza `npm ci` desde `package-lock.json`, copia sólo los archivos
necesarios del checkout frontend y ejecuta type-check más build Vite. El artefacto final se copia
a una imagen Nginx sin Node ni fuentes, ejecutada como UID/GID 101. La única variable Vite
inyectada es la URL pública absoluta de mismo origen; las credenciales del backend, PostgreSQL,
Redis y R2 no se entregan a esa etapa.

Nginx publica el frontend en 8080 y aplica:

- `/api/` hacia `api:8000`, conservando URI, cuerpo y códigos del backend;
- `proxy_intercept_errors off` para no reemplazar `400/401/403/409`;
- `proxy_request_buffering off` y límite de 26 MiB, compatible con audio de 25 MB e imágenes de 10 MiB;
- fallback a `index.html` para rutas Vue;
- un año e `immutable` sólo para `/assets/` generados con hash por Vite;
- `no-store` para `index.html` y para el fallback SPA;
- gzip para JS, CSS, JSON, SVG y texto;
- headers `nosniff`, `DENY`, referrer policy y permissions policy;
- media filesystem de staging en volumen Docker, read-only desde Nginx y sin caché larga.

D03 reemplazará ese volumen de media por Cloudflare R2. D02 no configura credenciales R2, CDN,
dominio público ni subida directa desde Vue.

La API ya no usa `runserver`. La imagen instala Gunicorn desde un lock de despliegue con hash,
después del `uv sync` backend, y conserva el usuario no root. El healthcheck comprueba tanto la
conexión PostgreSQL (`SELECT 1`) como `/api/v1/health/`; Redis continúa siendo transporte
recuperable y no se convierte en requisito de disponibilidad comercial.

## Seguridad de staging

El navegador usa el mismo origen para Vue y `/api`, de modo que staging no necesita CORS para
su operación normal. `CORS_ALLOWED_ORIGINS` permanece como lista explícita y el gate comprueba
que un origen ajeno no reciba `Access-Control-Allow-Origin`. No se introdujo wildcard CORS/CSRF.
El bind HTTP por defecto es `127.0.0.1`; un entorno remoto debe proporcionar su bind y URL pública
explícitos, y TLS/HSTS/CSP definitivos pertenecen a D04.

PostgreSQL y Redis mantienen sus puertos de diagnóstico en loopback. Sólo `frontend-proxy`
pertenece a la red `app`; no accede directamente a la red interna `data`.

## Gate integral

`scripts/test_d02_staging.sh` exige un namespace `homex-d02-*`, crea una base vacía y elimina
únicamente sus propios contenedores, redes y volúmenes. Verifica:

1. migraciones y privilegios runtime;
2. Gunicorn 23.0.0 y readiness API/PostgreSQL;
3. health API a través de Nginx;
4. igualdad byte a byte de respuestas `401` y `403` directas/proxy;
5. upload multipart PNG válido y lectura posterior de WebP desde `/media/`;
6. refresh directo de `/proformas/123` con respuesta SPA 200;
7. cache `immutable` de assets, `no-store` del HTML y gzip real;
8. headers base;
9. rechazo de CORS para origen no autorizado;
10. ausencia de patrones de secretos en el bundle;
11. Chromium real cargando `/login`, refrescando una ruta protegida y consultando el API.

`scripts/test_d02_contract.py` protege además servidor productivo, imágenes base por digest,
usuarios no root, caché, límites de upload, proxy sin interceptación y ausencia de wildcards.

## Evidencia local

| Gate | Resultado |
| --- | --- |
| imágenes backend y frontend/proxy | construidas correctamente |
| frontend | `npm ci`, type-check y Vite build correctos; 0 vulnerabilidades reportadas por npm |
| PostgreSQL vacío | todas las migraciones aplicadas |
| privilegios | `runtime-privileges-ok` |
| preservación HTTP | `d02-auth-status-preservation-ok`, `d02-permissions-preservation-ok` |
| multipart/media | `d02-multipart-media-ok` |
| SPA/cache/gzip | `d02-spa-cache-compression-ok` |
| CORS | `d02-cors-ok` |
| navegador | `d02-browser-smoke-ok` |
| gate final | `d02-http-api-smoke-ok` |
| regresión D01 | `d01-runtime-ok`, incluida persistencia, outbox, worker y NLP |

Durante la validación el host agotó espacio al extraer la imagen backend. Se eliminó sólo caché
de BuildKit e imágenes colgantes; no se tocaron volúmenes ni imágenes etiquetadas ajenas. El
primer build también reveló que un segundo `uv sync` retiraba Gunicorn; la instalación con hash
quedó situada después del sync final y el gate comprueba la versión dentro del contenedor.

## CI

El workflow añade `staging-integration`, que fija los SHA de backend/frontend, instala Chromium y
ejecuta el gate completo. Los jobs existentes construyen ahora ambas imágenes con esas mismas
revisiones. El número de run y su resultado deben añadirse después del commit/push, antes de
fusionar y declarar el cierre remoto formal.

## Operación

```bash
cp .env.example .env
# Sustituir secretos, rutas y la URL pública de staging.
docker compose --env-file .env build backend frontend-proxy
docker compose --env-file .env up -d postgres redis
docker compose --env-file .env run --rm migrate
docker compose --env-file .env run --rm grant-runtime
docker compose --env-file .env up -d api frontend-proxy worker
```

Gate completo:

```bash
BACKEND_CONTEXT=../homex-backend \
FRONTEND_CONTEXT=../homex-frontend \
POSTGRES_USER=postgres POSTGRES_DB=homex \
sh scripts/test_d02_staging.sh
```
