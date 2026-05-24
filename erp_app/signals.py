from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import Group
from .models import CourseEnrollment, Certificate, Student


@receiver(post_save, sender=Student)
def assign_user_groups(sender, instance, **kwargs):
    if not instance.user:
        return
    try:
        student_group = Group.objects.get(name='student')
        instance.user.groups.add(student_group)
    except Group.DoesNotExist:
        pass
    if instance.is_intern:
        try:
            intern_group = Group.objects.get(name='intern')
            instance.user.groups.add(intern_group)
        except Group.DoesNotExist:
            pass


@receiver(post_save, sender=CourseEnrollment)
def auto_create_course_certificate(sender, instance, **kwargs):
    if instance.status == 'completed':
        exists = Certificate.objects.filter(
            student=instance.student,
            course=instance.course,
            certificate_type='course'
        ).exists()
        if not exists:
            Certificate.objects.create(
                student=instance.student,
                course=instance.course,
                certificate_type='course',
                status='issued'
            )
