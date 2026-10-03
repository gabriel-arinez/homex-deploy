# D05 — Backup, restore, migración y rollback

## Estado y base

- rama: `feat/d05-backup-restore`;
- base rectora: `origin/main` en `b323f1f1fbf88fdc9d6ba658b8e138675bcb604b`;
- base técnica incorporada en la rama D05: D04 `2547f1a2792699e42713fec19447e3d6b914553e`;
- backend fijado: `9ce723048d98a3925be45d9c359a25e6be7b19f3`;
- frontend fijado: `deba1de244395dbdcb266f03026630b403768d71`;
- NLP fijado: `8d1750b2d1d26f6d90da10603216b7926bdaf820`;
- implementación operativa: `f46239e`;
- gate destructivo y CI: `8cd5d24`.

D04 tiene automatización verde en su rama, pero su validación externa Cloudflare/dispositivos y su
merge formal a `main` seguían pendientes al iniciar D05. No se modificó ni fusionó `main`: D05
nació desde el `main` actualizado e incorporó D04 sólo en su propia rama para completar la base
técnica. El cierre formal en la secuencia maestra queda condicionado a resolver esa precondición.

## Alcance implementado

- backup quiesced y verificable de PostgreSQL;
- backup de media persistente con inventario SHA-256, modos y tamaños;
- manifiesto de release y metadatos no secretos dentro de la unidad;
- exclusión de Redis, audio temporal, ASR, secretos y claves TLS;
- rechazo de audio, symlinks y rutas inseguras dentro de media;
- restore destructivo explícito a base limpia;
- extracción segura y staged de media, con restauración del ownership operativo;
- migraciones y privilegios runtime posteriores al restore;
- auditoría bidireccional PostgreSQL ↔ media;
- deploy ordenado con backup previo y smoke posterior;
- retención local configurable y runbook de rollback;
- gate unitario, contractual y ensayo destructivo real en CI.

No se agregó lógica comercial ni SQL paralelo a migraciones Django.

## Archivos principales

- `scripts/backup.sh`, `scripts/restore.sh`, `scripts/deploy.sh`, `scripts/smoke.sh`;
- `scripts/media_inventory.py`, `scripts/verify_media_integrity.py`;
- `scripts/test_media_inventory.py`, `scripts/test_d05_contract.py`;
- `scripts/test_d05_recovery.sh`, `scripts/test_d05_restored_runtime.py`;
- `docs/RECOVERY_RUNBOOK.md`;
- job `recovery` en `.github/workflows/ci.yml`.

## Contrato de integridad

La copia no se acepta si falla un checksum global, el inventario de media, el listado del dump o la
coincidencia de release. Después del restore, `verify_media_integrity.py` construye las keys
referenciadas por productos/adjuntos y las compara con el filesystem. El gate falla ante faltantes,
archivos no referenciados o symlinks.

El ensayo D05 crea producto, proforma, adjunto y variantes reales mediante el backend; escribe un
sentinel `.wav` en el volumen temporal; respalda; destruye PostgreSQL, Redis/audio y media; restaura;
ejecuta migraciones, smoke y la auditoría; y comprueba que los IDs, keys y archivos sobreviven sin
restaurar el audio.

## Comandos de validación

```sh
python3 scripts/test_media_inventory.py
python3 scripts/test_d05_contract.py
python3 scripts/validate_env_contract.py
python3 scripts/test_d04_contract.py
sh scripts/test_d05_recovery.sh
```

El último comando necesita Docker Compose y el checkout backend fijado. Se ejecutó localmente en el
namespace aislado `homex-d05-local` y terminó con `d05-backup-restore-gate-ok`; CI repite el mismo
ensayo en un runner limpio bajo `homex-d05-ci`.

## Riesgos y controles

- `--confirm` hace explícita la destrucción de la base objetivo;
- el restore rechaza un manifest de release distinto salvo override consciente;
- backup y media no pueden compartir árbol;
- un lock evita backups concurrentes;
- writers se detienen para capturar DB y media coherentes;
- la media anterior se conserva hasta que migraciones y auditoría concluyen;
- secretos/TLS requieren backup cifrado separado;
- la retención local no sustituye una copia off-host.

## Operación

El procedimiento completo, política inicial, restore y rollback están en
`docs/RECOVERY_RUNBOOK.md`.
