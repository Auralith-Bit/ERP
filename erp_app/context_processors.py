from .models import Employee, Department, Mentor, Student, Certificate
from .roles import get_user_roles, SUPER_ADMIN, TEACHING_STAFF, NORMAL_STAFF, STUDENT, INTERN


def sidebar_stats(request):
    if not request.user.is_authenticated:
        return {}

    full_name = request.user.get_full_name()
    if full_name:
        parts = full_name.split()
        initials = ''.join(p[0].upper() for p in parts if p)[:2]
    else:
        initials = request.user.username[:2].upper()

    roles = get_user_roles(request.user)

    return {
        'user_initials': initials,
        'sidebar_employee_count': Employee.objects.count(),
        'sidebar_department_count': Department.objects.count(),
        'sidebar_mentor_count': Mentor.objects.count(),
        'sidebar_student_count': Student.objects.count(),
        'sidebar_certificate_count': Certificate.objects.filter(status='issued').count(),
        'user_roles': roles,
        'is_super_admin': SUPER_ADMIN in roles,
        'is_teaching_staff': TEACHING_STAFF in roles,
        'is_normal_staff': NORMAL_STAFF in roles,
        'is_student': STUDENT in roles,
        'is_intern': INTERN in roles,
        'is_any_staff': bool(set(roles) & {SUPER_ADMIN, TEACHING_STAFF, NORMAL_STAFF}),
    }
