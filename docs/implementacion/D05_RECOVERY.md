# D05 — Backup, restore, migración y rollback

## Estado y base

**CERRADA — 8 de octubre de 2026.**

- rama: `feat/d05-backup-restore`;
- base rectora incorporada: `main` en `3fa35d30d7dce742a4bb4a21ee2479fa98dab4bd` (D04 cerrada);
- reconciliación D04 → D05: `17898bb238f74d7790764fd438e01fdaae980523`;
- backend fijado: `9ce723048d98a3925be45d9c359a25e6be7b19f3`;
- frontend fijado: `deba1de244395dbdcb266f03026630b403768d71`;
- NLP fijado: `8d1750b2d1d26f6d90da10603216b7926bdaf820`;
- implementación operativa: `f46239e`;
- gate destructivo inicial: `8cd5d24`;
- prevalidación segura antes de destrucción: `5587106590a0d6695473eaa065babfe58dda43da`;
- prueba de atomicidad/prevalidación: `a335d3d7e0e2f0e9db1f36d392d567300339cefb`;
- GitHub Actions push run `37833997224`: **success**.

La precondición D04 quedó formalmente cerrada y fusionada antes del cierre de D05. La rama D05 fue
reconciliada con ese `main`, reejecutó la CI completa y no mantiene bloqueos técnicos abiertos.

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
coincidencia de release. Antes de cualquier destrucción de PostgreSQL, `restore.sh` extrae la media
en staging, valida íntegramente su inventario y confirma que `database.dump` es legible con
`pg_restore --list`. Sólo entonces entra en la sección destructiva del restore.

Después del restore, `verify_media_integrity.py` construye las keys referenciadas por
productos/adjuntos y las compara con el filesystem. El gate falla ante faltantes, archivos no
referenciados o symlinks. El ensayo adicional corrompe de forma controlada el inventario de media y
demuestra que el restore falla conservando intacta una guardia creada en la base activa.

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
- media e inventario se prevalida completamente antes de tocar PostgreSQL;
- `pg_restore --list` valida el dump antes de `dropdb`;
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


## Evidencia final de cierre

La CI completa posterior a la reconciliación con D04 quedó verde. En particular, el job
`recovery` volvió a ejecutar el ensayo destructivo y la prueba negativa de media incoherente,
mientras los gates heredados D01–D04 continuaron verdes.

D05 cumple el criterio rector: existe un backup real que fue restaurado en un entorno limpio,
PostgreSQL y media quedaron coherentes después de la recuperación, el audio temporal no se restauró
y una unidad de media inválida es rechazada antes de modificar la base activa.

**D05 CERRADA. La siguiente fase formal es D06 — observabilidad, seguridad operacional y resiliencia.**
