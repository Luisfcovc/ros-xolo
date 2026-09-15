# Contrato interno de módulos y excepciones

**Versión**: 1 | **Estado**: diseño | **Modelo**: [data-model.md](../data-model.md).

## Responsabilidades y dependencias

| Componente | Es dueño de | Puede depender de | No debe hacer |
| --- | --- | --- | --- |
| Core | Identidades, catálogos mínimos, habilitación, permisos, tipos comunes de Asignación/Evento/Auditoría/Incidencia | Autenticación y persistencia Django | Redefinir publicación ni conceder planeación por rol operativo. |
| Programación | Periodos, contenido de jornadas/pausas, borradores, versiones, diferencias, selectores y reglas de disponibilidad | Contratos del core y su ORM dentro de la transacción del monolito | Mantener otro Empleado/Rol, registrar asistencia o llamar proveedores desde el dominio. |
| Exportaciones, adaptador de Programación | Payload congelado, layout, render, archivo privado y ciclo de generación | Selector publicado, autorización core, Chromium | Consultar catálogos/punteros vigentes durante render, exponer medios públicos o enviar archivos a terceros. |
| Vistas HTML/JSON | Validación de forma, sesión/CSRF, serialización y experiencia | Servicios/selectores autorizados | Implementar reglas de conflicto/publicación por separado o filtrar privacidad solo con CSS. |

Los módulos comparten base y proceso. Core emite un evento de cambio mediante un registro de
manejadores configurado en la raíz de aplicación; el manejador de Programación evalúa
inhabilitaciones dentro de la misma transacción. Core no importa directamente modelos del
módulo operativo. Fallo del manejador revierte también el cambio de core. No hay entrega
asíncrona externa ni éxito parcial del cambio de habilitación.
El manejador también procesa la desactivación de Empleado, porque la elegibilidad efectiva
requiere empleado activo y habilitación habilitada. Una baja lógica no salta las alertas por
el hecho de no modificar directamente HabilitaciónSucursal.

## Contexto de acceso

Todo servicio/selector recibe `ActorContext(user_id, organization_id)` construido desde sesión
validada. El servicio resuelve y comprueba el permiso actual; no confía en IDs o roles enviados
por el navegador. Personal se resuelve con `employee_id` del vínculo autenticado. Seleccionar
otra organización requiere pertenencia propia activa; una sucursal/objeto fuera de ámbito se
trata como no accesible, sin metadatos ni programación restringida.

## Operaciones del core

| Operación | Entradas | Resultado y garantías |
| --- | --- | --- |
| `authorize_planner` | actor, branch_id | Contexto autorizado o denegación; nunca consulta programación antes del control de ámbito. |
| `resolve_employee` | actor | Identidad personal del vínculo, incluso si no está habilitado para nuevas jornadas. |
| `get_planning_catalogs` | actor, branch_id | IDs/etiquetas/aplicabilidad visibles, empleados habilitados, revisión core y referencia horaria. |
| `resolve_shift` | actor, period_id, shift_id, start_date, offsets opcionales | Fechas/horas completas para confirmar; no escribe ni genera pausas. Turno fuera de ámbito, hora inexistente o ambigua sin offset se rechazan. |
| `apply_core_changes` | actor administrativo, manifest, expected_core_revision | Valida lote entero, toma mutex, aplica atómicamente, incrementa revisión y registra cambios/eventos. Rechaza referencias incompatibles, IDs ambiguos o base vieja. |

`apply_core_changes` solo se expone por comando administrativo autenticado mediante operador
identificado en el servidor. No equivale a permitir que un planeador cambie sus permisos.
Contrato del archivo de carga JSON: `schema_version=1`, `organization_id`,
`expected_core_revision`, listas `branches`, `employees`, `memberships`, `roles`, `areas`,
`stations`, `shifts`, `user_links`, `planner_grants`, con campos del modelo. IDs estables
obligatorios; listas omitidas no se modifican; elementos ausentes no se borran. Bajas mediante
flags explícitos. Validación previa `--validate-only`, sin persistencia; aplicación revalida.
Errores identifican lista/ID/campo y no imprimen secretos. `bootstrap_core` soporta inicialización
con revisión 0 y posteriores cambios bajo el mismo contrato. Contraseñas se configuran por un
canal de administración de cuentas, nunca se guardan en ese manifest ni en Git.
El actor inicial se crea con `createsuperuser` y el comando verifica que sea un administrador
activo; no basta escribir el nombre de un empleado en `--actor`. Acceso al comando requiere
administración del servidor. Esa cuenta tampoco obtiene por ello horarios colectivos desde
la aplicación: sus permisos de planeación se conceden por sucursal como los de cualquier usuario.

## Operaciones de Programación

| Operación | Entradas | Resultado |
| --- | --- | --- |
| `create_period` | actor, branch_id, date_from, date_to | Periodo + borrador inicial, fechas válidas y sin solapamiento. |
| `get_draft` | actor, period_id | Candidato de trabajo, lista actual, ETag, pendientes y continuidades de lectura; no publica. |
| `replace_draft` | actor, period_id, expected_etag, jornadas completas con pausas | Sustituye el candidato de ese periodo tras validarlo; quitar una ID existente significa retiro. No hay guardados parciales. |
| `publish_period` | actor, period_id, expected_etag | Snapshot/diferencias/puntero atómicos o `no_changes`; revalida todos los límites. |
| `get_published` | actor, period_id | Publicación local inmutable y continuidades con manifiesto coherente, más advertencia de borrador pendiente visible solo al planeador. |
| `get_personal_schedule` | actor, date_from, date_to | Solo publicaciones y cambios propios, estados vacíos y continuidades propias. |
| `get_history` | actor, period_id, version? | Planeador: ámbito autorizado. Personal: proyección propia con retiros/altas privados. |
| `export_published` | actor, period_id, png o pdf | Archivo coherente con manifiesto inicial o error explícito; no exporta borrador ni históricos. |

Todos los comandos de escritura relevantes toman el mutex de Organización antes de leer la
base que validarán. No hay operación de mover entre sucursales: guardar/publicar retiro en
origen, luego guardar/publicar alta con nueva Asignación en destino. Requiere permiso en cada
sucursal. Un borrador que retira la jornada no libera la publicación todavía vigente.

## Eventos y auditoría

Eventos confirmados: `core.membership_changed`, `core.catalog_changed`,
`core.planning_permission_changed`, `scheduling.period_created`, `scheduling.draft_saved`,
`scheduling.period_published`, `scheduling.incident_resolved`, `scheduling.export_ready` y
`scheduling.export_failed`. Sobre común: `event_id`, `organization_id`, `branch_id?`,
`actor_id`, `occurred_at`, `subject_type`, `subject_id`, `correlation_id`, `payload_version=1`.

`period_published` incluye `period_id`, `publication_id`, `version`, `previous_publication_id`
y IDs de cambios; el contenido sensible se obtiene mediante selectores autorizados. Evento y
auditoría de éxito están en la transacción de la operación. Auditoría de rechazo, si existe,
se distingue de un cambio aplicado y no conserva respuestas restringidas del cliente.

## Alertas e incidencias

Todas las alertas muestran tipo/prioridad, sucursal autorizada, periodo/empleado propio del
problema cuando corresponda, planeador responsable de actuar, contexto permitido y acción
requerida. El destinatario es el conjunto de planeadores con permiso en esa sucursal; no
presupone que el dueño deba resolverlo. No se envían notificaciones externas.

| Tipo | Activación | Resolución / historial | Prioridad y acción |
| --- | --- | --- | --- |
| `overlap` | Candidato comparte tiempo con otra jornada/reserva | Candidato corregido pasa validación; rechazo no cambia la base. Se vuelve a validar al guardar. | Alta: corregir horario o coordinar con planeador autorizado. Si origen restringido, sin nombre de sucursal, horario, ID ni empleado ajeno. |
| `stale_base` | ETag no coincide después del lock | Refrescar base y revisar cambios antes de enviar de nuevo. No reintento automático con ETag nuevo. | Alta: revisar versión actual; conservar entrada local señalada como no guardada. |
| `initial_publication_pending` | Periodo sin publicación, incluso vacío | Primera publicación válida | Media: revisar y publicar. |
| `revision_pending` | Contenido/lista del candidato difiere del publicado | Publicar válidamente o volver al contenido idéntico; sin aviso si no hay diferencia. | Media: revisar diferencias y publicar. |
| `employee_ineligible_future` | Habilitación perdida y jornadas vigentes con inicio futuro | Publicación retira/reasigna las afectadas, o evento de restitución elimina la causa. Paso del tiempo actualiza el conjunto futuro sin borrar el antecedente ni simular corrección. | Alta: retirar o reasignar jornadas futuras antes de republicar. Incidencia persiste con evento/motivo de resolución o cambio de condición. |

Una publicación fallida mantiene versión, contenido, auditoría de éxito y pendientes sin
cambios parciales. Al corregir el borrador desaparece el error de validación correspondiente,
pero permanece `revision_pending` hasta publicar. Una incidencia referida a la publicación
vigente no se resuelve solo por corregir el borrador.

## Compatibilidad

Los contratos son versión 1 del monolito, no compromisos de una API comercial. Cambios aditivos
de campos opcionales no cambian identidades. Cambios de semántica de intervalos, privacidad,
ETag, snapshot o evento requieren revisar contratos y pruebas de compatibilidad. Un futuro
conector debe preservar estos servicios como única vía de escritura y definir autoridad y
conciliación conforme a [research.md](../research.md), R2.
