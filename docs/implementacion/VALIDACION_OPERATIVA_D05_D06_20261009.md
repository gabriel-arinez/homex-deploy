# Verificación operacional D05/D06 — 9 de octubre de 2026

## Alcance y separación de evidencias

Esta acta documenta la **verificación manual sobre el host real Ubuntu** posterior al cierre automatizado de D05 y D06. No sustituye sus gates aislados y no convierte pendientes operativos en resultados aprobados.

## D06 — Observabilidad del host real

- Compose: proyecto `homex-prod`, endpoint privado HTTPS `homex.internal` sobre `10.254.254.1:443`; Tunnel Cloudflare previamente validado en D04.
- Monitor `homex-prod-monitor-1` saludable; archivo de métricas `/srv/homex/metrics/homex.prom` generado en volumen del host con UID/GID 10001; las métricas consultadas marcaron `homex_monitor_collection_healthy 1` y `homex_dependency_up` igual a 1 para PostgreSQL, Redis y API. `healthy` indica frescura de recolección, no garantiza la salud de todas las dependencias.
- API y Nginx fueron recreados de forma selectiva para aplicar configuración D06, sin reconstruir imágenes ni tocar PostgreSQL.
- Correlación real: respuesta `X-Request-ID` `836cd5e76e64549d7b7e1d4bf9471b5d`, mismo identificador en los registros JSON de Nginx y Gunicorn; endpoint `/api/v1/health/` devolvió HTTP 200.
- API, proxy, worker, PostgreSQL, Redis y monitor se observaron saludables; beat en ejecución.
- Se revisaron límites PIDs, rotación y configuración de métricas durante el diagnóstico D06. La ruta persistente `HOMEX_METRICS_HOST_PATH=/srv/homex/metrics` debe mantenerse en la configuración de despliegue del host.

## D05 — Backup real y reanudación

- Antes del ensayo sólo existía un dump PostgreSQL antiguo de `pre-secret-rotation`, sin unidad completa D05; no se identificaron timers HOMEX ni crontabs de backup.
- Se restringió `/srv/homex/backups` a propietario `gabriel:gabriel` y modo `0700`.
- Primer respaldo real completado con `homex-backup-ok`, código 0: `/srv/homex/backups/homex-20261009T051913Z`. Se publicaron `database.dump`, `media.tar.gz`, `media-manifest.json`, `release-manifest.yaml`, `recovery.json` y `SHA256SUMS`.
- `sha256sum -c SHA256SUMS`: cinco artefactos válidos. `pg_restore --list` leyó el dump correctamente. El inventario de media contenía `files: []` porque la media del host estaba vacía: esto **no** prueba todavía restauración de imágenes reales del host.
- Tras el backup, PostgreSQL conservó su volumen persistente, la API pudo establecer conexión SQL, el endpoint HTTPS respondió 200 y los servicios con healthcheck se observaron saludables.
- Hallazgo: la primera reanudación con `docker compose up -d` recreó PostgreSQL, Redis, migrator, grant-runtime y writers. Corrección `202fa62`: `docker compose start` sólo reinicia los escritores previamente detenidos. Regresión `e09b6e8`: verifica que los IDs de PostgreSQL, Redis y API no cambien por el backup, y confirma recuperación de la API. GitHub Actions ejecución `37888141253`: **success**.
- Timer systemd en host: `homex-backup.service` configurado para usuario `gabriel`, trabajo en checkout y variables explícitas; `homex-backup.timer` diario a las 03:00 `America/La_Paz`, `Persistent=false`, retención de 14 días. `systemd-analyze verify` sin errores; timer `enabled`/`active`, servicio `inactive` y primera ejecución programada para 2026-10-09 03:00 -04.
- **No hay evidencia todavía** de una ejecución del timer a las 03:00 ni de su resultado en journal: comprobar `systemctl status homex-backup.service`, `journalctl -u homex-backup.service` e integridad de la unidad nueva.

## Pendientes explícitos de operación (no bloquean cierre del contrato automatizado D05/D06)

1. Configurar copia cifrada fuera de la PC. La USB presente contenía GParted Live, no es un destino de respaldo. `gpg` disponible; `restic`, `rclone`, `borg` y `age` no instalados según diagnóstico.
2. Elegir proveedor externo, credenciales con privilegio mínimo, política de retención remota, comprobación periódica y ensayo de restauración **fuera de `homex-prod`**.
3. Verificar el primer disparo automático del timer y documentar un procedimiento de recuperación del host. Systemd depende de que la PC esté encendida; `Persistent=false` no recupera ejecuciones perdidas.
4. Versionar y parametrizar la instalación de las unidades systemd locales; actualmente sólo están en `/etc/systemd/system`.
5. Mantener respaldo separado y cifrado de CA/TLS y secretos conforme al runbook; las copias de aplicación no los incluyen.

**Estado:** D05 y D06 tienen sus gates de implementación aprobados. La operación externa cifrada y la recuperación off-host continúan pendientes; no presentar el respaldo local como estrategia de desastre completa.
