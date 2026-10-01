import time

from django.core.management.base import BaseCommand, CommandError
from django.db import connections


class Command(BaseCommand):
    help = 'Wait until the configured database accepts connections.'

    def add_arguments(self, parser):
        parser.add_argument('--timeout', type=int, default=60)

    def handle(self, *args, **options):
        timeout = options['timeout']
        if timeout < 1:
            raise CommandError('--timeout must be at least 1 second.')

        deadline = time.monotonic() + timeout
        while True:
            try:
                connections['default'].ensure_connection()
                self.stdout.write(self.style.SUCCESS('Database is ready.'))
                return
            except Exception as error:
                if time.monotonic() >= deadline:
                    raise CommandError(f'Database was unavailable after {timeout} seconds: {error}') from error
                self.stdout.write('Waiting for database...')
                time.sleep(2)
