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
Después levanta/verifica PostgreSQL, ejecuta `pg_restore --list` contra el dump y sólo entonces
detiene los writers, elimina/recrea la base y ejecuta `pg_restore`. Finalmente intercambia la media
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
