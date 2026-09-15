# Despliegue de ROS-XOLO en XOLO-Core

ROS-XOLO usa Cloudflare Access y Tunnel, Traefik y la red Docker externa `xolo_edge`.
No abre puertos de Django o PostgreSQL en el host ni crea un segundo `cloudflared`.

## Preparar la aplicación

```bash
mkdir -p /home/francisco/docker/apps
cd /home/francisco/docker/apps
git clone git@github.com:Luisfcovc/ros-xolo.git
cd ros-xolo
sudo install -d -m 0750 /srv/apps/ros-xolo/postgres
sudo install -d -m 0750 /srv/apps/ros-xolo/private_exports
sudo install -d -m 0750 /srv/apps/ros-xolo/staticfiles
sudo install -d -m 0750 /srv/apps/ros-xolo/config
sudo install -d -m 0750 /srv/backups/apps/ros-xolo
docker network inspect xolo_edge >/dev/null
```

## Configurar secretos

```bash
cp .env.example .env
chmod 600 .env
openssl rand -hex 32
nano .env
```

Configurar secretos reales y privados:

```dotenv
DJANGO_SECRET_KEY=<salida-de-openssl>
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=planeacion.xolodev.com,localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=https://planeacion.xolodev.com
ROS_XOLO_HOSTNAME=planeacion.xolodev.com
POSTGRES_DB=ros_xolo
POSTGRES_USER=ros_xolo
POSTGRES_PASSWORD=<secreto-distinto-y-largo>
POSTGRES_HOST=db
POSTGRES_PORT=5432
ROS_XOLO_TIME_ZONE=America/Mexico_City
EXPORT_STORAGE_ROOT=/app/private_exports
SESSION_COOKIE_SECURE=1
CSRF_COOKIE_SECURE=1
# Cloudflare Tunnel termina TLS antes de Traefik; no forzar otra redirección en Django.
SECURE_SSL_REDIRECT=0
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=1
SECURE_HSTS_PRELOAD=0
```

No versionar `.env`, respaldos ni exportaciones privadas.

## Construir y arrancar

En XOLO-Core usar exclusivamente `compose.production.yaml`; `compose.yaml` es de desarrollo.

```bash
docker compose -f compose.production.yaml config --quiet
docker compose -f compose.production.yaml build --pull
docker compose -f compose.production.yaml up -d db
docker compose -f compose.production.yaml run --rm web python manage.py check --deploy
docker compose -f compose.production.yaml run --rm web python manage.py migrate --noinput
docker compose -f compose.production.yaml up -d
docker compose -f compose.production.yaml ps
docker logs ros-xolo-web --tail=100
```

`ros-xolo-web` debe estar `healthy`; no deben aparecer puertos publicados por ROS-XOLO o PostgreSQL.

## Publicar mediante Cloudflare y Traefik

Agregar antes de `http_status:404` en `/home/francisco/docker/infra/cloudflared/config.yml`:

```yaml
- hostname: planeacion.xolodev.com
  service: http://traefik:80
```

```bash
cd /home/francisco/docker/infra/cloudflared
docker compose restart
```

Crear una aplicación Self-hosted de Cloudflare Access para `planeacion.xolodev.com`. Access protege
la red y Django conserva los roles específicos de planeador y empleado.

```bash
docker run --rm --network xolo_edge curlimages/curl \
  -H 'Host: planeacion.xolodev.com' http://traefik:80/health
```

Debe responder `{"status": "ok"}`. Confirmar HTTPS, cookies Secure, login, autorización de sucursal
y consulta personal.

## Datos, respaldo y actualización

Usar los comandos auditados de `docs/deployment/pilot.md` para crear cuentas y cargar un manifest
revisado. El manifest se guarda en `/srv/apps/ros-xolo/config/`, se monta como `/run/config/` de
solo lectura y debe tener permisos `600`. No ejecutar `seed_demo` ni usar SQL directo contra la base
del piloto.

```bash
STAMP=$(date +%Y%m%d-%H%M%S)
docker compose -f compose.production.yaml exec -T db \
  pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom \
  > "/srv/backups/apps/ros-xolo/ros-xolo-$STAMP.dump"
chmod 600 "/srv/backups/apps/ros-xolo/ros-xolo-$STAMP.dump"
```

Antes de actualizar, crear un respaldo. Después ejecutar:

```bash
git pull --ff-only
docker compose -f compose.production.yaml build --pull
docker compose -f compose.production.yaml run --rm web python manage.py migrate --noinput
docker compose -f compose.production.yaml up -d
```
