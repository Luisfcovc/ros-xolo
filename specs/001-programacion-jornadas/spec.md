# Feature Specification: Programación de jornadas operativas

**Feature Branch**: `main` (rama existente; esta especificación se identifica por su directorio)

**Feature Directory**: `specs/001-programacion-jornadas`

**Created**: 2026-09-14

**Status**: Draft

**Input**: User description: "El planeador debe crear, modificar y consultar la jornada de cada
empleado por sucursal y periodo: días, turno u horario y rol o estación; evitar traslapes;
programar intervalos de descanso/comida opcionales; consultar la programación completa como planeador y únicamente
la propia como empleado; exportar el periodo en PNG o PDF; y hacer visibles los cambios
posteriores a la publicación y la versión vigente. Primer entorno de prueba: XOLO Jaltepec."

El usuario principal es el dueño u operador responsable de la programación, denominado
**planeador**. El usuario secundario es el **empleado** que consulta su horario asignado.
La funcionalidad permite delegar la planeación en una persona autorizada y mantener una
referencia consultable de quién debe estar dónde y cuándo, sin comunicación presencial
individual del dueño. La programación servirá como referencia futura para el checador y las
actividades por turno.

## Clarifications

### Session 2026-09-14

- Q: ¿Debe el empleado poder consultar dentro del sistema su último horario guardado cuando no tenga conexión a internet?
  → A: No. La consulta requiere conexión; sin ella se informa que no se puede verificar el horario vigente.

- Q: Si un empleado deja de estar habilitado para trabajar en una sucursal, ¿qué debe pasar con sus jornadas futuras ya publicadas?
  → A: Conservarlas con una alerta al planeador; bloquear nuevas asignaciones y exigir corregir las jornadas afectadas antes de republicar el periodo.

- Q: Si cambia la lista de empleados de una sucursal después de publicar un periodo, ¿la vista y la exportación de esa versión deben conservar la lista original o mostrar la lista actual?
  → A: Conservar la lista de empleados de la publicación; actualizarla mediante una nueva revisión publicada.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Planear y publicar un periodo de la sucursal (Priority: P1)

Como planeador, quiero registrar y ajustar las jornadas del personal y consultar la programación
completa de una sucursal durante un periodo, para publicar una distribución de trabajo que
cualquier empleado pueda consultar sin pedirme instrucciones.

**Why this priority**: Establece la información operativa central y permite delegar la preparación
y publicación del horario sin requerir la presencia física del dueño.

**Independent Test**: Con empleados, sucursal, roles, estaciones y turnos de prueba disponibles,
un planeador crea un periodo de siete días, asigna jornadas, modifica una, retira otra y publica.
Se comprueba la programación guardada y publicada sin necesitar checador ni actividades.

**Acceptance Scenarios**:

1. **Given** un planeador autorizado en XOLO Jaltepec y un periodo nuevo, **When** registra
   jornadas con empleado, fechas, sucursal, horario y rol o estación, **Then** puede guardar
   el borrador y volver a consultar exactamente los datos registrados.
2. **Given** el borrador de una sucursal, **When** consulta el periodo completo, **Then** ve
   conjuntamente a todos los empleados habilitados para esa sucursal y a los empleados con
   jornadas asignadas allí, incluidos los días sin jornada asignada, sin mezclar otras sucursales.
3. **Given** jornadas en borrador, **When** modifica un horario o retira una jornada,
   **Then** la consulta refleja el cambio y registra quién lo realizó y cuándo.
4. **Given** un borrador válido, **When** el planeador publica el periodo, **Then** queda
   identificada la versión 1, con fecha y responsable, y sus jornadas pasan a ser consultables
   por los empleados correspondientes.
5. **Given** fechas inválidas, una estación de otra sucursal o un periodo que se solapa con otro
   de la misma sucursal, **When** intenta guardar, **Then** recibe el motivo y la corrección
   requerida, y se conserva el último contenido válido sin cambios parciales.
6. **Given** una jornada del domingo de 22:00 al lunes de 06:00, **When** consulta cualquiera
   de los periodos semanales afectados, **Then** ve las fechas reales y la continuidad del
   trabajo, con referencia al periodo de origen, sin duplicar la jornada ni su edición.
7. **Given** un planeador autorizado únicamente para una sucursal, **When** intenta crear,
   modificar, publicar o exportar la programación de otra sucursal, **Then** se rechaza
   la operación sin entregar la programación restringida ni modificarla.
8. **Given** un periodo válido sin jornadas, **When** el planeador lo publica,
   **Then** se crea su versión publicada y la consulta indica que no hay jornadas asignadas.
9. **Given** un empleado que deja de estar habilitado para la sucursal y tiene jornadas cuyo
   inicio aún no ocurre, **When** el planeador consulta su programación o intenta asignarle
   otra jornada, **Then** ve una alerta sobre las jornadas publicadas afectadas y se rechaza
   la nueva asignación; la publicación existente conserva su contenido y versión.

---

### User Story 2 - Consultar únicamente el horario propio (Priority: P1)

Como empleado, quiero consultar mi programación publicada con sucursal, días, horario, rol o
estación y intervalos de descanso/comida cuando estén programados, para saber dónde y cuándo presentarme y qué
asignación tengo, sin acceder a los horarios de mis compañeros.

**Why this priority**: Hace consultable el horario sin intervención del dueño y protege la
separación entre la vista colectiva del planeador y la consulta personal del empleado.

**Independent Test**: Con una programación publicada para dos empleados y dos sucursales,
cada empleado consulta su periodo. Se verifica que solo obtiene sus propias jornadas, aunque
intente abrir la consulta, historial o exportación colectiva de otro usuario.

**Acceptance Scenarios**:

1. **Given** un empleado con jornadas publicadas en dos sucursales, **When** consulta su periodo,
   **Then** ve únicamente sus jornadas, con sucursal, fechas, horario, rol o estación, intervalos de descanso/comida
   si existen y la identificación de la versión publicada de cada periodo de origen.
2. **Given** un empleado sin permiso de planeación, **When** intenta consultar horarios o cambios
   de compañeros o acceder a una exportación colectiva del sistema, **Then** no obtiene esos datos.
3. **Given** un borrador inicial aún no publicado, **When** un empleado consulta esas fechas,
   **Then** ve que no tiene programación publicada para ese periodo y no ve el borrador.
4. **Given** un periodo publicado en el que un empleado no tiene jornadas, **When** lo consulta,
   **Then** ve “sin jornadas asignadas” para esa versión, sin confundirlo con un periodo pendiente
   de publicación ni atribuir automáticamente vacaciones o ausencia.
5. **Given** una persona que también es planeador autorizado, **When** usa su consulta personal,
   **Then** ve solo sus jornadas; al usar la consulta de planeación, puede ver el conjunto
   únicamente de las sucursales para las que tiene permiso.
6. **Given** un empleado sin conexión a internet, **When** intenta consultar su horario,
   **Then** se informa que no se puede verificar la programación vigente y no se ofrece una
   copia guardada como consulta sin conexión; al reconectar, puede consultar la versión vigente.

---

### User Story 3 - Corregir asignaciones que se traslapan (Priority: P1)

Como planeador, quiero que se impida guardar o publicar jornadas incompatibles de un mismo
empleado, para no programarlo en dos lugares o turnos al mismo tiempo.

**Why this priority**: Una programación contradictoria deja al empleado sin una instrucción
ejecutable y obliga al dueño a resolver el conflicto en piso.

**Independent Test**: Con una jornada existente de 09:00 a 17:00, se intenta añadir otra de
16:00 a 22:00 para el mismo empleado, en la misma sucursal y en otra; ambas se rechazan.
Se comprueba por separado que una jornada de 17:00 a 21:00 sí es compatible.

**Acceptance Scenarios**:

1. **Given** una jornada de 09:00 a 17:00, **When** se intenta guardar otra del mismo empleado
   de 16:00 a 22:00, **Then** se bloquea el guardado, se señala el traslape y se conserva lo anterior.
2. **Given** una asignación en otra sucursal o en un periodo vecino, incluso si cruza medianoche,
   **When** se intenta guardar una jornada que comparte tiempo con ella, **Then** se detecta
   el conflicto; si el planeador no puede consultar la otra sucursal, el aviso no revela
   su programación y solicita coordinación con un planeador autorizado.
3. **Given** una jornada que termina a las 17:00, **When** se asigna otra que inicia a las 17:00,
   **Then** se permite porque no comparten tiempo; una jornada duplicada o de duración nula
   se rechaza.
4. **Given** un borrador válido cuando se guardó, **When** el planeador publica después de que
   otra asignación relevante cambió, **Then** se vuelven a comprobar los conflictos y una
   publicación inválida no sustituye la versión vigente.
5. **Given** una jornada en revisión, **When** el planeador cambia su horario, **Then** se evalúa
   el resultado propuesto sin tratar la versión anterior de esa misma programación como una
   segunda asignación; las jornadas de otros periodos y sucursales siguen participando.
6. **Given** un traslape señalado, **When** el planeador corrige el horario y guarda con éxito,
   **Then** desaparece el conflicto resuelto y se conserva la indicación de publicación pendiente
   hasta que publique válidamente la programación.

---

### User Story 4 - Publicar revisiones y comprender qué cambió (Priority: P1)

Como planeador, quiero preparar y publicar una revisión del horario, y como empleado quiero
distinguir el horario vigente y los cambios que me afectan, para evitar actuar sobre una
versión sustituida.

**Why this priority**: El horario pierde utilidad si las modificaciones dejan varias instrucciones
aparentemente vigentes o solo se comunican verbalmente.

**Independent Test**: Partiendo de una versión publicada, se modifica una jornada, se añade otra
y se retira una tercera. Antes de publicar se conserva la consulta anterior del empleado;
después se comprueban la nueva versión, las diferencias y el historial filtrado por persona.

**Acceptance Scenarios**:

1. **Given** la versión 1 publicada, **When** el planeador guarda una revisión en borrador,
   **Then** él ve que hay cambios pendientes y los empleados siguen consultando la versión 1.
2. **Given** una revisión válida, **When** se publica, **Then** se genera la siguiente versión
   del periodo y se muestra qué jornadas se añadieron, modificaron o retiraron, con fecha,
   responsable y valores anteriores y nuevos de los campos que cambiaron.
3. **Given** un cambio de día, horario, sucursal, rol, estación o descanso/comida que afecta a un empleado,
   **When** consulta después de su publicación, **Then** encuentra su programación vigente y
   el cambio correspondiente, sin tener que comparar listas completas de otros empleados.
4. **Given** una jornada que se retira o se reasigna a otra persona, **When** se publica,
   **Then** el empleado original ve el retiro de su asignación y el nuevo empleado ve su alta,
   sin que ninguno reciba los datos de programación de la otra persona.
5. **Given** varias revisiones publicadas, **When** se consulta el historial autorizado,
   **Then** permanecen identificables las versiones anteriores y sus diferencias;
   no se presentan como vigentes ni se altera su contenido al editar catálogos de turnos.
6. **Given** dos planeadores trabajando sobre la misma revisión, **When** uno intenta guardar
   o publicar sobre contenido que el otro ya cambió, **Then** se avisa que su base quedó
   desactualizada y se exige revisarla antes de sustituir trabajo ajeno.
7. **Given** un borrador idéntico a la versión publicada, **When** se intenta publicarlo,
   **Then** se informa que no hay cambios y se conserva el número de versión, sin anunciar
   una modificación inexistente.
8. **Given** jornadas futuras publicadas de un empleado que ya no está habilitado en la
   sucursal, **When** el planeador intenta republicar sin corregirlas, **Then** la publicación
   se bloquea; al retirar o reasignar las jornadas afectadas a personal habilitado y publicar
   válidamente, se muestran los cambios y la alerta resuelta deja de figurar como pendiente.
9. **Given** una versión publicada y un cambio posterior en la lista de empleados de la
   sucursal, **When** el planeador prepara y publica una revisión con la lista actualizada,
   **Then** la versión anterior conserva su lista y la nueva identifica las filas añadidas
   o retiradas, aunque no haya cambiado ninguna jornada.

---

### User Story 5 - Programar intervalos de descanso/comida opcionales dentro de la jornada (Priority: P2)

Como planeador, quiero añadir, cambiar o quitar intervalos opcionales de descanso/comida dentro
de la jornada de cada empleado, para dejar explícitas las pausas que pueden usarse para comer
o para otro tipo de descanso cuando la operación las programe.

**Why this priority**: Complementa la jornada sin impedir programar o publicar cuando no se
definen intervalos de descanso/comida.

**Independent Test**: Sobre una jornada de 09:00 a 17:00 se añade un descanso/comida de 13:00 a 13:30,
se consulta como empleado y se intenta registrar uno fuera de la jornada.

**Acceptance Scenarios**:

1. **Given** una jornada válida sin intervalos de descanso/comida, **When** se guarda y publica, **Then** la ausencia
   de descanso/comida programado no provoca un error ni crea un intervalo automático.
2. **Given** una jornada de 09:00 a 17:00, **When** se registra un descanso/comida de 13:00 a 13:30,
   **Then** aparece dentro de esa jornada tanto para el planeador como para el empleado.
3. **Given** una jornada con un descanso/comida existente, **When** se añade un descanso/comida fuera del
   intervalo de trabajo, de duración nula o que se traslapa con otro descanso/comida, **Then** se rechaza
   y se indica el intervalo que debe corregirse.
4. **Given** un descanso/comida programado, **When** se acorta la jornada y el descanso/comida queda fuera,
   **Then** no se guarda el cambio hasta ajustar o retirar ese descanso/comida; si ya estaba publicado,
   el ajuste solo cambia la consulta del empleado después de publicar una revisión.
5. **Given** una jornada con descanso/comida de 13:00 a 13:30, **When** se intenta asignar otro turno
   durante ese descanso/comida, **Then** se rechaza el traslape con la jornada completa.

---

### User Story 6 - Exportar el periodo publicado como PNG o PDF (Priority: P2)

Como planeador, quiero obtener la programación publicada de una sucursal y un periodo en PNG
o PDF, para compartirla o imprimirla fuera del sistema con una identificación clara de su versión.

**Why this priority**: Permite distribuir el horario fuera del sistema sin volver a transcribirlo
y conserva una referencia de cuál versión se compartió.

**Independent Test**: Con un periodo publicado que incluya jornadas nocturnas, intervalos de descanso/comida y días
sin asignación, se genera cada formato y se compara con la misma versión consultada en el sistema.

**Acceptance Scenarios**:

1. **Given** un periodo publicado, **When** el planeador selecciona PNG o PDF, **Then** obtiene
   el formato solicitado con toda la programación de la sucursal y el periodo seleccionados.
2. **Given** jornadas, intervalos de descanso/comida y días sin asignación en la versión publicada, **When** se abre
   el archivo, **Then** esos datos coinciden con la programación y se identifican sucursal,
   fechas, referencia horaria, versión, publicación y momento de generación.
3. **Given** una programación de muchas filas o jornadas nocturnas, **When** se exporta,
   **Then** no faltan empleados, días, intervalos de descanso/comida ni fechas de término; la imagen conserva texto
   legible al visualizarla a su resolución y el PDF permite imprimir todas las filas sin recortes.
4. **Given** una exportación de la versión 1 y una revisión publicada después, **When** se
   consulta el archivo anterior, **Then** conserva su identificación de versión 1 y su aviso
   de copia estática; la nueva exportación corresponde a la nueva versión.
5. **Given** que la programación cambia durante la generación o esta falla, **When** finaliza
   la operación, **Then** se obtiene una copia coherente de las versiones identificadas al
   iniciar la exportación o un error explícito, nunca un archivo presentado como completo
   con datos mezclados, faltantes o pertenecientes a otra sucursal.
6. **Given** un periodo que solo tiene borrador, **When** se intenta exportar,
   **Then** se indica que debe publicarse antes; si existe una revisión en borrador, se exporta
   la versión publicada y se aclara que los cambios pendientes no están incluidos.
7. **Given** una versión publicada y cambios posteriores en el personal habilitado para la
   sucursal, **When** se consulta o exporta esa misma versión antes de publicar una revisión,
   **Then** se conserva exactamente la lista publicada, incluidos los empleados sin jornadas.

### Edge Cases

- Una jornada cruza medianoche, cambia de semana o termina en otro periodo: conserva sus fechas
  completas y se muestra como continuidad donde corresponda, sin crear una segunda asignación.
- Dos sucursales usan referencias horarias distintas: el traslape se evalúa por el tiempo real
  coincidente y cada jornada muestra la referencia horaria de su sucursal.
- Una jornada termina exactamente cuando otra comienza: no hay traslape. El traslado entre
  sucursales no se calcula en esta entrega.
- Un empleado tiene dos jornadas separadas el mismo día: se permiten si no se traslapan.
  Los intervalos de descanso/comida no abren huecos disponibles para otras jornadas.
- Un periodo no tiene jornadas o una revisión retira todas: puede publicarse sin asignaciones
  y sigue siendo distinguible de un periodo nunca publicado.
- Una consulta incluye personas habilitadas sin jornadas o con asignaciones retiradas:
  se muestra su situación sin revelar horarios ajenos a un empleado.
- Se cambia un turno del catálogo después de publicar: el horario publicado conserva sus
  valores; cualquier cambio en jornadas existentes necesita una revisión explícita.
- Una revisión cambia de sucursal una jornada: se retira de la programación de origen y se añade
  a la de destino mediante sus revisiones respectivas; el destino no puede publicarse mientras
  exista un traslape con la asignación vigente de origen. Se requieren permisos en cada sucursal.
- Un planeador carece de permisos para ver una asignación que causa conflicto: recibe el bloqueo
  y la acción de coordinación requerida sin los detalles restringidos.
- Un empleado deja de estar habilitado para una sucursal con jornadas futuras ya publicadas:
  se conserva la versión publicada y se alerta al planeador. No se retiran automáticamente
  las jornadas; las afectadas deben resolverse antes de republicar el periodo.
- Cambia la lista de empleados de la sucursal después de publicar: la vista y las
  exportaciones de esa versión conservan la lista publicada, incluidos los empleados sin
  jornadas. Actualizar las filas requiere preparar y publicar una revisión.
- Dos planeadores editan simultáneamente, o cambian asignaciones después de validarlas:
  no se sobrescribe trabajo ni se publica un conflicto silenciosamente.
- Un archivo descargado se comparte después de una nueva publicación: conserva su versión
  y fecha; no puede actualizarse ni revocarse dentro de una copia que ya salió del sistema.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE limitar crear, modificar, publicar y exportar programaciones a
  planeadores autorizados para su organización y sucursal. El rol operativo asignado en una
  jornada NO DEBE otorgar por sí solo permisos de planeación.
- **FR-002**: El planeador DEBE poder crear y consultar periodos con sucursal y fechas inicial
  y final inclusivas; la semana es la selección predeterminada. La fecha final no puede preceder
  a la inicial. Los periodos de planeación de una misma sucursal NO DEBEN solaparse; para cambiar
  días ya incluidos se modifica el periodo existente. Las revisiones pertenecen al mismo periodo.
- **FR-003**: En el borrador, la vista del planeador DEBE reunir a todos los empleados
  actualmente habilitados para la sucursal y los que tengan jornadas en ella durante el periodo,
  con sus días, horarios, rol o estación e intervalos de descanso/comida, e indicar los días
  sin jornada. La vista publicada DEBE conservar la lista de empleados fijada al publicar
  esa versión. Ambas vistas DEBEN distinguir borrador y versión publicada.
- **FR-004**: Cada jornada DEBE identificar empleado, sucursal, fecha y hora de inicio y fin,
  y al menos un rol o una estación; puede incluir ambos. Elegir un turno DEBE resolver su horario
  concreto para esas fechas; también DEBE permitirse capturarlo directamente.
- **FR-005**: Las asignaciones nuevas o modificadas DEBEN usar empleados de la organización
  habilitados para trabajar en la sucursal y roles, estaciones y turnos aplicables. La pérdida
  posterior de habilitación se gestiona conforme a FR-030 y no invalida el historial publicado.
  Una estación DEBE pertenecer a la
  sucursal seleccionada. La sucursal de la jornada DEBE coincidir con la de su programación y
  su fecha local de inicio DEBE estar dentro del periodo. El sistema DEBE rechazar referencias
  incompatibles e indicar la corrección.
- **FR-006**: El planeador DEBE poder añadir, modificar y retirar jornadas en un borrador,
  consultarlas después de guardar y preparar esas mismas operaciones en revisiones de periodos
  publicados. Una retirada publicada DEBE conservarse en el historial.
- **FR-007**: El sistema DEBE permitir varias jornadas no superpuestas en un día y jornadas
  que crucen medianoche con fecha de término explícita. El fin DEBE ser posterior al inicio;
  no se DEBE inferir automáticamente un cambio de día para justificar un horario inválido.
- **FR-008**: El sistema DEBE impedir guardar una asignación o publicar un periodo que produzca
  un traslape del mismo empleado, considerando todas las sucursales y periodos de la organización.
  DEBE comprobar jornadas publicadas y otros borradores activos, incluidas continuidades
  nocturnas, usando las fechas y horas reales. En una revisión se evalúa el reemplazo completo
  del periodo y no se cuenta su versión anterior como otra asignación.
- **FR-009**: Un traslape DEBE existir cuando dos jornadas comparten tiempo de duración positiva;
  terminar al inicio de otra es válido. Los duplicados DEBEN rechazarse. Los intervalos de descanso/comida NO DEBEN
  descontarse del intervalo usado para detectar traslapes.
- **FR-010**: Un rechazo de guardado o publicación DEBE indicar el problema y cómo corregirlo,
  preservando el último estado válido sin cambios parciales. Los detalles de asignaciones en
  otras sucursales solo DEBEN mostrarse si el planeador tiene permiso de consulta sobre ellas.
- **FR-011**: Una jornada DEBE admitir cero o más intervalos opcionales de descanso/comida con inicio
  y fin explícitos, duración positiva, contenidos completamente en la jornada y sin traslaparse
  entre sí. El sistema NO DEBE exigir ni generar intervalos de descanso/comida cuando el planeador no los programe.
- **FR-012**: El planeador DEBE poder añadir, modificar o retirar intervalos de descanso/comida. Cambiar una jornada
  DEBE volver a validar sus intervalos de descanso/comida; si alguno queda fuera, el guardado DEBE exigir corregirlo
  o retirarlo. Las consultas y revisiones DEBEN reflejar los intervalos de descanso/comida como parte de la jornada.
- **FR-013**: La publicación DEBE ser una acción explícita del planeador sobre un periodo
  completo, con nueva validación de sus asignaciones. La primera publicación DEBE crear la
  versión 1. Un periodo vacío válido DEBE poder publicarse como “sin jornadas asignadas”.
- **FR-014**: Después de publicar, las modificaciones DEBEN prepararse en un borrador de
  revisión mientras la versión publicada sigue vigente. Solo una nueva publicación válida
  DEBE sustituirla, incrementando en uno la versión del periodo. Un borrador idéntico a la
  versión publicada NO DEBE producir otra versión ni un aviso de cambios pendientes; al intentar
  publicarlo se DEBE informar que no hay cambios. Guardar un borrador no publica.
- **FR-015**: Cada publicación DEBE conservar una versión histórica con su contenido, incluida
  la lista de empleados, responsable y fecha y hora. Las altas, modificaciones, retiradas
  y publicaciones DEBEN dejar un registro
  de autor, momento y datos afectados. Cambiar catálogos o revisiones posteriores NO DEBE
  alterar los valores de versiones ya publicadas.
- **FR-016**: Al publicar una revisión, el sistema DEBE señalar que hubo cambios y mostrar las
  diferencias con la versión publicada anterior: jornadas añadidas y retiradas y valores antes
  y después de empleado, fechas, horas, rol, estación y intervalos de descanso/comida que hayan cambiado. Los cambios
  de sucursal DEBEN quedar reflejados como retiro y alta en sus periodos correspondientes. Si
  cambia la lista de empleados, el planeador DEBE poder identificar las filas añadidas o retiradas,
  aunque no cambien las jornadas. La consulta personal DEBE mantener su restricción a datos propios.
- **FR-017**: Los planeadores DEBEN poder consultar el historial de sus sucursales y cada empleado
  únicamente el de sus propias asignaciones. Una reasignación DEBE mostrarse como retiro para
  la persona anterior y alta para la nueva, sin revelar la programación de la otra persona.
  Las diferencias e historial DEBEN permanecer consultables durante la vida del periodo, aunque
  exista una publicación posterior o el empleado ya no tenga jornadas vigentes.
- **FR-018**: La consulta personal DEBE mostrar solo las jornadas publicadas del empleado que
  consulta, en las sucursales y fechas afectadas, con horario, rol o estación, intervalos de descanso/comida y versión.
  Esa restricción DEBE aplicarse también al detalle y al historial, aunque intente acceder
  directamente a información de otro empleado. La consulta personal de un planeador también
  DEBE limitarse a sus propias jornadas.
- **FR-019**: El sistema DEBE diferenciar “sin programación publicada” de “sin jornadas asignadas
  en la versión vigente”. NO DEBE revelar borradores a los empleados ni interpretar la ausencia
  de asignación como asistencia, falta, permiso o vacaciones. Aunque el periodo consultado aún
  no esté publicado, DEBE mostrar las continuidades de jornadas propias ya publicadas en otro
  periodo y aclarar su origen, sin afirmar que no hay trabajo programado en esas fechas.
- **FR-020**: Antes de guardar o publicar sobre una programación que otro planeador haya
  modificado, el sistema DEBE detectar que la base está desactualizada, impedir la sustitución
  silenciosa y solicitar revisar el contenido actual. Si falla una publicación, la versión
  anterior DEBE permanecer vigente.
- **FR-021**: La vista del planeador DEBE identificar los conflictos que bloquean su operación,
  las incidencias por pérdida de habilitación de empleados para una sucursal, la programación
  pendiente de publicación y las revisiones pendientes, con empleado o periodo afectado,
  contexto permitido y acción requerida. Tras resolver la condición y, cuando corresponda,
  publicar la corrección, esta DEBE dejar de figurar como pendiente.
- **FR-022**: El planeador DEBE poder exportar la versión publicada de una sucursal y un periodo
  específico como una imagen PNG o un documento PDF. Si solo hay borrador, DEBE indicarse la
  necesidad de publicar. Si hay revisión pendiente, DEBE aclararse que se exporta la publicada.
- **FR-023**: Ambas exportaciones DEBEN incluir todos los empleados y días de la vista colectiva publicada
  del periodo, jornadas, roles o estaciones, intervalos de descanso/comida programados y días sin jornada, además de
  sucursal, fechas del periodo, referencia horaria, versión, momento de publicación y generación.
  Las jornadas nocturnas DEBEN conservar su fecha de término. Las continuidades procedentes
  de otro periodo DEBEN identificar ese periodo y su versión de origen.
- **FR-024**: El PNG DEBE conservar todo el contenido con texto legible a su resolución; el PDF
  DEBE permitir imprimirlo legiblemente, repartido en páginas cuando sea necesario y repitiendo
  el contexto de sucursal, periodo y versión. NO DEBEN cortarse ni omitirse filas o datos por
  exceder el área visible en pantalla.
- **FR-025**: Cada exportación DEBE corresponder a las versiones publicadas identificadas al
  iniciarla, sin incorporar cambios posteriores de manera parcial. DEBE indicar que es una copia
  estática y que la vigencia se consulta en el sistema. Un fallo DEBE informarse y NO DEBE
  entregar un archivo incompleto como resultado exitoso ni modificar la programación.
- **FR-026**: El sistema DEBE restringir la generación y obtención de exportaciones colectivas
  a los planeadores autorizados, incluida la apertura directa de un archivo servido por el
  sistema. Esta autorización no implica envío automático a terceros.
- **FR-027**: Las jornadas DEBEN conservar su vínculo con Organización, Sucursal, Empleado, Rol
  o Estación y, si se eligió, Turno, usando las mismas identidades del dominio común. La
  programación publicada DEBE distinguir el trabajo previsto de la asistencia o ejecución real.
- **FR-028**: Cada jornada DEBE pertenecer al periodo que contiene su fecha local de inicio.
  Si se extiende a otro periodo, las consultas y exportaciones de este DEBEN mostrar su
  continuidad con referencia a la asignación y versión de origen, sin duplicarla; la edición
  DEBE realizarse en el periodo de origen. La detección de conflictos DEBE abarcar toda su duración.

- **FR-029**: La consulta del horario propio DEBE requerir conexión a internet. Si no hay
  conexión o se pierde durante la consulta, el sistema DEBE informar que no puede verificar
  el horario vigente y NO DEBE presentar datos anteriores como vigentes. La consulta de una
  copia guardada dentro del sistema sin conexión queda fuera del alcance de esta entrega.

- **FR-030**: Si un empleado pierde su habilitación para trabajar en una sucursal, el sistema
  DEBE bloquear nuevas asignaciones allí y alertar al planeador sobre sus jornadas publicadas
  cuyo inicio aún no haya ocurrido. Esas jornadas DEBEN conservar su contenido y versión vigente
  hasta una publicación explícita de la corrección; NO DEBEN retirarse automáticamente.
  El sistema DEBE impedir republicar el periodo mientras contenga las jornadas futuras afectadas
  sin corregir; el planeador DEBE retirarlas o reasignarlas a personal habilitado para publicarlo.
  La pérdida de habilitación NO DEBE eliminar ni modificar el historial publicado.

- **FR-031**: Cada versión publicada DEBE fijar la lista de empleados de su programación,
  incluidos quienes no tienen jornadas asignadas. Los cambios posteriores en la lista de
  empleados habilitados de la sucursal NO DEBEN modificar las filas de esa versión en consultas
  ni exportaciones. Actualizar la lista DEBE requerir preparar y publicar una revisión y generar
  el siguiente número de versión, aun cuando no cambien las jornadas.

### Key Entities *(include if feature involves data)*

- **Organización y Sucursal**: Ámbitos compartidos que delimitan empleados, permisos y lugar
  de trabajo; la sucursal determina la referencia horaria de sus jornadas.
- **Empleado**: Persona del dominio común que recibe jornadas; su identidad es la misma
  aunque trabaje en distintas sucursales. Su habilitación para trabajar en una sucursal determina
  si puede recibir nuevas asignaciones allí; perderla no elimina sus registros publicados.
- **Rol, Área y Estación**: Contexto operativo compartido del trabajo; la estación está ubicada
  en una sucursal y área. El rol en una jornada describe trabajo y no equivale a permiso de planeador.
- **Turno**: Referencia compartida que permite proponer un horario; cada jornada conserva las
  fechas y horas concretas asignadas, sin depender de cambios posteriores en esa referencia.
- **Programación de periodo**: Agrupa las jornadas de una sucursal para un intervalo de fechas;
  identifica su estado de publicación, versión vigente y revisión pendiente, si existe.
- **Asignación de jornada**: Uso de Asignación del dominio común que vincula un empleado con
  sucursal, inicio, fin, rol o estación y turno opcional dentro de una programación.
- **Intervalo de descanso/comida**: Intervalo opcional de descanso dentro de una asignación de
  jornada, que puede usarse para comer o para otro tipo de pausa; identifica inicio y fin
  planificados y no constituye otra jornada.
- **Versión de programación y cambio**: Conserva el contenido publicado de un periodo,
  incluida su lista de empleados, y las diferencias de una revisión, incluidos retiros de
  jornadas y filas de empleados. Distingue versiones vigentes e históricas.
- **Estado, Evento y Auditoría**: Conceptos del dominio común para distinguir borrador,
  publicación e historial, y atribuir cada operación a su responsable y momento.
- **Exportación de programación**: Copia estática en PNG o PDF de versiones identificadas,
  con sucursal, periodo y fecha de generación; no sustituye la referencia vigente del sistema.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En el piloto de XOLO Jaltepec, al menos un planeador autorizado distinto del dueño
  completa y publica una semana del personal y realiza cinco ajustes de jornadas en un máximo
  de diez minutos para esos ajustes, sin ayuda presencial del dueño. La revisión confirma
  que el 100 % de las asignaciones publicadas coincide con las decisiones de planeación registradas.
- **SC-002**: Al menos el 90 % de los empleados participantes identifica su siguiente jornada,
  sucursal, horario, rol o estación y descanso/comida cuando exista en un máximo de un minuto,
  sin preguntar al dueño o planeador ni consultar horarios de compañeros.
- **SC-003**: En los escenarios de aceptación, se bloquea el 100 % de los traslapes y duplicados,
  incluidos los que cruzan sucursales, medianoche o periodos; se acepta el 100 % de los casos
  válidos de jornadas contiguas o separadas.
- **SC-004**: Ningún intento de consulta personal, historial u obtención de exportación colectiva
  por un empleado sin permiso revela programación ajena en las pruebas de permisos.
- **SC-005**: El 100 % de las revisiones de prueba conserva la versión anterior hasta publicar,
  deja una sola versión vigente por periodo e identifica todas las altas, modificaciones y
  retiradas. Al menos el 90 % de los empleados afectados identifica qué cambió en su horario
  en un minuto o menos al consultar una revisión del piloto.
- **SC-006**: El 100 % de los intervalos de descanso/comida de prueba válidos puede guardarse y consultarse;
  el 100 % de los intervalos fuera de jornada, de duración nula o superpuestos se rechaza.
  Toda jornada válida sin descanso/comida puede publicarse.
- **SC-007**: Para una semana de referencia de 20 empleados y hasta dos jornadas por empleado
  por día, el planeador obtiene cada formato de exportación en un máximo de 30 segundos.
  La comparación con las versiones identificadas confirma cero omisiones o diferencias y
  permite leer todos los datos del PNG y del PDF impreso.
- **SC-008**: Con esa misma carga de referencia, al menos el 95 % de las consultas de programación
  completa y personal realizadas durante la validación muestra el resultado en tres segundos
  o menos, medidos desde la selección del periodo.
- **SC-009**: El 100 % de los escenarios de modificación concurrente, validación fallida o fallo
  de exportación conserva el último estado válido y comunica la acción necesaria, sin sustituir
  silenciosamente jornadas ni presentar resultados parciales como completos.

- **SC-010**: En el 100 % de los escenarios de consulta personal sin conexión o con pérdida de
  conexión, se comunica que no puede verificarse la vigencia del horario y no se presentan
  datos anteriores como vigentes; al recuperar la conexión se puede consultar la versión vigente.

- **SC-011**: En el 100 % de los escenarios de pérdida de habilitación de un empleado con
  jornadas futuras publicadas, se conserva la publicación original y se alerta al planeador;
  se rechazan nuevas asignaciones y republicaciones sin resolver las jornadas afectadas.
  Al publicar su corrección válida, la incidencia deja de figurar como pendiente.

- **SC-012**: En el 100 % de los escenarios de cambio de la lista de empleados posterior a
  una publicación, las consultas y exportaciones de esa versión conservan la lista original.
  Una revisión publicada que solo actualiza la lista genera una nueva versión e identifica
  todas las filas añadidas o retiradas sin modificar el contenido de versiones anteriores.

## Assumptions

- **Publicación y vigencia**: Se adopta publicación manual y explícita, con una sola versión
  publicada vigente y un único borrador de trabajo por sucursal y periodo. Los cambios del
  borrador no se comunican como vigentes hasta publicar. La comparación destacada corresponde
  a la publicación anterior; el historial conserva diferencias previas, sin requerir un acuse
  de lectura del empleado.
- **Periodos**: La semana predeterminada va de lunes a domingo, pero se admiten periodos de
  otras longitudes con fechas inclusivas. Los periodos de una misma sucursal no se solapan;
  para corregir días ya incluidos se edita su programación. Una jornada pertenece al periodo
  de su inicio y las continuidades nocturnas se muestran como referencias.
- **Horarios**: Se utiliza la referencia horaria configurada para la sucursal. No se infieren
  fechas de término, duración de intervalos de descanso/comida, tiempos de traslado ni descansos a partir de nombres
  de turno o de espacios sin asignación. Al menos rol o estación es obligatorio; ambos son válidos.
- **Conflictos en borrador**: Las jornadas de otros borradores activos también se consideran
  asignaciones reservadas para detectar conflictos. El planeador puede retirar una asignación
  de esos borradores dentro de sus permisos para liberar el intervalo; un borrador ajeno se
  resuelve coordinándose con su planeador. Los cambios rechazados no se guardan parcialmente.
- **Descanso/comida**: Se admiten cero o más intervalos por jornada. Programar un descanso/comida no registra
  su disfrute real ni implica reglas sobre remuneración o cumplimiento laboral.
- **Lista de empleados publicada**: Cada versión conserva la lista incluida al publicarse,
  incluso sus filas sin jornadas. El borrador utiliza el personal habilitado actual y las
  asignaciones del periodo; incorporar esa lista a la vista publicada requiere una nueva
  publicación, aunque las jornadas permanezcan iguales.
- **Pérdida de habilitación**: Los cambios del catálogo de empleados no cancelan por sí solos
  jornadas futuras publicadas. Su corrección requiere intervención y publicación del planeador;
  el historial se conserva y la incidencia permanece pendiente hasta que se resuelve.
- **Conectividad**: La consulta del horario propio requiere conexión a internet. No se incluye
  consulta sin conexión de un horario guardado dentro del sistema. Las exportaciones PNG y PDF
  mantienen su función de copias estáticas para uso fuera del sistema.
- **Exportaciones**: Esta entrega exporta la versión publicada, no borradores ni versiones
  históricas. Los archivos son copias estáticas que el planeador comparte o imprime por su
  cuenta; los controles de consulta del sistema no pueden limitar el uso de una copia ya
  descargada y distribuida fuera de él.
- **Dependencias de dominio y permisos**: Se requiere disponer de organizaciones, sucursales,
  empleados identificados y habilitados para trabajar en ellas, roles, estaciones y turnos
  cuando se utilicen, además de reconocer quién consulta y su ámbito autorizado. No se presume
  que estos catálogos o permisos estén implementados: su disponibilidad debe resolverse en el
  plan. La administración general de esos catálogos no forma parte de esta especificación.
- **Alcance de la planeación**: La preparación sigue siendo una decisión humana que puede
  realizar cualquier planeador autorizado. Se elimina la dependencia personal del dueño para
  registrar, comunicar y consultar el horario, sin prometer generación automática. Copiar
  semanas, plantillas recurrentes, optimización automática, intercambios solicitados por
  empleados, aprobación en varios niveles y notificaciones externas quedan fuera de esta entrega.
- **Módulos posteriores**: Checador, asistencia real, nómina, cálculo de horas extra, validación
  de normativa laboral, cobertura mínima de personal y creación o ejecución de actividades
  por turno quedan fuera del alcance. Se preservan las referencias de dominio para usarlas
  posteriormente; esta especificación no exige implementar esos módulos ni conectores concretos.
- **Constitución**: Se aplica la [constitución de ROS-XOLO v1.0.0](../../.specify/memory/constitution.md).
  Esta función reduce la comunicación presencial, hace explícita la asignación y señala
  conflictos y publicaciones pendientes al planeador. Confirmar asistencia o ejecución correcta
  de actividades corresponde a funcionalidades posteriores; publicar una jornada no demuestra
  que el empleado haya asistido.
- **Validación inicial**: El primer piloto real se realiza en XOLO Jaltepec, con un planeador
  autorizado y empleados participantes cuya cantidad y resultados se registran. La semana de
  20 empleados es una carga de referencia para las mediciones, no una afirmación sobre la
  dotación actual ni un límite de capacidad. Los objetivos de tiempo son supuestos verificables
  de esta especificación y deben mantenerse identificados al planear la validación.
