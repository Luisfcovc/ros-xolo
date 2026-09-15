# Validación automatizada

Fecha: 2026-09-15 (entorno local Docker).

| Grupo | Comando | Resultado |
| --- | --- | --- |
| Unit, contract e integration | `docker compose run --rm web pytest --reuse-db tests/unit tests/contract tests/integration -q` | Superado (código 0). |
| Renderizado real PNG/PDF | `docker compose run --rm web pytest --reuse-db tests/integration/programacion/test_export_generation.py::test_real_renderer_produces_valid_private_png_and_pdf -q` | 2 superadas en 16.36 s. |
| Unidad de payload de exportación | `docker compose run --rm web pytest --reuse-db tests/unit/programacion/test_exports.py -q` | 5 superadas en 19.58 s. |
| E2E | `docker run --rm --network ros-xolo_default -v <raíz>:/app -w /app ros-xolo-e2e:latest pytest tests/e2e -q` | 6 superadas en 14.99 s. Se usó la imagen local para no depender de Docker Hub. |

Antes de ejecutar las pruebas se aplicaron migraciones y se comprobó el conjunto de demostración:

```powershell
docker compose run --rm web python manage.py migrate --noinput
docker compose run --rm -e ROS_XOLO_DEMO_PASSWORD=<valor-local> web python manage.py seed_demo --week-start 2026-09-21
```

`seed_demo` se ejecutó dos veces con la misma semana y conservó el mismo periodo de referencia,
confirmando su idempotencia. La contraseña no se imprimió ni se registró.
