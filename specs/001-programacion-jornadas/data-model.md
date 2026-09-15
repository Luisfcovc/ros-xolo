# Modelo de datos: Programación de jornadas operativas

**Fecha**: 2026-09-14 | **Referencias**: [spec.md](spec.md), [research.md](research.md).

Diseño lógico para PostgreSQL; no contiene migraciones ni modelos de implementación.
Nombres de dominio en español y campos contractuales en `snake_case`. IDs internos UUID,
instantes UTC y referencias IANA. Todas las entidades de negocio llevan `organization_id`;
las referencias entre organizaciones se rechazan aunque el UUID exista.

## Core compartido

| Entidad | Campos principales | Relaciones y reglas |
| --- | --- | --- |
| Organización | `id`, `name`, `core_revision`, `created_at` | Raíz de ámbito y fila mutex de escrituras. `core_revision` crece con cambios relevantes de catálogos/permisos/habilitación. |
| Sucursal | `id`, `organization_id`, `name`, `timezone`, `active` | Zona IANA válida. Una sucursal por periodo/jornada. Cambiar su zona no altera periodos ya creados ni snapshots. |
| Empleado | `id`, `organization_id`, `display_name`, `active` | Identidad común incluso entre sucursales. Baja lógica; nunca borrar si tiene referencias históricas. |
| HabilitaciónSucursal | `id`, `organization_id`, `employee_id`, `branch_id`, `enabled`, `changed_at`, `changed_by` | Única por empleado/sucursal. Puede asignarse solo si empleado activo y habilitación vigente. Cambios dejan evento/auditoría e incrementan revisión de core. |
| Rol | `id`, `organization_id`, `name`, `active`, `applicable_branch_ids` | Trabajo operativo. No concede acceso al sistema. Relación de aplicabilidad explícita; sin lista implícita de todas las sucursales. |
| Área | `id`, `organization_id`, `branch_id`, `name`, `active` | Agrupa estaciones de una sucursal. Solo se implementa lo necesario para ubicar Estación. |
| Estación | `id`, `organization_id`, `branch_id`, `area_id`, `name`, `active` | Área y estación deben ser de la misma sucursal. |
| Turno | `id`, `organization_id`, `name`, `start_local_time`, `end_local_time`, `end_day_offset`, `active`, `applicable_branch_ids` | Propuesta de horario, con desplazamiento de día explícito no negativo. Se resuelve contra fecha de inicio y zona del periodo. No genera pausas ni infiere fin por nombre. |
| UsuarioOrganización | `id`, `organization_id`, `user_id`, `employee_id?`, `active` | Cuenta autenticada de Django. Un vínculo por usuario/organización; empleado de la misma organización. La identidad personal viene de aquí. |
| PermisoPlaneación | `id`, `organization_id`, `user_id`, `branch_id`, `enabled` | Concesión explícita: consultar colectivo, crear/editar/publicar, historial y exportar en esa sucursal. No derivar del Rol operativo ni de HabilitaciónSucursal. |
| Asignación | `id`, `organization_id`, `kind`, `created_by`, `created_at` | Identidad compartida estable, `kind=jornada` en esta entrega. Empleado/tiempos pertenecen al contenido de borrador o snapshot; reasignar no inventa otra identidad. |

Permiso para consultar la programación propia requiere una cuenta activa y vínculo con Empleado;
perder HabilitaciónSucursal no elimina ese vínculo ni su historial. Una persona con los dos
perfiles mantiene el filtro personal cuando usa la consulta propia. No se implementan todavía
Actividad, Procedimiento ni Evidencia; el dominio no equipara programación con ejecución.

## Agregado Programación de periodo

| Entidad | Campos principales | Relaciones y restricciones |
| --- | --- | --- |
| PeriodoProgramación | `id`, `organization_id`, `branch_id`, `date_from`, `date_to`, `timezone`, `current_publication_id?`, `edit_revision`, `created_by`, `created_at` | `date_to >= date_from`; fechas inclusivas. Zona copiada de sucursal al crear. Sucursal/fechas/zona no se modifican después de crear; cambiar jornadas se hace dentro del periodo existente. |
| BorradorProgramación | `id`, `organization_id`, `period_id`, `base_publication_id?`, `active`, `updated_at`, `updated_by` | Máximo uno por periodo. Contiene el reemplazo completo propuesto. Tras publicar queda sincronizado/inactivo; abrir revisión clona el contenido publicado sin modificarlo. |
| AsignaciónJornada | `assignment_id`, `organization_id`, `period_id` | Extensión uno a uno de Asignación, preservada aun al retirar un borrador. Fija para siempre el periodo de origen; no duplica identidades ni datos de Empleado. |
| JornadaBorrador | `organization_id`, `draft_id`, `assignment_id`, `employee_id`, `branch_id`, `starts_at`, `ends_at`, `start_local`, `end_local`, `start_offset`, `end_offset`, `timezone`, `role_id?`, `station_id?`, `shift_id?`, `labels` | Única `(draft_id, assignment_id)`; al menos rol o estación. Asignación pertenece a este periodo de origen para toda su vida. `labels` conserva nombres resueltos de las referencias; se renuevan al seleccionar explícitamente otra referencia. |
| DescansoBorrador | `id`, `organization_id`, `draft_id`, `assignment_id`, `starts_at`, `ends_at`, `start_local`, `end_local`, `start_offset`, `end_offset` | Cero o más por jornada; identidad estable en revisiones. Duración positiva, contenido en jornada, sin intersección positiva entre pausas. |

La lista del borrador es una proyección: empleados habilitados actuales de la sucursal UNION
empleados con jornadas propias del borrador, deduplicados por ID. La consulta incorpora además
las personas con continuidades en una sección identificada; no crea asignaciones adicionales.
No persistir una lista congelada de borrador que oculte cambios de habilitación. El ETag de su
vista contiene `period_id`, `edit_revision`, `current_publication_id` y `core_revision` para
evitar publicar una lista distinta de la revisada por el planeador.

## Publicación inmutable e historial

| Entidad | Campos principales | Reglas |
| --- | --- | --- |
| PublicaciónProgramación | `id`, `organization_id`, `period_id`, `version`, `previous_publication_id?`, `published_by`, `publisher_label`, `published_at`, `content_hash`, `branch_label`, `date_from`, `date_to`, `timezone` | Única `(period_id, version)`; primera versión 1, siguientes +1. Puntero anterior del mismo periodo. Contenido inmutable y sin borrado durante vida del periodo. Vigencia se deriva del puntero del periodo, no reescribiendo el snapshot. |
| FilaEmpleadoPublicada | `organization_id`, `publication_id`, `employee_id`, `employee_label`, `display_order` | Única `(publication_id, employee_id)`; incluye habilitados sin jornadas y personas con jornadas propias. Congelada; orden determinista. |
| JornadaPublicada | `organization_id`, `publication_id`, `assignment_id`, `employee_id`, `branch_id`, `starts_at`, `ends_at`, `start_local`, `end_local`, `start_offset`, `end_offset`, `timezone`, `role_id?`, `station_id?`, `shift_id?`, `labels` | Snapshot de jornada: IDs comunes más valores/nombres resueltos; no consulta el catálogo actual para reconstruir historia. Única `(publication_id, assignment_id)`; empleado incluido en fila publicada. |
| DescansoPublicado | `organization_id`, `publication_id`, `assignment_id`, `break_id`, `starts_at`, `ends_at`, valores locales/offset | Snapshot inmutable de pausas con mismas reglas de intervalo. |
| CambioPublicación | `id`, `organization_id`, `publication_id`, `assignment_id?`, `employee_id?`, `kind`, `before`, `after`, `changed_fields` | `kind=assignment_added/modified/removed/roster_added/roster_removed/roster_modified`. Diferencias contra publicación anterior, no contra catálogo ni contra borrador. Valores ausentes como null. |

Una nueva publicación congela la lista revisada, incluidas etiquetas actuales de sus filas.
Cambios de etiquetas explícitos también forman parte del contenido; `roster_modified` evita
que el historial quede vacío si cambia solo un nombre. Un catálogo de turnos modificado no
cambia automáticamente el horario ni las etiquetas de jornadas existentes.

Para igualdad, ordenar por IDs estables y comparar jornadas, sus pausas y filas con etiquetas.
Excluir autor, tiempo de generación/publicación, IDs de snapshot, número de versión y orden de
presentación incidental. Primera publicación vacía crea v1. Con publicación previa, igualdad
devuelve `no_changes`; cambio de lista sin jornadas genera siguiente versión (FR-014/031).

La proyección personal se construye antes de serializar: si una Asignación pasa de empleado A
a B, A recibe retiro con su `before` y `after=null`; B recibe alta con `before=null` y su `after`.
Ninguno obtiene la identidad ni los valores del otro. Historial de A sigue disponible aunque ya
no tenga filas/jornadas vigentes. El planeador autorizado sí obtiene la diferencia completa.

## Continuidad y manifiesto de lectura

**ContinuidadJornada** es una proyección, no tabla de asignaciones: `assignment_id`,
`origin_period_id`, `origin_publication_id`, `origin_version`, contenido original completo,
`visible_from`, `visible_to`, `read_only=true`. Existe cuando una jornada intersecta el
intervalo consultado y su fecha local de inicio pertenece a otro periodo. Puede abarcar más
de un periodo; no se restringe la búsqueda solo al vecino inmediato.

La vista publicada del destino mantiene sus filas/jornadas congeladas. Las continuidades se
muestran en sección aparte, usando nombres/versiones de origen; no añaden filas al roster
congelado, no duplican edición y no cuentan de nuevo en conflictos. Un cambio en origen puede
cambiar esa sección sin incrementar la versión local; siempre se identifica mediante manifiesto.
La consulta histórica local mantiene su contenido local y enlaza el historial de origen; no
presenta continuidades actuales como parte del snapshot histórico local.

**ManifiestoProgramación**: `organization_id`, `branch_id?`, intervalo consultado,
`selected_period_id?`, `selected_publication_id?`, `sources[]` con periodo/publicación/versión,
`verified_at` y `manifest_hash`. Una transacción corta REPEATABLE READ fija los punteros y
materializa contenido; después no se leen catálogos ni punteros actuales para esa respuesta.
Solo se incluyen fuentes de la misma sucursal en vista colectiva; la personal puede agrupar
varias sucursales, siempre con filtro de empleado. Sin publicación local, la consulta personal
sigue mostrando las continuidades propias publicadas y rotula correctamente la ausencia local.

## Eventos, auditoría, incidencias y alertas

| Entidad | Campos | Uso |
| --- | --- | --- |
| Evento | `id`, `organization_id`, `branch_id?`, `type`, `subject_id`, `actor_id`, `occurred_at`, `payload`, `correlation_id` | Hechos confirmados de core y Programación, insertados en la misma transacción. Sin bus externo inicial. |
| Auditoría | `id`, `organization_id`, `branch_id?`, `actor_id`, `occurred_at`, `operation`, `subject_id`, `before`, `after`, `outcome`, `correlation_id` | Cambios de borrador, catálogo, habilitación y publicación. Un rollback no deja auditoría de éxito; un rechazo puede registrarse separadamente como rechazo, sin datos restringidos en respuesta/log. |
| Incidencia | `id`, `organization_id`, `branch_id`, `employee_id?`, `period_id`, `type`, `detected_at`, `source_event_id`, `affected_assignment_ids`, `status`, `resolved_at?`, `resolution_event_id?` | Registro trazable por pérdida de habilitación con jornadas publicadas futuras. No modifica ni elimina las jornadas publicadas. |
| Alerta | proyección `key`, `type`, `priority`, ámbito, responsable destinatario, sujeto, `context`, `required_action`, `source_event_id?`, estado | Presenta excepciones al planeador dentro de sus permisos; no crea otro módulo operativo. Condiciones detalladas en contracts/core.md. |

Al perder habilitación se identifican jornadas publicadas con `starts_at > validation_time`;
se conserva su publicación y se abre/actualiza la incidencia por periodo. La publicación de una
corrección resuelve las afectadas retiradas o reasignadas válidamente. La consulta vuelve a
evaluar las futuras aún afectadas; no depender de una tarea que altere snapshots. Si el inicio
pasa mientras sigue inhabilitado, el antecedente persiste en auditoría y la incidencia registra
ese cambio de condición; no inventa asistencia ni una corrección publicada. Las alertas de
bloqueo futuro se derivan de las que todavía inician en el futuro. Si se restituye habilitación,
la resolución por restitución se atribuye a ese evento, nunca se registra como republicación.

## Exportación

**ExportaciónProgramación**: `id`, `organization_id`, `branch_id`, `period_id`, `requested_by`,
`format=png|pdf`, `status=generating|ready|failed|expired`, `requested_at`, `generated_at?`,
`expires_at?`, `manifest`, `expected_counts`, `content_hash?`, `private_storage_key?`,
`byte_size?`, `duration_ms?`, `error_code?`, `pending_draft_excluded`.

Manifiesto/payload se fijan al iniciar la lectura consistente. La generación sucede fuera del
lock de escritura. `ready` solo después de validar resultado completo y renombrar atómicamente
el temporal; `failed` no expone bytes. Revalidar permiso al entregar el resultado y en cada
descarga. La retención inicial de archivos es 24 h; expirar archivos no borra publicaciones,
manifiestos ni auditoría. Una petición posterior genera otra copia desde la publicación vigente.

## Invariantes y validación transaccional

1. **Ámbito**: toda FK y selección valida organización; empleado habilitado y referencias
   activas/aplicables en jornadas nuevas o modificadas. Estación/Área y jornada/periodo deben
   coincidir en sucursal. Al menos `role_id` o `station_id` es obligatorio.
2. **Fechas**: fecha local de inicio dentro del periodo propietario; fin explícito mayor que
   inicio. Guardar UTC y representación resuelta local evita reinterpretar un histórico al
   cambiar zona o reglas horarias. Rechazar offsets incompatibles y fechas locales inexistentes.
3. **Pausas**: positivas, contenidas y no superpuestas; recalcular validación al cambiar jornada.
   Una pausa puede coincidir con un borde de la jornada, pero no extenderse fuera de él.
4. **Conflictos**: construir candidato completo C de P; compararlo internamente y con jornadas
   vigentes y borradores activos de otros periodos de la organización. Excluir contenido viejo
   de P, históricos y proyecciones de continuidad. Descansos no liberan tiempo.
5. **Mutex**: toda escritura relevante adquiere primero la fila de Organización bajo READ
   COMMITTED; relee permisos, ETag y dependencias después del lock. Ningún admin/carga salta
   el servicio. Duración breve; renderizado fuera del lock. Timeout conserva el estado previo.
6. **Publicar**: usar un instante único tras adquirir el lock. Bloquear jornadas futuras de
   personal ya inhabilitado; permitir retirar/reasignar y conservar intactas jornadas ya
   iniciadas, aunque el empleado haya perdido habilitación. Cualquier jornada modificada
   sigue validando empleado/referencias actuales. No invalidar historia por cambio de catálogo.
7. **Atomicidad**: validación, snapshot/diferencias, puntero vigente, incremento de revisión,
   auditoría/evento y resolución de incidencias aplicable ocurren en un commit. Rechazo deja
   intactos el borrador guardado y publicación previa. La entrada rechazada solo permanece en
   el formulario local, señalada como no guardada.

Restricciones de base: FKs y borrado protegido; unicidad de borrador y versión; duraciones
positivas; exclusión de rangos de fecha por organización/sucursal con `btree_gist`; índices
por empleado/inicio/fin en jornadas activas/publicadas y periodo/versión. No aplicar una
exclusión global de jornadas que impida coexistir borrador y publicación del mismo periodo.
El usuario de aplicación no expone escrituras arbitrarias fuera de los servicios.
Las tablas de publicaciones, filas, jornadas, pausas y cambios publicados son append-only:
el rol de ejecución recibe lectura/inserción, sin UPDATE/DELETE sobre esos snapshots. Migraciones
y mantenimiento usan un rol separado. El puntero vigente mutable reside en PeriodoProgramación.

## Transiciones

| Estado/condición | Operación | Resultado |
| --- | --- | --- |
| Periodo nuevo | Crear | Borrador inicial, revisión 1, sin publicación; puede estar vacío. |
| Borrador inicial | Guardar válido | Incrementar revisión si cambia el contenido; persistir todo y auditar. |
| Borrador inicial | Publicar válido | v1 y puntero vigente; borrador sincronizado/inactivo. |
| Publicado limpio | Editar o cambiar lista de core | Vista de revisión con diferencias; la publicación permanece intacta. Un cambio de core no publica. |
| Revisión pendiente | Guardar/publicar con ETag viejo | 412, solicitar refresco; no cambia contenido ni versión. |
| Revisión pendiente | Publicar válido con diferencias | vN+1, snapshot/diff y reemplazo atómico; sin pendientes propios. |
| Publicado/revisión | Publicar sin diferencias semánticas | 200 `no_changes`, conserva vN; sin anuncio ficticio. |
| Cualquier borrador | Validación o conflicto fallido | 422/409; conservar último estado válido y describir corrección. |
| Futuras publicadas + pérdida de habilitación | Cambio de core | Incidencia/alerta; misma publicación; bloquea nueva asignación y republicación inválida. |
| Exportación generando | Validación completa o fallo | `ready` o `failed`, sin archivo parcial exitoso. |

## Trazabilidad del modelo

| Requisitos | Elementos |
| --- | --- |
| FR-001/005/018/026/027 | Core, habilitación, usuario y permiso por sucursal; selectores personales. |
| FR-002/004/006/007/011/012 | Periodo, Asignación/JornadaBorrador y Descanso. |
| FR-008/009/010/020 | Conjuntos de conflicto, mutex, ETag y commit atómico. |
| FR-003/013/014/015/016/017/031 | Snapshot, filas congeladas, igualdad y cambios privados. |
| FR-019/028/029 | Continuidad, manifiesto y estado de consulta verificada. |
| FR-021/030 | Evento, Auditoría, Incidencia y proyección de Alerta. |
| FR-022/023/024/025 | Exportación, manifiesto, integridad y archivo privado. |
