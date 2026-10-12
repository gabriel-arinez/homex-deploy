# Apartado 0 — Evidencia remota inicial y bloqueo del ensayo en host

**Fecha de observación:** 2026-10-11 America/La_Paz (ejecuciones GitHub UTC 2026-10-12).  
**Alcance:** diagnóstico remoto y trazabilidad; no equivale a evidencia de ejecución en el host.

## Base GitHub consultada

| Repositorio | main al diagnóstico | Último workflow main observado |
| --- | --- | --- |
| homex-frontend | `691bdc52751fdd137049e6790c91b6504b26d48f` | [38188205360](https://github.com/gabriel-arinez/homex-frontend/actions/runs/38188205360) — failure |
| homex-backend | `a715876cc9b3c4a85aa397e736e60b18b90085fa` | [38188201596](https://github.com/gabriel-arinez/homex-backend/actions/runs/38188201596) — success |
| homex-nlp | `0390a461551f105d138ef4e73aae57e7e16c7360` | [38188210073](https://github.com/gabriel-arinez/homex-nlp/actions/runs/38188210073) — success |
| homex-deploy | `68194a292a8f7c35552a33321c5503bfc5fe5cbd` | [38188197433](https://github.com/gabriel-arinez/homex-deploy/actions/runs/38188197433) — success |

- `main` respondió `protected: false` en los cuatro repositorios; la consulta de rulesets devolvió `[]` y los endpoints de branch protection devolvieron 403 al conector. **No afirmar protección efectiva sin acceso para auditarla**.
- El log frontend identifica únicamente `docs/D07_TRAZABILIDAD_INTERREPOSITORIO_20261011.md` bajo `prettier --check .`. PR de corrección: [frontend #14](https://github.com/gabriel-arinez/homex-frontend/pull/14). **El PR no constituye PASS hasta CI verde y merge verificado**.
- Manifiesto `releases/manifest.yaml`: `0.7.0-d07-rc2`, `status: candidate`; conservar digests GHCR y fuentes RC2.
- GitHub confirma estado de código **únicamente**. No se ha observado directamente `homex-prod` ni se ha realizado recovery de host desde esta sesión.

## Matriz inicial — no confundir historia con nueva evidencia

| Gate | Estado | Motivo / evidencia faltante |
| --- | --- | --- |
| Inspección GitHub HEAD y CI históricos | PASS | HEAD y URL de cada run anteriores |
| Detección de causa del fallo frontend | PASS | Log de run 38188205360, job format |
| Corrección y CI final de frontend | NOT RUN | CI/merge/CI main posteriores pendientes |
| Inspección actual de contenedores y volúmenes host | BLOCKED | No existe acceso al host desde el entorno de GitHub; ejecutar diagnóstico de solo lectura en host |
| Recuperación aislada D04 → D07 → D04 integral | NOT RUN | Requiere recursos aislados comprobados, fallo real a mitad de migración, DB/media referenciada y todos los servicios |
| Redis, worker, beat, Outbox, fencing, duplicados | NOT RUN | Requiere pruebas reales con PostgreSQL/Redis/Celery aislados |
| Restic/R2 actualmente operativo, timer, alertas | NOT RUN | Solo pruebas documentadas históricamente, falta lectura actual del host |
| Contratos y regresión final de los cuatro main | NOT RUN | Revalidar tras PR y cambios técnicos |

## Prohibiciones y pendientes operativos

Mantener `homex-prod` y su Cloudflare sin intervención. No promover RC2 ni ejecutar D08/F11. No borrar snapshots ni usar `restic forget --prune`. El backup original D04 y los namespaces previos son intocables sin autorización adicional.

**Retención R2 propuesta para evaluación (no aprobada ni automatizada):** documentar ventana de recuperación y RPO/RTO medidos con restauración real; designar al responsable de infraestructura para custodia de claves, seguimiento diario del timer y prueba mensual de recuperación aislada. Las generaciones y costes deben calcularse sobre tamaños/frecuencia medidos; no imponer una política arbitraria.

**Alertas propuestas, pendientes de aprobación operativa:** notificación de ejecución de backup fallida, copia offsite fallida, snapshot no reciente, chequeo de integridad fallido y prueba de restore no conforme. Validar las alertas en un repositorio Restic de ensayo y sin cambiar producción.

## Condición para completar apartado 0

No declarar CERRADO mientras falte recuperación aislada integral PASS, pruebas reales de resilience, comprobación Restic/R2 y CI final de todas las `main`. Los ensayos físicos y promoción productiva D07 permanecen diferidos por decisión funcional.

## Adenda de cierre en host

Las limitaciones remotas de esta acta fueron resueltas posteriormente mediante
dos namespaces aislados en el host. El cierre autoritativo, la matriz
`PASS / BLOCKED / NOT RUN`, los comandos de reproducción y la evidencia
versionada se encuentran en
[`QA0_CIERRE_ESTABILIZACION_20261011.md`](QA0_CIERRE_ESTABILIZACION_20261011.md).
Esta adenda no cambia `homex-prod`, no promueve RC2 y no habilita D08/F11.
