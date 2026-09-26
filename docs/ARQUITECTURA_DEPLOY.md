| frontend | `9374c2f73b5496dc79fd70dbb250ac4f645f8ec5` (`main`) | FE02 | satisfecha; FE04 ya fusionada || backend | `9fac22ecc4f471237e6611b5a226532ab2a037ab` | F08.4 | satisfecha; `main` además contiene contrato FE04 |# Arquitectura de despliegue HOMEX

## Alcance

`homex-deploy` ensambla releases inmutables de `homex-backend`, `homex-frontend` y
`homex-nlp`. PostgreSQL continúa siendo la autoridad comercial; Redis sólo transporta IDs de
trabajo; R2 conserva media pública persistente; el audio ASR es privado, temporal y queda fuera
de backups.

D00 materializa el contrato y una baseline local de PostgreSQL/Redis. No pretende ser una
configuración productiva ni anticipa las imágenes que corresponden a D01/D02.

## Topología objetivo

```text
cliente -> proxy TLS -> Vue estático
                     -> Django API -> PostgreSQL
                                   -> R2
                                   -> temporal de audio privado compartido con worker

PostgreSQL/outbox -> publicador -> Redis -> worker Celery -> ASR + homex-nlp -> PostgreSQL
                                  ^
                     reconciliador y limpiador independientes
```

API y worker deben ejecutar la misma revisión de backend. `homex-nlp` no se despliega como
servicio HTTP: el worker consume el wheel `0.1.0` fijado por hash. Producción no monta checkouts
Git dentro de contenedores.

## Fuentes auditadas para D00

| Componente | Revisión auditada | Precondición | Resultado |
| --- | --- | --- | --- |
| backend | `adb949268277da4361f37c96b786c5cdd0265750` | F08.4 | satisfecha |
| frontend | `db969c00b06fbdc22bd30937f40ebf8d0a045505` (`main`) | FE02 | satisfecha |
| NLP | `b5fe2921320c9031f6d44dc5c91a18411daa393e` | F06 | satisfecha |

La reauditación del 26 de septiembre de 2026 usa los `main` vigentes. El frontend ya superó
la precondición mínima FE02 y tiene FE04 fusionada; el backend conserva F08.4 cerrado y además
incorpora los contratos requeridos por FE03/FE04. Los cambios posteriores a la auditoría inicial
no alteraron los nombres de variables utilizados por deploy, los comandos de worker/outbox ni la
ausencia de un servidor WSGI/ASGI productivo fijado. Las revisiones registradas no son referencias
flotantes.

## Procesos y comandos reales

| Proceso | Comando trazado al repositorio fuente |
| --- | --- |
| migración | `uv run python manage.py migrate --noinput` |
| API de desarrollo | `uv run python manage.py runserver` |
| worker | `uv run celery -A config worker --loglevel=INFO` |
| scheduler | `uv run celery -A config beat --loglevel=INFO` |
| publicar outbox | `uv run python manage.py publicar_outbox_capturas` |
| reconciliar outbox | `uv run python manage.py reconciliar_outbox_capturas` |
| limpiar audio | `uv run python manage.py limpiar_audio_temporal` |
| frontend desarrollo | `npm run dev` |
| frontend build | `npm run build` |

No se inventa un comando de servidor productivo: `homex-backend` todavía no declara Gunicorn,
Uvicorn u otro servidor WSGI/ASGI de producción en su lock. D01 debe resolverlo en el repositorio
propietario antes de construir la imagen API.

Celery Beat contiene las tres tareas periódicas, pero el plan exige que la limpieza sobreviva a
la caída del worker de inferencia. D01 debe orquestar el comando de limpieza como proceso/job
independiente y decidir si publicación y reconciliación usan comandos separados o colas aisladas.

## Puertos y dependencias

| Recurso | Puerto interno | Exposición D00 | Autoridad |
| --- | ---: | --- | --- |
| PostgreSQL | 5432 | loopback configurable | imagen oficial |
| Redis | 6379 | loopback configurable | imagen oficial |
| Django dev | 8000 | no creado en D00 | backend |
| Vite dev | 5173 | no creado en D00 | frontend |

`homex-nlp` no abre puerto. Las dependencias externas son PostgreSQL 17, Redis, Cloudflare R2,
el artefacto del modelo ASR y, durante build, los registros de paquetes. R2 y el modelo se
materializan en fases posteriores.

## Health y readiness auditados

- Backend expone `GET /api/v1/health/`, público, que devuelve `{"estado":"ok"}`. Es liveness;
  no consulta PostgreSQL, Redis, worker, migraciones ni R2.
- PostgreSQL usa `pg_isready` en Compose.
- Redis usa `redis-cli ping` en Compose.
- No existe endpoint de readiness de aplicación.
- No existe health HTTP separado para NLP porque NLP es una biblioteca del worker.
- La disponibilidad del worker puede comprobarse con Celery inspect/ping, aún no orquestado.

Deploy no falsificará readiness. El endpoint que refleje dependencias internas debe añadirse y
probarse en `homex-backend` antes de declararlo en D01.

## Contrato de configuración

`.env.example` conserva los nombres consumidos por backend y frontend y añade únicamente
variables propias de orquestación (`COMPOSE_PROJECT_NAME`, `POSTGRES_*`, `REDIS_PORT`) y
`DJANGO_SETTINGS_MODULE` para seleccionar explícitamente los settings de producción. Se eliminaron `BACKEND_PORT`,
`FRONTEND_PORT`, `NLP_PORT` y `APP_ENV`: no pertenecían a ningún contrato fuente.

Las variables NLP generales de su `.env.example` no se duplican: la integración vigente del
backend fija `RULES_ONLY` y sólo consume la configuración ASR expuesta en su propio contrato.
Las credenciales R2 sólo llegan al backend. `VITE_API_BASE_URL` es pública por definición y no
debe contener secretos.

## Persistencia y redes de la baseline

- `postgres_data` es el único volumen persistente en D00.
- Redis se configura sin AOF ni snapshots: es reconstruible desde PostgreSQL/outbox.
- La red `data` es interna.
- Los puertos publicados se enlazan a `127.0.0.1`, no a todas las interfaces.
- D00 no crea volúmenes para media ni audio.

La separación de roles PostgreSQL para migrador y runtime ya está especificada por backend,
pero la imagen oficial inicial sólo crea un usuario. D01 debe incorporar el bootstrap controlado
sin hacer que el runtime sea propietario del esquema.

## Manifiesto de release

`releases/manifest.yaml` registra revisiones exactas, hash del wheel NLP y versiones de datos.
Los campos `pending-d01`/`pending-d02` sólo son válidos mientras el estado sea `baseline`.
El JSON Schema aplica esta regla: `candidate`, `released` y `superseded` requieren modelo ASR
con SHA-256 real e imágenes inmutables `tag@sha256:digest`. El contrato se valida contra
`releases/manifest.schema.json` y además tiene pruebas negativas que impiden relajar esa
invariante.

El estado esperado de Django no se representa con un SHA Git. `runtime.expected_migrations`
registra las migraciones hoja por app y D01 deberá compararlas con `showmigrations`/la base real
antes de arrancar los procesos de aplicación.

## Faltantes en repositorios propietarios

| Propietario | Faltante | Bloquea |
| --- | --- | --- |
| backend | servidor WSGI/ASGI productivo bloqueado en dependencias | imagen API D01 |
| backend | readiness real de DB/Redis/migraciones según decisión de aplicación | gate D01/D02 |
| deploy + backend | bootstrap migrador/runtime con roles separados | runtime D01 |
| deploy | versión/hash y entrega offline del modelo ASR | worker D01 |
| frontend | continuar integrando el build de `main` hasta FE08 | release candidata D04 |

Estos faltantes no se solucionan con endpoints ficticios, sleeps ni comandos inventados.
