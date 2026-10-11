# Runbook de backup, restore y rollback

## Alcance de la unidad de recuperación

Cada directorio `homex-<UTC>` producido por `scripts/backup.sh` contiene una unidad indivisible:

- `database.dump`: PostgreSQL en formato custom de `pg_dump`;
- `media.tar.gz`: media comercial bajo `HOMEX_MEDIA_HOST_PATH`;
- `media-manifest.json`: path, modo, tamaño y SHA-256 por archivo;
- `release-manifest.yaml`: release exacta que produjo los datos;
- `recovery.json`: formato, fecha, proyecto e inclusiones/exclusiones;
- `SHA256SUMS`: integridad de todos los artefactos anteriores.

Redis, el volumen `audio_temporal`, el modelo ASR, secretos, tokens y claves TLS privadas no entran
en esta unidad. La CA y las claves TLS deben copiarse por el procedimiento de secretos del operador,
cifradas y separadas del backup de aplicación.

## Preparación

1. Crear `.env.production` fuera de Git desde `.env.production.example`.
2. Exportar las variables que consumen los scripts de host:

   ```sh
   export COMPOSE_PROJECT_NAME=homex-prod
   export HOMEX_ENV_FILE=.env.production
   export HOMEX_MEDIA_HOST_PATH=/srv/homex/media
   export HOMEX_BACKUP_ROOT=/srv/homex/backups
   export HOMEX_BACKUP_RETENTION_DAYS=14
   ```

3. Mantener backup y media en árboles distintos. El script rechaza un backup dentro de media.
4. Restringir `.env.production` y el directorio de backups al usuario operativo.

La política inicial es un backup diario, retención local de 14 días y al menos una copia cifrada
fuera del servidor. Un job externo debe copiar sólo unidades que ya contengan `SHA256SUMS`; una
unidad `.tmp` nunca es válida.

## Crear y verificar un backup

```sh
scripts/backup.sh
cd /srv/homex/backups/homex-AAAAMMDDTHHMMSSZ
sha256sum -c SHA256SUMS
pg_restore --list database.dump >/dev/null
```

El script detecta los servicios escritores activos, los detiene durante el dump/captura de media y
los reanuda al finalizar. El directorio final se publica mediante rename sólo después de verificar
checksums. Si aparece audio, un symlink o una ruta ASR dentro de media, el backup falla cerrado.

## Restaurar a una instalación limpia

Antes de operar, verificar que el checkout y `releases/manifest.yaml` corresponden al manifiesto de
la copia. El restore se niega a combinar releases distintas. La excepción
`HOMEX_RESTORE_ALLOW_RELEASE_MISMATCH=1` sólo se usa en una migración ensayada y documentada.

```sh
export HOMEX_MEDIA_UID=10001 HOMEX_MEDIA_GID=10001
scripts/restore.sh /srv/homex/backups/homex-AAAAMMDDTHHMMSSZ --confirm
docker compose -f docker-compose.yml -f compose.production.yml \
  --env-file .env.production --project-name homex-prod \
  --profile operations up -d api worker beat frontend-proxy
scripts/smoke.sh
```

El procedimiento verifica `SHA256SUMS` y la metadata de recuperación, extrae la media en staging y
valida íntegramente su inventario **antes de cualquier operación destructiva sobre PostgreSQL**.
Después levanta PostgreSQL y espera una consulta SQL real (`SELECT 1`) para evitar carreras durante
el arranque; luego ejecuta `pg_restore --list` contra el dump y sólo entonces detiene los writers,
elimina/recrea la base y ejecuta `pg_restore`. Finalmente intercambia la media
prevalidada, aplica migraciones/permisos y ejecuta la auditoría DB ↔ media. Detecta referencias sin
archivo, archivos no referenciados y symlinks. Redis y audio arrancan vacíos.

Si la media o su inventario no coinciden, el restore termina antes de `dropdb`; la base activa no
se modifica. El gate D05 comprueba explícitamente esta propiedad con una guardia de base de datos.

## Migración controlada

`scripts/deploy.sh` implementa el orden operativo: validar Compose, levantar PostgreSQL/Redis,
crear backup previo si la base responde, ejecutar `migrate`, aplicar privilegios runtime, levantar
API/worker/beat/proxy y ejecutar smoke. En la primera instalación puede usarse
`HOMEX_DEPLOY_SKIP_BACKUP=1` porque aún no existe estado comercial.

Antes de una migración incompatible se debe ensayar el restore con la release anterior. Django no
se revierte automáticamente: el rollback autoritativo es recuperar conjuntamente DB, media y
manifest de la unidad previa.

## Rollback de release

1. Detener API, worker, beat y proxy.
2. Seleccionar la última unidad verificada anterior al despliegue fallido.
3. Volver al tag/commit y a las imágenes declaradas por su `release-manifest.yaml`.
4. Ejecutar `scripts/restore.sh <unidad> --confirm`.
5. Levantar la release anterior y ejecutar `scripts/smoke.sh`.
6. Conservar logs y la unidad fallida para análisis; no mezclar su DB con media anterior.

Si el restore falla después del intercambio de media, el script repone el directorio previo. La DB
puede haber sido recreada, por lo que se repite el restore completo; nunca se promueve un estado
parcial.

## Ensayo periódico

Al menos una vez por release y periódicamente en operación:

1. cargar datos e imágenes representativos;
2. colocar un sentinel en el volumen de audio temporal;
3. respaldar;
4. destruir volumen DB, media y volúmenes efímeros del entorno de ensayo;
5. restaurar;
6. ejecutar migraciones, smoke y auditoría DB ↔ media;
7. confirmar que el sentinel de audio no existe en el backup ni tras restore;
8. alterar de forma controlada un inventario de media, recalcular el checksum externo y verificar
   que el restore lo rechaza sin modificar la base activa.

`scripts/test_d05_recovery.sh` automatiza exactamente ese ensayo sobre un namespace Compose
aislado `homex-d05-*` y nunca acepta credenciales productivas.

## Copia externa cifrada D07 — Restic + Cloudflare R2 (operacional)

**Ruta oficial del host HOMEX a partir del 11-10-2026:** backup D05 local,
validación SHA-256, snapshot cifrado de la **unidad indivisible** en Cloudflare R2.
No se usa R2 como backend de media comercial; ésta permanece en filesystem local.

Configuración privada fuera de Git, propiedad del usuario operativo, con permisos
restrictivos:

- `~/.config/homex/restic-r2.env` (`0600`): exporta `RESTIC_REPOSITORY`,
  `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` y `AWS_DEFAULT_REGION`.
- `~/.config/homex/restic-password` (`0600`): contraseña del repositorio.
- `/srv/homex/backups/.restic-cache` (`0700`): caché local.
- Bucket externo: `homex-backups-prod`; nunca registrar endpoint completo ni secretos en evidencia.

El servicio `homex-backup.service` instalado invoca
`scripts/backup_and_offsite.sh`; realiza una comprobación remota inicial,
llama a `scripts/backup.sh`, y sólo publica en R2 una unidad válida mediante
`scripts/backup_restic.sh`. El timer está habilitado para las 03:00 (-04).
Un fallo de red/Restic causa fallo del servicio y debe revisarse con
`systemctl show` y `journalctl`; no confundir copia local con offsite exitoso.

### Verificar el respaldo remoto (sin modificar producción)

```sh
cd ~/HOMEX/homex-deploy
(
  set -eu
  . "$HOME/.config/homex/restic-r2.env"
  export RESTIC_PASSWORD_FILE="$HOME/.config/homex/restic-password"
  restic snapshots --tag homex-d07-offsite
  restic check
)
systemctl list-timers homex-backup.timer --no-pager
systemctl show homex-backup.service -p Result -p ExecMainStatus
```

### Recuperar una unidad en un directorio aislado

```sh
cd ~/HOMEX/homex-deploy
(
  set -eu
  . "$HOME/.config/homex/restic-r2.env"
  export RESTIC_PASSWORD_FILE="$HOME/.config/homex/restic-password"
  DESTINO=$(mktemp -d "$HOME/Descargas/homex-r2-recuperacion-XXXXXXXX")
  restic restore f2a5e6e0843d --target "$DESTINO"
  echo "Directorio de recuperación: $DESTINO"
)
```

El resultado recupera el árbol de rutas original bajo el directorio destino
(`srv/homex/backups/homex-...`). **Nunca** restaurar directamente sobre los
volúmenes productivos. Localizar la unidad extraída, ejecutar
`(cd UNIDAD && sha256sum -c SHA256SUMS)`, verificar el manifiesto de media con
`python3 scripts/media_inventory.py extract` y `verify`, y restaurar el dump
en PostgreSQL **17.6** aislado. El `pg_restore` 16 del host no puede leer el
dump CUSTOM 1.16 generado por PostgreSQL 17; usar las herramientas del contenedor
`postgres:17.6-alpine3.22`. El ensayo aislado del 11-10-2026 recuperó 34
tablas, 52 funciones, 48 triggers, 52 migraciones y media íntegra. Los cero
productos/pedidos correspondían a los datos existentes en ese backup de ensayo.

Para un restore operativo integral seguir las precondiciones de este runbook:
verificar release y compatibilidad de migraciones, usar namespace aislado y
hacer smoke y auditoría DB ↔ media antes de modificar la instalación productiva.

### Conservación, permisos y recuperación ante desastres

La retención **local** es de 14 días. La política de retención **en R2**
todavía no está aprobada ni automatizada: no ejecutar
`restic forget --prune` sin pruebas de restauración y definición de política.
Se requiere custodia separada y documentada de la contraseña y credenciales
para sobrevivir a pérdida total del host; no introducirlas en Git ni en el backup.
La prueba puntual de recuperación no sustituye ejercicios periódicos.

El 11-10-2026 se verificaron los snapshots cifrados
`395aaedb2a93` (ejecución manual) y `f2a5e6e0843d`
(disparo automático a las 00:25). La ejecución automática produjo
`homex-20261011T042511Z`, `homex-backup-and-offsite-ok` y servicios
productivos saludables después de reanudarse.

### Mecanismo histórico GPG (no usado en producción)

`scripts/backup_offsite.sh` y `scripts/test_d07_offsite.sh` permanecen
únicamente por compatibilidad con pruebas históricas de CI. No se debe
configurar el método GPG/mount junto a Restic ni asumir que es el flujo activo
del timer. Su retirada exigirá actualización independiente de contratos.

