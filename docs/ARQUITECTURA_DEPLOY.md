# Arquitectura de despliegue HOMEX

## Autoridades y topología

PostgreSQL es la autoridad comercial. Redis transporta identificadores y puede reconstruirse
desde outbox. R2 es la media persistente del perfil productivo desde D03. D02 conserva un volumen Docker de media sólo para staging. El audio ASR vive en un
volumen privado, temporal y excluido de backups. `homex-nlp` es un wheel embebido en el worker, no un servicio HTTP.

```text
Navegador
   |
   +--> Nginx :8080 --> Vue estático
   |        |
   |        +--> /api --> Gunicorn/Django --> PostgreSQL
   |                         |                    ^
   |                         +--> audio temporal  | outbox
   |                                              |
   |                                    Redis --> worker Celery
   |                                              |
   |                                      ASR + homex-nlp 0.1.0
   |
   +--> dominio media --> Cloudflare CDN --> R2 homex-public-media
```

## Fuentes fijadas

| Componente | Revisión/versión |
| --- | --- |
| backend | `0659dc553af15b2125fad9b4ac0579669916e77b` |
| frontend | `57c32d3aa2c2e46fbcc7136f6a90995b67c664ea` |
| NLP | `0.1.0`, evidencia de integración `55236655956c2f488af645aafa657db39af66b60` |
| wheel NLP | SHA-256 `cfacc3a987f6158f43934cb64304fa50ea3e577cfa576f3db1e6d2a9576d19e6` |
| ASR | `Systran/faster-whisper-small@536b0662742c02347bc0e980a01041f333bce120` |
| ASR model.bin | SHA-256 `3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671` |

## Imagen común

`docker/backend.Dockerfile` usa el lock backend y el extra `worker`; no instala dependencias
flotantes. El contexto backend se entrega mediante un contexto BuildKit nombrado y sólo se copian
archivos necesarios, evitando `.env`, `.git` y checkouts montados en runtime. La imagen ejecuta
como UID/GID 10001, no root.

API y worker usan exactamente `homex/backend:d02-0659dc5`; Vue/Nginx usa `homex/frontend-proxy:d02-57c32d3`. D01 es una release `baseline`,
por lo que el manifiesto fija el tag común pero no presenta un image ID local como si fuera un
digest de registry. Un digest inmutable `tag@sha256:...` será obligatorio al pasar a
`candidate`, tal como exige el JSON Schema. La imagen base uv sí está fijada por digest.

## Orden de arranque y roles

1. PostgreSQL crea roles separados `homex_migrator` y `homex_runtime`.
2. `migrate` ejecuta Django una sola vez con el rol migrador.
3. `grant-runtime` aplica el SQL de privilegios propiedad de backend.
4. API/worker esperan el cierre exitoso de ambos jobs y los healthchecks de datos.
5. API/worker conectan exclusivamente como runtime.

El runtime recibe DML sobre tablas y uso de secuencias; no ownership ni DDL. El mapa de
migraciones hoja HOMEX se compara contra Django y contra `django_migrations`.

## Procesos

| Servicio/job | Comando real |
| --- | --- |
| migrate | `python manage.py migrate --noinput` |
| API D02 | `gunicorn config.wsgi:application --bind=0.0.0.0:8000` |
| worker | `celery -A config worker --loglevel=INFO` |
| publisher | `python manage.py publicar_outbox_capturas` |
| reconciler | `python manage.py reconciliar_outbox_capturas` |
| cleanup | `python manage.py limpiar_audio_temporal` |

D02 instala Gunicorn 23.0.0 desde un lock de despliegue con hash. Esta dependencia es propia de
la imagen operativa y se instala después del sync backend para que uv no la retire.

## Almacenamiento y exposición

- `postgres_data`: persistente, probado tras reinicio.
- Redis: sin AOF/snapshot, no autoritativo.
- `audio_temporal`: compartido sólo por API, worker y cleanup; modo `0700`; sin puerto/ruta HTTP.
- modelo ASR: bind mount sólo en worker y de solo lectura.
- `media_persistente`: existe sólo en el perfil staging D02.
- `homex-public-media`: único almacenamiento persistente productivo, accedido por Django con credenciales R2; las lecturas públicas usan el dominio CDN.
- PostgreSQL guarda object keys `productos/…` y `proformas/…`; no URLs ni binarios.
- frontend: artefacto Vite inmutable dentro de la imagen Nginx.

La red `data` es interna. PostgreSQL/Redis sólo publican loopback para diagnóstico local. API se
publica en loopback para diagnóstico; Nginx es el punto HTTP de staging y por defecto también
publica sólo en loopback.

## Health

- PostgreSQL: `pg_isready`.
- Redis: `redis-cli ping`.
- API: healthcheck de despliegue con conexión PostgreSQL, `SELECT 1` y `GET /api/v1/health/`.
- Nginx: documento raíz accesible y dependencia sobre API healthy.
- worker: `celery inspect ping` dirigido al nodo fijo.

Redis no forma parte del readiness comercial de API: si cae, PostgreSQL/outbox conserva el trabajo.

## Resiliencia verificada

El gate `scripts/test_d01_runtime.sh` comprueba base vacía, segunda migración no-op, permisos,
API/worker reales, wheel NLP, pipeline F08, modelo ASR montado read-only, temporal `0700`,
persistencia PostgreSQL tras reinicio, outbox creado con Redis detenido, publicación al volver
Redis y cleanup con el worker detenido. Después de reiniciar PostgreSQL, Redis o worker, el gate
espera explícitamente a que vuelvan a responder antes de continuar.

El script rechaza cualquier `D01_COMPOSE_PROJECT` que no comience con `homex-d01-`, evitando
que su cleanup con `down --volumes` pueda apuntar accidentalmente al proyecto normal.

El job CI `asr-contract` verifica además el `oid sha256` del puntero Git LFS de
`model.bin` directamente contra el snapshot Hugging Face fijado, sin descargar los 484 MB.
Para una provisión local real, `scripts/verify_asr_model.py` exige también
`config.json`, `tokenizer.json` y `vocabulary.txt` y calcula el SHA-256 completo de
`model.bin`.

## Perfil productivo D03

`compose.production.yml` reemplaza la configuración de staging por settings Django productivos y
retira el volumen `/var/lib/homex/media` de API, worker y Nginx. Las credenciales R2 sólo llegan a
procesos Django. `infra/r2/` crea el bucket `homex-public-media`, el dominio propio TLS y una regla
de caché limitada a los prefijos públicos. Vue consume únicamente URLs públicas devueltas por el
API. El endpoint R2, access key y secret key están ausentes de su build, OpenAPI y runtime.
