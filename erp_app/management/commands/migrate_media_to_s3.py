from django.core.management.base import BaseCommand
from django.core.files.storage import default_storage
from django.conf import settings
from erp_app.models import IDCard, Certificate, Course


class Command(BaseCommand):
    help = 'Migrate existing local media files to S3'

    def handle(self, *args, **options):
        models_with_files = []

        for card in IDCard.objects.all():
            if card.file and not default_storage.exists(card.file.name):
                path = card.file.path
                with open(path, 'rb') as f:
                    saved = default_storage.save(card.file.name, f)
                self.stdout.write(f'  Uploaded ID card: {saved}')
                models_with_files.append('IDCard')

        for cert in Certificate.objects.all():
            if cert.file and not default_storage.exists(cert.file.name):
                path = cert.file.path
                with open(path, 'rb') as f:
                    saved = default_storage.save(cert.file.name, f)
                self.stdout.write(f'  Uploaded certificate: {saved}')
                models_with_files.append('Certificate')

        for course in Course.objects.all():
            if course.syllabus and not default_storage.exists(course.syllabus.name):
                path = course.syllabus.path
                with open(path, 'rb') as f:
                    saved = default_storage.save(course.syllabus.name, f)
                self.stdout.write(f'  Uploaded syllabus: {saved}')
                models_with_files.append('Syllabus')

        if not models_with_files:
            self.stdout.write('No files needed migration.')
        else:
            self.stdout.write(self.style.SUCCESS(f'Done. Migrated files from: {", ".join(set(models_with_files))}'))
