# Plan maestro de implementación, despliegue y operación — HOMEX Deploy

**Fecha de revisión:** 25 de septiembre de 2026  
**Versión del plan:** 1.0  
**Repositorio:** gabriel-arinez/homex-deploy  
**Rama rectora:** main  
**Repositorio recién inicializado:** commit 343f6eb390f4794a49f1bad1a242c1af2817ef0b  
**Repositorios coordinados:** homex-backend, homex-frontend, homex-nlp y homex-deploy  
**Objetivo operativo:** convertir los tres componentes de HOMEX en una release reproducible, observable, recuperable y desplegable sin mover reglas de negocio a infraestructura.

---

# 0. Propósito

Este documento es el contrato de ejecución de homex-deploy.

El repositorio de despliegue no es un cuarto lugar para implementar lógica comercial. Su responsabilidad es ensamblar, versionar, desplegar, proteger, observar, respaldar y recuperar los componentes que ya son autoridad en sus repositorios de origen.

Cada fase de este plan define:

1. precondiciones inter-repositorio;
2. alcance permitido;
3. trabajo obligatorio;
4. trabajo prohibido;
5. pruebas y gates;
6. evidencia de cierre;
7. condición para iniciar la siguiente fase.

Una fase no se considera terminada porque Docker Compose arranque o porque una URL responda. Deben pasar todos los gates de la fase y la evidencia debe quedar versionada.

---

# 1. Auditoría de estado al crear este plan

La planificación de deploy se construye sobre el estado real de los repositorios al 25 de septiembre de 2026, no sobre una secuencia hipotética.

## 1.1. homex-nlp

Estado confirmado en main:

- F00–F06 implementadas y fusionadas;
- versión de integración homex-nlp 0.1.0;
- contrato externo v1;
- paquete preparado para consumo del backend;
- CI de main verde en el commit b5fe2921320c9031f6d44dc5c91a18411daa393e;
- la antigua persistencia SQLite no es parte de la arquitectura activa;
- el paquete NLP no es autoridad de negocio, permisos ni persistencia comercial.

Para deploy, la fase NLP que importa como precondición técnica es F06.

Las fases F07–F11 descritas por el plan NLP son fases coordinadas del sistema. En particular, F10 corresponde a despliegue reproducible y recuperación y será satisfecha principalmente mediante este repositorio.

## 1.2. homex-backend

Estado confirmado en main:

- F07.0–F07.7 cerradas;
- F08.0–F08.4 cerradas;
- F08 está formalmente cerrada con PostgreSQL, Redis y worker real;
- media persistente F07.7 cerrada;
- Cloudflare R2 quedó definido como proveedor productivo, pero su provisión real pertenece a infraestructura;
- auth/me y capabilities están integrados en main;
- el contrato de listado, búsqueda, filtros y paginación requerido por FE03 está integrado en main;
- CI de main verde en adb949268277da4361f37c96b786c5cdd0265750.

Por tanto:

- F09 — integración con frontend está en curso;
- F10 — despliegue y recuperación no está cerrada;
- F11 — piloto y cierre no está cerrada.

Este repositorio será la principal fuente de evidencia para cerrar backend F10.

## 1.3. homex-frontend

Estado confirmado en main:

- FE00 cerrada;
- FE01 cerrada;
- FE02 cerrada;
- CI de main verde en fff381b52d0c7e4bad8cec6749caf30ee098e72d.

Existe la rama feat/fe03-clientes-productos con el commit:

- 99a327ece01703633bfe3964109f927ef5a6053f — FE03 clientes y catálogo visual.

Sin embargo, esa rama está divergida respecto de main y FE03 no se considera cerrada desde el punto de vista de este plan hasta que:

- se actualice con el contrato backend vigente;
- sus gates vuelvan a pasar;
- CI remoto esté verde;
- se fusione a main;
- exista evidencia final de cierre.

Por tanto, FE04–FE09 permanecen pendientes.

## 1.4. homex-deploy

Estado confirmado:

- un único commit inicial;
- README y .env.example básicos;
- docker-compose.yml vacío;
- nginx/default.conf vacío;
- docs/ARQUITECTURA_DEPLOY.md vacío;
- este PLAN_MAESTRO.md era un placeholder vacío;
- no existe todavía CI;
- no existen imágenes;
- no existe manifiesto de release;
- no existe backup/restore;
- no existe observabilidad;
- no existe entorno integrado reproducible.

Conclusión de la auditoría:

**Deploy puede comenzar ahora. No debe esperar a FE09.**

D00–D03 pueden ejecutarse mientras frontend continúa FE03–FE08. Las fases de release integrado D04 en adelante sí dependen de que frontend y backend hayan alcanzado sus respectivos puntos de integración.

---

# 2. Jerarquía de autoridad

Cuando dos documentos parezcan contradecirse, usar este orden:

1. contratos y decisiones ya cerradas del backend para negocio, API, PostgreSQL, R2 y permisos;
2. contrato v1 y documentación de integración de homex-nlp para NLP/ASR;
3. OpenAPI versionado del backend para frontend/API;
4. plan maestro vigente de homex-backend;
5. plan maestro vigente de homex-frontend;
6. plan maestro vigente de homex-nlp;
7. este plan para infraestructura;
8. configuraciones históricas o experimentales.

Infraestructura nunca corrige una contradicción comercial inventando comportamiento.

Si una fase de deploy descubre que falta una capacidad en una aplicación, debe registrar el bloqueo en el repositorio propietario y esperar el cambio allí.

---

# 3. Fronteras de responsabilidad

## 3.1. homex-backend es dueño de

- autenticación y autorización;
- API y OpenAPI;
- reglas comerciales;
- migraciones Django;
- PostgreSQL como autoridad comercial;
- Celery/tasks y contrato de worker;
- outbox, publicación y reconciliación;
- archivos temporales privados de audio según su contrato;
- integración con homex-nlp;
- object keys y metadatos de media;
- endpoints de health/readiness que dependan del estado real de la aplicación.

## 3.2. homex-nlp es dueño de

- paquete homex-nlp;
- contrato v1;
- reglas/NER;
- ASR desacoplado;
- configuración y artefactos/versiones del modelo;
- lógica pura de comparación HITL.

No es dueño de PostgreSQL, Redis, HTTP, permisos ni persistencia comercial.

## 3.3. homex-frontend es dueño de

- aplicación Vue;
- build de producción;
- contrato OpenAPI consumido;
- navegación y UI;
- seguridad del código cliente;
- no incluir secretos en el bundle.

No debe duplicar Nginx, TLS, Compose o infraestructura productiva.

## 3.4. homex-deploy es dueño de

- Dockerfiles y ensamblaje de release cuando sean exclusivamente infraestructura;
- Docker Compose de desarrollo integrado/staging/producción;
- reverse proxy;
- TLS/HTTPS;
- headers de seguridad;
- configuración de red;
- secretos de despliegue;
- manifiesto de versiones;
- migración controlada de release;
- health orchestration;
- backup/restore;
- R2 productivo y dominio público de media;
- persistencia y volúmenes operativos;
- limpieza independiente de audio temporal;
- logging/monitorización;
- smoke tests;
- runbooks;
- rollback compatible;
- evidencia de recuperación.

Este repositorio no contiene modelos ORM, reglas de permisos, cálculos comerciales, lógica NLP ni componentes Vue de dominio.

---

# 4. Arquitectura objetivo

La topología productiva objetivo es:

~~~text
Internet
   |
   v
Reverse proxy / TLS
   |
   +---- / ----------------------> Vue estático
   |
   +---- /api/... ---------------> Django/DRF API
                                      |
                                      +---- PostgreSQL
                                      |
                                      +---- Redis
                                      |
                                      +---- Cloudflare R2
                                      |
                                      +---- temporales privados NLP
                                                |
                                                v
Redis <------------------------- publicador/reconciliador
  |
  v
Worker Django/Celery
  |
  +---- ASR
  |
  +---- homex-nlp fijado por versión
  |
  +---- PostgreSQL
~~~

Media pública persistente:

~~~text
Vue/API
   |
   +---- URLs públicas estables ----> media.<dominio>
                                        |
                                        v
                              Cloudflare R2 Standard
                              bucket: homex-public-media
                              prefijos:
                              - productos/
                              - proformas/
~~~

Reglas:

- PostgreSQL es la autoridad comercial;
- Redis no es fuente de verdad;
- R2 contiene binarios persistentes de media pública;
- PostgreSQL conserva keys/metadatos, no binarios;
- audio NLP es temporal, privado y excluido de backups;
- ningún volumen Docker productivo se usa como media comercial persistente;
- API y worker usan la misma release de backend;
- el worker consume una versión exacta de homex-nlp;
- frontend se sirve como build estático;
- producción no depende de repositorios Git montados dentro de contenedores.

---

# 5. Estrategia de releases

Toda release integrada debe declarar exactamente qué ejecuta.

Se creará:

~~~text
releases/
└── manifest.yaml
~~~

El manifiesto debe incluir como mínimo:

- versión/release HOMEX;
- SHA o tag exacto de homex-backend;
- SHA o tag exacto de homex-frontend;
- versión y artefacto exacto de homex-nlp;
- hash del wheel/artefacto NLP;
- versión del modelo ASR;
- hash o identificador del modelo ASR;
- imagen/tag/digest de API;
- imagen/tag/digest de worker;
- imagen/tag/digest de frontend/proxy;
- versión de PostgreSQL;
- versión de Redis;
- versión de esquema/migración esperada;
- fecha de creación de release.

Está prohibido definir producción con main, latest u otra referencia flotante como única identificación.

---

# 6. Variables, secretos y configuración

## 6.1. Regla principal

.env.example documenta nombres y semántica, nunca secretos reales.

Producción debe inyectar secretos desde el mecanismo del entorno de despliegue. Ningún secreto se versiona.

## 6.2. Familias mínimas

El contrato final de variables se obtiene de los repositorios fuente durante D00. Debe cubrir, como mínimo:

- Django;
- PostgreSQL;
- Redis/Celery;
- R2/S3 compatible;
- dominio de media;
- CORS/CSRF/hosts;
- frontend API base cuando realmente sea necesaria en build/runtime;
- rutas/modelos ASR;
- directorio temporal NLP;
- configuración de proxy/TLS;
- logging.

No se crearán nombres alternativos en deploy si ya existe un nombre contractual en la aplicación.

## 6.3. Prohibiciones

- secretos en Git;
- secretos dentro del bundle Vue;
- secrets ARG/ENV permanentes en capas de imagen;
- credenciales R2 expuestas al navegador;
- contraseña PostgreSQL dentro de compose versionado;
- usar un único usuario PostgreSQL con privilegios de propietario para runtime si backend ya define separación de roles.

---

# 7. Persistencia y volúmenes

Persistencia productiva permitida:

- PostgreSQL: volumen persistente y respaldado;
- modelos ASR: artefacto preinstalado o volumen/versionado de solo lectura, según cierre de D01;
- certificados si la plataforma elegida los requiere localmente.

Persistencia no autoritativa:

- Redis: reconstruible; no sustituye outbox/PostgreSQL;
- temporales NLP: volumen/directorio privado y efímero, excluido de backup;
- cachés de build: nunca parte de la release;
- frontend: imagen inmutable, sin volumen mutable de código.

R2 es almacenamiento externo y no un volumen Docker.

---

# 8. Migraciones y arranque

La release no permite que múltiples réplicas ejecuten migraciones sin coordinación.

Patrón objetivo:

1. validar variables y servicios;
2. backup previo cuando corresponda;
3. ejecutar un job/servicio one-shot de migración;
4. verificar que la migración terminó correctamente;
5. iniciar/actualizar API y worker;
6. ejecutar smoke;
7. promover la release;
8. conservar procedimiento de rollback/restore.

No usar migrate como efecto lateral no coordinado de cada arranque de API.

Si una migración no es compatible con rollback de aplicación, la documentación debe declararlo antes de desplegar.

---

# 9. Health, readiness y smoke

D00 debe inventariar los checks reales del backend.

Si falta un endpoint que deba reflejar estado interno real, se implementa en homex-backend antes de declararlo disponible desde deploy.

Checks mínimos del sistema:

- reverse proxy responde;
- frontend entrega index/assets;
- fallback SPA funciona;
- API liveness;
- API readiness con dependencias necesarias;
- PostgreSQL healthy;
- Redis healthy;
- worker disponible;
- migraciones en versión esperada;
- flujo API autenticado mínimo;
- lectura/escritura R2 de prueba en entorno no productivo;
- ruta de media pública accesible;
- ausencia de secretos en respuestas.

Los checks de health no deben ejecutar operaciones comerciales irreversibles.

---

# 10. Backups y recuperación

## 10.1. PostgreSQL

Debe existir:

- script de backup;
- verificación del archivo generado;
- política de retención;
- restore a una instancia limpia;
- smoke posterior al restore;
- registro de fecha, versión y migración;
- documentación de RPO/RTO cuando la decisión de negocio exista.

## 10.2. R2

El backup PostgreSQL no copia binarios de R2.

Debe documentarse:

- que PostgreSQL contiene keys/metadatos;
- cómo verificar referencias DB ↔ R2;
- qué hacer ante referencia huérfana;
- qué hacer ante objeto faltante;
- cómo validar consistencia después de restore.

## 10.3. Audio NLP

El audio temporal:

- no entra en backup;
- no entra en snapshots persistentes;
- no se recupera como archivo histórico;
- tiene limpieza independiente del worker de inferencia.

---

# 11. Reverse proxy y frontend

El proxy productivo debe cubrir:

- HTTPS;
- redirección HTTP → HTTPS;
- fallback SPA;
- proxy de API;
- compresión;
- cache largo para assets con hash;
- no cachear incorrectamente index.html;
- CSP;
- HSTS cuando HTTPS definitivo esté validado;
- X-Content-Type-Options;
- Referrer-Policy;
- límites de body compatibles con los uploads permitidos por backend;
- timeouts compatibles con recepción de audio sin convertir al proxy en almacenamiento.

La política exacta de CSP debe construirse a partir del frontend real y del dominio público de media. No usar unsafe-inline/unsafe-eval por comodidad salvo justificación explícita y temporal.

---

# 12. Estrategia de ramas y protocolo de ejecución

Cada fase de deploy se implementa en una rama propia.

Patrón:

~~~text
main
  ├── feat/d00-baseline
  ├── feat/d01-core-runtime
  ├── feat/d02-staging-proxy
  ├── feat/d03-r2-media
  ├── feat/d04-release-candidate
  ├── feat/d05-backup-restore
  ├── feat/d06-observabilidad
  ├── feat/d07-release
  └── feat/d08-piloto-cierre
~~~

Reglas:

- una fase parte de main después de fusionar la anterior, salvo paralelismo explícitamente autorizado por este plan;
- una PR corresponde a una fase;
- no mezclar cambios de aplicación que pertenecen a backend/frontend/NLP;
- no cerrar una fase con CI rojo;
- no ocultar fallos con sleeps arbitrarios;
- no usar latest;
- no fijar secretos de ejemplo reales;
- no eliminar healthchecks para hacer pasar Compose.

Cada fase crea:

~~~text
docs/implementacion/<FASE>.md
~~~

El informe incluye:

- commit base;
- precondiciones inter-repositorio verificadas;
- archivos modificados;
- imágenes/versiones;
- variables añadidas;
- pruebas;
- resultado de gates;
- evidencia CI;
- riesgos;
- bloqueos;
- comandos de operación;
- commit final.

---

# 13. CI mínimo de homex-deploy

D00 debe crear CI con jobs independientes.

Mínimo progresivo:

## 13.1. config

- docker compose config;
- validación de archivos YAML;
- comprobación de variables requeridas sin secretos;
- validación del manifiesto de release.

## 13.2. build

- construir imágenes sin cache obligatorio;
- no depender de archivos no versionados;
- comprobar que el frontend usa npm ci;
- comprobar que Python usa locks/artefactos fijados.

## 13.3. proxy

- nginx -t o equivalente real dentro de la imagen;
- fallback SPA;
- proxy /api;
- headers esperados.

## 13.4. integration

Con servicios efímeros:

- PostgreSQL;
- Redis;
- migraciones desde vacío;
- API;
- worker;
- smoke mínimo.

## 13.5. recovery

A partir de D05:

- backup;
- destrucción de la base de prueba;
- restore;
- smoke posterior.

CI nunca utiliza credenciales productivas.

---

# 14. Fases de ejecución

# D00 — Baseline de infraestructura y contrato de despliegue

**Objetivo:** convertir el repositorio inicial vacío en una base verificable sin desplegar todavía producción.

**Puede comenzar ahora.**

## Precondiciones obligatorias de otros repositorios

- homex-nlp: F06 cerrada y fusionada a main;
- homex-backend: F08.4 cerrada y fusionada a main;
- homex-frontend: FE02 cerrada y fusionada a main.

Estado al crear este plan: **las tres precondiciones están satisfechas**.

FE03 no es precondición de D00.

## Trabajo obligatorio

- auditar .env.example de los tres repositorios;
- inventariar comandos reales de API, worker, publicador/reconciliador y limpieza;
- inventariar health/readiness existentes;
- inventariar puertos reales;
- inventariar dependencias externas;
- definir estructura definitiva del repositorio;
- crear compose base válido;
- crear CI inicial;
- crear esquema de releases/manifest.yaml;
- completar docs/ARQUITECTURA_DEPLOY.md;
- documentar qué componentes faltantes requieren cambios en su repo propietario;
- retirar del .env.example de deploy variables inventadas que no correspondan al contrato real.

## Prohibido

- crear endpoints ficticios de health;
- inventar comandos Celery;
- copiar lógica Python;
- introducir R2 con credenciales reales;
- crear todavía producción definitiva.

## Gates

- docker compose config;
- YAML válido;
- CI verde;
- ninguna variable contractual duplicada con otro nombre;
- arquitectura y comandos trazables a repositorios fuente.

## Cierre

docs/implementacion/D00_BASELINE.md.

---

# D01 — Runtime integrado de backend + NLP

**Objetivo:** ejecutar localmente de forma reproducible la parte server-side real de HOMEX.

## Precondiciones obligatorias

- D00 cerrada;
- homex-backend F08.4 cerrada;
- homex-nlp F06 cerrada.

Frontend no es precondición.

## Trabajo obligatorio

Construir/orquestar:

- PostgreSQL versionado;
- Redis versionado;
- imagen backend común para API y worker;
- API Django;
- worker Celery;
- publicador/reconciliador según comandos reales del backend;
- servicio/job independiente de limpieza de audio;
- modelo/artefacto ASR fijado por versión/hash;
- wheel/artefacto homex-nlp exacto;
- volumen temporal NLP privado y no respaldado;
- job de migración one-shot;
- healthchecks internos;
- redes separadas cuando aporten aislamiento real.

## Tests obligatorios

- base vacía → migrate;
- segunda migración → no-op;
- API inicia;
- Redis inicia;
- worker responde;
- pipeline F08 feliz con worker real;
- caída/reinicio de Redis no convierte Redis en fuente de verdad;
- temporales de audio no quedan expuestos públicamente;
- cleanup puede ejecutarse aunque el worker NLP esté detenido;
- reinicio de contenedores no pierde PostgreSQL.

## Cierre

docs/implementacion/D01_CORE_RUNTIME.md.

---

# D02 — Staging integrado y reverse proxy

**Objetivo:** disponer de un entorno integrado estable que frontend pueda utilizar durante FE03–FE08.

## Precondiciones obligatorias

- D01 cerrada;
- homex-frontend FE02 cerrada;
- contrato auth/OpenAPI consumido por FE02 vigente.

FE03 puede estar todavía en desarrollo.

## Trabajo obligatorio

- build reproducible del frontend;
- imagen/etapa estática de frontend;
- reverse proxy;
- proxy /api;
- fallback SPA;
- API base correcta;
- cache de assets con hash;
- index sin cache inadecuado;
- compresión;
- límites de upload compatibles;
- headers base;
- entorno staging reproducible;
- smoke navegador/API.

## Regla de coordinación

Durante FE03–FE08 este entorno puede actualizar el SHA de frontend/backend para integración, pero una release candidata no puede usar referencias flotantes.

## Tests obligatorios

- refresh directo de una ruta Vue no produce 404;
- assets se sirven correctamente;
- /api llega al backend;
- 401/403 se conservan y no son transformados por Nginx;
- uploads permitidos atraviesan el proxy;
- frontend no contiene secretos;
- no hay CORS/CSRF relajado universalmente para “hacer funcionar” staging.

## Cierre

docs/implementacion/D02_STAGING_PROXY.md.

---

# D03 — Cloudflare R2 y media pública

**Objetivo:** materializar la infraestructura externa ya congelada por backend F07.7.

## Precondiciones obligatorias

- D01 cerrada;
- homex-backend F07.7 cerrada;
- homex-backend F08.4 cerrada;
- disponibilidad de cuenta/configuración Cloudflare necesaria.

Frontend FE03 no necesita estar cerrada para iniciar D03.

## Trabajo obligatorio

- provisionar bucket único homex-public-media;
- configurar prefijos productos/ y proformas/;
- configurar dominio propio de media;
- configurar lectura pública;
- inyectar credenciales sólo en backend;
- comprobar que URLs devueltas son públicas/estables;
- definir cache/CDN;
- documentar rotación de credenciales;
- comprobar que producción falla claramente si faltan variables;
- comprobar que ningún volumen Docker reemplaza R2.

## Tests obligatorios

- carga de imagen de producto;
- lectura pública sin autenticación;
- variantes WebP accesibles;
- adjunto de proforma accesible;
- borrado autorizado elimina objetos esperados;
- prefijos correctos;
- base conserva key y no URL completa;
- ningún secreto aparece en frontend, OpenAPI o logs.

## Cierre

docs/implementacion/D03_R2_MEDIA.md.

---

# D04 — Release candidate integrada

**Objetivo:** congelar una combinación completa backend/frontend/NLP lista para ensayos de producción.

## Precondiciones obligatorias

Antes de iniciar D04 deben estar terminadas:

- homex-nlp F06;
- homex-backend F08.4;
- homex-frontend FE08;
- integración backend F09 en alcance funcional necesario para FE08;
- D00–D03.

La evidencia de D04 puede formar parte del cierre formal de backend F09 si el último gate pendiente es el E2E compartido en entorno integrado; no se permite que ambos lados se declaren cerrados basándose solamente el uno en el otro.

## Trabajo obligatorio

- fijar SHAs/tags de backend y frontend;
- fijar artefacto/hash NLP;
- fijar modelo ASR;
- generar manifest.yaml;
- build limpio de todas las imágenes;
- Compose de release/producción;
- política definitiva de secrets;
- CSP real;
- HSTS después de validar HTTPS;
- TLS;
- hosts/CORS/CSRF productivos;
- source maps según política;
- límites de recursos iniciales;
- smoke E2E crítico.

## E2E mínimo

- login;
- identidad/capabilities;
- clientes;
- catálogo;
- proforma manual;
- aprobación;
- pedido + movimiento de stock + OT;
- recibo;
- LISTO_ENTREGA;
- nota de entrega;
- captura NLP;
- procesamiento worker;
- HITL;
- media pública.

## Cierre

docs/implementacion/D04_RELEASE_CANDIDATE.md.

---

# D05 — Backup, restore, migración y rollback

**Objetivo:** demostrar recuperación real antes de considerar producción.

## Precondiciones obligatorias

- D04 cerrada;
- backend F09 funcionalmente cerrado para la release candidata;
- frontend FE08 cerrada.

## Trabajo obligatorio

Crear:

- scripts/backup.sh;
- scripts/restore.sh;
- scripts/deploy.sh;
- scripts/smoke.sh;
- procedimiento de migración;
- procedimiento de rollback compatible;
- verificación DB ↔ R2;
- documentación recovery/runbook.

## Ensayo obligatorio

1. desplegar release candidata;
2. cargar datos representativos;
3. generar backup PostgreSQL;
4. destruir/recrear la base de prueba;
5. restaurar;
6. ejecutar migraciones necesarias;
7. levantar API/worker;
8. ejecutar smoke;
9. verificar keys de media contra R2;
10. verificar que ningún audio fue respaldado.

**No se cierra D05 con un backup nunca restaurado.**

## Cierre

docs/implementacion/D05_RECOVERY.md con evidencia exacta del restore.

---

# D06 — Observabilidad, seguridad operacional y resiliencia

**Objetivo:** hacer observable el sistema y comprobar fallos operativos controlados.

## Precondiciones obligatorias

- D05 cerrada;
- backend F08.4 cerrada;
- release candidata D04 disponible.

## Trabajo obligatorio

- logs estructurados o formato operacional definido;
- correlación suficiente entre proxy/API/worker;
- evitar datos sensibles;
- métricas básicas de API, worker, Redis y PostgreSQL;
- espacio de disco para temporales;
- alertas mínimas;
- health/readiness consumibles;
- rotación de logs;
- límites CPU/RAM iniciales;
- reinicio controlado;
- documentación monitoring/README.md.

## Fallos a ensayar

- PostgreSQL no disponible;
- Redis no disponible;
- worker caído;
- proxy reiniciado;
- API reiniciada;
- R2 no disponible;
- temporal lleno o cleanup fallido;
- contrato/configuración incompleta;
- dos solicitudes concurrentes de procesamiento.

## Cierre

docs/implementacion/D06_OBSERVABILIDAD_RESILIENCIA.md.

---

# D07 — Release productiva y cierre de F10

**Objetivo:** producir una release operable y generar la evidencia que necesitan los planes backend/NLP/frontend.

## Precondiciones obligatorias

- D00–D06 cerradas;
- homex-backend F09 cerrada o con única dependencia documental de este despliegue;
- homex-frontend FE08 cerrada;
- homex-nlp F06 cerrada;
- CI completa verde;
- restore ensayado.

## Trabajo obligatorio

- tag/version de release;
- manifiesto inmutable;
- builds finales;
- migración controlada;
- despliegue;
- smoke;
- validación HTTPS;
- validación R2;
- validación worker real;
- validación de backup;
- documentación installation/operations/recovery;
- checklist de rollback;
- evidencia de versiones.

## Efecto inter-repositorio

El cierre D07 debe aportar evidencia para:

- homex-backend F10 — Despliegue y recuperación;
- homex-nlp F10 — Despliegue reproducible y recuperación;
- homex-frontend FE09 — sección Release/homex-deploy.

La documentación de esos repositorios debe referenciar la release/manifiesto exactos, no copiar infraestructura.

## Cierre

docs/implementacion/D07_RELEASE.md.

---

# D08 — Piloto, operación y cierre integrado

**Objetivo:** soportar el piloto real sin modificar silenciosamente la arquitectura y cerrar la operación de la versión.

## Precondiciones obligatorias

Antes de iniciar D08 deben estar terminadas o formalmente enlazadas a D07:

- homex-backend F10;
- homex-nlp F10;
- homex-frontend FE09 release/deploy;
- D07.

## Trabajo obligatorio

- fijar versión del piloto;
- conservar manifiesto;
- monitorear salud y errores;
- ejecutar backups durante el periodo;
- probar runbook ante incidencia simulada;
- documentar cambios realizados durante piloto;
- clasificar feedback como defecto, mejora o requisito;
- no afinar NLP sobre test formal ya observado;
- no conservar audio para facilitar investigación;
- preparar handoff operacional.

## Coordinación final

D08 alimenta:

- homex-backend F11;
- homex-nlp F11;
- cierre/piloto de frontend FE09;
- checklist integrado de los cuatro repositorios.

## Cierre

docs/implementacion/D08_PILOTO_CIERRE.md.

---

# 15. Matriz de dependencias inter-repositorio

| Deploy | Backend requerido | Frontend requerido | NLP requerido | Estado al 25-09-2026 |
|---|---|---|---|---|
| D00 | F08.4 cerrada | FE02 cerrada | F06 cerrada | Listo para iniciar |
| D01 | F08.4 cerrada | No requerido | F06 cerrada | Listo tras D00 |
| D02 | F08.4 + auth/OpenAPI estable | FE02 cerrada | F06 | Listo tras D01 |
| D03 | F07.7 + F08.4 | FE02 suficiente | F06 | Listo tras D01 |
| D04 | F09 funcional para FE08 | FE08 cerrada | F06 | Bloqueado por avance frontend/integración |
| D05 | F09 de release | FE08 cerrada | F06 | Bloqueado por D04 |
| D06 | F08.4/F09 | FE08 cerrada | F06 | Bloqueado por D05 |
| D07 | F09 cerrado | FE08 cerrada | F06 | Bloqueado por D00–D06 |
| D08 | F10 cerrado/enlazado a D07 | FE09 release/deploy | F10 cerrado/enlazado a D07 | Bloqueado por D07 |

Nota sobre dependencias circulares:

- FE08 necesita un entorno integrado real; D02 existe precisamente para proporcionarlo antes de FE08.
- FE09 coordina con homex-deploy; por eso D07 no exige FE09 ya cerrada. D07 produce la evidencia que permite cerrar la parte de release/deploy de FE09.
- backend F10 y NLP F10 son objetivos de sistema que se materializan en este repositorio. D07 produce su evidencia de cierre; no se exige F10 como precondición de D07.

---

# 16. Secuencia recomendada desde el estado actual

~~~text
Estado actual
|
|-- NLP F06 ------------------------------ CERRADA
|-- Backend F08.4 ------------------------ CERRADA
|-- Frontend FE02 ------------------------ CERRADA
|-- Frontend FE03 ------------------------ EN DESARROLLO
|
v
D00 baseline/contrato deploy
|
v
D01 backend + NLP + PostgreSQL + Redis
|
+----------------------+
|                      |
v                      v
D02 staging/proxy      D03 R2/media
|                      |
+----------+-----------+
           |
           | mientras frontend avanza FE03 -> FE08
           | y backend completa F09
           v
D04 release candidate integrada
|
v
D05 backup/restore/rollback
|
v
D06 observabilidad/resiliencia
|
v
D07 release productiva
|
+--> evidencia backend F10
+--> evidencia NLP F10
+--> evidencia frontend FE09
|
v
D08 piloto/cierre integrado
|
+--> backend F11
+--> NLP F11
+--> cierre frontend/piloto
~~~

---

# 17. Estructura objetivo del repositorio

La estructura puede evolucionar durante D00, pero la intención contractual es:

~~~text
homex-deploy/
├── compose.yaml
├── compose.production.yaml
├── .env.example
├── README.md
├── docker/
│   ├── backend/
│   └── frontend/
├── nginx/
│   ├── nginx.conf
│   └── homex.conf
├── redis/
│   └── redis.conf
├── releases/
│   └── manifest.yaml
├── scripts/
│   ├── deploy.sh
│   ├── backup.sh
│   ├── restore.sh
│   ├── smoke.sh
│   └── cleanup-audio.sh
├── monitoring/
│   └── README.md
└── docs/
    ├── PLAN_MAESTRO.md
    ├── ARQUITECTURA_DEPLOY.md
    ├── installation.md
    ├── operations.md
    ├── recovery.md
    └── implementacion/
        ├── D00_BASELINE.md
        ├── D01_CORE_RUNTIME.md
        ├── D02_STAGING_PROXY.md
        ├── D03_R2_MEDIA.md
        ├── D04_RELEASE_CANDIDATE.md
        ├── D05_RECOVERY.md
        ├── D06_OBSERVABILIDAD_RESILIENCIA.md
        ├── D07_RELEASE.md
        └── D08_PILOTO_CIERRE.md
~~~

El nombre compose.yaml reemplazará docker-compose.yml durante D00 únicamente si se hace como migración explícita y documentada; no mantener dos archivos equivalentes sin una razón.

---

# 18. Prohibiciones de diseño

No introducir:

- lógica comercial en scripts Bash;
- SQL manual que compita con migraciones Django;
- SQLite como sustituto de PostgreSQL;
- Redis como fuente de verdad;
- audio histórico;
- audio en backups;
- media persistente en filesystem del host;
- binarios de media en PostgreSQL;
- un segundo bucket privado no aprobado;
- URLs firmadas como arquitectura paralela;
- Cloudflare Images;
- MinIO productivo;
- subida Vue → R2;
- secretos en Git;
- latest como release productiva;
- ramas flotantes en manifest;
- migración automática desde todas las réplicas;
- frontend con credenciales R2;
- permisos relajados sólo para simplificar Compose;
- bypass de TLS/CORS/CSRF como solución permanente;
- mocks como única evidencia de D04–D08.

---

# 19. Definición de terminado de una fase deploy

Una fase está terminada únicamente cuando:

- [ ] precondiciones inter-repositorio verificadas;
- [ ] alcance coincide con el plan;
- [ ] no mueve lógica a infraestructura;
- [ ] configuración validada;
- [ ] imágenes reproducibles cuando aplica;
- [ ] versiones no flotantes cuando aplica;
- [ ] healthchecks verdes;
- [ ] smoke verde;
- [ ] integración real verde cuando aplica;
- [ ] secretos ausentes de Git/logs/bundle;
- [ ] CI remoto verde;
- [ ] documentación de fase creada;
- [ ] riesgos/bloqueos documentados;
- [ ] no existen skips críticos;
- [ ] commit/PR contiene sólo la fase.

---

# 20. Definición de listo para producción

HOMEX no se considera listo para producción mientras no estén simultáneamente cumplidos:

- [ ] D00–D07 cerradas;
- [ ] backend F09 cerrado;
- [ ] frontend FE08 cerrada;
- [ ] release frontend FE09 coordinada;
- [ ] NLP F06 fijada por artefacto/version;
- [ ] backend/NLP F10 con evidencia de D07;
- [ ] PostgreSQL restaurado exitosamente desde backup de ensayo;
- [ ] migraciones controladas;
- [ ] API/worker comparten versión backend;
- [ ] homex-nlp fijado;
- [ ] modelo ASR fijado;
- [ ] Redis no contiene estado irrecuperable;
- [ ] audio excluido de backup y limpieza independiente verificada;
- [ ] R2 homex-public-media operativo;
- [ ] productos/ y proformas/ operativos;
- [ ] dominio público de media operativo;
- [ ] HTTPS;
- [ ] CSP/HSTS/headers validados;
- [ ] secretos externos;
- [ ] health/readiness;
- [ ] logs/metrics;
- [ ] smoke E2E crítico;
- [ ] manifiesto de release archivado;
- [ ] rollback/restore documentado y ensayado.

**Principio final:** homex-deploy no adelanta el negocio. Su trabajo comienza temprano para dar a frontend/backend un entorno real de integración, pero una release sólo se promueve cuando las fases de aplicación que consume están formalmente cerradas y sus versiones quedan inmovilizadas en un manifiesto reproducible.
