# D07 — Cierre de implementación y pendientes diferidos

**Fecha de corte:** 2026-10-11  
**Rama:** `feat/d07-release-productiva`  
**PR:** https://github.com/gabriel-arinez/homex-deploy/pull/8  
**Release:** `0.7.0-d07-rc2` — **candidate** (NO promovida).  
**Decisión:** fusionar el trabajo de implementación en `main` por petición explícita del responsable del proyecto, **sin desplegar D07**, sin modificar el manifiesto a `released` y sin afirmar el cierre operativo/productivo.

## Implementado y evidenciado

- Manifiesto RC2 con referencias inmutables GHCR por digest para backend y frontend-proxy; validaciones de imagen/OCI y prechecks de despliegue.
- Pruebas de integración, seguridad/privacidad, contratos de release, resiliencia, medios, NLP/ASR y Outbox en escenarios aislados, según `docs/implementacion/D07_RELEASE.md`.
- Respaldo local y copia externa cifrada con Restic/R2 y restauración puntual aislada, según `docs/RECOVERY_RUNBOOK.md`. R2 no sirve la multimedia comercial.
- Compatibilidad de esquema D04 y D07 RC2; comprobaciones de migración `capturas.0007` → `0008` y recuperación de datos comerciales en PostgreSQL aislados.
- Se comprobaron los SHA-256 de las unidades `homex-20261009T051913Z`, `homex-20261011T041518Z` y `homex-20261011T042511Z`. Solo la primera corresponde a D04; las dos restantes a D07 RC1.
- Se creó en el host un worktree D04 separado en `~/Descargas/homex-d07-recovery-gate/deploy-d04` desde `2e5e0c5`; la copia del backup D04 y su manifiesto coinciden. Imágenes locales D04 disponibles (`homex/backend:d04-9ce7230`, `homex/frontend-proxy:d04-deba1de`).
- Restauración D04 en namespace `homex-d07-recovery-gate`: PostgreSQL 17.6 saludable, 34 tablas públicas, historial `capturas` con 7 migraciones; `grant-runtime` = 0 con `runtime-privileges-ok`; verificador de media = 0 con `db-media-integrity-ok` (0 archivos esperados/presentes). La sesión de terminal se cerró durante el ensayo; **no se observó el marcador final `homex-restore-ok`**, por tanto no se considera prueba integral terminada.
- En la última observación, los siete contenedores productivos de `homex-prod` continuaban activos y saludables o activos según servicio.

## Pendientes que NO deben marcarse como terminados

1. **Recovery/failover D07 operacional completo:** levantar API, worker, Redis y componentes pertinentes de D04 en el namespace aislado; verificar health/readiness/smoke; inducir fallo real controlado de migración D04→D07; comprobar que no se reanudan escritores antiguos de forma insegura; restaurar unidad D04 compatible y validar rollback de servicios, DB y media. Documentar outputs, checksums y criterios de aceptación. Las pruebas simuladas de `deploy.sh` NO sustituyen esto.
2. **Integridad comercial y media bajo concurrencia:** probar recuperación integral de ficheros referenciados por registros reales y reconciliación de tareas Outbox tras consumo/duplicados, incluyendo apagones de procesos/Redis sin perder trabajo. El backup D04 de este ensayo contenía 0 ficheros.
3. **Dispositivos y acceso privado:** PC, tablet y móvil autorizados, rechazo a equipo no autorizado, rutas reales HTTPS/Zero Trust y experiencia de flujo voz→NLP→HITL→medios persistentes sobre hardware definitivo.
4. **Rendimiento y producción:** perfilar ASR/CPU/RAM/latencia en el hardware objetivo; ventana autorizada de migración; backup predeploy + copia remota, smoke/readiness/monitor y procedimiento de reversión.
5. **Operación de R2:** aprobar política de retención remota, ensayar su automatización segura y alertas ante fallo de red/almacenamiento; custodiar por separado credenciales y contraseña de recuperación. No ejecutar `restic forget --prune` sin política.
6. **Mantenimiento del ensayo:** inspeccionar/retirar cuando se autorice los contenedores/volúmenes de ensayo D07, incluidos `homex-d07-recovery-gate` y los antiguos RC2; no aplicar `docker compose down -v` sobre otros proyectos ni tocar `homex-prod`.

## Reanudación recomendada

1. Partir de `main` tras el merge; abrir rama nueva específica de validación/cierre operativo, no ejecutar los procedimientos pendientes sobre producción.
2. Inspeccionar los recursos existentes `homex-d07-recovery-gate` **antes** de reutilizar o limpiar. Mantener el backup de origen `/srv/homex/backups/homex-20261009T051913Z` inmutable.
3. Completar el test integral y actualizar evidencias del runbook; ejecutar CI, registrar SHA y resultado.
4. Solo con todos los gates operativos verdes y autorización explícita, considerar promoción a `released` y despliegue. **Este merge no constituye autorización de despliegue.**

## Notas importantes

- `D07_RELEASE.md` incluye observaciones históricas RC1/RC2 y frases anteriores que condicionaban el merge a la validación completa. La decisión actual es **merge de implementación con pendientes expresos**, no aprobación de release productiva; prevalece este criterio para interpretar el estado posterior.
- Las verificaciones locales comunicadas durante el ensayo no sustituyen una inspección directa actual de procesos/volúmenes ni pruebas nuevas.
