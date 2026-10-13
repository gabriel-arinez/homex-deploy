# HOMEX — Estándar de ingeniería y gobernanza multi-repositorio (AP1)

**Fecha de adopción propuesta:** 12/10/2026. **Estado:** para revisión en PR
y vigencia tras integración en `main` de `homex-deploy`.

## 1. Alcance y autoridad

Este es el **documento rector transversal** para
`homex-frontend`, `homex-backend`, `homex-nlp` y `homex-deploy`.
Establece el proceso de calidad y trazabilidad en AP1 y AP2–AP5,
sin desplazar contratos de dominio: el backend y PostgreSQL son autoridad
monetaria, transaccional y comercial; NLP **propone**, la validación humana
acepta/corrige antes de persistir, frontend presenta y delega validaciones,
deploy versiona y opera releases. Un cambio técnico no aprueba por sí solo
una nueva decisión funcional: decisiones AP1–AP5 del documento de traspaso
2026-10-12 prevalecen en el rediseño; apartado 6 en adelante no aprobado.

Planes maestros de cada repositorio conservan sus convenciones. Contratos
versionados (OpenAPI, esquemas NLP, manifiestos de release) gobiernan las
interfaces efectivas. `homex_bd_final_v3.sql` se contrasta con migraciones
Django operativas y no representa una prohibición de migrar.

## 2. Flujo Git y PR

1. Antes de editar: identificar directorio real, `git status`, HEAD, ramas,
   remotos, upstream, diferencias ajenas y CI más reciente; no sobrescribir
   trabajo no propio. Los SHA de las fases son referencias, no checkout forzado.
2. Abrir rama de alcance limitado, de preferencia
   `fix/<fase>-<tema>`, `feat/<fase>-<tema>`,
   `test/<fase>-<tema>`, `docs/<fase>-<tema>` o
   `chore/<fase>-<tema>`. No modificar `main` directamente durante
   desarrollo. Commits pequeños, mensajes descriptivos, sin secretos.
3. PR contra `main`: motivo/requisito aprobado, repos afectados, rutas y
   contratos, migraciones/compatibilidad, pruebas positivas/negativas,
   comandos, riesgo, rollback, CI y evidencia. Declarar honestamente
   fallos, omisiones y bloqueos. Preferir revisión independiente del autor.
4. Merge tras gates requeridos en verde, conflictos resueltos y aprobación del
   revisor de diseño/función; usar la revisión formal de GitHub cuando
   esté habilitada y **no fingir** aprobación automática ni del mismo autor.
5. Tras merge: comprobar `main` y todos sus jobs de CI usando el SHA del
   merge, registrar enlace a ejecución y reconciliar cambios interrepo.
   Un PR verde no sustituye CI posterior al merge.
6. No emplear force push, reset hard, limpieza destructiva ni operaciones
   sobre ramas ajenas sin autorización. Para diagnóstico local guardar
   artefactos en `~/Descargas/`; no guardar secretos en estos archivos.

## 3. Quality gates existentes que NO deben rehacerse

| Repo | Convenciones | Contratos y pruebas | Seguridad |
| --- | --- | --- | --- |
| Frontend | Node 24, `npm ci`, lockfile, Prettier, Oxlint, ESLint, TypeScript | Vitest unit/component, Playwright E2E/responsive/a11y/integración real, build y OpenAPI snapshot/tipos generados | `npm audit --audit-level=high`, Gitleaks |
| Backend | Python 3.11, `uv.lock`, Ruff, Django checks | PostgreSQL real: migraciones, pytest, concurrencia, permisos DB, OpenAPI drift, F08/F09/F10 | Gitleaks, autorización/IDOR, `uv audit --locked` cuando PR AP1 de audit se integre |
| NLP | Python 3.11, `uv.lock`, Ruff | pytest, corpus/offsets/NER, schemas, distribución, consumidor backend y runtime ASR | Gitleaks, `uv audit --locked` cuando PR AP1 de audit se integre |
| Deploy | Compose, YAML, release manifest, pins/digests | builds, integration, health, backups, restores, resilience, QA0 documentado | Gitleaks, checks operativos y gates de release |

Las tecnologías de CI son propiedad de cada repositorio. No cambiar scripts
de pruebas para obtener un verde artificial, ni duplicar QA0 (ya cerrado).
Las pruebas nuevas de AP2, AP3–AP5 se agregan en las capas pertinentes.

Para dependencias Python se prefiere **`uv audit --locked`**, con consulta a
OSV y sin infraestructura de pago, ejecutado en CI. Un hallazgo no debe
ocultarse con `continue-on-error` ni listas masivas de exclusión;
se gestiona como vulnerabilidad reproducible o se justifica excepción
revisada con vencimiento. `uv.lock` se conserva; cambios se verifican en
CI e integraciones después de actualizarlo.

## 4. Matriz de seguridad transversal

- **Identidad/roles:** Django autoriza con clases de permisos y queryset
  del usuario. El frontend no determina propiedad; ningún endpoint
  (incluidos adjuntos, PDF, imágenes, audio y HITL) debe permitir IDOR.
  Admin puede actuar globalmente si su capacidad está definida.
- **Entradas:** serializer backend y validación PostgreSQL para datos
  comerciales; tipos, tamaño, MIME real y almacenamiento efímero para media/
  audio; no confiar en validaciones visuales.
- **Dinero/stock:** snapshots, total, reglas de moneda, transición y stock
  bajo transacción del backend/PG; nunca cálculos definitivos sólo en Vue.
- **Secretos/configuración:** no versionar credenciales; mínimo privilegio
  de token y roles PG; no exponer puertos DB/Redis ni credenciales en logs,
  comentarios o artefactos.
- **Releases:** manifiesto fija SHAs/digests y contratos de componentes;
  release RC2 continúa `candidate`. Está expresamente prohibido
  promocionar D07 o tocar `homex-prod` por ejecutar AP1–AP5.
- **Disponibilidad y privacidad:** backups, restore, observabilidad y
  limpieza de audio conservan cobertura QA0; ensayos destructivos sólo
  en namespaces aislados y con revisión de sus precondiciones.

## 5. Sincronización de contratos

Para todo cambio de endpoint, request/response, permisología o estado:
cambiar backend, `docs/openapi.yaml`, snapshot frontend y tipos generados,
consumidores Vue, pruebas de contrato, documentación de permisos y CI
de integración. Para voz/NLP: cambiar schemas/ejemplos, validadores,
consumer backend, procesamiento HITL y tests de extremos con idempotencia
y datos protegidos. Deploy sólo cambia pins/manifiesto mediante
un proceso de release **separado y autorizado**.

Migraciones: primero revisar histórico operativo y SQL de referencia,
proponer migración compatible, ejecutar migrate sobre PostgreSQL aislado,
demostrar propiedades de integridad y rollback aplicable, probar migración
con datos anteriores. No modificar DB productiva sin autorización.

## 6. Evidencia de aceptación por paquete

Cada AP tendrá: matriz decisión → rutas/migraciones/contrato → pruebas y
evidencia; CI por commit y posterior al merge; escenarios negativos
(propietario/ajeno/admin, errores de cliente, falla de stock, rollback,
concurrencia/idempotencia cuando aplique); lista de regresiones; PRs,
commits y riesgos residuales. AP2 audita eficacia de suites existentes;
no se interpreta el número de tests como cobertura suficiente.

## 7. Protección de main: dependencia externa visible

**Verificado al inicio AP1:** los cuatro `main` tenían
`protected=false`, sin reglas obligatorias de revisión; `homex-deploy`
devolvía una colección vacía de rulesets. GitHub connector vigente
**no dispone de acciones de administración de reglas**, aunque la
identidad pueda ver `permissions.admin=true` en metadatos del repo.
No afirmar que están activadas hasta leerlas de vuelta.

Seguimiento: [homex-deploy #11](https://github.com/gabriel-arinez/homex-deploy/issues/11).
Acción por propietario: GitHub, cada repositorio → Settings →
Rules → Rulesets (o Settings → Branches → Branch protection)
→ crear regla activa para `main`, requerir PR, revisión independiente,
resolución de hilos, checks CI concretos y bloquear force push/deletion.
Si GitHub limita esas funciones por plan/permisos, **documentar bloqueo
y aceptar explícitamente el riesgo de bypass**, manteniendo PR + verificación
manual hasta que puedan exigirse.

La selección de checks se hace con los nombres exactos reportados por
GitHub Actions. No exigir workflows basados en pin de RC2 para validar
cambios de `main` como si sustituyeran un gate de integración actual.
Un equipo de un solo autor necesita un revisor independiente real para
activar «required approving reviews» sin bloquear todos los merges.

**Estado de aplicación:** las políticas de este documento son estándar
de trabajo desde su merge; la configuración de GitHub sólo es efectiva
cuando `protected=true` y/o el ruleset correspondiente esté activo.
