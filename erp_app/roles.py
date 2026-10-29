from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


SUPER_ADMIN = 'super_admin'
TEACHING_STAFF = 'teaching_staff'
NORMAL_STAFF = 'normal_staff'
STUDENT = 'student'
INTERN = 'intern'


def get_user_roles(user):
    if not user.is_authenticated:
        return []
    try:
        from django.core.cache import cache
        key = f'user_roles:{getattr(user, "pk", "anon")}'
        cached = cache.get(key)
        if cached is not None:
            return cached
    except Exception:
        cached = None
    roles = set()
    if user.is_superuser:
        roles.add(SUPER_ADMIN)
    try:
        for group in user.groups.all():
            roles.add(group.name)
    except Exception:
        pass
    try:
        if hasattr(user, 'student_profile') and user.student_profile:
            roles.add(STUDENT)
    except Exception:
        pass
    result = list(roles)
    try:
        from django.core.cache import cache
        key = f'user_roles:{getattr(user, "pk", "anon")}'
        cache.set(key, 300)
        cache.set(key, result, 300)
    except Exception:
        pass
    return result


def has_role(user, *roles):
    user_roles = get_user_roles(user)
    return any(r in user_roles for r in roles)


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            if has_role(request.user, *roles):
                return view_func(request, *args, **kwargs)
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('dashboard')
        return _wrapped
    return decorator


def teaching_staff_required(view_func):
    return role_required(SUPER_ADMIN, TEACHING_STAFF)(view_func)


def normal_staff_required(view_func):
    return role_required(SUPER_ADMIN, NORMAL_STAFF, TEACHING_STAFF)(view_func)


def staff_required(view_func):
    return role_required(SUPER_ADMIN, TEACHING_STAFF, NORMAL_STAFF)(view_func)
