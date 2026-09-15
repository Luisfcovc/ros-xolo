# ROS-XOLO Constitution

## Core Principles

En esta constitución, DEBE y NO DEBE expresan obligaciones verificables.

### I. Operación reproducible sin presencia del dueño

ROS-XOLO DEBE convertir la forma de operar del dueño en procedimientos, responsabilidades y
reglas explícitas que cualquier empleado asignado al trabajo pueda seguir. Cada flujo operativo
DEBE permitir completar su recorrido normal sin la presencia física del dueño o encargado y sin
depender de instrucciones verbales no registradas. Las situaciones que requieran su decisión
DEBEN aparecer como excepciones con contexto suficiente para resolverlas.

Toda funcionalidad propuesta DEBE explicar cómo contribuye a ejecutar, verificar o supervisar
esa operación reproducible. Sus criterios de aceptación DEBEN identificar la dependencia de
supervisión presencial que eliminan o el principio operativo que sostienen. El propósito es
convertir el conocimiento del dueño en un sistema que pueda repetirse entre personas y sucursales.

### II. Ejecución guiada y cumplimiento verificable

Para cada actividad asignada, el sistema DEBE indicar quién es responsable, qué hacer, cuándo
hacerlo, cómo hacerlo y con qué criterio se considera correcto el resultado. El empleado DEBE
poder consultar el procedimiento aplicable durante la ejecución en piso.

Cada actividad DEBE definir la confirmación o evidencia proporcional al trabajo y su regla de
validación. El sistema DEBE distinguir una ejecución reportada de un resultado validado cuando
la regla requiera una comprobación adicional; una marca de completado NO DEBE sustituir esa
comprobación. Una omisión, un bloqueo o un resultado incorrecto DEBE quedar registrado con su
estado y la incidencia correspondiente, conforme a las reglas definidas para el flujo.

Los cambios de estado y las validaciones DEBEN conservar trazabilidad del responsable, momento
y evidencia o motivo. Esto permite comprobar el resultado sin observar personalmente cada tarea.

### III. Supervisión por excepciones

La experiencia del dueño u operador responsable DEBE mostrar excepciones, riesgos y decisiones
pendientes con prioridad, sucursal, responsable, contexto y acción requerida. Las alertas DEBEN
tener una condición de activación y una condición de resolución explícitas, con trazabilidad hasta
la actividad o evento que las originó.

La supervisión cotidiana NO DEBE exigir revisar listas completas de checklists ni validar
manualmente cada ejecución normal. El detalle de actividades, evidencias y auditoría DEBE estar
disponible para investigar una excepción. Los criterios de aceptación de supervisión DEBEN
demostrar que el dueño puede identificar qué requiere su intervención sin recorrer esas listas.

### IV. Monolito modular con dominio compartido

La arquitectura inicial DEBE ser una plataforma central implementada como monolito modular,
extensible mediante módulos con responsabilidades y contratos explícitos. NO DEBE introducir
microservicios desde el inicio. Las dependencias entre módulos DEBEN estar documentadas y
respetar sus límites; cada plan DEBE justificar la incorporación de un módulo nuevo.

El core DEBE mantener el modelo de dominio común definido en esta constitución. Los módulos
DEBEN reutilizar sus identidades, significados y contratos, y NO DEBEN crear representaciones
incompatibles del mismo concepto. Las extensiones del dominio DEBEN declarar su relación con
el core y el impacto sobre los módulos existentes.

Esta estructura permite ampliar capacidades manteniendo una operación y un dominio coherentes.
Una futura separación en servicios DEBE contar con evidencia de una necesidad operativa o técnica,
una decisión arquitectónica documentada y un plan de migración compatible con estos principios.

### V. Integración antes que duplicación

Antes de construir capacidades cubiertas por un POS, ERP u otro sistema existente, el plan DEBE
evaluar si una integración satisface la necesidad. Cuando sea viable, DEBE preferirse integrar.
Odoo y Loyverse son ejemplos de sistemas a evaluar; su mención no selecciona un proveedor ni
obliga a implementar un conector concreto.

La decisión DEBE documentar cobertura funcional, acceso a los datos, restricciones, costo de
operación y motivos para integrar o construir. Una capacidad equivalente solo DEBE desarrollarse
internamente cuando se documente por qué la integración no cubre la necesidad.

Cada integración DEBE definir la fuente de verdad de los datos intercambiados, su correspondencia
con el dominio común y el manejo de fallos y discrepancias. Los contratos del proveedor DEBEN
quedar encapsulados en el módulo de integración. El foco del producto es la ejecución operativa
del restaurante, por lo que la duplicación de otros sistemas requiere esa justificación explícita.

## Contexto del producto y modelo de dominio

ROS-XOLO es el nombre de trabajo de una plataforma de ejecución operativa para restaurantes.
El problema central es la dependencia de la presencia física del dueño o encargado. El objetivo
es convertir su forma de operar en un sistema reproducible que cualquier empleado pueda seguir.

El usuario principal es el dueño u operador responsable de una o varias sucursales. El usuario
secundario es el empleado que ejecuta tareas en piso. Cada especificación DEBE identificar el
usuario y contexto de operación afectados, y distinguir las necesidades de ejecución de las
necesidades de supervisión cuando intervengan ambos perfiles.

El modelo de dominio común del core comprende: **Organización, Sucursal, Empleado, Rol, Área,
Estación, Turno, Actividad, Procedimiento, Asignación, Evidencia, Incidencia, Estado, Alerta,
Evento y Auditoría**. Este vocabulario DEBE usarse de forma consistente en especificaciones,
contratos y módulos. Los datos operativos DEBEN identificar su organización y, cuando corresponda,
su sucursal; las responsabilidades y permisos DEBEN delimitarse por rol y ámbito de operación.
Las relaciones y reglas concretas DEBEN definirse en los diseños de las funcionalidades que
utilicen estos conceptos, sin exigir implementar todos los módulos en la primera entrega.

**XOLO Jaltepec** DEBE ser el primer entorno de prueba real. Sus procedimientos y situaciones de
piso DEBEN servir para validar las primeras capacidades. Los datos y reglas propios de esa
sucursal DEBEN representarse como configuración o datos del dominio, sin acoplar el core a una
única sucursal.

## Flujo de desarrollo y validación

Cada cambio funcional DEBE tener una especificación con problema operativo, usuario, escenario
y criterios de aceptación verificables antes de implementarse. El plan DEBE documentar los
módulos y conceptos de dominio afectados, las integraciones consideradas y la comprobación de
cumplimiento de esta constitución. Las tareas DEBEN vincularse con esos criterios.

La revisión de especificaciones, planes e implementaciones DEBE comprobar, según aplique:

1. Que el recorrido normal pueda ejecutarse sin presencia física del dueño o encargado.
2. Que la asignación identifique responsable, trabajo, momento, procedimiento y validación.
3. Que las omisiones, bloqueos y resultados incorrectos generen estados e incidencias trazables,
   y que el dueño reciba las excepciones, riesgos y decisiones que requieran su atención.
4. Que los módulos respeten el dominio compartido y los límites del monolito modular.
5. Que las capacidades que se solapen con sistemas existentes tengan una decisión de integración
   o construcción justificada.

Cada criterio aplicable DEBE acompañarse de evidencia de validación; la no aplicabilidad DEBE
justificarse. Las verificaciones DEBEN cubrir el recorrido normal y las excepciones del flujo
modificado. Los cambios en contratos compartidos o integraciones DEBEN comprobar compatibilidad
y comportamiento ante fallos en los límites afectados.

Antes de declarar una capacidad operativa validada para su extensión a otras sucursales, DEBE
probarse en XOLO Jaltepec con los perfiles afectados. La validación DEBE registrar el escenario,
resultado, evidencia y dependencias de intervención presencial detectadas. Los criterios de
aceptación DEBEN fijarse antes de la prueba; los incumplimientos DEBEN resolverse y verificarse
antes de declarar superada la validación.

## Governance

Esta constitución es la referencia normativa para las especificaciones, planes, tareas y
revisiones de ROS-XOLO. Una decisión técnica o de producto NO DEBE contradecir sus obligaciones.
Toda revisión de cambios DEBE indicar los principios aplicables, la evidencia de cumplimiento
y las desviaciones encontradas. Una desviación DEBE corregirse o tramitarse como enmienda antes
de aceptar el cambio; una justificación en el plan no modifica por sí sola la constitución.

Toda enmienda DEBE incluir motivo, texto propuesto, principios afectados, impacto sobre el
trabajo existente y acciones de transición cuando correspondan. El responsable del producto
DEBE aprobarla y la revisión técnica DEBE evaluar su impacto cuando afecte arquitectura,
contratos o datos. La enmienda DEBE quedar registrada en el historial de versiones del archivo.

El versionado DEBE seguir MAJOR.MINOR.PATCH: MAJOR para eliminar o redefinir principios o reglas
de forma incompatible; MINOR para añadir principios o secciones, o ampliar materialmente sus
obligaciones sin incompatibilidad; PATCH para aclaraciones o correcciones sin cambio normativo.
Cada enmienda DEBE actualizar la versión y la fecha de última modificación, preservando la fecha
de ratificación original. Las fechas DEBEN usar el formato ISO YYYY-MM-DD.

La versión 1.0.0 constituye la adopción inicial de estos principios el 2026-09-14. Las plantillas
y comandos dependientes consultan esta constitución durante su ejecución; su revisión no exige
modificar esas plantillas como parte de una enmienda constitucional.

**Version**: 1.0.0 | **Ratified**: 2026-09-14 | **Last Amended**: 2026-09-14
