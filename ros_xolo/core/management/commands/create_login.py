"""Create a non-shared login without placing its password in configuration files."""

from getpass import getpass

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Crea una cuenta de inicio de sesión y solicita la contraseña de forma interactiva."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)

    def handle(self, *args, **options):
        username = options["username"].strip()
        if not username:
            raise CommandError("El usuario no puede estar vacío.")
        user_model = get_user_model()
        if user_model.objects.filter(username=username).exists():
            raise CommandError("Ya existe una cuenta con ese usuario.")
        password = getpass("Contraseña: ")
        confirmation = getpass("Confirmar contraseña: ")
        if not password:
            raise CommandError("La contraseña no puede estar vacía.")
        if password != confirmation:
            raise CommandError("Las contraseñas no coinciden.")
        user = user_model.objects.create_user(username=username, password=password)
        self.stdout.write(self.style.SUCCESS(f"Cuenta creada: {user.username}"))
