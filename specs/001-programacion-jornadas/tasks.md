---

description: "Tareas de implementación de la programación de jornadas operativas"
---

# Tasks: Programación de jornadas operativas

**Input**: Documentos de diseño en `/specs/001-programacion-jornadas/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: La especificación y el plan requieren pruebas de dominio, contratos, integración, concurrencia PostgreSQL, recorridos Playwright, privacidad, conectividad y exportaciones. En cada historia, escribir las pruebas indicadas y confirmar que fallan antes de implementar.

**Organization**: Las tareas se agrupan por historia para entregar y comprobar incrementos funcionales. Las historias US2–US6 usan la publicación básica de US1, pero cada fase define su propia prueba independiente.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo porque afecta archivos distintos y no depende de otra tarea incompleta de la fase.
- **[Story]**: Historia de usuario correspondiente (`US1` a `US6`).
- Todas las tareas indican rutas exactas.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Crear el esqueleto reproducible de Django, PostgreSQL y Playwright descrito en el plan.

- [X] T001 Definir Python 3.13, Django 5.2 LTS, psycopg 3, Gunicorn, Playwright, Pillow y pypdf con parches compatibles, hashes y configuración de formato/lint en pyproject.toml
- [X] T002 Generar el bloqueo reproducible de dependencias de aplicación y prueba en requirements.lock
- [X] T003 Crear el punto de entrada y el paquete de configuración Django en manage.py y config/settings.py
- [X] T004 [P] Crear las aplicaciones modulares y sus configuraciones en ros_xolo/core/apps.py y ros_xolo/programacion/apps.py
- [X] T005 [P] Crear la imagen Linux de Python, Chromium y fuentes locales en Dockerfile
- [X] T006 Configurar los servicios PostgreSQL 17, web y e2e, healthchecks, volúmenes privados y montaje de evidencia en compose.yaml
- [X] T007 [P] Documentar todas las variables locales, de prueba y de piloto sin secretos en .env.example
- [X] T008 [P] Crear la plantilla HTML común accesible y la navegación separada de planeación/consulta personal en ros_xolo/templates/base.html
- [X] T009 [P] Crear la estructura de paquetes de pruebas y evidencia mediante tests/__init__.py, tests/unit/__init__.py, tests/contract/__init__.py, tests/integration/__init__.py, tests/e2e/__init__.py y docs/validation/.gitkeep

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Implementar identidad, ámbitos, auditoría, transacciones y contratos comunes que bloquean todas las historias.

**⚠️ CRITICAL**: Ninguna historia puede implementarse hasta completar esta fase.

### Tests for foundational behavior

- [X] T010 [P] Escribir pruebas fallidas de aislamiento por organización, permiso explícito por sucursal y separación entre Rol operativo y permiso de planeación en tests/unit/core/test_authorization.py
- [X] T011 [P] Escribir pruebas fallidas del contrato atómico de bootstrap, revisión de core y referencias incompatibles en tests/contract/core/test_bootstrap_core.py
- [X] T012 [P] Escribir pruebas fallidas del mutex de Organización, timeout de 5 s y rollback de evento/auditoría con conexiones PostgreSQL independientes en tests/integration/core/test_transactions.py

### Foundational implementation

- [X] T013 Implementar Organización, Sucursal, Empleado, HabilitaciónSucursal, Rol, Área, Estación y Turno en ros_xolo/core/models/catalogs.py, manteniendo `organization_id` en cada entidad de negocio, zona IANA válida, bajas lógicas y `end_day_offset` explícito no negativo
- [X] T014 Implementar UsuarioOrganización y PermisoPlaneación en ros_xolo/core/models/access.py con un vínculo por usuario/organización, empleado opcional de la misma organización y concesión única explícita por usuario/sucursal
- [X] T015 [P] Implementar Asignación, Evento, Auditoría e Incidencia con UUID, instantes UTC, correlation_id y borrado protegido en ros_xolo/core/models/operations.py
- [X] T016 Crear migraciones, FKs de tenant, unicidades, índices y borrado protegido de Core en ros_xolo/core/migrations/0001_initial.py
- [X] T017 Implementar ActorContext, resolve_employee y authorize_planner con ocultación 404 de objetos fuera de ámbito en ros_xolo/core/services/authorization.py
- [X] T018 [P] Implementar get_planning_catalogs y resolve_shift con aplicabilidad por sucursal, offsets explícitos y rechazo de horas ambiguas/inexistentes en ros_xolo/core/selectors/catalogs.py
- [X] T019 Implementar el mutex de Organización bajo READ COMMITTED, orden de lock y traducción de timeout a write_busy en ros_xolo/core/services/locking.py
- [X] T020 Implementar apply_core_changes como lote validado y atómico que incrementa core_revision y registra eventos/auditoría en ros_xolo/core/services/catalog_changes.py
- [X] T021 Implementar el registro desacoplado de manejadores de eventos de Core y Programación, con fallo del manejador que revierte la transacción, en ros_xolo/core/events/registry.py
- [X] T022 Implementar bootstrap_core --validate-only/aplicar con manifest schema_version=1, actor administrativo real, IDs estables, flags de baja y errores sin secretos en ros_xolo/core/management/commands/bootstrap_core.py
- [X] T023 [P] Implementar el sobre JSON de error, códigos HTTP y redacción de conflictos restringidos en ros_xolo/core/http/errors.py
- [X] T024 Configurar sesión, CSRF, cookies Secure en piloto, Cache-Control `private, no-store`, URLs y cierre por POST en config/settings.py y config/urls.py

**Checkpoint**: Core autoriza por tenant/sucursal y todas las escrituras posteriores pueden usar el mismo mutex, auditoría y manejo de errores.

---

## Phase 3: User Story 1 - Planear y publicar un periodo de la sucursal (Priority: P1) 🎯 MVP

**Goal**: Un planeador autorizado crea un periodo, guarda/reconsulta su programación completa y publica una versión 1, incluso vacía, con trazabilidad y continuidades nocturnas.

**Independent Test**: Con catálogos demo, crear una semana, añadir/modificar/retirar jornadas, recargar el borrador y publicar; comprobar datos exactos, filas sin jornada, v1, auditoría, errores atómicos, límites de sucursal y periodo vacío sin usar consulta personal, revisiones ni exportación.

### Tests for User Story 1

- [X] T025 [P] [US1] Escribir pruebas fallidas de POST/GET periodos, GET/PUT borrador, resolve-shift, publish y published, incluidos 401/403/404/409/412/428/422 y ETag, en tests/contract/programacion/test_periods_api.py
- [X] T026 [P] [US1] Escribir pruebas fallidas de modelos para fechas inclusivas, jornada nocturna, rol/estación, turno resuelto, pausas iniciales, filas congeladas y snapshots inmutables en tests/unit/programacion/test_schedule_models.py
- [X] T027 [P] [US1] Escribir pruebas fallidas de Q1 para guardado de reemplazo completo, retiro, periodo vacío, referencias inválidas, rollback y auditoría en tests/integration/programacion/test_planning_publication.py
- [X] T028 [P] [US1] Escribir el recorrido Playwright fallido de planeación/publicación de escritorio y excepciones antes del detalle en tests/e2e/test_q1_planning.py

### Implementation for User Story 1

- [X] T029 [US1] Implementar PeriodoProgramación y BorradorProgramación en ros_xolo/programacion/models/drafts.py con `date_to >= date_from`, fechas inclusivas, periodos no solapados por sucursal, máximo un borrador por periodo y sucursal/fechas/zona inmutables después de crear
- [X] T030 [US1] Implementar AsignaciónJornada, JornadaBorrador y DescansoBorrador en ros_xolo/programacion/models/drafts.py con única `(draft_id, assignment_id)`, al menos rol o estación, fin posterior al inicio, fecha local inicial dentro del periodo, etiquetas resueltas y pausas de duración positiva contenidas y no superpuestas
- [X] T031 [US1] Implementar PublicaciónProgramación, FilaEmpleadoPublicada, JornadaPublicada y DescansoPublicado en ros_xolo/programacion/models/publications.py con única `(period_id, version)`, filas únicas por publicación/empleado, jornadas únicas por publicación/asignación y snapshots append-only durante la vida del periodo
- [X] T032 [US1] Crear migraciones de periodos, exclusión de rangos de fecha con btree_gist, borradores, jornadas, pausas, publicaciones, filas e índices por empleado/intervalo en ros_xolo/programacion/migrations/0001_initial.py
- [X] T033 [US1] Implementar parsing RFC 3339, conservación UTC/local/offset/zona y validación de fechas locales ambiguas o inexistentes en ros_xolo/programacion/services/time.py
- [X] T034 [US1] Implementar create_period bajo mutex, control de ámbito y creación atómica de borrador inicial en ros_xolo/programacion/services/periods.py
- [X] T035 [US1] Implementar validación completa de tenant, habilitación, referencias, sucursal, fecha, rol/estación, fin y pausas sin mutación parcial en ros_xolo/programacion/services/validation.py
- [X] T036 [US1] Implementar replace_draft con payload completo, IDs estables, retiros por ausencia, detección ETag, no-op semántico y auditoría en ros_xolo/programacion/services/drafts.py
- [X] T037 [US1] Implementar la primera publicación atómica con v1, roster congelado, snapshots, hash, puntero vigente, evento/auditoría y soporte de periodo vacío en ros_xolo/programacion/services/publication.py
- [X] T038 [US1] Implementar selectores de periodos, borrador y publicación colectiva con filas sin jornada, estados, alertas iniciales y continuidades de solo lectura con periodo/versión de origen en ros_xolo/programacion/selectors/planning.py
- [X] T039 [US1] Implementar las rutas JSON de sucursales, catálogos, periodos, resolve-shift, borrador, publicación y vista publicada en ros_xolo/programacion/views/planning_api.py y ros_xolo/programacion/urls.py
- [X] T040 [US1] Implementar la pantalla de planeación con selector semanal, editor de múltiples jornadas, fechas completas, rol/estación, estado guardado/local y publicación explícita en ros_xolo/programacion/templates/programacion/planning.html
- [X] T041 [US1] Implementar carga/guardado con If-Match, preservación visual de entrada rechazada, refresco manual tras 412 y publicación solo de contenido guardado en ros_xolo/programacion/static/programacion/planning.js

**Checkpoint**: US1 funciona de extremo a extremo y constituye el MVP demostrable.

---

## Phase 4: User Story 2 - Consultar únicamente el horario propio (Priority: P1)

**Goal**: Cada empleado consulta únicamente su programación publicada y la vista invalida el contenido cuando no puede verificarlo con el servidor.

**Independent Test**: Con publicaciones para dos personas, dos sucursales y dos organizaciones, cada perfil ve solo lo propio; borradores y datos ajenos permanecen ocultos, se distinguen los estados vacíos y offline/error/sesión vencida ocultan el horario anterior.

### Tests for User Story 2

- [X] T042 [P] [US2] Escribir pruebas fallidas de `/me/schedule` y acceso directo a rutas colectivas/otro tenant, incluido doble perfil y estados vacío publicado/no publicado, en tests/contract/programacion/test_personal_api.py
- [X] T043 [P] [US2] Escribir pruebas fallidas de proyección personal previa a serialización, continuidades propias y manifiesto/hash sin datos ajenos en tests/unit/programacion/test_personal_projection.py
- [X] T044 [P] [US2] Escribir el recorrido Playwright fallido móvil de Q2/Q8 para offline, timeout, 401, pageshow, segundo plano y reconexión en tests/e2e/test_personal_schedule.py

### Implementation for User Story 2

- [X] T045 [US2] Implementar get_personal_schedule con identidad derivada de sesión, publicaciones/continuidades propias, estados `not_published|published` y `assigned|none`, y filtrado antes del manifiesto en ros_xolo/programacion/selectors/personal.py
- [X] T046 [US2] Implementar GET `/api/v1/me/schedule` sin aceptar employee_id y con respuestas no almacenables en ros_xolo/programacion/views/personal_api.py
- [X] T047 [P] [US2] Implementar la vista móvil con próxima jornada, sucursal, fechas, rol/estación, pausas, versión, última verificación y estados vacíos diferenciados en ros_xolo/programacion/templates/programacion/personal_schedule.html
- [X] T048 [US2] Implementar estados loading/verified/unverified/authentication_required, timeout de 5 s, comprobación cada 15 s, invalidación <=20 s, descarte de respuestas viejas y revalidación al reconectar/volver al primer plano en ros_xolo/programacion/static/programacion/personal_schedule.js
- [X] T049 [US2] Impedir service worker, localStorage, IndexedDB y caché HTTP de horarios y mostrar el requisito de JavaScript en ros_xolo/programacion/templates/programacion/personal_schedule.html

**Checkpoint**: US2 es verificable con dos empleados sin exponer datos colectivos ni horarios obsoletos.

---

## Phase 5: User Story 3 - Corregir asignaciones que se traslapan (Priority: P1)

**Goal**: Rechazar duplicados y todo traslape positivo del mismo empleado entre sucursales, periodos, publicaciones y borradores activos, aceptando intervalos adyacentes.

**Independent Test**: Partiendo de 09:00–17:00, rechazar 16:00–22:00 y duplicados en cualquier ámbito, aceptar 17:00–21:00 y comprobar que solo una de dos escrituras concurrentes incompatibles confirma.

### Tests for User Story 3

- [X] T050 [P] [US3] Escribir pruebas fallidas de intervalos semiabiertos, duplicados, medianoche, zonas distintas, pausas que no liberan tiempo y reemplazo de la propia versión en tests/unit/programacion/test_conflicts.py
- [X] T051 [P] [US3] Escribir pruebas fallidas de Q3 con publicaciones y borradores de otros periodos/sucursales y carreras sincronizadas en conexiones PostgreSQL independientes en tests/integration/programacion/test_overlap_concurrency.py
- [X] T052 [P] [US3] Escribir pruebas fallidas de 409 overlap y redacción total de ID/sucursal/horario/datos ajenos cuando falta permiso en tests/contract/programacion/test_conflict_errors.py

### Implementation for User Story 3

- [X] T053 [US3] Implementar comparación `[inicio, fin)` del candidato completo contra sí mismo, publicaciones vigentes y borradores activos ajenos, excluyendo históricos, continuidades y contenido viejo del mismo periodo, en ros_xolo/programacion/services/conflicts.py
- [X] T054 [US3] Integrar la validación de conflictos después del mutex y la relectura de estado en guardado y publicación, conservando el estado anterior ante rechazo, en ros_xolo/programacion/services/validation.py
- [X] T055 [US3] Implementar la alerta overlap con prioridad, ámbito, contexto permitido y acción de corregir/coordinar en ros_xolo/programacion/selectors/alerts.py
- [X] T056 [US3] Mostrar el conflicto junto a los campos afectados sin incorporar detalles restringidos al HTML o campos ocultos en ros_xolo/programacion/static/programacion/planning.js
- [X] T057 [US3] Escribir el recorrido Playwright de Q3 para corrección del traslape y permanencia de publicación pendiente en tests/e2e/test_q3_conflicts.py

**Checkpoint**: US3 impide contradicciones incluso en carreras y conserva la privacidad del origen del conflicto.

---

## Phase 6: User Story 4 - Publicar revisiones y comprender qué cambió (Priority: P1)

**Goal**: Mantener una sola versión vigente, publicar revisiones inmutables, mostrar diferencias privadas e historial y resolver incidencias de habilitación/lista sin sobrescribir trabajo concurrente.

**Independent Test**: Sobre v1, modificar/añadir/retirar/reasignar, publicar v2 y comprobar antes/después, historial, filtros personales, no_changes, ETag viejo, rollback, lista-only y pérdida de habilitación.

### Tests for User Story 4

- [X] T058 [P] [US4] Escribir pruebas fallidas de igualdad semántica y diferencias assignment/roster added/modified/removed con valores before/after en tests/unit/programacion/test_publication_diff.py
- [X] T059 [P] [US4] Escribir pruebas fallidas de privacidad de reasignación A→B, historial personal completo y snapshots inmunes a cambios de catálogo en tests/unit/programacion/test_history_projection.py
- [X] T060 [P] [US4] Escribir pruebas fallidas de versiones/historial paginado, `limit` 50/máximo 200, no_changes, stale_base y alertas en tests/contract/programacion/test_versions_api.py
- [X] T061 [P] [US4] Escribir pruebas fallidas de Q5/Q7/Q9 para publicación concurrente, fallo entre snapshot/puntero, cambio solo de roster, baja vs publicación e incidencia/resolución en tests/integration/programacion/test_revisions.py

### Implementation for User Story 4

- [X] T062 [US4] Implementar CambioPublicación en ros_xolo/programacion/models/publications.py con `kind=assignment_added/modified/removed/roster_added/roster_removed/roster_modified`, before/after nulos cuando corresponda y contenido inmutable
- [X] T063 [US4] Crear la migración de diferencias publicadas, restricciones append-only y permisos de rol de ejecución sin UPDATE/DELETE sobre snapshots en ros_xolo/programacion/migrations/0002_publication_changes.py
- [X] T064 [US4] Implementar apertura/clonado de revisión y comparación semántica ordenada por IDs que excluya autor, timestamps, IDs de snapshot, versión y orden incidental en ros_xolo/programacion/services/revisions.py
- [X] T065 [US4] Extender publish_period para vN+1, diferencias, cambios solo de lista, no_changes, resolución atómica de incidencias y conservación de vN ante cualquier fallo en ros_xolo/programacion/services/publication.py
- [X] T066 [US4] Implementar el manejador de desactivación/habilitación que abre o actualiza incidencias sobre jornadas publicadas con `starts_at > validation_time` sin modificar snapshots en ros_xolo/programacion/events/core_changes.py
- [X] T067 [US4] Implementar get_history colectivo y personal paginado, incluida proyección privada de retiro/alta y permanencia de retiros antiguos, en ros_xolo/programacion/selectors/history.py
- [X] T068 [US4] Implementar rutas de versiones, detalle histórico, historial personal y alertas activas con autorización previa en ros_xolo/programacion/views/history_api.py
- [X] T069 [P] [US4] Implementar pantalla de historial con versión vigente/histórica, before/after, autor/fecha, paginación y diferencias de roster en ros_xolo/programacion/templates/programacion/history.html
- [X] T070 [US4] Implementar resumen previo a publicar, estados initial_publication_pending/revision_pending/employee_ineligible_future y resolución visible solo tras publicación/restitución en ros_xolo/programacion/templates/programacion/planning.html

**Checkpoint**: US4 conserva historia inmutable, evita sobrescrituras y permite comprender cada cambio sin revelar reasignaciones ajenas.

---

## Phase 7: User Story 5 - Programar intervalos de descanso/comida opcionales (Priority: P2)

**Goal**: Añadir, modificar y retirar cero o más pausas válidas dentro de una jornada, sin que reduzcan el intervalo reservado.

**Independent Test**: En una jornada 09:00–17:00, publicar ninguna pausa y varias válidas; rechazar duración cero, pausas fuera/superpuestas y una jornada acortada que deje su pausa fuera.

### Tests for User Story 5

- [X] T071 [P] [US5] Escribir pruebas fallidas de pausas opcionales, positivas, contenidas, no superpuestas, bordes válidos e invalidación al acortar jornada en tests/unit/programacion/test_breaks.py
- [X] T072 [P] [US5] Escribir pruebas fallidas de payload completo de pausas, IDs estables y errores 422 con ruta de campo en tests/contract/programacion/test_breaks_api.py
- [X] T073 [P] [US5] Escribir el recorrido Playwright fallido Q4 de alta/cambio/retiro de pausas y visibilidad para planeador/empleado en tests/e2e/test_q4_breaks.py

### Implementation for User Story 5

- [X] T074 [US5] Integrar creación, modificación y retiro de DescansoBorrador en el reemplazo atómico de jornada en ros_xolo/programacion/services/drafts.py
- [X] T075 [US5] Integrar pausas en snapshots, hashes, diferencias de campos y proyecciones colectiva/personal sin generar intervalos automáticos en ros_xolo/programacion/services/publication.py
- [X] T076 [US5] Añadir controles accesibles de múltiples pausas con fecha/hora explícita y errores por intervalo en ros_xolo/programacion/templates/programacion/_assignment_form.html
- [X] T077 [US5] Implementar edición local de pausas y revalidación visual al cambiar los límites de la jornada en ros_xolo/programacion/static/programacion/assignment_form.js

**Checkpoint**: US5 funciona como extensión opcional; una jornada sin pausas sigue siendo válida y publicable.

---

## Phase 8: User Story 6 - Exportar el periodo publicado como PNG o PDF (Priority: P2)

**Goal**: Generar archivos privados completos y coherentes de la versión publicada, con manifiesto, continuidades y autorización renovada.

**Independent Test**: Exportar PNG/PDF de un periodo publicado con 20 personas, siete días, dos jornadas por persona/día, pausas, filas vacías y continuidad nocturna; comparar contenido/manifiesto, inspeccionar legibilidad y provocar saturación, tamaño excesivo, timeout, cambio durante render y revocación de permiso.

### Tests for User Story 6

- [X] T078 [P] [US6] Escribir pruebas fallidas del payload congelado, expected_counts, hash, estados generating/ready/failed/expired y pending_draft_excluded en tests/unit/programacion/test_exports.py
- [X] T079 [P] [US6] Escribir pruebas fallidas de POST export, metadatos/descarga privada, MIME, 409/410/422/503 y reautorización en tests/contract/programacion/test_exports_api.py
- [X] T080 [P] [US6] Escribir pruebas fallidas de Q6 para publicación durante render, fallo/timeout/saturación, limpieza de temporal, revocación y cero archivo parcial en tests/integration/programacion/test_export_generation.py
- [X] T081 [P] [US6] Escribir el recorrido Playwright fallido de selección PNG/PDF, aviso de revisión pendiente, descarga y bloqueo al empleado en tests/e2e/test_q6_exports.py

### Implementation for User Story 6

- [X] T082 [US6] Implementar ExportaciónProgramación en ros_xolo/programacion/models/exports.py con `format=png|pdf`, estados generating/ready/failed/expired, manifiesto, recuentos, hash, clave privada, bytes, duración, error y vencimiento de 24 h
- [X] T083 [US6] Crear la migración, índices de expiración y almacenamiento de metadatos sin publicar archivos en ros_xolo/programacion/migrations/0003_exports.py
- [X] T084 [US6] Implementar lectura REPEATABLE READ que fija publicación local y orígenes de continuidades, filtra una sola sucursal y produce payload/manifiesto inmutable en ros_xolo/programacion/exports/payload.py
- [X] T085 [P] [US6] Implementar la plantilla autoescapada con todas las filas/días/pausas, fechas de término, continuidades, aviso estático y contexto repetible en ros_xolo/programacion/templates/programacion/export.html
- [X] T086 [US6] Implementar renderer Playwright con fuentes locales, máximo dos renderizaciones por instancia, timeout de 25 s, PNG <=60 millones de píxeles y <=30 000 px por dimensión, PDF A4 horizontal >=10 pt y publicación atómica del temporal en ros_xolo/programacion/exports/renderer.py
- [X] T087 [US6] Verificar IDs/recuentos contra DOM, tipo, bytes, dimensiones PNG y estructura/páginas PDF antes de marcar ready en ros_xolo/programacion/exports/validation.py
- [X] T088 [US6] Implementar generación síncrona fuera del lock, estados/error/auditoría, limpieza de temporales y purga de expirados en ros_xolo/programacion/services/exports.py y ros_xolo/programacion/management/commands/purge_exports.py
- [X] T089 [US6] Implementar rutas de solicitud/estado/archivo con permiso actual, Content-Disposition y UI de formato/advertencias en ros_xolo/programacion/views/export_api.py y ros_xolo/programacion/templates/programacion/export_controls.html

**Checkpoint**: US6 entrega ambos formatos sin omisiones, mezcla de versiones ni acceso por URL conocida.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Completar datos demo, validación automatizada, mediciones, seguridad operativa y evidencia del piloto exigidos por todas las historias.

- [X] T090 Implementar seed_demo idempotente con organización demo, XOLO Jaltepec, segunda sucursal/zona, segundo tenant, 20 empleados, perfiles y reference-week sin imprimir secretos en ros_xolo/programacion/management/commands/seed_demo.py
- [X] T091 [P] Implementar validate_exports para ambos formatos, periodos/nombres largos, continuidades, recuentos/IDs y render de todas las páginas a evidencia en ros_xolo/programacion/management/commands/validate_exports.py
- [X] T092 [P] Implementar benchmark_schedule con 100 consultas colectivas, 100 personales, cinco exportaciones por formato y tiempos desde acción visible en ros_xolo/programacion/management/commands/benchmark_schedule.py
- [X] T093 Ejecutar y corregir las suites unit, contract, integration y e2e de quickstart en tests/ y registrar comandos/resultados reproducibles en docs/validation/automated-tests.md
- [X] T094 Ejecutar validate_exports, revisar el PNG al 100 % y todas las páginas PDF, y registrar manifiestos, comparación y legibilidad en docs/validation/exports/report.md
- [X] T095 Ejecutar benchmark_schedule contra la carga de referencia y registrar tasa de consultas <=3 s, p95, tiempos individuales, entorno y exportaciones <=30 s en docs/validation/performance.json
- [X] T096 [P] Documentar despliegue HTTPS con DEBUG=False, hosts/cookies/CSRF, WSGI, estáticos, rol restringido, migraciones, check --deploy, backup y ensayo de restauración en docs/deployment/pilot.md
- [ ] T097 Ejecutar el piloto con un planeador distinto del dueño y empleados participantes, registrar SC-001–SC-012, evidencia, ayuda presencial, incidencias, correcciones y repruebas sin datos sensibles en docs/validation/pilot-jaltepec.md

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sin dependencias; puede comenzar de inmediato.
- **Foundational (Phase 2)**: Depende de Setup y bloquea todas las historias.
- **US1 (Phase 3)**: Depende de Foundational y entrega la preparación/publicación básica usada por las demás historias.
- **US2 (Phase 4)**: Depende de US1 para disponer de publicaciones; su selector y UI personal son independientes de US3–US6.
- **US3 (Phase 5)**: Depende de US1 para integrar la regla en guardar/publicar; no depende de US2.
- **US4 (Phase 6)**: Depende de US1; usa el control ETag fundacional y puede avanzar después de US1 en paralelo con US2/US3.
- **US5 (Phase 7)**: Depende de los modelos iniciales de pausa de US1; puede avanzar después de US1 en paralelo con US2–US4.
- **US6 (Phase 8)**: Depende de US1 para snapshots publicados y de US5 para incluir pausas completas; el resto puede prepararse en paralelo con US2–US4.
- **Polish (Phase 9)**: T090 puede comenzar tras US1; T091–T095 requieren US1–US6; T096 puede avanzar tras Foundational; T097 requiere todas las historias y la validación previa.

### User Story Dependency Graph

```text
Setup → Foundational → US1 (MVP)
                          ├── US2
                          ├── US3
                          ├── US4
                          └── US5 ── US6
                                      └── Polish/Pilot
```

### Within Each User Story

1. Escribir las pruebas de la historia y confirmar que fallan por la capacidad ausente.
2. Implementar modelos y migraciones antes de servicios que los persisten.
3. Implementar reglas de dominio y selectores antes de exponer rutas.
4. Implementar HTML/JavaScript después del contrato del servidor.
5. Ejecutar las pruebas de la historia y comprobar el estado persistido antes del checkpoint.

### Parallel Opportunities

- En Setup, T004, T005, T007, T008 y T009 afectan archivos independientes.
- En Foundational, T010–T012 pueden escribirse en paralelo; T015 y T018 afectan módulos separados después de sus modelos base.
- Las tareas de pruebas marcadas [P] dentro de cada historia pueden escribirse simultáneamente antes de la implementación.
- Tras US1, US2, US3, US4 y la preparación de US5 pueden desarrollarse en paralelo por equipos distintos.
- En US6, la plantilla de exportación T085 puede avanzar junto con modelos/migración, y los comandos T091/T092 son independientes entre sí cuando el dominio está completo.
- T096 puede prepararse en paralelo con la implementación funcional y validarse al final.

---

## Parallel Examples

### User Story 1

```text
Task: "Escribir contrato de periodos/borrador/publicación en tests/contract/programacion/test_periods_api.py"
Task: "Escribir pruebas de modelos en tests/unit/programacion/test_schedule_models.py"
Task: "Escribir integración Q1 en tests/integration/programacion/test_planning_publication.py"
Task: "Escribir recorrido Q1 en tests/e2e/test_q1_planning.py"
```

### User Stories after MVP

```text
Developer A: US2 en ros_xolo/programacion/selectors/personal.py y su UI
Developer B: US3 en ros_xolo/programacion/services/conflicts.py
Developer C: US4 en ros_xolo/programacion/services/revisions.py y history.py
Developer D: US5 en la edición y publicación de pausas
```

### User Story 6

```text
Task: "Escribir pruebas unitarias en tests/unit/programacion/test_exports.py"
Task: "Escribir contrato HTTP en tests/contract/programacion/test_exports_api.py"
Task: "Escribir integración de fallos en tests/integration/programacion/test_export_generation.py"
Task: "Escribir recorrido de descarga en tests/e2e/test_q6_exports.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Completar Setup.
2. Completar Foundational.
3. Completar US1 y ejecutar T025–T028.
4. Detenerse en el checkpoint y demostrar creación, edición, retiro, recarga y publicación v1, incluido periodo vacío.

### Incremental Delivery

1. **MVP**: Setup + Foundational + US1.
2. **Consulta segura**: añadir US2 y validar privacidad/conectividad.
3. **Consistencia operativa**: añadir US3 y US4 para conflictos, revisiones, historial e incidencias.
4. **Detalle de jornada**: añadir US5 para pausas opcionales.
5. **Distribución estática**: añadir US6 para PNG/PDF coherentes.
6. **Validación real**: completar Phase 9 y no declarar expansión antes de superar el piloto XOLO Jaltepec.

### Execution Notes

- Los tests de concurrencia usan `TransactionTestCase`, conexiones PostgreSQL independientes y barreras explícitas; SQLite no es sustituto.
- Toda escritura relevante adquiere primero el mutex de Organización y vuelve a leer permisos, ETag y dependencias.
- El renderer nunca mantiene el mutex y nunca consulta catálogos o punteros vigentes después de congelar el payload.
- No usar admin, cargas directas o SQL como vías que eviten los servicios auditados.
- Las tareas del piloto registran evidencia; los artefactos de diseño no cuentan como pruebas superadas.
