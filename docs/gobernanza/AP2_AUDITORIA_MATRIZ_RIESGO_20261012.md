# HOMEX — AP2: auditoría de pruebas, matriz de riesgo y seguimiento (12/10/2026)

**Alcance**: cuatro repositorios; solo ramas AP2; **sin cambios a `homex-prod`**, manifiesto RC2, backup real, D07 ni secretos. La auditoría es de evidencia funcional; 42 jobs verdes en AP1 no equivalen a cero riesgos.

## Baseline verificable de `main` previo a AP2

| Repositorio | CI y estado | Evidencia de ejecución |
| --- | --- | --- |
| backend | [38330824357](https://github.com/gabriel-arinez/homex-backend/actions/runs/38330824357): 13/13 jobs | 195 tests PostgreSQL/67.96 s; 12 concurrency/7.97 s |
| frontend | [38330085332](https://github.com/gabriel-arinez/homex-frontend/actions/runs/38330085332): 13/13 | 72 tests Vitest/11 archivos; E2E, a11y, integración real |
| NLP | [38330659108](https://github.com/gabriel-arinez/homex-nlp/actions/runs/38330659108): 3/3 | 58 tests; 14 distribución/consumidor |
| deploy | [38330620054](https://github.com/gabriel-arinez/homex-deploy/actions/runs/38330620054): 13/13 | Contratos de env/compose/release, build, smoke, recovery y resiliencia QA0 |

No se identificaron tests `skipped` en los resúmenes de pytest/Vitest de baseline consultados; **no** se afirma ausencia global de flaky tests ni se presume una medición de mutation score.

## Matriz de riesgo → capa → gate → estado

| Prioridad | Riesgo | Evidencia de pruebas (preexistentes + AP2) | Límite |
| --- | --- | --- | --- |
| P0 | Aprobación, stock y OT incompletos/dobles | Backend `tests/api/test_ap2_regresion_comercial.py` + `tests/integration/test_f073_ventas.py`; PostgreSQL `tests-postgresql` y `concurrency-postgresql` | Estados futuros de AP3 no implementados |
| P0 | IDOR vendedores/clientes/media/documentos | Backend suites F076/F077; AP2 listado y acción ajena con 404; frontend error 401/403 | Mantener auditoría de cualquier endpoint nuevo en AP3–AP5 |
| P0 | Reversa con recibo emitido | Backend AP2 HTTP negativo, F074 servicio/BD | Cancelaciones futuras requieren regresión adicional |
| P0 | ASR timeout o eliminación incorrecta | NLP AP2 validación/limpieza y suite ASR; backend F082/F083/F084 | Revalidar cuando se modifiquen callbacks HITL |
| P1 | POST duplicado desde UI | Frontend `src/tests/fe08/ap2-http-regression.spec.ts` con peticiones MSW contadas | Interacción editor nuevo en AP5 |
| P1 | Env malformado atraviesa gate | Deploy `scripts/test_ap2_env_contract.py` + `validate_env_contract.py` ejecutados desde `compose-config` | No ejecutar contra `.env.production` privado |
| P1 | Promoción indebida y pérdida de recovery | CI D07/QA0 y `test_qa0_contract.py` preexistentes | RC2 sigue `candidate`; QA0 no se repite destructivamente |

## Hallazgo de falsa cobertura y corrección

`validate_env_contract.py` comparaba solamente **nombres** extraídos de líneas: una clave declarada sin `=` podía contar como presente. AP2 refuerza sintaxis de declaraciones y añade casos negativos ejecutables (`sin '='`, duplicada, desconocida, clave inválida y `export`), con `tempfile` aislado. No se toca el entorno real.

## Gates de ejecución

- Backend: `uv run pytest -ra`, `uv run pytest -ra -m concurrency`, Ruff, migraciones/OpenAPI.
- Frontend: `npm run test:unit -- --run`, type/lint/format, Playwright, E2E real.
- NLP: `make check`, distribución, runtime/consumidor.
- Deploy: `python3 scripts/test_ap2_env_contract.py` y CI completo; QA0 preexistente se reutiliza.
- Cada PR de AP2 debe conservar resultados **PASS/FAIL reales**, job URL y SHA; un CI verde en PR **no reemplaza** revisión de CI post-merge.

## Deuda aceptada por separación de fases

Las 20 pruebas de aceptación del documento maestro de traspaso incluyen reglas todavía **no implementadas** (AP3–AP5): `EN_REVISION`, `NO_CONCRETADA`, editor sin persistencia, cliente inline atómico, renovación, PDF nuevo, recuperación, doble sesión. No deben declararse PASS en AP2 ni introducir estados/migraciones de forma anticipada. Resolver en fase funcional con pruebas PostgreSQL/E2E interrepo.

**Bloqueo externo heredado de AP1**: branch protection/rulesets de `main` de los cuatro repositorios aún no estaban activos al comenzar AP2. Tracked en [homex-deploy #11](https://github.com/gabriel-arinez/homex-deploy/issues/11). Sin simular aprobación independiente.
