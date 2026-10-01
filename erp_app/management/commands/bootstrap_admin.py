import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Create the first administrator from explicit BOOTSTRAP_ADMIN_* environment variables.'

    def handle(self, *args, **options):
        username = os.environ.get('BOOTSTRAP_ADMIN_USERNAME', '').strip()
        email = os.environ.get('BOOTSTRAP_ADMIN_EMAIL', '').strip()
        password = os.environ.get('BOOTSTRAP_ADMIN_PASSWORD', '')
        if not (username and email and password):
            raise CommandError('Set BOOTSTRAP_ADMIN_USERNAME, BOOTSTRAP_ADMIN_EMAIL, and BOOTSTRAP_ADMIN_PASSWORD together.')

        User = get_user_model()
        existing = User.objects.filter(username__iexact=username).first()
        if existing:
            if not existing.is_superuser:
                raise CommandError(f"Username '{username}' already exists but is not a superuser. Choose another bootstrap username.")
            self.stdout.write(self.style.WARNING(f"Administrator '{username}' already exists; its password was not changed."))
            return

        try:
            validate_password(password)
        except ValidationError as error:
            raise CommandError('Bootstrap administrator password rejected: ' + '; '.join(error.messages)) from error

        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"Administrator '{username}' created."))
