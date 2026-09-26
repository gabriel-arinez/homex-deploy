# Arquitectura de despliegue HOMEX

## Autoridades y topología

PostgreSQL es la autoridad comercial. Redis transporta identificadores y puede reconstruirse
desde outbox. R2 será la media persistente en D03. El audio ASR vive en un volumen privado,
temporal y excluido de backups. `homex-nlp` es un wheel embebido en el worker, no un servicio HTTP.

```text
API Django ---------> PostgreSQL <--------- worker Celery
   |                       |                       |
   +-> audio temporal      +-> outbox -> Redis ---+
                                                  |
                                      ASR + homex-nlp 0.1.0
```

## Fuentes fijadas

| Componente | Revisión/versión |
| --- | --- |
| backend | `9fac22ecc4f471237e6611b5a226532ab2a037ab` |
| frontend | `9374c2f73b5496dc79fd70dbb250ac4f645f8ec5` |
| NLP | `0.1.0`, commit `b5fe2921320c9031f6d44dc5c91a18411daa393e` |
| wheel NLP | SHA-256 `cfacc3a987f6158f43934cb64304fa50ea3e577cfa576f3db1e6d2a9576d19e6` |
| ASR | `Systran/faster-whisper-small@536b0662742c02347bc0e980a01041f333bce120` |
| ASR model.bin | SHA-256 `3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671` |

## Imagen común

`docker/backend.Dockerfile` usa el lock backend y el extra `worker`; no instala dependencias
flotantes. El contexto backend se entrega mediante un contexto BuildKit nombrado y sólo se copian
archivos necesarios, evitando `.env`, `.git` y checkouts montados en runtime. La imagen ejecuta
como UID/GID 10001, no root.

API y worker usan exactamente `homex/backend:d01-9fac22e`. El digest local validado está en el
manifiesto. La base uv está fijada también por digest.

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
| API D01 local | `python manage.py runserver 0.0.0.0:8000 --noreload` |
| worker | `celery -A config worker --loglevel=INFO` |
| publisher | `python manage.py publicar_outbox_capturas` |
| reconciler | `python manage.py reconciliar_outbox_capturas` |
| cleanup | `python manage.py limpiar_audio_temporal` |

El servidor Django es deliberadamente sólo el runtime local D01. D02 no puede promoverlo a
staging/producción: backend todavía debe fijar un servidor WSGI/ASGI productivo en su lock.

## Almacenamiento y exposición

- `postgres_data`: persistente, probado tras reinicio.
- Redis: sin AOF/snapshot, no autoritativo.
- `audio_temporal`: compartido sólo por API, worker y cleanup; modo `0700`; sin puerto/ruta HTTP.
- modelo ASR: bind mount sólo en worker y de solo lectura.
- frontend y R2: fuera de D01.

La red `data` es interna. PostgreSQL/Redis sólo publican loopback para diagnóstico local. API se
publica en loopback; no existe aún reverse proxy público.

## Health

- PostgreSQL: `pg_isready`.
- Redis: `redis-cli ping`.
- API: liveness real `GET /api/v1/health/`.
- worker: `celery inspect ping` dirigido al nodo fijo.

Backend aún no ofrece readiness de dependencias; deploy no lo falsifica. Ese cambio propietario
sigue siendo requisito previo para declarar staging listo en D02.

## Resiliencia verificada

El gate `scripts/test_d01_runtime.sh` comprueba base vacía, segunda migración no-op, permisos,
API/worker reales, wheel NLP, pipeline F08, modelo ASR read-only, temporal `0700`, persistencia
PostgreSQL tras reinicio, outbox creado con Redis detenido, publicación al volver Redis y cleanup
con el worker detenido. El namespace del gate es exclusivo y siempre se limpia preservando el
código de salida original.
