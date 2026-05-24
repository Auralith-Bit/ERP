from django.db import migrations


def get_perms(apps, model, actions):
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    ct = ContentType.objects.get_for_model(model)
    codenames = [f'{action}_{model._meta.model_name}' for action in actions]
    return list(Permission.objects.filter(content_type=ct, codename__in=codenames))


def create_roles(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    Course = apps.get_model('erp_app', 'Course')
    Mentor = apps.get_model('erp_app', 'Mentor')
    Student = apps.get_model('erp_app', 'Student')
    Employee = apps.get_model('erp_app', 'Employee')
    Department = apps.get_model('erp_app', 'Department')
    IDCard = apps.get_model('erp_app', 'IDCard')
    Certificate = apps.get_model('erp_app', 'Certificate')
    Project = apps.get_model('erp_app', 'Project')
    Notification = apps.get_model('erp_app', 'Notification')

    def g(model, actions):
        return get_perms(apps, model, actions)

    # ── Super Admin ──────────────────────────────────────────────
    group_sa, _ = Group.objects.get_or_create(name='super_admin')
    group_sa.permissions.set(list(Permission.objects.all()))

    # ── Teaching Staff ───────────────────────────────────────────
    group_ts, _ = Group.objects.get_or_create(name='teaching_staff')
    ts_perms = []
    ts_perms += g(Course, ['add', 'change', 'delete', 'view'])
    ts_perms += g(Mentor, ['add', 'change', 'delete', 'view'])
    ts_perms += g(Student, ['add', 'change', 'delete', 'view'])
    ts_perms += g(Certificate, ['add', 'change', 'delete', 'view'])
    ts_perms += g(Employee, ['view'])
    ts_perms += g(Department, ['view'])
    ts_perms += g(Notification, ['add', 'view'])
    try:
        can_issue = Permission.objects.get(codename='can_issue_certificates')
        ts_perms.append(can_issue)
    except Permission.DoesNotExist:
        pass
    group_ts.permissions.set(ts_perms)

    # ── Normal Staff ─────────────────────────────────────────────
    group_ns, _ = Group.objects.get_or_create(name='normal_staff')
    ns_perms = []
    ns_perms += g(Employee, ['add', 'change', 'delete', 'view'])
    ns_perms += g(Department, ['add', 'change', 'delete', 'view'])
    ns_perms += g(IDCard, ['add', 'change', 'delete', 'view'])
    ns_perms += g(Project, ['add', 'change', 'delete', 'view'])
    ns_perms += g(Course, ['view'])
    ns_perms += g(Mentor, ['view'])
    ns_perms += g(Student, ['view'])
    ns_perms += g(Certificate, ['view'])
    ns_perms += g(Notification, ['add', 'view'])
    group_ns.permissions.set(ns_perms)

    # ── Student ──────────────────────────────────────────────────
    group_st, _ = Group.objects.get_or_create(name='student')
    st_perms = []
    st_perms += g(Course, ['view'])
    st_perms += g(Certificate, ['view'])
    st_perms += g(Mentor, ['view'])
    group_st.permissions.set(st_perms)

    # ── Intern ───────────────────────────────────────────────────
    group_in, _ = Group.objects.get_or_create(name='intern')
    in_perms = []
    in_perms += g(Course, ['view'])
    in_perms += g(Certificate, ['view'])
    in_perms += g(Mentor, ['view'])
    in_perms += g(Employee, ['view'])
    in_perms += g(Department, ['view'])
    group_in.permissions.set(in_perms)


def remove_roles(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name__in=[
        'super_admin', 'teaching_staff', 'normal_staff', 'student', 'intern',
    ]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('erp_app', '0007_alter_certificate_certificate_type'),
    ]

    operations = [
        migrations.RunPython(create_roles, remove_roles),
    ]
