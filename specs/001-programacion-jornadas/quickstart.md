# Quickstart de validación: Programación de jornadas

**Estado**: guía para la implementación posterior, 2026-09-14.
Actualmente solo existen los artefactos de diseño: los comandos de aplicación de esta guía
todavía deben implementarse. No ejecutar ni reportar como superadas pruebas de un producto
que aún no existe. Referencias: [plan](plan.md), [modelo](data-model.md),
[contrato HTTP](contracts/http.md), [interfaz/exportación](contracts/ui-export.md).

## Prerrequisitos y entorno

- Docker y Docker Compose disponibles; en Windows, Docker Desktop con contenedores Linux.
- Implementación de `compose.yaml`, Dockerfile, dependencias fijadas y comandos descritos abajo.
- Configuración local en `.env`, nunca con secretos reales versionados. El servicio `web`
  contiene Python/Django y Chromium, `db` PostgreSQL 17; `e2e` es un servicio de pruebas del
  mismo proyecto, no otro servicio de producto. Exponer web local en `http://localhost:8000`.
- Entorno demo aislado. No apuntar fixtures, pruebas ni fallos inducidos a la base del piloto real.

El compose debe ejecutar migraciones con credenciales de mantenimiento y el servidor con el
rol restringido del modelo. El wrapper de comandos usa credenciales de prueba únicamente para
crear/destruir bases de prueba; no amplía permisos del servidor. Servir estáticos empaquetados
mediante proxy o adaptador local configurado en la implementación.

Desde la raíz del repositorio, en PowerShell, después de implementar:

```powershell
Copy-Item -LiteralPath '.env.example' -Destination '.env'
docker compose build
docker compose up -d db
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py collectstatic --noinput
docker compose run --rm web python manage.py seed_demo --week-start 2026-09-21
docker compose up -d web
docker compose run --rm web python manage.py check
```

Antes de `build`, completar `.env` con valores locales y contraseña demo elegida por el operador.
`seed_demo` obtiene esa contraseña por entorno y no la imprime. Es idempotente: mismos IDs,
sin duplicar ni borrar datos modificados; rechaza organizaciones no marcadas demo. Reporta
IDs/usuarios/rutas de los escenarios, nunca secretos. Elegir una semana futura al ejecutar
después de las fechas del ejemplo; las pruebas automáticas fijan reloj para escenarios futuros.

El comando crea una organización demo, XOLO Jaltepec configurada, segunda sucursal de prueba
con otra zona horaria, roles/áreas/estaciones/turnos y 20 empleados de referencia. Perfiles:
planeador limitado a Jaltepec, planeador con ambas sucursales, empleado A, empleado B y una
persona que es empleado y planeador. Usuarios tienen identificadores demo documentados por
el comando, empleados sin jornadas y habilitaciones explícitas. Una segunda organización
de prueba permite verificar aislamiento de tenant. No son datos reales de dotación de XOLO.
El escenario `reference-week` queda publicado y listo para exportar/medir. Los Q automatizados
preparan fixtures independientes; el recorrido manual Q1 usa una semana libre distinta de la
referencia para evitar colisionar con ese periodo. Las pruebas no dependen de ejecutar Q1–Q10
en un orden que vaya acumulando modificaciones.

## Comprobación automatizada

Los directorios de pruebas y comandos son parte de los entregables definidos en plan.md:

```powershell
docker compose run --rm web python manage.py test tests.unit tests.contract tests.integration
docker compose run --rm e2e python -m unittest discover -s tests/e2e -p 'test_*.py'
docker compose run --rm web python manage.py validate_exports --scenario reference-week --output-dir /app/docs/validation/exports
docker compose run --rm web python manage.py benchmark_schedule --scenario reference-week --samples 100 --output /app/docs/validation/performance.json
```

Pruebas E2E usan la API Python de Playwright y unittest; `e2e` espera readiness de web, recibe
su URL interna y credenciales demo por entorno. El compose de desarrollo monta
`docs/validation` para conservar resultados fuera del contenedor. Los comandos terminan con
código distinto de cero si falla un criterio; no convierten falta de dependencias en prueba omitida.

`validate_exports` prueba los dos formatos, periodos largos, nombres largos y continuidades;
produce PNG/PDF, manifiestos, comparación de recuentos/IDs y PNG de cada página del PDF para
revisión. Incluir dependencias de inspección en el entorno de prueba (Pillow y pypdf; Poppler
para render de PDF), fijadas durante implementación. Abrir todas las imágenes y revisar al
100 %; imprimir el PDF o comprobarlo a tamaño de impresión. La comparación automática no
sustituye la revisión visual requerida por SC-007.

`benchmark_schedule` utiliza navegador autenticado y mide desde selección de periodo hasta
resultado visible y desde clic de exportación hasta archivo descargable. Registra tiempos
individuales, tasa <=3 s y p95 de cada tipo de consulta, duración de cada formato y entorno.
Usar 100 consultas completas y 100 personales; realizar al menos cinco exportaciones por
formato. Cada exportación de referencia debe terminar <=30 s. No medir solo tiempo del endpoint.

## Escenarios de aceptación ejecutables

Cada Q corresponde a pruebas/fixtures con el mismo nombre y a un recorrido manual en la UI.
Resultado esperado: 100 % de casos funcionales, permisos y fallos superados; registrar fallos
con versión, actor, pasos y evidencia antes de corregir y repetir.

| Caso | Pasos | Resultado esperado | Cobertura |
| --- | --- | --- | --- |
| Q1 Planeación/publicación | Entrar como planeador limitado; crear semana, guardar jornadas, cambiar una y retirar otra, recargar y publicar. Repetir con periodo vacío. Intentar fechas invertidas, periodo solapado y estación ajena. | Guarda exactamente lo válido, deja autor/fecha, publica v1 incluso vacío; rechazos no dejan cambios parciales. Vista incluye días/personas sin jornada y excepciones antes del detalle. | US1; FR-001 a FR-007, FR-013/015/021/027; SC-001/008/009. |
| Q2 Privacidad | Consultar como A, B y doble perfil; manipular IDs/URLs de colectivo, detalle, historial, exportación y otro tenant. Retirar/reasignar A→B y publicar; crear otra revisión y volver a consultar historial de A. | Personal siempre propio, sin borrador ni datos de reemplazo; retiros antiguos conservados; otra sucursal/tenant no entrega contenido ni metadatos restringidos. Distingue vacío publicado/no publicado. | US2/4; FR-001/016 a FR-019/026; SC-004/005. |
| Q3 Traslapes | Base A 09:00–17:00; probar 16:00–22:00, duplicado, 17:00–21:00 y otro turno durante una pausa. Repetir en otra sucursal/zona, borrador ajeno y jornada nocturna. Ejecutar dos guardados incompatibles con barrera de concurrencia. | Bloquea todo traslape positivo y acepta adyacencia; no descuenta comidas. En sucursal restringida solo bloqueo genérico. Solo una escritura incompatible confirma. | US3; FR-007 a FR-010/020; SC-003/009. |
| Q4 Pausas | Guardar/publicar cero pausas y varias válidas; intentar fuera de jornada, duración cero y superposición; acortar jornada dejando pausa fuera. | Cero pausas permitido; válidas visibles; inválidas rechazan jornada completa hasta corregir/retirar. | US5; FR-011/012; SC-006. |
| Q5 Revisiones/concurrencia | Modificar/añadir/retirar sobre v1; comprobar empleado antes y después de publicar. Abrir mismo borrador en dos sesiones y guardar/publicar con mismo ETag. Publicar de nuevo sin cambios; inducir excepción entre snapshot y puntero. | Antes sigue v1; luego una sola v2 con diferencias correctas. Segunda base vieja recibe 412; sin cambios conserva número; rollback conserva todos los datos, incluida auditoría de éxito. | US4; FR-006/008/013 a FR-017/020/021; SC-005/009. |
| Q6 Exportación/continuidad | Publicar domingo 22:00→lunes 06:00 con pausa; consultar/exportar semana de origen y destino. Generar PNG/PDF con 20 personas × 7 días × hasta 2 jornadas. Publicar una revisión durante render, cambiar un turno y revocar permisos en pruebas separadas. Inducir timeout/fallo/saturación/exceso de dimensiones. | Fechas y origen completos, sin duplicar edición ni mezclar sucursales; manifiesto coherente anterior al render, cero omisiones/recortes. Revisión pendiente no entra. Revocación deniega resultado/descarga; fallos no entregan archivos parciales. Copia vieja mantiene versión/aviso. | US6; FR-022 a FR-028; SC-004/007/009. |
| Q7 Inhabilitación | Deshabilitar A con jornada futura publicada mediante contrato core. Consultar como planeador/A, intentar nueva jornada y republicar sin resolver; corregir borrador, comprobar alerta y publicar retiro/reasignación. Correr carrera de publicación vs baja. | Publicación/historial no cambian con la baja; bloquea nueva jornada/republicación inválida. Alertas se mantienen mientras la publicada siga afectada y se resuelven con corrección publicada. Carrera queda en orden coherente con un evento de baja y sin pérdida de trazabilidad. | FR-005/021/030; SC-011/009. |
| Q8 Conectividad | Abrir horario A, pasar offline, fallar la API manteniendo navegador online, vencer sesión y restaurar red. Probar historial del navegador y volver del segundo plano. | Oculta datos previos al detectar fallo; mensaje de vigencia no verificable; sin caché offline. Fallo silencioso se detecta <=20 s en pestaña activa; reconexión solo muestra datos después de respuesta válida. | FR-018/029; SC-010. |
| Q9 Lista publicada | Publicar v1 con persona sin jornada; habilitar a otra y deshabilitar a una sin jornada. Consultar/exportar v1; refrescar borrador y publicar cambio solo de lista. Añadir después en origen una continuidad de persona fuera del roster destino. | v1 conserva filas/etiquetas; v2 identifica altas/retiros sin cambios inventados de jornada. Continuidad aparece separada con versión de origen, sin mutar roster destino. | FR-003/015/016/028/031; SC-012. |
| Q10 Traslado/periodos | Guardar retiro en origen y tratar de guardar alta incompatible en destino; publicar retiro y repetir alta/publicación. Crear periodos solapados simultáneamente. Consultar continuidad personal en destino aún no publicado; probar jornada que atraviesa varios periodos. | Destino bloqueado hasta retiro publicado; permisos en ambas sucursales. Solo un periodo solapado confirma. Continuidades propias visibles aunque destino no esté publicado, con origen y sin duplicados. | FR-002/005/008/019/028; SC-003/009. |

Carreras de Q3/Q5/Q7/Q10 deben usar conexiones PostgreSQL diferentes y sincronización explícita,
no solo dos llamadas secuenciales. Comprobar postestado de borrador, versiones, puntero,
auditoría e incidencias. La base nunca debe contener una publicación incompatible exitosa;
si publicación ocurre antes de la baja, queda válida en ese momento y la baja posterior abre
la incidencia requerida. Una jornada ya iniciada sin cambios no se invalida retroactivamente.

Probar además horas inexistentes/ambiguas en una zona IANA que tenga cambios estacionales,
offsets incompatibles, más de dos jornadas válidas en un día y periodos mayores de siete días.
La referencia de 20 personas no debe convertirse en límite accidental del dominio.

## Datos y operación del piloto real

Configurar un despliegue separado con HTTPS, `DEBUG=False`, hosts/cookies/CSRF correctos,
servidor WSGI y backup PostgreSQL. Ejecutar `check --deploy`, migraciones y ensayo de
restauración en base separada; registrar evidencia. Eliminar fixtures no es el mecanismo de
convertir una base demo en producción. Comando previsto de carga, desde la raíz:

```powershell
docker compose run --rm web python manage.py createsuperuser --username operador-inicial
docker compose run --rm web python manage.py bootstrap_core --input /run/config/pilot-core.json --actor operador-inicial --validate-only
docker compose run --rm web python manage.py bootstrap_core --input /run/config/pilot-core.json --actor operador-inicial
docker compose run --rm web python manage.py check --deploy
```

Montar el manifest local revisado en `/run/config` de solo lectura. Sigue [contracts/core.md](contracts/core.md);
no incluye contraseñas ni horarios inventados. Inicializar cuentas por administración controlada,
asignar un planeador distinto del dueño y empleados participantes; registrar cantidad real.
Cambios de habilitación se realizan por ese mismo comando auditado, no por SQL directo.

## Evidencia y criterios del piloto XOLO Jaltepec

Registrar en `docs/validation/pilot-jaltepec.md`: fecha, versión de aplicación, configuración,
hardware/red, número/perfiles de participantes, escenario, pasos, tiempo, resultado, evidencia,
incidencias, correcciones/repruebas y cualquier ayuda presencial necesaria. No versionar datos
personales sensibles ni credenciales; referenciar evidencia de acceso controlado.

| Criterio | Medición para aceptar |
| --- | --- |
| SC-001 | Un planeador distinto del dueño publica una semana y completa cinco ajustes en <=10 min, sin ayuda presencial; 100 % coincide con decisiones registradas. |
| SC-002 | >=90 % de participantes identifica próxima jornada/lugar/rol o estación/pausas en <=1 min, sin preguntar ni ver compañeros. Registrar numerador y denominador. |
| SC-003/004/006/009/010/011/012 | Todos los escenarios correspondientes Q2–Q10 superados, con evidencia de privacidad, intervalos, rollback, conexión, inhabilitación y lista congelada. |
| SC-005 | Todas las revisiones preservan invariantes; >=90 % de empleados afectados identifica su cambio en <=1 min. |
| SC-007 | Ambos formatos completos/legibles; cada exportación de referencia <=30 s y cero diferencias contra manifiesto. |
| SC-008 | >=95 % de cada conjunto de consultas completas/personales muestra resultado en <=3 s, desde seleccionar periodo. |

El responsable registra cada incumplimiento, lo corrige y repite la comprobación antes de
declarar el piloto superado. No se declara capacidad operativa validada para otras sucursales
con solo pruebas sintéticas. Esta guía define validación; no contiene implementación ni tests completos.
