from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('erp_app', '0009_student_is_intern'),
    ]

    operations = [
        migrations.AddField(
            model_name='certificate',
            name='authorized_signature_text',
            field=models.CharField(blank=True, help_text='Optional digital signature text for the dynamic signer', max_length=150),
        ),
        migrations.AddField(
            model_name='certificate',
            name='authorized_signer_name',
            field=models.CharField(blank=True, default='Supriya Dwivedi', max_length=150),
        ),
        migrations.AddField(
            model_name='certificate',
            name='authorized_signer_title',
            field=models.CharField(blank=True, default='Full Stack Developer', max_length=150),
        ),
        migrations.AddField(
            model_name='certificate',
            name='location',
            field=models.CharField(blank=True, default='Auralith Bit', max_length=150),
        ),
        migrations.AddField(
            model_name='certificate',
            name='program_start_date',
            field=models.CharField(blank=True, help_text='Display value for the start date, e.g. 2082/11/25', max_length=40),
        ),
        migrations.AddField(
            model_name='certificate',
            name='program_title',
            field=models.CharField(blank=True, help_text='Course, workshop, internship, or certificate program title', max_length=255),
        ),
    ]
