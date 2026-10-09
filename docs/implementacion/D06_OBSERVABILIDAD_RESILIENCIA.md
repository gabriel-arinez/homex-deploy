# D06 — Observabilidad, seguridad operacional y resiliencia

## Estado y base

**IMPLEMENTACIÓN COMPLETA Y VALIDACIÓN LOCAL VERDE — 9 de octubre de 2026.**

- rama: `feat/d06-observabilidad-resiliencia`;
- base: `f509390bccaf0f2be12d243367838b43bea758dd` (`main`, D05 cerrada);
- backend fijado: `9ce723048d98a3925be45d9c359a25e6be7b19f3`;
- frontend fijado: `deba1de244395dbdcb266f03026630b403768d71`;
- topología privada D04 y recuperación D05 preservadas;
- ninguna prueba controló la instalación real ni `homex-cloudflared.service`.

## Observabilidad implementada

Nginx genera un identificador por solicitud, lo devuelve como `X-Request-ID`, lo propaga a Django y
escribe eventos JSON en stdout. Gunicorn registra el mismo identificador, método, URI, estado y
duración. No se registran cuerpos, JWT, cabeceras Authorization ni secretos. Celery conserva su
`task_id`; el salto asíncrono se sigue mediante captura, intento y outbox en PostgreSQL.

Todos los procesos productivos usan el driver Docker `json-file` con rotación inicial `10m × 5`.
PostgreSQL, Redis, API, worker, beat, Nginx y monitor tienen límites CPU/RAM y PIDs. Los límites
existentes de D04 se conservaron y se añadió el límite de procesos.

El perfil `observability` incorpora un monitor no expuesto a red pública ni al socket Docker. Cada
ciclo produce:

- disponibilidad de PostgreSQL, Redis y API;
- tamaño de la base PostgreSQL;
- cantidad de outbox pendientes;
- bytes y porcentaje usado de media y audio temporal;
- estado normal/advertencia/crítico con umbrales 80%/90%;
- duración y timestamp de la recolección.

Las métricas se escriben atómicamente en `homex.prom`, compatible con textfile collectors, y el
mismo ciclo deja un evento JSON saneado. El healthcheck del monitor exige que el archivo permanezca
actualizado.

## Resiliencia automatizada

`scripts/test_d06_resilience.sh` exige un namespace `homex-d06-*`, genera TLS bajo `/tmp`, crea una
base y almacenamientos descartables y destruye únicamente sus propios recursos. Verifica:

1. PostgreSQL detenido: la consulta SQL falla y el monitor publica `postgres=0`; al volver, SQL,
   health y HTTPS se recuperan.
2. Redis detenido: API sigue disponible, el monitor publica `redis=0`; al volver, worker recupera
   `pong`.
3. API, worker y proxy reiniciados: todos regresan a `healthy`.
4. Proxy/origen detenido: HTTPS deja de responder y vuelve tras levantarlo. Es la simulación local
   del tramo origen del Tunnel; el servicio Cloudflare real no se manipula.
5. Media read-only: una escritura del usuario no-root falla; permisos restaurados permiten escribir.
6. Disco lleno: un tmpfs aislado produce y valida `ENOSPC`, sin llenar el host.
7. Cleanup con audio read-only: el job devuelve error visible y no reporta éxito falso.
8. Configuración incompleta: Compose rechaza ausencia de `DJANGO_SECRET_KEY`.
9. Acceso sin JWT: conserva `401` a través de HTTPS/Nginx.
10. Dos recepciones simultáneas con la misma idempotencia: una captura, un intento y un outbox;
    una respuesta creada y otra reutilizada.
11. Correlación: el mismo request ID aparece en respuesta, Nginx y Gunicorn; worker responde con su
    identidad Celery.
12. Logs: búsqueda negativa de tokens y variables sensibles.

La caída real del Tunnel y el bloqueo de un dispositivo no enrolado ya fueron demostrados
físicamente en D04. D06 conserva esa arquitectura y documenta su respuesta operacional; repetir
esas acciones contra la instalación real contradice el requisito de aislamiento de esta fase.

## Runbook

`docs/OPERATIONS_RUNBOOK.md` define diagnóstico y recuperación para PostgreSQL, Redis, API, worker,
Nginx, Tunnel, media, disco lleno, cleanup, configuración incompleta, acceso no autorizado y
procesamiento concurrente. Las operaciones destructivas de datos continúan delegadas al runbook
D05.

## Evidencia local

| Gate | Resultado |
| --- | --- |
| contrato D06 | `d06-observability-contract-ok` |
| métricas y health | `d06-metrics-health-ok` |
| correlación segura | `d06-log-correlation-ok` |
| acceso no autorizado | `d06-unauthorized-access-ok` |
| PostgreSQL | `d06-postgresql-failure-recovery-ok` |
| Redis | `d06-redis-degraded-recovery-ok` |
| reinicios | `d06-process-restarts-ok` |
| origen/Tunnel | `d06-tunnel-origin-failure-recovery-ok` |
| media read-only | `d06-media-readonly-recovery-ok` |
| disco lleno | `d06-disk-full-controlled-ok` |
| cleanup fallido | `d06-cleanup-failure-visible-ok` |
| configuración incompleta | `d06-incomplete-config-rejected-ok` |
| concurrencia | `d06-concurrent-idempotency-ok` |
| worker | `d06-worker-correlation-task-id-ok` |
| cierre integral | `d06-resilience-gate-ok` |

Regresiones:

- contrato de entorno: `45 staging + 74 producción`;
- D02, D03, D04 y D05 contractuales: verdes;
- manifiesto de release: verde;
- inventario de media: 3/3;
- restore destructivo D05: `d05-backup-restore-gate-ok`;
- prevalidación negativa D05 conservó la base activa;
- migraciones desde PostgreSQL vacío y segunda ejecución no-op dentro de los gates: verdes;
- `git diff --check`, sintaxis Python/Shell, YAML y Compose: verdes.

## CI

El job `resilience-observability` fija los mismos SHA de D04/D05, construye las imágenes y ejecuta
el gate destructivo completo en `homex-d06-ci`. Ante fallo publica logs Compose durante siete días.
Los jobs heredados D00–D05 permanecen intactos y vuelven a ejecutar build, runtime, staging, media,
release privada, recovery y gitleaks. La evidencia remota se añadirá después de publicar el commit y
obtener la ejecución verde.
