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
