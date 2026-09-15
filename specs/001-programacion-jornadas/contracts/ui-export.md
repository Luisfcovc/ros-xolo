# Contrato de experiencia, consulta y exportación

**Estado**: diseño | **Referencias**: [HTTP](http.md), [core](core.md), [modelo](../data-model.md).

## Planeación

La entrada presenta sucursal y periodo seleccionado, versión vigente y estado de publicación.
La selección inicial propone lunes a domingo. La lista de excepciones aparece antes del detalle
de jornadas, con prioridad/contexto/acción; no exige recorrer toda la programación para detectar
una revisión pendiente, base desactualizada o empleado inhabilitado.

La vista de borrador muestra habilitados actuales y personas con asignaciones propias, incluidos
días sin jornada. Distingue contenido guardado de cambios locales no guardados y de publicación
vigente. La vista publicada usa filas congeladas, incluso si cambia el personal actual.
Nunca traducir día sin jornada a falta, vacaciones o descanso disfrutado.

El editor permite más de una jornada por día. Requiere empleado, fechas completas, inicio/fin
y al menos rol o estación. Turno propone fechas completas que deben confirmarse. No inferir
que 06:00 es mañana si la fecha de fin recibida es hoy; el usuario debe indicar el día de fin.
Las pausas son opcionales y se editan en el mismo formulario/guardado de su jornada.

Al guardar, errores aparecen junto a campos y con acción; se preservan la entrada local y el
último contenido válido del servidor, claramente separados. Un 412 exige refrescar y revisar
antes de volver a guardar; no se reintenta con un token nuevo en segundo plano. La publicación
es un botón explícito sobre contenido guardado; muestra resumen de diferencias y versión base.
El botón no envía cambios locales sin guardar como si ya hubieran sido revisados.

Una publicación inicial vacía está permitida. Un intento sin diferencias informa “No hay
cambios para publicar” y conserva versión. Modificar solo filas de empleados también cuenta
como revisión y muestra altas/retiros. Guardar una revisión conserva para el empleado la
versión vigente previa hasta publicar.

## Continuidades e historial

Jornadas nocturnas siempre muestran inicio y fin con fecha, referencia horaria y origen.
En el destino se presentan en “Continuidades de otros periodos”, de solo lectura, con enlace
a la edición del origen únicamente si el usuario tiene permiso. Se usa esa sección aun si la
persona no pertenece al roster congelado local; la lista del destino no se recalcula.

Cabecera: versión del periodo local. Cada continuidad: periodo/versión de origen. El manifiesto
identifica el conjunto utilizado; una revisión en origen actualiza su continuidad al volver
a consultar sin atribuirla a una publicación nueva del destino. Consultas de históricos locales
se rotulan “Versión histórica” y no presentan referencias actuales como contenido histórico.

Historial del planeador muestra valores antes/después, autor y fecha. Historial personal muestra
solo cambios propios; reasignación como retiro para quien sale y alta para quien entra, sin
datos del otro. Retiros permanecen consultables aun después de otras revisiones. Las listas
paginadas permiten llegar a todos los cambios y no solo a los más recientes.

## Horario personal verificado

Diseño móvil con próxima jornada, sucursal, fechas/horas, rol/estación, pausas y versión.
Si no hay publicación local, mostrar “Sin programación publicada para este periodo”; si
existe y no hay jornada propia, “Sin jornadas asignadas en esta versión”. Las continuidades
propias publicadas se muestran en ambos casos; el estado local vacío no debe ocultarlas.

Cada consulta visible identifica la última verificación con el servidor. Sin conexión o al
fallar una petición, ocultar horario/cambios anteriores y mostrar “No se puede verificar la
programación vigente. Reintenta cuando tengas conexión”. Reconectar inicia consulta nueva;
no vuelve a mostrar el contenido anterior solo porque el navegador emita `online`.

Estados de interfaz: `loading`, `verified`, `unverified`, `authentication_required`. Al seleccionar
fechas o volver al primer plano se pasa a loading hasta verificar. `offline`, timeout/error
de red o error servidor invalidan verified; 401 exige sesión. El cambio confirmado de periodo
invalida respuestas de solicitudes anteriores. La comprobación autenticada ocurre cada 15 s
con timeout de 5 s mientras la pestaña está activa; evento offline invalida de inmediato y
fallo silencioso se detecta dentro de 20 s en esa condición. La hora de última comprobación
permanece explícita: no se promete una detección instantánea que el navegador no garantiza.

No guardar horario en service worker, localStorage, IndexedDB ni caché HTTP. En `pageshow`
y regreso desde segundo plano se oculta hasta revalidar para evitar restaurar contenido viejo.
Con JavaScript deshabilitado se informa que debe habilitarse para esta consulta verificada.
Las copias PNG/PDF descargadas son otra experiencia: archivos estáticos identificados.

## Exportación completa

Solo planeadores con permiso pueden generar u obtener archivos. No hay exportación colectiva
en la consulta personal ni envío automático a terceros. Formatos seleccionables PNG/PDF;
si no existe publicación, explicar que debe publicarse. Si hay revisión pendiente, advertir
“Se exportará la versión publicada; los cambios pendientes no están incluidos”.

La solicitud identifica al inicio una publicación local y todas las publicaciones que aportan
continuidades en una lectura consistente. Renderer recibe únicamente ese payload congelado.
No vuelve a consultar habilitaciones, nombres de catálogos ni “última versión”. El alcance
colectivo pertenece a una única sucursal; una coincidencia de empleado no arrastra otras sucursales.

Ambos formatos contienen:

- Sucursal, fechas inclusivas del periodo, zona horaria, versión local, fecha/responsable de
  publicación, momento de generación y manifiesto legible de versiones de origen.
- Todas las filas publicadas y todos los días; jornadas completas con rol/estación, pausas
  programadas y fin con fecha. Sin jornadas: texto explícito sin interpretación de asistencia.
- Sección completa de continuidades con fechas reales y referencia de origen; nunca otra
  asignación ni filas silenciosamente añadidas al roster congelado.
- Aviso: “Copia estática. Consulta la versión vigente en ROS-XOLO”. Cada página PDF repite el
  contexto necesario, incluido número de página y referencia a las versiones utilizadas.

### PNG

Un solo PNG de todo el contenido, no una captura del área visible/scroll. Bloques de hasta
siete días apilados para periodos largos, con ancho estable y altura variable. Texto mínimo
propuesto 16 px CSS a escala de captura 1, revisado al 100 % de resolución; nombres largos y
varias jornadas/pausas amplían celdas, no se ocultan con puntos suspensivos.

Preflight inicial: <=60 millones de píxeles y <=30 000 px en cualquier dimensión. Excederlo
produce `export_too_large` sin archivo y sugiere solicitar PDF completo; no cambia el formato
elegido automáticamente. Estos límites protegen recursos del renderizador, no limitan la
cantidad de empleados o duración de periodo en el dominio. La referencia SC-007 debe caber.

### PDF

A4 horizontal con texto >=10 pt, saltos de página explícitos, cabeceras y contexto repetidos.
Dividir periodos largos en bloques de días y filas en páginas; una fila demasiado alta se
divide en bloques de continuación identificados, conservando todos sus datos. No depender de
`overflow:hidden`, escalado ilimitado o `break-inside:avoid` para una fila mayor que la página.

### Integridad y fallos

Antes de renderizar, comparar IDs/recuentos de filas, jornadas, pausas, días y continuidades
del payload contra el DOM preparado. Esperar fuentes/layout locales. Tras generar, verificar
tipo real, bytes no vacíos, dimensiones PNG y estructura/páginas del PDF. Pruebas automáticas
comparan texto PDF y una inspección visual comprueba la legibilidad de todos los bloques.

Límites iniciales: dos renderizaciones simultáneas por instancia, 25 s de render y retención
de archivo terminado 24 h. Saturación devuelve `export_busy`; timeout/fallo no ofrece éxito
ni archivo parcial. Registrar error/manifest/duración y limpiar temporales. Publicación durante
render puede completar, pero su contenido no entra en el archivo ya iniciado. Revocación de
permiso impide obtener el resultado y cualquier descarga posterior, aunque se conozca la URL.

Una copia descargada conserva sus versiones y aviso después de republicar; el sistema no
promete actualizar ni revocar bytes que ya se distribuyeron fuera de él.
