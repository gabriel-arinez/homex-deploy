# Runbook operacional HOMEX

## Alcance y reglas

Este runbook cubre la release privada `homex.internal`. PostgreSQL continúa siendo la autoridad,
Redis sólo transporta trabajo y el audio es temporal. Nunca copiar tokens, contraseñas, JWT,
cuerpos de solicitudes ni audio a tickets o logs. Toda acción destructiva sobre datos debe seguir
`docs/RECOVERY_RUNBOOK.md` y disponer de un backup verificado.

Los logs se consultan con `docker compose logs` y rotan mediante `json-file` (`10m × 5` por
contenedor). Nginx y API comparten `request_id`; el worker se sigue mediante `task_id` de Celery y
los IDs de captura/intento almacenados en PostgreSQL. Para correlación: buscar primero el
`X-Request-ID` de la respuesta en Nginx y Gunicorn, después el intento/outbox y finalmente el
`task_id` publicado. Los logs no incluyen Authorization ni cuerpos.

## Estado y métricas

Arranque del monitor:

```sh
mkdir -p /srv/homex/metrics
chown 10001:10001 /srv/homex/metrics
docker compose -f docker-compose.yml -f compose.production.yml \
  --env-file .env.production --profile operations --profile observability up -d monitor
```

`/srv/homex/metrics/homex.prom` contiene disponibilidad de PostgreSQL, Redis y API; tamaño de base;
outbox pendiente; y uso de media/audio temporal. Puede ser leído por un textfile collector sin
exponer puertos adicionales. Estados de almacenamiento: `0` normal, `1` advertencia, `2` crítico.
Umbrales iniciales: 80% y 90%. El monitor también escribe un evento JSON seguro por ciclo. El healthcheck del contenedor\nindica **recolector activo y emitiendo datos recientes**, no que todas las dependencias estén\nsanas. Para incidentes, consultar `homex_monitor_collection_healthy` (0 degradado, 1 sano)\ny `homex_dependency_up` por dependencia. La recolección no envía alertas externas; el\noperador debe revisar las métricas o configurar un colector/alertmanager privado en D07.\nEl despliegue oficial inicia el monitor y falla si no alcanza su healthcheck.\nLas métricas son de almacenamiento del filesystem donde están montados media y audio;\nla prueba ENOSPC utiliza un tmpfs aislado y **no demuestra** la respuesta de la aplicación\na un volumen comercial lleno.

Verificación diaria:

```sh
docker compose -f docker-compose.yml -f compose.production.yml --env-file .env.production \
  --profile operations --profile observability ps
tail -n 30 /srv/homex/metrics/homex.prom
df -h /srv/homex/media /srv/homex/backups /srv/homex/metrics
docker system df
systemctl status homex-cloudflared.service --no-pager
```

## PostgreSQL no disponible

Síntomas: API `unhealthy`, `homex_dependency_up{dependency="postgres"}=0`, errores de conexión.
No ejecutar migraciones repetidamente. Revisar contenedor, espacio y logs PostgreSQL; levantarlo y
esperar `pg_isready` más `SELECT 1`. Luego comprobar API y ejecutar `scripts/smoke.sh`. Si los datos
o el volumen están dañados, detener writers y aplicar el runbook D05.

## Redis no disponible

La API puede continuar disponible. Las capturas quedan protegidas por PostgreSQL/outbox y el worker
no procesará hasta recuperar Redis. Reiniciar Redis, comprobar `redis-cli ping`, worker `pong` y
ejecutar publisher/reconciler. No restaurar Redis desde backup ni convertirlo en autoridad.

## API, worker o Nginx reiniciados

Reiniciar un proceso por vez. Esperar su healthcheck antes de continuar. Para worker, confirmar
`celery inspect ping`; para Nginx, consultar HTTPS y revisar que `X-Request-ID` exista. Si Nginx cae,
el Tunnel puede estar conectado pero el origen permanecerá inaccesible.

## Tunnel detenido

Comprobar `homex-cloudflared.service`, su token-file y conectividad, sin imprimir el token. Detener
el Tunnel debe cortar acceso remoto, mientras PostgreSQL, Redis y API siguen sin exposición
pública. Después de iniciarlo, validar desde un dispositivo enrolado y revisar HTTPS. No cambiar la
interfaz `homex0`, abrir puertos públicos ni relajar Zero Trust para recuperar acceso.

## Media ausente o read-only

Detener cargas, comprobar mount y permisos UID/GID `10001`, integridad y espacio. No cambiar a un
volumen efímero. Restaurar permisos o media desde D05, ejecutar la auditoría DB ↔ media y luego un
upload/delete controlado. Un directorio read-only debe producir un fallo visible, nunca éxito falso.

## Disco lleno

Con 80% investigar crecimiento; con 90% suspender cargas y backups locales. Medir por separado
media, backups, métricas y Docker. No borrar media referenciada ni audio recuperable. Ejecutar el
cleanup de audio, aplicar la retención de backups y limpiar únicamente caché/imágenes Docker no
usadas. Tras liberar espacio, ejecutar monitor, smoke e integridad DB ↔ media.

## Cleanup fallido

El job debe devolver código no cero y conservar el archivo que no pudo borrar. Revisar permisos,
mount y PostgreSQL antes de reintentarlo. No usar `rm -rf` sobre el volumen completo: un audio puede
ser todavía la única entrada recuperable de un intento pendiente.

## Configuración incompleta

Compose y Django deben fallar antes de servir. Corregir el gestor externo de secretos o `.env`
productivo con permisos restrictivos. No reemplazar valores faltantes por defaults inseguros ni
registrar el contenido completo del entorno.

## Dispositivo no autorizado

Debe fallar en Cloudflare Zero Trust antes de mostrar HOMEX. Confirmar enrolamiento, política y
postura del dispositivo desde administración. No desactivar la política globalmente. Si el login
HOMEX resulta accesible desde un dispositivo no enrolado, tratarlo como incidente: detener Tunnel,
revisar rutas privadas y rotar el token si existe sospecha de exposición.

## Procesamiento concurrente

La misma `clave_idempotencia` debe producir una captura, un intento y un outbox. Ante duplicados o
estados divergentes, detener publishers, conservar evidencia PostgreSQL y capturar IDs técnicos; no
editar filas manualmente. El gate D06 reproduce dos recepciones simultáneas y verifica la
serialización real.

## Ensayo automatizado

```sh
D06_COMPOSE_PROJECT=homex-d06-local \
D06_WORK_DIR=/tmp/homex-d06-local \
BACKEND_CONTEXT=../homex-backend FRONTEND_CONTEXT=../homex-frontend \
sh scripts/test_d06_resilience.sh
```

El namespace `homex-d06-*`, TLS, media, métricas y datos son descartables. El gate nunca controla
`homex-cloudflared.service` real: simula pérdida del origen deteniendo sólo su proxy aislado. La
prueba física de Tunnel y dispositivo no autorizado permanece en la evidencia D04.
