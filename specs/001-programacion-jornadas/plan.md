# Implementation Plan: Programación de jornadas operativas

**Branch**: `main` | **Date**: 2026-09-14 | **Spec**: [spec.md](spec.md)

**Input**: `specs/001-programacion-jornadas/spec.md`

**Contexto Spec Kit**: `setup-plan.ps1 -Json` devolvió `BRANCH=001-programacion-jornadas`,
identificador derivado del directorio. La rama Git comprobada es `main`, coincidente con la
especificación. Se conserva esa rama.

**Estado**: diseño de fases 0 y 1. El repositorio contiene especificaciones y no código de
aplicación. Las rutas de código y comandos de quickstart son entregables de implementación
posterior; no se afirma que existan ni que se hayan ejecutado pruebas del producto.

## Summary

Permitir que un planeador autorizado prepare y publique jornadas por sucursal y periodo, y que
cada empleado consulte solo su horario publicado y sus cambios. La publicación explícita
reemplaza la comunicación presencial del dueño. Incluye descansos/comidas opcionales,
prevención de traslapes, versiones históricas y exportaciones PNG/PDF coherentes.

Se construirá una aplicación web en un monolito modular Django con PostgreSQL. El core aporta
identidades y permisos; Programación conserva un borrador por periodo y publicaciones
inmutables. Las escrituras breves se serializan por organización y validan todo el periodo
antes del commit. Las consultas/exportaciones fijan las versiones utilizadas, incluidas las
continuidades nocturnas de otros periodos.

## Technical Context

**Language/Version**: Python 3.13; HTML/CSS y JavaScript local para edición y estado de conexión.

**Primary Dependencies**: Django 5.2 LTS, psycopg 3, Playwright Python con su Chromium
correspondiente y Gunicorn en Linux. Fijar parches compatibles y hashes al implementar.
Sin SPA, Redis ni broker inicial. Soporte y alternativas en [research.md](research.md), R1/R7.

**Storage**: PostgreSQL 17 para dominio, borradores, versiones, auditoría e incidencias.
Volumen privado para exportaciones temporales, fuera de rutas estáticas públicas, con retención
inicial de 24 horas. Publicaciones retenidas durante la vida del periodo. Copias de base y
restauración ensayada antes del piloto.

**Testing**: dominio y contratos con Django; TransactionTestCase con conexiones PostgreSQL
independientes para carreras; Playwright para recorridos, privacidad y offline; inspección de
PNG/PDF y métricas de extremo a extremo. SQLite no sustituye las pruebas transaccionales.

**Target Platform**: Linux con HTTPS en piloto; desarrollo Docker Compose compatible con
Windows/Docker Desktop. Navegador de escritorio para planeación y móvil para consulta.
XOLO Jaltepec como primer entorno real, zona configurable `America/Mexico_City`.

**Project Type**: aplicación web central con un despliegue de aplicación y una base de datos.
Rutas JSON como contrato interno de la interfaz del mismo origen, sin API pública general.

**Performance Goals**: SC-008, >=95 % de consultas completas/personales en <=3 s desde seleccionar
periodo; SC-007, cada exportación en <=30 s. Referencia de siete días, 20 empleados y hasta dos
jornadas por persona/día. SC-001/002/005 requieren medición con personas. Son metas pendientes
de validación, no rendimientos acreditados.

**Constraints**: aislamiento organización/sucursal/empleado; rol operativo distinto de permiso;
consulta personal solo con conexión; intervalos absolutos semiabiertos; publicación atómica;
historial y lista publicada inmutables; pérdida de habilitación sin cancelación automática.
Sin nómina, asistencia, normativa laboral, automatización de horarios ni notificaciones externas.

**Scale/Scope**: seis historias, FR-001 a FR-031 y SC-001 a SC-012. Una organización/sucursal
reales iniciales y segunda sucursal sintética para límites. La semana de 20 empleados es carga
de referencia, no límite funcional; se admiten periodos de otras longitudes.

**Resolución de incógnitas**: R1 pila/despliegue, R2 integración, R3 identidad/catálogos mínimos,
R4 tiempo/reservas, R5 concurrencia, R6 versiones/listas/continuidades, R7 exportación,
R8 conectividad y R9 validación quedaron resueltas en fase 0. Sin aclaraciones bloqueantes.

## Constitution Check

Referencia: [constitución v1.0.0](../../.specify/memory/constitution.md). Entrada a investigación:
sin contradicciones conocidas en el alcance; la decisión de integración se exigió en fase 0
antes de diseñar. Revisión posterior a fase 1: controles de diseño satisfechos. PASS acredita
el diseño y su evidencia prevista, no la ejecución de pruebas.

| Principio/control | Resultado y evidencia de validación prevista |
| --- | --- |
| I. Operación sin dueño | PASS. Planeador delegado publica y empleado consulta; Q1/Q2 y piloto SC-001/002 demuestran autonomía. |
| II. Ejecución y trazabilidad | PASS en lo aplicable. Jornada identifica responsable, lugar, rol/estación y tiempo; auditoría atribuye cambios/publicación. Actividad, Procedimiento, Evidencia y asistencia real no aplican a esta entrega de programación (FR-027); no se simula su cumplimiento. |
| III. Excepciones | PASS. Conflicto, base vieja, publicación pendiente e inhabilitación tienen condición, prioridad, ámbito, contexto permitido y acción; contracts/core.md y Q3/Q5/Q7 cubren activación/resolución. |
| IV. Monolito/dominio | PASS. Core compartido y módulo Programación; Exportaciones es adaptador interno. Sin microservicios ni identidades duplicadas. Límites en contracts/core.md. |
| V. Integrar antes de duplicar | PASS tras R2. Odoo y Loyverse evaluados por cobertura, acceso, restricciones y operación. Se justifica construir esta capacidad sin POS/ERP ni conector especulativo. |
| Organización y permisos | PASS. Relaciones del mismo tenant y autorización en servidor incluso historial/archivos. Consulta personal siempre filtrada por identidad autenticada. Q2/Q3. |
| XOLO Jaltepec | PASS de diseño. Sucursal como configuración; piloto registra perfil, escenario, resultado, evidencia y dependencias presenciales. No declarar expansión validada antes de superarlo. |

**Resultado posterior al diseño**: sin desviaciones constitucionales. Instalación, pruebas y
piloto son trabajo posterior explícito, no aclaraciones de diseño sin resolver.

## Project Structure

### Documentation (this feature)

```text
specs/001-programacion-jornadas/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── core.md
│   ├── http.md
│   └── ui-export.md
└── checklists/requirements.md
```

`tasks.md` corresponde a `$speckit-tasks` y no se genera durante este comando.

### Source Code (repository root)

Estructura propuesta, todavía no creada:

```text
manage.py
pyproject.toml
requirements.lock
Dockerfile
compose.yaml
.env.example
config/                       # configuración, URLs, WSGI
ros_xolo/
├── core/
│   ├── models/                # identidades, permisos, auditoría, incidencias/eventos
│   ├── services/              # autorización y cambios de core bajo mutex
│   ├── selectors/
│   ├── management/commands/   # bootstrap_core, seed_demo
│   └── migrations/
└── programacion/
    ├── models/                # periodos, borrador, snapshots y cambios
    ├── services/              # guardar, publicar, validar y exportar
    ├── selectors/             # colectivo, personal e historial
    ├── exports/               # Chromium y almacenamiento privado
    ├── views/                 # HTML y JSON sin reglas duplicadas
    ├── templates/programacion/
    ├── static/programacion/   # CSS y JavaScript local
    ├── management/commands/   # validate_exports, benchmark_schedule, purge_exports
    └── migrations/
tests/
├── unit/
├── contract/
├── integration/
└── e2e/
docs/validation/               # evidencia futura de pruebas y piloto
```

**Structure Decision**: una aplicación Django permite transacciones compartidas entre core y
Programación y una sola política de autorización. No se añade frontend independiente, servicio
de identidad, cola de exportación ni módulo Integraciones sin una función en esta entrega.

## Diseño y secuencia de implementación

1. **Base y core mínimo**: Docker/PostgreSQL, sesiones, usuario-empleado y permisos por sucursal,
   catálogos y comandos auditados. `bootstrap_core` resuelve datos reales y cambios de habilitación;
   `seed_demo` crea fixtures sintéticos. No exponer admin como vía que eluda servicios.
2. **Borrador**: periodos de fechas inclusivas, jornadas/pausas completas, captura directa o
   resolución de turno, guardados atómicos y ETag obligatorio. El mutex de organización coordina
   cambios de core. Sucursal/fechas del periodo fijas tras crearlo; se edita su contenido.
3. **Publicación/privacidad**: snapshots, versiones correlativas, diferencias por Asignación,
   filtrado antes de serializar, histórico y manifiesto de continuidades. Reasignación como
   retiro/alta independiente para cada empleado.
4. **Excepciones/revisión**: revalidación al publicar, base vieja, diferencias nulas, cambio solo
   de lista e incidencia por inhabilitación. Traslado: retiro publicado en origen y alta en destino.
5. **Exportación**: lectura consistente corta; render fuera de lock; archivo disponible solo
   tras completitud; nueva autorización al descargar. PNG completo y PDF paginado.
6. **Validación/piloto**: ejecutar [quickstart.md](quickstart.md), incluidos fallos, carreras,
   offline y comparación de archivos; registrar resultados y observaciones de XOLO Jaltepec.

Las pausas forman parte del modelo inicial aunque su interfaz sea P2. Esta secuencia no
sustituye la lista de tareas trazables que generará la fase siguiente.

## Riesgos y contención

| Riesgo | Decisión y prueba |
| --- | --- |
| Escrituras concurrentes validan un hueco | Mutex de organización, releer después del lock y validar todo; conexiones independientes Q3/Q5. |
| Catálogo cambia mientras se edita | ETag incluye revisión de core; refrescar y confirmar lista antes de publicar. Snapshots no leen etiquetas actuales. |
| Continuidad cambia en origen | Lista del destino congelada y sección separada con manifiesto de origen; Q6/Q9. |
| Exportación omite o mezcla contenido | Payload congelado, verificación de recuentos y layout; fallo explícito al exceder recursos; Q6. |
| Mutex/renderizador limita capacidad | Transacciones cortas y render fuera del lock; medir referencia antes de introducir locks finos o cola. |
| Datos anteriores parecen vigentes offline | Sin caché persistente; ocultar al detectar fallo y verificar antes de volver a mostrar; Q8. |

## Complexity Tracking

No hay violaciones que justificar. El mutex por organización y el renderizador dentro del
monolito simplifican la operación inicial. Este plan no concede excepciones a la constitución.
