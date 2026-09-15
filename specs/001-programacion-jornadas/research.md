# Investigación: Programación de jornadas operativas

**Fecha**: 2026-09-14 | **Entrada**: [spec.md](spec.md) | **Resultado**: decisiones de fase 0 resueltas.

El repositorio contiene la constitución y especificaciones, sin aplicación, catálogos, identidad
ni dependencias implementadas. Se investigaron tres frentes en paralelo: integración con
proveedores; tiempo/concurrencia/publicaciones; y pila web/exportación/conectividad. Las
decisiones siguientes son propuestas de diseño sustentadas en requisitos y documentación
primaria; no equivalen a pruebas de un producto o de una cuenta contratada.

## R1. Pila del monolito

**Decisión**: Python 3.13, Django 5.2 LTS, psycopg 3 y PostgreSQL 17. HTML adaptable mediante
plantillas y JavaScript local pequeño, sin SPA. Docker Compose para aplicación y base; Linux,
Gunicorn y HTTPS para piloto. Fijar parches y hashes compatibles durante implementación.

**Rationale**: Django aporta ORM, sesiones, CSRF y renderizado en una aplicación. Django 5.2
admite Python 3.13 y PostgreSQL 14 o superior; PostgreSQL 17 es una línea soportada. Django 5.2
tiene soporte extendido hasta abril de 2028, por lo que deberá planearse su actualización antes
de esa fecha. La elección minimiza piezas iniciales y permite compartir una transacción entre
dominio y programación. [Django 5.2](https://docs.djangoproject.com/en/5.2/releases/5.2/),
[PostgreSQL/psycopg](https://docs.djangoproject.com/en/5.2/ref/databases/#postgresql-notes),
[soporte Django](https://www.djangoproject.com/download/#supported-versions),
[soporte PostgreSQL](https://www.postgresql.org/support/versioning/).

**Alternativas consideradas**: API/SPA separadas, FastAPI más bibliotecas de identidad y
administración, y SQLite. No aportan una ventaja necesaria para los dos perfiles del piloto;
SQLite tampoco reproduce la concurrencia PostgreSQL que debe verificarse.

## R2. Integrar o construir

**Decisión**: construir exclusivamente Programación y el core mínimo en ROS-XOLO; sin conector
Odoo/Loyverse en esta entrega. No hay un proveedor contratado ni datos externos preexistentes
acreditados en el repositorio. ROS-XOLO será la única autoridad de la programación.

| Dimensión | Odoo Planning | Loyverse | Construcción elegida |
| --- | --- | --- | --- |
| Cobertura | Turnos, recursos, roles, borrador/publicación y portal personal documentados. | Gestión de empleados/permisos y registro de entradas/salidas; sus Shifts corresponden a caja. | Periodos, reservas, versiones, diferencias privadas y exportaciones conforme a FR-001 a FR-031. |
| Brecha | La documentación no acredita el conjunto de garantías de lista/versiones inmutables, reservas entre borradores, publicación completa atómica e historial privado requerido. Requeriría adaptar y probar. | No se acredita publicación versionada de jornadas futuras ni exportación de snapshots equivalentes. | Desarrollo y pruebas propios de la capacidad, sin duplicar POS, asistencia ni ERP. |
| Acceso/restricciones | API externa JSON-2 en plan Custom; cada llamada tiene su transacción. Un cambio compuesto requeriría método transaccional específico. | Tokens de Back Office con acceso a recursos de API; no acreditamos endpoints/campos concretos de empleados. | Una base transaccional y permisos internos por ámbito. |
| Costo operativo | Licencia, configuración y personalización; implantación, Odoo.sh y mantenimiento de código propio no están incluidos en la tarifa base descrita. | Employee Management es complemento pagado por sucursal; además habría operación del conector y del horario propio. | Alojamiento, PostgreSQL, copias/restauración, renderizador y mantenimiento. No se afirma costo cero ni una ventaja cuantificada. |

Fuentes de cobertura: [Odoo Planning](https://www.odoo.com/documentation/19.0/applications/services/planning.html),
[Loyverse Employee Management](https://loyverse.com/en-us/employee-management),
[Shifts de caja](https://help.loyverse.com/help/shift-management-loyverse-pos).
Acceso y condiciones: [API Odoo](https://www.odoo.com/documentation/19.0/pt_BR/developer/reference/external_api.html),
[precios Odoo](https://www.odoo.com/pricing), [tokens Loyverse](https://help.loyverse.com/help/loyverse-api),
[precios Loyverse](https://loyverse.com/pricing). Consulta: 2026-09-14; no se fijan tarifas comerciales.

**Rationale**: integrar captura básica de turnos no elimina las reglas que concentran el riesgo
de esta función. Dividir la autoridad entre turnos de un ERP y versiones de ROS-XOLO añade una
conciliación que también habría que construir. Adaptar Odoo es técnicamente plausible, pero
requiere adoptar y operar ese ERP con personalizaciones para este primer módulo. Con la evidencia
disponible no hay una integración estándar que satisfaga el contrato completo.

**Alternativas consideradas**: Odoo como autoridad con portal adaptado, Odoo como fuente de turnos
y snapshots locales, Loyverse como fuente de personal, o construir POS/ERP propios. Las primeras
requieren adopción y correspondencias adicionales sin resolver toda la función; la última queda
fuera del producto. No se interpreta ausencia de documentación como imposibilidad del proveedor.

**Límite de una integración futura**: el módulo Integraciones encapsularía proveedor, cuenta/base,
tipo e ID externos y su correspondencia con IDs internos; nunca unir empleados por nombre. Odoo
employee/resource y Loyverse employee podrían mapearse a Empleado; store a Sucursal solo mediante
configuración explícita. Rol de Planning no concede permisos ROS-XOLO; cash shifts y timecards no
son jornadas planificadas. Importar a preparación, validar y aplicar de forma atómica/idempotente;
ante credenciales, red, datos incompletos o discrepancias, conservar el último estado válido y
registrar incidencia. No borrar publicaciones ni habilitaciones por ausencia temporal en una
respuesta. Verificar esquema, permisos, límites y costos de una cuenta real antes de incorporar
el conector; esas verificaciones no son dependencias de la opción elegida.

## R3. Catálogos e identidad disponibles desde la primera entrega

**Decisión**: core mínimo con Organización, Sucursal, Empleado, habilitación de trabajo,
Rol operativo, Área/Estación y Turno; autenticación Django, vínculo usuario-empleado y concesión
explícita de planeación por sucursal. Carga inicial y cambios controlados mediante comando
`bootstrap_core`, más `seed_demo` sintético. Sin administración general ni proveedor de identidad externo.

**Rationale**: la especificación declara estas dependencias, pero no presume que existan. Las
sesiones y CSRF proporcionan mecanismos de autenticación, pero los permisos por objeto/sucursal
deben implementarse expresamente en servicios y selectores. Cada consulta personal toma el
empleado de la sesión antes de serializar datos. [Sesiones Django](https://docs.djangoproject.com/en/5.2/topics/http/sessions/),
[CSRF](https://docs.djangoproject.com/en/5.2/ref/csrf/),
[permisos por objeto](https://docs.djangoproject.com/en/5.2/topics/auth/customizing/#handling-object-permissions).

**Alternativas consideradas**: identidades ficticias en producción, admin genérico sin reglas,
conceder planeación por el rol de la jornada, o esperar un ERP no contratado. Ninguna satisface
la dependencia ni FR-001/005/018. Los datos reales del piloto se cargarán con revisión del operador;
la falta de esos datos no impide definir el diseño.

## R4. Tiempo, periodos y conjuntos que reservan disponibilidad

**Decisión**: instantes UTC conscientes de zona, IANA por sucursal y representación local/offset
conservada en snapshots. Jornada `[inicio, fin)` con fin explícito posterior al inicio. Periodo
local inclusivo representado como `daterange(inicio, fin + 1 día, '[)')`. Rechazar horas locales
inexistentes; en horas ambiguas exigir offset explícito válido. Un turno propone fecha de término
mediante un desplazamiento de días explícito de su catálogo; el usuario confirma fechas completas.

**Rationale**: así la comparación usa tiempo real entre zonas y permite intervalos adyacentes;
las pausas no restan disponibilidad. PostgreSQL dispone de rangos y operadores de intersección;
Django recomienda fechas conscientes de zona. [Rangos PostgreSQL](https://www.postgresql.org/docs/17/rangetypes.html),
[zonas Django](https://docs.djangoproject.com/en/5.2/topics/i18n/timezones/).

Para candidato completo C del periodo P, comparar C internamente y contra publicaciones vigentes
y borradores activos de todos los otros periodos de la organización. Excluir por completo el
borrador anterior y la publicación anterior de P; históricos sustituidos no reservan. Dos
jornadas del mismo empleado chocan si `a.inicio < b.fin && b.inicio < a.fin`. Una continuidad es
una referencia de lectura, nunca una segunda reserva. La publicación vigente de origen sigue
bloqueando un traslado a otra sucursal hasta que se publique su retiro; esto aplica también al
guardado del destino. Detalles restringidos se reemplazan por mensaje genérico de coordinación.

**Alternativas consideradas**: comparar solo días/horas locales, descontar comidas, excluir
publicaciones ajenas cuando tienen borrador, o reservar mediante históricos. Incumplen FR-007/010/028
y pueden liberar una asignación todavía vigente o bloquear revisiones válidas.

## R5. Concurrencia y atomicidad

**Decisión**: `transaction.atomic()` en READ COMMITTED y `SELECT FOR UPDATE` de la Organización
como primer lock para toda escritura de programación, habilitación, permisos o catálogos
relevantes. Releer después del lock y validar el candidato completo. ETag combina revisión del
periodo, publicación vigente y revisión de core; base vieja devuelve 412 sin sobrescribir.

**Rationale**: serializar brevemente por organización evita carreras incluso cuando la consulta
de conflictos no encuentra filas. Consultas posteriores al lock ven los commits previos en
READ COMMITTED. Publicación, snapshot, diferencias, puntero vigente y auditoría se confirman
juntos; una excepción revierte todo. [Bloqueos PostgreSQL](https://www.postgresql.org/docs/17/explicit-locking.html),
[aislamiento](https://www.postgresql.org/docs/17/transaction-iso.html),
[transacciones Django](https://docs.djangoproject.com/en/5.2/topics/db/transactions/).

**Alternativas consideradas**: solo lock de jornadas existentes, validación JavaScript, locks
por empleado con orden complejo, serializable con reintentos, o exclusión global de intervalos.
Las primeras no protegen inserciones; la exclusión global impide la coexistencia válida de
borrador/publicación del mismo periodo. Locks más finos quedan para una necesidad medida.

Los cambios de core incrementan `core_revision`, incluso si obligan a refrescar algún borrador
no afectado directamente: es una invalidación conservadora. Nunca mantener este lock mientras
Chromium renderiza o mientras el usuario decide. Límite inicial de espera de lock: 5 s; agotarlo
produce error reintentable sin escritura parcial.

## R6. Publicaciones, igualdad, filas y continuidades

**Decisión**: snapshot inmutable de jornadas, pausas y lista de empleados por versión. Identidad
estable de Asignación para comparar; reasignación proyectada como retiro/alta privados. Igualdad
semántica ignora autor/fecha/versión y orden accidental; compara contenido y filas. Primera
publicación vacía crea v1; otra idéntica no incrementa; cambio solo de lista sí incrementa.

**Rationale**: las ediciones de catálogos o una baja no reescriben historia. Borrador usa habilitados
actuales más personas con jornadas propias; las continuidades se agregan como referencias. Una
vista publicada conserva siempre su lista, y presenta continuidades en sección separada con los
datos y versión de origen, incluso si esa persona no figura en la lista del destino. Así FR-028
no modifica silenciosamente las filas congeladas por FR-031.

La vista es compuesta: versión local y manifiesto de versiones de origen. Resolver ambos dentro
de una lectura corta REPEATABLE READ; después solo usar esos IDs inmutables. La versión local
por sí sola no identifica cambios posteriores de una continuidad. Un destino no publicado puede
mostrar continuidades propias publicadas en origen; continúa rotulado como no publicado.

**Alternativas consideradas**: consultar catálogos actuales al mostrar históricos, copiar jornadas
al destino, congelar para siempre la continuidad en su versión anterior o atribuir toda la vista
a la versión local. Producen cambios históricos, duplicados o información de origen desactualizada.

## R7. PNG y PDF con el mismo contenido

**Decisión**: Playwright Python y Chromium fijados conjuntamente, ejecución síncrona dentro del
monolito. Capturar primero payload/manifiesto en una transacción de lectura consistente; cerrar
esa transacción, renderizar HTML autoescapado y fuentes locales sin red externa, comprobar
contenido y generar temporal privado. Publicar el archivo solo tras completitud y reautorizar
descarga. Registrar manifest, hash, duración y estado de generación.

**Rationale**: Playwright ofrece captura completa PNG y PDF con CSS de impresión. Un payload
materializado evita mezclar publicaciones al renderizar. `full_page` por sí solo no acredita que
estén todas las filas ni resuelve límites de recursos. [Navegadores Playwright](https://playwright.dev/python/docs/browsers),
[capturas](https://playwright.dev/python/docs/screenshots),
[PDF](https://playwright.dev/python/docs/api/class-page#page-pdf).

PNG: bloques de hasta siete días apilados, letra mínima propuesta de 16 px CSS, captura a escala
1 y altura completa; máximo inicial de 60 millones de píxeles y 30 000 px por dimensión.
PDF: A4 horizontal, texto >=10 pt, páginas y continuaciones explícitas con contexto repetido;
sin ocultar desbordes ni reducir indefinidamente. Presupuestos iniciales: dos renderizaciones
simultáneas por instancia y 25 s por render, dejando margen para SC-007. Saturación o exceso
produce error explícito; el dominio no queda limitado a 20 personas ni siete días. Ante un PNG
demasiado grande se puede solicitar PDF, sin sustituir silenciosamente el formato.

**Alternativas consideradas**: capturar tabla visible del cliente, motores diferentes por formato,
URLs públicas de medios o Redis/Celery desde el inicio. Complican coherencia, privacidad o
operación sin necesidad acreditada. Validar presupuestos en la carga de referencia antes del piloto.

## R8. Consulta personal con conexión

**Decisión**: `Cache-Control: private, no-store`, sin service worker ni persistencia del horario
en navegador. Mostrar versión y hora de última verificación; ocultar contenido al evento offline,
fallo de consulta, timeout o sesión vencida. Revalidar al seleccionar fechas, `pageshow`, volver
al primer plano y reconectar; comprobación autenticada cada 15 s con timeout de 5 s mientras
la vista esté activa. Una respuesta vieja no debe reemplazar la de una selección más reciente.

**Rationale**: `navigator.onLine` no garantiza acceso al servidor. La interfaz no promete detección
instantánea: cuando no hay evento de desconexión, el plazo de detección inicial es de hasta
20 s en una pestaña activa. Durante ese plazo identifica la última comprobación, no una vigencia
indefinida; tras el fallo no presenta datos anteriores como vigentes. [HTML Standard: onLine](https://html.spec.whatwg.org/multipage/system-state.html#dom-navigator-online-dev).

**Alternativas consideradas**: copia offline, restaurar la caché al recibir `online`, o consultar
una sola vez al abrir. No cumplen la aclaración de conectividad. Sin JavaScript mostrar requisito
de habilitarlo para esta consulta verificada, sin exponer un horario antiguo.

## R9. Validación y operación

**Decisión**: probar intervalos/diferencias como dominio, contratos/permisos en Django,
concurrencia con TransactionTestCase y conexiones PostgreSQL independientes, y recorridos
móviles/escritorio con Playwright. Comparar identificadores/recuentos del payload y salida,
extraer texto PDF y revisar PNG y todas las páginas. Medir tiempos desde la acción del usuario
en el entorno documentado, además de pruebas humanas en XOLO Jaltepec.

**Rationale**: TestCase envuelve pruebas en transacciones y puede ocultar errores de locks;
las carreras requieren límites reales. El despliegue requiere configuración de seguridad y
servidor de producción. [select_for_update](https://docs.djangoproject.com/en/5.2/ref/models/querysets/#select-for-update),
[TransactionTestCase](https://docs.djangoproject.com/en/5.2/topics/testing/tools/#transactiontestcase),
[despliegue Django](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/).

**Alternativas consideradas**: solo pruebas de interfaz, solo base en memoria o declarar objetivos
del piloto cumplidos con fixtures. No verifican privacidad, atomicidad ni autonomía de las personas.

## Cierre de investigación

No quedan aclaraciones técnicas bloqueantes. Versiones exactas de paquetes, credenciales, datos
reales y métricas se producirán en la implementación/validación definida; no se dan por existentes.
La decisión R2 satisface el control constitucional de integración antes de avanzar al diseño.
