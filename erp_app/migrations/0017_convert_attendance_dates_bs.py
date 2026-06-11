from django.db import migrations
from nepali_datetime import date as NepaliDate
from datetime import date as EnglishDate


def ad_to_bs(ad_date_str):
    if not ad_date_str:
        return ''
    try:
        ad_date = EnglishDate.fromisoformat(ad_date_str)
        nepali_date = NepaliDate.from_datetime_date(ad_date)
        return nepali_date.strftime('%Y-%m-%d')
    except (ValueError, TypeError):
        return ad_date_str


def convert_ad_to_bs(apps, schema_editor):
    Attendance = apps.get_model('erp_app', 'Attendance')
    for att in Attendance.objects.all():
        if att.date:
            att.date = ad_to_bs(str(att.date))
            att.save(update_fields=['date'])


class Migration(migrations.Migration):

    dependencies = [
        ('erp_app', '0016_attendance_bs_date'),
    ]

    operations = [
        migrations.RunPython(convert_ad_to_bs, migrations.RunPython.noop),
    ]
