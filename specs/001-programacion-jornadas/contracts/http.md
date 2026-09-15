# Contrato HTTP de la interfaz de Programación

**Versión**: 1 | **Estado**: diseño; rutas por implementar.
**Base**: `/api/v1`. JSON UTF-8, fechas ISO `YYYY-MM-DD`, datetimes RFC 3339 con offset
explícito, IDs UUID. [Modelo](../data-model.md) y [servicios](core.md) son normativos.

## Autenticación, concurrencia y errores

Sesión Django del mismo origen, cookies HttpOnly/SameSite y Secure bajo HTTPS. CSRF en todos
los POST/PUT y cierre de sesión. El servidor deriva organización activa de sesión y comprueba
pertenencia; no acepta que `organization_id` en un payload cambie el tenant. Permiso por
sucursal para todas las rutas de planeación, versiones y exportaciones. Respuestas privadas
con `Cache-Control: private, no-store`; no endpoints de archivos públicos.

GET de borrador devuelve `ETag` opaco, representando revisión del periodo, publicación vigente
y revisión de core. PUT de borrador y POST de publicación requieren `If-Match` con ese valor.
Sin precondición: 428. Base distinta: 412 `stale_base`, con instrucción de refrescar; solo un
usuario autorizado recibe el ETag actual. Un reintento tras error de red primero obtiene el
estado y lo revisa: no se sustituye automáticamente `If-Match`. Un cambio semántico incrementa
revisión; un PUT idéntico conserva la revisión y devuelve `saved=false`.

Sobre de error:

```json
{
  "error": {
    "code": "overlap",
    "message": "La jornada coincide con otra asignación.",
    "action": "Corrige el horario o coordina con un planeador autorizado.",
    "fields": [{"path": "assignments[0].starts_at", "code": "overlap"}],
    "correlation_id": "a0000000-0000-4000-8000-000000000001"
  }
}
```

| HTTP | Códigos / conducta |
| --- | --- |
| 400 | `invalid_request`: JSON, campos desconocidos o fechas mal formadas. |
| 401 | `authentication_required`: sesión ausente/vencida; API nunca devuelve HTML de login como éxito. |
| 403 | `permission_denied` para una acción no permitida o CSRF inválido; no incluir datos de programación. |
| 404 | `not_found` para objeto inexistente o fuera del ámbito visible, incluyendo otras organizaciones/sucursales. |
| 409 | `overlap`, `period_overlap`, `not_published`, `employee_ineligible_future`; describir corrección sin detalles restringidos. |
| 412 / 428 | `stale_base` / `precondition_required`; no cambios. |
| 422 | `invalid_interval`, `invalid_break`, `invalid_reference`, `ambiguous_local_time`, `nonexistent_local_time`, `export_too_large`. |
| 410 | `export_expired`, solo después de autorizar el ámbito. |
| 503 | `write_busy`, `export_busy`, `export_failed`, `export_timeout`; reintentable cuando corresponda, sin archivo parcial. |

Errores de conflictos pueden añadir `conflicts[]` únicamente con jornadas que el actor tenga
permiso de consultar. Un conflicto restringido no incluye IDs, sucursal, horas ni datos ajenos;
ni siquiera en campos ocultos, HTML, cabeceras o logs entregados al cliente.

## Rutas

| Método y ruta | Entrada | Éxito |
| --- | --- | --- |
| GET `/planning/branches` | Sin entrada | 200: sucursales con permiso y su zona. |
| GET `/planning/branches/{branch_id}/catalogs` | Sin entrada | 200: empleados habilitados y referencias aplicables, `core_revision`. |
| POST `/planning/periods` | `branch_id`, `date_from`, `date_to` | 201: periodo/borrador, `Location` y ETag. Periodo repetido/solapado: 409 con referencia existente solo si autorizada. |
| GET `/planning/periods?branch_id=...&from=...&to=...` | Fechas inclusivas | 200: periodos que intersectan, estado y versión; lista vacía explícita. |
| GET `/planning/periods/{period_id}/draft` | Sin entrada | 200: borrador efectivo, lista, ETag, pendientes y continuidades de lectura. |
| PUT `/planning/periods/{period_id}/draft` | `If-Match`, `assignments[]` completo | 200: candidato guardado, ETag, `saved` y `has_pending_changes`. Toda retirada es explícita por ausencia de ID en reemplazo completo. |
| POST `/planning/periods/{period_id}/resolve-shift` | `shift_id`, `start_date`, offsets opcionales | 200: fechas/horas propuestas para confirmar, sin persistencia. |
| POST `/planning/periods/{period_id}/publish` | `If-Match`, cuerpo `{}` | 201: nueva publicación/diff, ETag; 200 `outcome=no_changes` si idéntico. Nunca publica payload de jornadas no guardado. |
| GET `/planning/periods/{period_id}/published` | Sin entrada | 200: snapshot local vigente + continuidades y manifiesto, o 409 `not_published`. |
| GET `/planning/periods/{period_id}/versions` | `cursor?`, `limit?` | 200: historial paginado con versión, fecha/autor y enlace al detalle. |
| GET `/planning/periods/{period_id}/versions/{version}` | Versión entera >=1 | 200: contenido histórico local inmutable y diferencias contra versión anterior; `is_current`. |
| GET `/planning/alerts?branch_id=...` | Sucursal autorizada | 200: alertas activas con condiciones/acciones definidas en core.md. |
| GET `/me/schedule?from=...&to=...` | Fechas inclusivas, sin employee_id | 200: únicamente horario propio publicado, estados y manifiesto personal. |
| GET `/me/history?from=...&to=...` | Fechas, `cursor?`, `limit?` | 200: cambios propios y versiones de periodos intersectados, incluso si retirado del vigente. |
| GET `/me/periods/{period_id}/versions/{version}` | IDs/versión | 200: proyección propia de esa versión; 404 si no existe relación propia con el periodo. |
| POST `/planning/periods/{period_id}/exports` | `format` igual a `png` o `pdf` | 201 solo al terminar: ID, manifiesto, hash, tamaño, vencimiento y URL privada de descarga. |
| GET `/planning/exports/{export_id}` | Sin entrada | 200: estado/metadatos; requiere permiso actual. No entrega contenido de una generación fallida. |
| GET `/planning/exports/{export_id}/file` | Sin entrada | 200: bytes completos, `image/png` o `application/pdf`, `Content-Disposition: attachment`; requiere permiso actual. |

Historial: orden descendente por publicación/versión e ID estable, `limit` predeterminado 50,
máximo 200 y `next_cursor=null` al acabar. La interfaz permite recorrer todas las páginas;
ni diferencias ni retiros antiguos desaparecen al publicar de nuevo. Las consultas completas
de un periodo y el exportador no reutilizan una página truncada de historial.

## Payload de borrador

Ejemplo ilustrativo de una jornada de turno nocturno con fecha de término explícita:

```json
{
  "assignments": [{
    "assignment_id": "a0000000-0000-4000-8000-000000000010",
    "employee_id": "a0000000-0000-4000-8000-000000000020",
    "starts_at": "2026-09-27T22:00:00-06:00",
    "ends_at": "2026-09-28T06:00:00-06:00",
    "role_id": "a0000000-0000-4000-8000-000000000030",
    "station_id": null,
    "shift_id": null,
    "breaks": [{
      "break_id": "a0000000-0000-4000-8000-000000000040",
      "starts_at": "2026-09-28T01:00:00-06:00",
      "ends_at": "2026-09-28T01:30:00-06:00"
    }]
  }]
}
```

Cliente genera UUID para una asignación/pausa nueva; el servidor rechaza un ID ya perteneciente
a otro periodo/organización. Al modificar se conserva el ID. La organización, sucursal y zona
se derivan del periodo; el cliente no puede moverlas en ese PUT. `breaks` es obligatorio y puede
ser `[]`; `assignments=[]` representa retirar todas las jornadas. `role_id`, `station_id` y
`shift_id` pueden ser null, pero al menos rol o estación debe existir. Referencias incompatibles,
campos desconocidos o datos de continuidad como jornada local se rechazan.

El servidor verifica offsets contra la zona del periodo y deriva fecha local; una fecha local
de inicio fuera del periodo es inválida. Elegir Turno se resuelve antes de guardar; el resultado
se confirma como fechas completas. `shift_id` conserva procedencia y no obliga a recalcular
horarios existentes al editar el catálogo. Las pausas llegan completas junto con la jornada.

Respuesta de borrador: `period`, `base_publication`, `edit_revision`, `core_revision`,
`assignments`, `roster`, `continuities`, `has_pending_changes`, `alerts`. Cada jornada de
salida incluye IDs, etiquetas, fechas/horas locales/UTC, zona y pausas. Continuidades tienen
`read_only=true` y referencias de origen; nunca se incluyen en `assignments` del PUT.

## Respuesta publicada y personal

Respuesta colectiva: `period`, `publication`, `roster`, `assignments`, `continuities`,
`manifest`, `pending_draft_excluded`. `publication` incluye ID/versión/autor/fecha y
`is_current_at_verification=true`; `manifest` incluye `verified_at`, versión local y todas
las versiones de origen utilizadas. Un periodo publicado vacío responde 200 con lista de
filas congelada y jornadas vacías, sin inventar ausencias.

Respuesta personal: `range`, `verified_at`, `manifest_hash`, `periods[]`, `assignments[]`,
`continuities[]`, `changes[]`. Cada elemento de `periods` incluye solo sucursal/periodo,
versión propia relevante y `publication_state=not_published|published`,
`assignment_state=assigned|none`, `included_in_roster`. `none` es local a esa versión:
si hay continuidades se muestran igualmente. La persona nueva que aún no figura en una lista
publicada ve esa condición sin que se añadan filas al snapshot.

Periodos relevantes personales: sucursales habilitadas actuales más periodos con una fila,
jornada o cambio propio histórico en el intervalo. Un periodo nunca publicado no entrega
contenido de borrador, lista de compañeros, conteos, `has_pending_changes`, auditoría de
borrador ni el hash colectivo. El manifiesto/hash personal se calcula después del filtro
personal; puede identificar la versión de origen sin exponer su contenido ajeno.

`changes` del horario presenta diferencias de la publicación vigente contra la anterior;
`/me/history` conserva todas. `before/after` se filtran según core.md antes de serializar;
no incluir el empleado de reemplazo en un retiro. Un planeador que usa `/me` tiene exactamente
la misma restricción. La UI nunca usa rutas colectivas para construir la consulta personal.

## Publicación y exportación

Publicar responde `outcome=published`, `publication_id`, `version`, `published_at`,
`previous_version`, `changes` y ETag nuevo. Un borrador inicial vacío publica v1. Si ya hay
publicación y la comparación es idéntica: `outcome=no_changes`, misma versión y ningún aviso
de cambio nuevo. Los cambios solo de lista sí producen publicación y diferencias de filas.

Exportar acepta únicamente `format`; no acepta versión histórica ni un snapshot del cliente.
La captura de versiones se realiza al iniciar la transacción consistente de esa solicitud.
Si cambia el horario durante render, el archivo conserva íntegramente el manifiesto fijado.
Respuesta incluye `export_id`, `format`, `manifest`, `generated_at`, `expires_at`, `sha256`,
`byte_size`, `download_url`, `pending_draft_excluded`. La descarga también autoriza la sucursal
actualmente; un URL conocido no concede acceso. Retiro de permiso durante generación impide
entregar metadatos/archivo al finalizar aunque el snapshot ya se haya renderizado internamente.

## Contratos HTML de entrada

`/accounts/login/` y `/accounts/logout/` usan sesión/CSRF; cierre por POST. Páginas:
`/planning/` (sucursales, periodos y excepciones), `/planning/periods/{id}/` (editor/vigente),
`/planning/periods/{id}/history/` y `/me/schedule/` (horario e historial personal).
Estas páginas y la API aplican el mismo control de ámbito. HTML renderizado y JSON no pueden
contener datos que el perfil no deba recibir. Detalles de interacción en [ui-export.md](ui-export.md).
