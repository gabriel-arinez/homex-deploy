# AP6 — Trazabilidad de release sin promoción

AP6 modifica contratos y persistencia en aplicación, pero no cambia la topología, secretos,
backups ni servicios de `homex-deploy`. Se mantiene D07 RC2 `0.7.0-d07-rc2` como **candidate** y no
se ejecutó ninguna acción sobre `homex-prod`.

La integración de AP6 debe crear una release posterior con commits/digests nuevos de backend y
frontend, manteniendo el wheel NLP `0.1.0` y declarando el adaptador HITL comercial `2.0`. El
manifiesto definitivo sólo puede fijarse después de que los PR de los cuatro repos estén verdes.

## Controles requeridos antes de una futura promoción

- migrar desde PostgreSQL vacío y sobre copia aislada de un respaldo histórico;
- conservar `CAJA` y `TOTAL_NEGOCIADO` históricos sin conversión inferida;
- verificar que media comercial y audio temporal mantienen sus políticas actuales;
- ejecutar pruebas concurrentes de venta/reversa decimal y recuperación outbox;
- regenerar OpenAPI/cliente TypeScript y ejecutar E2E comercial;
- ensayar backup/restore con los nuevos tipos `numeric(14,4)` y tablas/relaciones de familias;
- actualizar el manifiesto de release con SHA y digest reales, sin reutilizar RC2.

Los diagnósticos locales de AP6 se guardan fuera de los repositorios en
`~/Descargas/ap6-preflight-20261013/`. No contienen secretos ni datos productivos promovidos.

## AP6.0.21 — migración posterior requerida

AP6.0.21 reemplaza las columnas técnicas paralelas de `especificaciones_mueble` por
`datos_tecnicos JSONB` mediante una migración Django nueva. No cambia contenedores, red, storage,
backups ni secretos. La candidata D07 RC2 permanece inmóvil y no incorpora estos cambios.

Antes de una release posterior se debe respaldar PostgreSQL, ejecutar la migración sobre una copia
aislada, comprobar la preservación del JSON y ensayar rollback/restore como unidad coherente con
media. La migración no afecta audio temporal ni autoriza conservarlo. Backend debe fijarse antes del
frontend regenerado; NLP conserva wheel `0.1.0` y contrato v1. El diagnóstico AP6.0.21 está en
`~/Descargas/ap6021-diagnostico-20261014/`; no se modificó `homex-prod`.


## AP6.0.21 — corrección de auditoría: actualización de fichas aprobadas

La migración histórica `proformas.0009` está aplicada en algunos entornos y **no se
reescribe**. Si una base está todavía en `0008` y contiene especificaciones asociadas a
proformas `APROBADA`, el trigger PostgreSQL de inmutabilidad bloqueará el `UPDATE`
que hace la migración de datos. Por ello, el gate previo de una futura release debe
verificar las migraciones efectivas y **contar esas fichas**, no asumir que están vacías.

En una copia PostgreSQL restaurada y aislada, con backup íntegro de la base y media
asociada, verificar checksum SHA-256 y ejecutar desde el backend compatible
`scripts/ap6021_upgrade_aprobadas.py` con `--backup`, `--sha256`,
`--expected-database` y `--confirm AP6021-UPGRADE-CONTROLADO`. El script
aplica `0009` y `0010` dentro de una única transacción, desactiva exclusivamente
el trigger de especificaciones mientras posee bloqueo exclusivo de su tabla,
comprueba igualdad de todos los JSON migrados y lo reactiva antes del commit.
Si falla, el rollback PostgreSQL de la transacción restaura también el estado
del trigger. El CI del backend crea y **restaura** un `pg_dump -Fc` de prueba,
migra una ficha `APROBADA` y otra `BORRADOR` y revalida inmutabilidad.

Si `0009` ya está aplicada, sólo se requiere migrar `0010` normalmente y
confirmar el esquema. Desde `0010` el downgrade Django a `0009/0008` está
deliberadamente prohibido para evitar perder `datos_tecnicos`: el procedimiento
de reversión es restaurar backup PostgreSQL y media consistentes con la
versión anterior de backend/frontend, con ensayo del restore previo.

Esta guía **no autoriza** ejecutar las migraciones contra `homex-prod`,
actualizar manifiestos/digests, desplegar una release ni promover D07 RC2.
