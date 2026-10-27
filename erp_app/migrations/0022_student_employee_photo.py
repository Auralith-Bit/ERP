from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('erp_app', '0021_alter_student_enrolled_date_expense'),
    ]

    operations = [
        migrations.AddField(
            model_name='student',
            name='photo',
            field=models.ImageField(blank=True, null=True, upload_to='profile_photos/'),
        ),
        migrations.AddField(
            model_name='employee',
            name='photo',
            field=models.ImageField(blank=True, null=True, upload_to='profile_photos/'),
        ),
    ]
