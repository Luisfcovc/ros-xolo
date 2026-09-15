# Despliegue HTTPS del piloto

Este procedimiento describe el despliegue de ROS-XOLO para XOLO Jaltepec. El piloto debe ejecutarse en Linux con HTTPS terminado en un proxy inverso y una base PostgreSQL privada. `compose.yaml` sirve para desarrollo y pruebas; su servicio `web` usa `runserver` y no debe exponerse como servidor de producción.

## Configuración segura

Crear `.env` a partir de `.env.example` y proporcionar valores generados fuera del repositorio:

```dotenv
DJANGO_SECRET_KEY=<secreto-largo-y-aleatorio>
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=horarios.example.org
ROS_XOLO_TIME_ZONE=America/Mexico_City
SESSION_COOKIE_SECURE=1
CSRF_COOKIE_SECURE=1
SECURE_SSL_REDIRECT=1
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=1
SECURE_HSTS_PRELOAD=0
POSTGRES_DB=ros_xolo
POSTGRES_USER=ros_xolo
POSTGRES_PASSWORD=<secreto-largo-y-aleatorio>
POSTGRES_HOST=db
EXPORT_STORAGE_ROOT=/app/private_exports
```

El proxy debe reenviar `Host` y `X-Forwarded-Proto: https`, redirigir HTTP a HTTPS y publicar únicamente TLS moderno. La configuración usa ese header mediante `SECURE_PROXY_SSL_HEADER`. El volumen PostgreSQL y `private_exports` deben ser privados; nunca servir exportaciones desde rutas estáticas.

## Construcción, migraciones y WSGI

Desde la raíz del checkout aprobado:

```bash
docker compose build --pull web
docker compose run --rm web python manage.py check --deploy
docker compose run --rm web python manage.py migrate --noinput
docker compose run --rm web python manage.py collectstatic --noinput
```

Resolver todas las advertencias de `check --deploy` sobre `DEBUG`, hosts, cookies, HTTPS, HSTS, secret key y estáticos antes de continuar.

El proceso de producción debe usar Gunicorn, no `runserver`:

```bash
docker compose up -d db
docker compose run --rm web python manage.py migrate --noinput
docker run -d --name ros-xolo-web --env-file .env <imagen-aprobada> \
  gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 60
```

Conectar el contenedor a la red privada del proxy y publicar solo 443. Servir `STATIC_ROOT` desde el proxy o un volumen de solo lectura; registrar los workers y timeout usados.

## Cuenta restringida y carga inicial

Montar el manifest revisado como `/run/config/pilot-core.json` de solo lectura. Crear la cuenta inicial y cargar catálogos mediante el comando auditado:

```bash
docker compose run --rm web python manage.py createsuperuser --username operador-inicial
docker compose run --rm web python manage.py bootstrap_core --input /run/config/pilot-core.json --actor operador-inicial --validate-only
docker compose run --rm web python manage.py bootstrap_core --input /run/config/pilot-core.json --actor operador-inicial
```

El planeador debe ser distinto del dueño y recibir solo las sucursales necesarias. No usar cuentas compartidas ni modificar habilitaciones mediante SQL directo. No versionar datos personales ni contraseñas.

## Backup y ensayo de restauración

Hacer un dump lógico cifrado antes de cada versión y diariamente durante el piloto, en un destino privado fuera de evidencia y rutas web:

```bash
docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --file=/backup/ros-xolo-$(date +%Y%m%d-%H%M%S).dump
```

Restaurar siempre en una instancia separada y desechable, nunca sobre la base del piloto:

```bash
createdb -U ros_xolo ros_xolo_restore_test
pg_restore -U ros_xolo --clean --if-exists --dbname=ros_xolo_restore_test /backup/<dump>.dump
DJANGO_DEBUG=0 POSTGRES_HOST=<restore-host> python manage.py check --deploy
DJANGO_DEBUG=0 POSTGRES_HOST=<restore-host> python manage.py migrate --check
```

Comprobar catálogos, publicaciones, auditoría e incidencias, además de una consulta colectiva y una personal. Registrar fecha, versión, dump, duración, resultado y evidencia en el registro operativo privado.

## Salida, supervisión y rollback

Antes de abrir el piloto comprobar HTTPS y redirección, cookies `Secure`, CSRF, `Cache-Control: private, no-store`, healthcheck de PostgreSQL, logs sin secretos, `check --deploy`, migraciones y acceso restringido. Mantener la imagen anterior y el backup hasta finalizar la verificación.

Ante un fallo, retirar tráfico en el proxy, conservar logs/auditoría, volver a la imagen anterior y restaurar solo bajo decisión del responsable. No borrar el volumen original; repetir `check --deploy` y las consultas de privacidad antes de reanudar tráfico.
