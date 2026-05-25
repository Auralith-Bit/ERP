import os
import json
import io
import qrcode
from functools import wraps
from pathlib import Path
from base64 import b64encode
from datetime import datetime
from PIL import Image
from django.conf import settings
from django.db.models import Count, Sum, Q
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Group
from django.contrib import messages
from django.apps import apps
from django.urls import reverse, NoReverseMatch
from django.http import JsonResponse, HttpResponse, FileResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods
from .models import Course, Mentor, Student, Project, Employee, Department, Notification, IDCard, Certificate
from .roles import (get_user_roles, has_role,
    SUPER_ADMIN, TEACHING_STAFF, NORMAL_STAFF, STUDENT, INTERN,
    role_required, teaching_staff_required, normal_staff_required, staff_required)

def student_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return _wrapped

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            next_url = request.GET.get('next', request.POST.get('next', 'dashboard'))
            return redirect(next_url)
        messages.error(request, 'Invalid username or password.')
    return render(request, 'erp_app/login.html')


def logout_view(request):
    logout(request)
    return redirect('login')


def index(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return redirect('login')

def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        email = request.POST.get('email', '')
        if not username or not password:
            messages.error(request, 'Please provide both username and password.')
        elif User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists. Please choose another.')
        else:
            user = User.objects.create_user(username=username, password=password, email=email)
            Student.objects.get_or_create(
                user=user,
                defaults={'name': username, 'email': email}
            )
            messages.success(request, 'Account created successfully. Please sign in.')
            return redirect('login')
    return render(request, 'erp_app/register.html')

    #staff registration view with code verification and role assignment
def staff_register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        email = request.POST.get('email', '')
        staff_type = request.POST.get('staff_type', '')
        staff_code = request.POST.get('staff_code', '')

        expected_code = getattr(settings, 'STAFF_REGISTRATION_CODE', 'STAFF2024')
        if staff_code != expected_code:
            messages.error(request, 'Invalid staff registration code.')
            return render(request, 'erp_app/staff_register.html')

        if not username or not password:
            messages.error(request, 'Please provide both username and password.')
        elif User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
        elif staff_type not in ('teaching', 'normal'):
            messages.error(request, 'Invalid staff type.')
        else:
            user = User.objects.create_user(username=username, password=password, email=email)
            group_name = 'teaching_staff' if staff_type == 'teaching' else 'normal_staff'
            try:
                group = Group.objects.get(name=group_name)
                user.groups.add(group)
            except Group.DoesNotExist:
                pass
            messages.success(request, f'{staff_type.title()} staff account created. Please sign in.')
            return redirect('login')
    return render(request, 'erp_app/staff_register.html')


@login_required
def promote_to_intern(request, student_id):
    if not has_role(request.user, SUPER_ADMIN, TEACHING_STAFF, NORMAL_STAFF):
        messages.error(request, 'You do not have permission to promote users.')
        return redirect('dashboard')
    student = get_object_or_404(Student, id=student_id)
    student.is_intern = True
    student.save()
    messages.success(request, f'{student.name} has been upgraded to intern.')
    return redirect('employees')


def password_reset(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        email = request.POST.get('email')
        messages.success(request, 'If an account exists for this email, password reset details have been sent.')
        return redirect('login')
    return render(request, 'erp_app/password_reset.html')


@login_required
def dashboard(request):
    roles = get_user_roles(request.user)
    context = {
        'trained_learners': Student.objects.count(),
        'projects_delivered': Project.objects.filter(status='completed').count(),
        'live_classes': Course.objects.filter(status='live').count(),
        'expert_mentors': Mentor.objects.count(),
        'courses': Course.objects.select_related('mentor').all()[:5],
        'projects': Project.objects.all()[:5],
        'is_admin': has_role(request.user, SUPER_ADMIN, TEACHING_STAFF, NORMAL_STAFF),
    }
    return render(request, 'erp_app/dashboard.html', context)

@login_required
def courses(request):
    context = {
        'courses': Course.objects.select_related('mentor').annotate(enrollment_count=Count('enrollments')).all(),
        'is_admin': has_role(request.user, SUPER_ADMIN, TEACHING_STAFF),
    }
    return render(request, 'erp_app/courses.html', context)


@login_required
def course_syllabus(request, course_id):
    """Render a simple syllabus view or download link for a course."""
    course = get_object_or_404(Course, id=course_id)
    return render(request, 'erp_app/course_syllabus.html', {'course': course, 'is_admin': has_role(request.user, SUPER_ADMIN, TEACHING_STAFF)})

@login_required
@require_http_methods(["GET"])
def notifications_feed(request):
    notifications = Notification.objects.filter(is_active=True).order_by('-created_at')[:20]
    payload = [
        {
            'id': notification.id,
            'title': notification.title,
            'message': notification.message,
            'created_at': notification.created_at.isoformat(),
            'sender': notification.created_by.username if notification.created_by else 'Admin',
        }
        for notification in notifications
    ]
    return JsonResponse(payload, safe=False)

@login_required
def mentors(request):
    mentor_list = Mentor.objects.annotate(course_count=Count('course')).prefetch_related('course_set').all()
    context = {
        'mentors': mentor_list,
        'is_admin': has_role(request.user, SUPER_ADMIN, TEACHING_STAFF),
    }
    return render(request, 'erp_app/mentors.html', context)

@login_required
def employees(request):
    employee_type = request.GET.get('type', '')
    emp_list = Employee.objects.select_related('department').all()
    mentor_list = Mentor.objects.annotate(course_count=Count('course')).all()

    if employee_type:
        if employee_type == 'mentor':
            context = {
                'employees': Employee.objects.none(),
                'mentors': mentor_list,
                'types': Employee.EMPLOYEE_TYPES,
                'current_type': employee_type,
                'is_admin': has_role(request.user, SUPER_ADMIN, NORMAL_STAFF),
            }
            return render(request, 'erp_app/employees.html', context)
        emp_list = emp_list.filter(employee_type=employee_type)

    types = Employee.EMPLOYEE_TYPES
    context = {
        'employees': emp_list,
        'mentors': mentor_list,
        'types': types,
        'current_type': employee_type,
        'is_admin': has_role(request.user, SUPER_ADMIN, NORMAL_STAFF),
    }
    return render(request, 'erp_app/employees.html', context)

@login_required
def departments(request):
    dept_list = Department.objects.prefetch_related('employee_set').annotate(employee_count=Count('employee')).all()
    context = {
        'departments': dept_list,
        'is_admin': has_role(request.user, SUPER_ADMIN, NORMAL_STAFF),
    }
    return render(request, 'erp_app/departments.html', context)

@login_required
def integration(request):
    context = {}
    return render(request, 'erp_app/integration.html', context)

@login_required
def id_generation(request):
    if request.method == 'POST':
        if not has_role(request.user, SUPER_ADMIN, NORMAL_STAFF):
            messages.error(request, 'Only admin can upload ID cards.')
            return redirect('id_generation')
        
        card_type = request.POST.get('card_type')
        uploaded_file = request.FILES.get('id_card_file')
        owner_id = request.POST.get('owner_id')

        if not card_type or not owner_id or not uploaded_file:
            messages.error(request, 'Please select a valid user and upload an ID card image.')
        else:
            if card_type == 'student':
                student = Student.objects.filter(id=owner_id).first()
                if student:
                    IDCard.objects.create(card_type='student', student=student, file=uploaded_file)
                    Notification.objects.create(
                        title='Student ID uploaded',
                        message=f'Student ID card for {student.name} has been uploaded.',
                        created_by=request.user,
                    )
                    messages.success(request, f'Student ID card uploaded for {student.name}.')
                else:
                    messages.error(request, 'Selected student was not found.')
            elif card_type == 'employee':
                employee = Employee.objects.filter(id=owner_id).first()
                if employee:
                    IDCard.objects.create(card_type='employee', employee=employee, file=uploaded_file)
                    Notification.objects.create(
                        title='Employee ID uploaded',
                        message=f'Employee ID card for {employee.name} has been uploaded.',
                        created_by=request.user,
                    )
                    messages.success(request, f'Employee ID card uploaded for {employee.name}.')
                else:
                    messages.error(request, 'Selected employee was not found.')
            else:
                messages.error(request, 'Invalid ID card type.')

    students = Student.objects.all()
    employees = Employee.objects.select_related('department').all()
    courses = Course.objects.all()
    departments = Department.objects.all()
    student_cards = IDCard.objects.filter(card_type='student').select_related('student')
    employee_cards = IDCard.objects.filter(card_type='employee').select_related('employee')
    context = {
        'students': students,
        'employees': employees,
        'courses': courses,
        'departments': departments,
        'student_cards': student_cards,
        'employee_cards': employee_cards,
        'is_admin': has_role(request.user, SUPER_ADMIN, NORMAL_STAFF),
    }
    return render(request, 'erp_app/id_generation.html', context)

@login_required
@require_http_methods(["DELETE"])
def delete_id_card(request, card_id):
    """Delete an ID card and return JSON response"""
    if not has_role(request.user, SUPER_ADMIN, NORMAL_STAFF):
        return JsonResponse({'status': 'error', 'message': 'Permission denied.'}, status=403)
    try:
        card = IDCard.objects.get(id=card_id)
        card_type = card.get_card_type_display()
        owner_name = card.owner_name
        card.delete()
        return JsonResponse({
            'status': 'success',
            'message': f'{card_type} ID card for {owner_name} deleted successfully.'
        })
    except IDCard.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'ID card not found.'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@login_required
def budget_fees(request):
    courses = Course.objects.all()
    projects = Project.objects.all()
    context = {
        'courses': courses,
        'projects': projects,
        'is_admin': has_role(request.user, SUPER_ADMIN, NORMAL_STAFF),
    }
    return render(request, 'erp_app/budget_fees.html', context)

@login_required
def search(request):
    query = request.GET.get('q', '').strip()
    results = []
    total_matches = 0

    if query:
        course_matches = Course.objects.filter(
            Q(name__icontains=query) |
            Q(category__icontains=query) |
            Q(description__icontains=query) |
            Q(status__icontains=query) |
            Q(mentor__name__icontains=query)
        ).select_related('mentor')[:20]

        mentor_matches = Mentor.objects.filter(
            Q(name__icontains=query) |
            Q(email__icontains=query) |
            Q(specialization__icontains=query) |
            Q(bio__icontains=query)
        )[:20]

        student_matches = Student.objects.filter(
            Q(name__icontains=query) |
            Q(email__icontains=query) |
            Q(phone__icontains=query)
        )[:20]

        project_matches = Project.objects.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(client__icontains=query) |
            Q(status__icontains=query)
        )[:20]

        employee_matches = Employee.objects.filter(
            Q(name__icontains=query) |
            Q(email__icontains=query) |
            Q(role__icontains=query) |
            Q(employee_type__icontains=query) |
            Q(department__name__icontains=query)
        ).select_related('department')[:20]

        department_matches = Department.objects.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query)
        )[:20]

        results = [
            {'title': 'Courses', 'items': course_matches},
            {'title': 'Mentors', 'items': mentor_matches},
            {'title': 'Students', 'items': student_matches},
            {'title': 'Projects', 'items': project_matches},
            {'title': 'Employees', 'items': employee_matches},
            {'title': 'Departments', 'items': department_matches},
        ]
        total_matches = sum(item['items'].count() for item in results)

    context = {
        'query': query,
        'results': results,
        'total_matches': total_matches,
    }
    return render(request, 'erp_app/search_results.html', context)

@login_required
def workbench(request):
    all_models = apps.get_models()
    model_data = []
    for model in all_models:
        if model._meta.app_label not in ('erp_app',):
            continue
        admin_url = None
        if has_role(request.user, SUPER_ADMIN):
            try:
                admin_url = reverse(f'admin:{model._meta.app_label}_{model.__name__.lower()}_changelist')
            except NoReverseMatch:
                admin_url = None
        model_data.append({
            'name': model._meta.verbose_name_plural.title(),
            'model_name': model.__name__,
            'app_label': model._meta.app_label,
            'count': model.objects.count(),
            'fields': [f.verbose_name.title() for f in model._meta.fields],
            'admin_url': admin_url,
        })
    context = {
        'model_data': sorted(model_data, key=lambda x: x['name']),
    }
    return render(request, 'erp_app/workbench.html', context)

@login_required
def workbench_table(request, app_label, model_name):
    model = None
    for m in apps.get_models():
        if m.__name__ == model_name and m._meta.app_label == app_label:
            model = m
            break
    if not model:
        return render(request, 'erp_app/workbench.html', {'error': 'Model not found'})
    fields = [f for f in model._meta.fields]
    objects_list = model.objects.all()
    
    # Add display values for choice fields
    choice_fields = {f.name for f in model._meta.fields if hasattr(f, 'choices') and f.choices}
    
    context = {
        'model': model,
        'model_name': model.__name__,
        'model_verbose_plural': model._meta.verbose_name_plural.title(),
        'model_app_label': model._meta.app_label,
        'model_class_name': model.__name__,
        'fields': fields,
        'objects': objects_list,
        'choice_fields': choice_fields,
    }
    return render(request, 'erp_app/workbench_table.html', context)


@login_required
@require_http_methods(["GET"])
def get_students(request):
    """API endpoint to get all students as JSON"""
    students = Student.objects.all().values('id', 'name', 'email')
    return JsonResponse(list(students), safe=False)


@login_required
@require_http_methods(["GET"])
def get_employees(request):
    """API endpoint to get all employees as JSON"""
    employees = Employee.objects.select_related('department').all().values('id', 'name', 'email', 'department__name', 'employee_type')
    return JsonResponse(list(employees), safe=False)


@login_required
@require_http_methods(["GET"])
def get_courses(request):
    """API endpoint to get all courses as JSON"""
    courses = Course.objects.all().values('id', 'name', 'category', 'status')
    return JsonResponse(list(courses), safe=False)


@login_required
@require_http_methods(["GET"])
def get_departments(request):
    """API endpoint to get all departments as JSON"""
    departments = Department.objects.all().values('id', 'name', 'head')
    return JsonResponse(list(departments), safe=False)


@login_required
@require_http_methods(["POST"])
def generate_student_id(request):
    """Generate student ID card with QR code containing all details"""
    try:
        data = json.loads(request.body)
        student_id = data.get('student_id')
        course_id = data.get('course_id')
        
        if not student_id or not course_id:
            return JsonResponse({'error': 'Missing student_id or course_id'}, status=400)
        
        student = Student.objects.get(id=student_id)
        course = Course.objects.get(id=course_id)
        
        # Generate unique ID
        unique_id = f"STU-{student_id:05d}-{course_id:05d}"
        date_generated = datetime.now().strftime('%Y-%m-%d')
        
        # Create QR code data with all details in JSON format
        qr_data = json.dumps({
            'type': 'STUDENT_ID',
            'id': unique_id,
            'name': student.name,
            'email': student.email,
            'phone': student.phone or 'N/A',
            'course': course.name,
            'category': course.category,
            'enrolled_date': student.enrolled_date.strftime('%Y-%m-%d'),
            'date_generated': date_generated
        })
        
        # Generate QR code with all details
        qr = qrcode.QRCode(version=None, box_size=10, border=5)
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        img_io = io.BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)
        img_base64 = b64encode(img_io.getvalue()).decode()
        
        return JsonResponse({
            'success': True,
            'id': unique_id,
            'student_name': student.name,
            'student_email': student.email,
            'phone': student.phone or 'N/A',
            'course_name': course.name,
            'course_category': course.category,
            'enrolled_date': student.enrolled_date.strftime('%Y-%m-%d'),
            'date_generated': date_generated,
            'qr_code': f'data:image/png;base64,{img_base64}'
        })
    except Student.DoesNotExist:
        return JsonResponse({'error': 'Student not found'}, status=404)
    except Course.DoesNotExist:
        return JsonResponse({'error': 'Course not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def generate_employee_id(request):
    """Generate employee ID card with QR code containing all details"""
    try:
        data = json.loads(request.body)
        employee_id = data.get('employee_id')
        
        if not employee_id:
            return JsonResponse({'error': 'Missing employee_id'}, status=400)
        
        employee = Employee.objects.select_related('department').get(id=employee_id)
        
        # Generate unique ID
        unique_id = f"EMP-{employee_id:05d}"
        date_generated = datetime.now().strftime('%Y-%m-%d')
        department_name = employee.department.name if employee.department else 'N/A'
        employee_type_display = employee.get_employee_type_display()
        
        # Create QR code data with all details in JSON format
        qr_data = json.dumps({
            'type': 'EMPLOYEE_ID',
            'id': unique_id,
            'name': employee.name,
            'email': employee.email,
            'role': employee.role or 'N/A',
            'department': department_name,
            'employee_type': employee_type_display,
            'joined_date': employee.joined_date.strftime('%Y-%m-%d'),
            'date_generated': date_generated
        })
        
        # Generate QR code with all details
        qr = qrcode.QRCode(version=None, box_size=10, border=5)
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        img_io = io.BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)
        img_base64 = b64encode(img_io.getvalue()).decode()
        
        return JsonResponse({
            'success': True,
            'id': unique_id,
            'employee_name': employee.name,
            'employee_email': employee.email,
            'role': employee.role or 'N/A',
            'department': department_name,
            'employee_type': employee_type_display,
            'joined_date': employee.joined_date.strftime('%Y-%m-%d'),
            'date_generated': date_generated,
            'qr_code': f'data:image/png;base64,{img_base64}'
        })
    except Employee.DoesNotExist:
        return JsonResponse({'error': 'Employee not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def verify_id_card(request):
    """Verify and display ID card details from scanned QR code data"""
    try:
        data = json.loads(request.body)
        qr_data_str = data.get('qr_data')
        
        if not qr_data_str:
            return JsonResponse({'error': 'No QR data provided'}, status=400)
        
        # Parse QR code data
        qr_data = json.loads(qr_data_str)
        card_type = qr_data.get('type')
        
        if card_type == 'STUDENT_ID':
            return JsonResponse({
                'success': True,
                'type': 'student',
                'id': qr_data.get('id'),
                'name': qr_data.get('name'),
                'email': qr_data.get('email'),
                'phone': qr_data.get('phone'),
                'course': qr_data.get('course'),
                'category': qr_data.get('category'),
                'enrolled_date': qr_data.get('enrolled_date'),
                'date_generated': qr_data.get('date_generated')
            })
        elif card_type == 'EMPLOYEE_ID':
            return JsonResponse({
                'success': True,
                'type': 'employee',
                'id': qr_data.get('id'),
                'name': qr_data.get('name'),
                'email': qr_data.get('email'),
                'role': qr_data.get('role'),
                'department': qr_data.get('department'),
                'employee_type': qr_data.get('employee_type'),
                'joined_date': qr_data.get('joined_date'),
                'date_generated': qr_data.get('date_generated')
            })
        else:
            return JsonResponse({'error': 'Invalid ID card type'}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid QR code data format'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def certificates(request):
    cert_type = request.GET.get('type', '')
    search_q = request.GET.get('q', '').strip()

    certs = Certificate.objects.select_related('student', 'course').all()

    if has_role(request.user, SUPER_ADMIN, TEACHING_STAFF, NORMAL_STAFF):
        pass
    elif hasattr(request.user, 'student_profile') and request.user.student_profile:
        certs = certs.filter(student=request.user.student_profile)
    else:
        certs = certs.none()

    if cert_type:
        certs = certs.filter(certificate_type=cert_type)

    if search_q:
        certs = certs.filter(
            Q(certificate_number__icontains=search_q) |
            Q(student__name__icontains=search_q) |
            Q(course__name__icontains=search_q)
        )

    context = {
        'certificates': certs,
        'is_admin': has_role(request.user, SUPER_ADMIN) or request.user.has_perm('erp_app.can_issue_certificates'),
        'current_type': cert_type,
        'search_query': search_q,
    }
    return render(request, 'erp_app/certificates.html', context)


@login_required
def issue_certificate(request):
    if not has_role(request.user, SUPER_ADMIN) and not request.user.has_perm('erp_app.can_issue_certificates'):
        messages.error(request, 'You do not have permission to issue certificates.')
        return redirect('certificates')

    if request.method == 'POST':
        student_id = request.POST.get('student')
        course_id = request.POST.get('course')
        certificate_type = request.POST.get('certificate_type', 'internship')
        internship_details = request.POST.get('internship_details', '')

        if not student_id:
            messages.error(request, 'Please select a student.')
        else:
            student = get_object_or_404(Student, id=student_id)
            course = None
            if course_id:
                course = Course.objects.filter(id=course_id).first()

            uploaded_file = request.FILES.get('certificate_file')

            cert = Certificate.objects.create(
                student=student,
                course=course if certificate_type in ('course', 'workshop') else None,
                certificate_type=certificate_type,
                status='issued',
                file=uploaded_file,
                internship_details=internship_details,
            )

            Notification.objects.create(
                title='Certificate Issued',
                message=f'{cert.get_certificate_type_display()} certificate {cert.certificate_number} issued to {student.name}.',
                created_by=request.user,
            )

            messages.success(request, f'Certificate {cert.certificate_number} issued to {student.name}.')
            return redirect('certificates')

    students = Student.objects.all()
    courses = Course.objects.all()
    context = {
        'students': students,
        'courses': courses,
        'is_admin': has_role(request.user, SUPER_ADMIN) or request.user.has_perm('erp_app.can_issue_certificates'),
    }
    return render(request, 'erp_app/issue_certificate.html', context)


@login_required
def preview_certificate(request, cert_id):
    cert = get_object_or_404(Certificate.objects.select_related('student', 'course'), id=cert_id)

    if not has_role(request.user, SUPER_ADMIN, TEACHING_STAFF, NORMAL_STAFF):
        if not hasattr(request.user, 'student_profile') or request.user.student_profile != cert.student:
            messages.error(request, 'You do not have access to this certificate.')
            return redirect('certificates')

    if cert.certificate_type == 'workshop':
        template_name = 'erp_app/certificate_preview_workshop.html'
    elif cert.certificate_type == 'course':
        template_name = 'erp_app/certificate_preview_course.html'
    else:
        template_name = 'erp_app/certificate_preview_internship.html'
    context = {
        'certificate': cert,
        'is_admin': has_role(request.user, SUPER_ADMIN) or request.user.has_perm('erp_app.can_issue_certificates'),
    }
    return render(request, template_name, context)


def _pdf_escape(value):
    text = str(value or '')
    text = text.encode('latin-1', 'replace').decode('latin-1')
    return text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)').replace('\r', ' ').replace('\n', ' ')


def _pdf_text(commands, text, x, y, size=12, font='F1', color=(0, 0, 0), align='left'):
    safe_text = _pdf_escape(text)
    estimated_width = len(safe_text) * size * 0.5
    if align == 'center':
        x -= estimated_width / 2
    elif align == 'right':
        x -= estimated_width
    commands.append(f'{color[0]:.3f} {color[1]:.3f} {color[2]:.3f} rg')
    commands.append(f'BT /{font} {size} Tf {x:.2f} {y:.2f} Td ({safe_text}) Tj ET')


def _wrap_words(text, max_chars):
    words = str(text or '').split()
    lines = []
    current = ''
    for word in words:
        candidate = f'{current} {word}'.strip()
        if len(candidate) > max_chars and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or ['']

def _write_simple_certificate_pdf(certificate, pdf_path):
    page_width, page_height = 792, 612
    blue = (26 / 255, 75 / 255, 141 / 255)
    pink = (222 / 255, 43 / 255, 93 / 255)
    slate = (30 / 255, 41 / 255, 59 / 255)
    muted = (100 / 255, 116 / 255, 139 / 255)
    light = (226 / 255, 232 / 255, 240 / 255)

    title_map = {
        'workshop': 'Certificate of Workshop Participation',
        'internship': 'Certificate of Internship',
        'course': 'Certificate of Course Completion',
    }
    description_map = {
        'workshop': 'for actively participating in the workshop',
        'internship': 'for successfully completing the internship program at AURALITH BIT',
        'course': 'for successfully completing the course',
    }
    note_map = {
        'workshop': 'with demonstrated engagement and practical application',
        'internship': 'with demonstrated competence and professional conduct',
        'course': 'with demonstrated understanding and satisfactory performance',
    }

    commands = [
        '1 1 1 rg 0 0 792 612 re f',
        f'{blue[0]:.3f} {blue[1]:.3f} {blue[2]:.3f} RG 4 w 46 46 700 520 re S',
        f'{light[0]:.3f} {light[1]:.3f} {light[2]:.3f} RG 1 w 58 58 676 496 re S',
    ]

    _pdf_text(commands, 'AURALITH BIT', page_width / 2, 516, 13, 'F2', blue, 'center')
    _pdf_text(commands, 'Centre for Development & Training', page_width / 2, 486, 24, 'F2', blue, 'center')
    commands.append(f'{pink[0]:.3f} {pink[1]:.3f} {pink[2]:.3f} rg 356 464 80 3 re f')

    _pdf_text(commands, title_map.get(certificate.certificate_type, title_map['course']), page_width / 2, 422, 26, 'F2', slate, 'center')
    _pdf_text(commands, 'PRESENTED TO', page_width / 2, 386, 11, 'F1', (0.58, 0.64, 0.72), 'center')
    _pdf_text(commands, certificate.student.name, page_width / 2, 346, 34, 'F2', blue, 'center')
    _pdf_text(commands, description_map.get(certificate.certificate_type, description_map['course']), page_width / 2, 316, 14, 'F1', muted, 'center')

    y = 286
    if certificate.certificate_type in ('course', 'workshop') and certificate.course:
        _pdf_text(commands, certificate.course.name, page_width / 2, y, 20, 'F2', pink, 'center')
        y -= 30
    elif certificate.certificate_type == 'internship' and certificate.internship_details:
        for line in _wrap_words(certificate.internship_details, 78)[:4]:
            _pdf_text(commands, line, page_width / 2, y, 12, 'F1', muted, 'center')
            y -= 18
        y -= 8

    _pdf_text(commands, note_map.get(certificate.certificate_type, note_map['course']), page_width / 2, y, 13, 'F1', muted, 'center')

    detail_y = 188
    details = [
        ('Date of Issue', certificate.issue_date.strftime('%B %d, %Y')),
        ('Certificate No.', certificate.certificate_number),
        ('Status', certificate.get_status_display()),
    ]
    for x, (label, value) in zip((210, 396, 582), details):
        _pdf_text(commands, label.upper(), x, detail_y, 9, 'F1', (0.58, 0.64, 0.72), 'center')
        _pdf_text(commands, value, x, detail_y - 22, 14, 'F2', slate, 'center')

    commands.append(f'{light[0]:.3f} {light[1]:.3f} {light[2]:.3f} RG 1 w 172 122 m 620 122 l S')
    for x, name, label in ((250, 'Authorized Signature', 'Program Coordinator'), (542, 'AURALITH BIT', 'Director')):
        commands.append('0.741 0.773 0.820 RG 1 w %.2f 95 m %.2f 95 l S' % (x - 90, x + 90))
        _pdf_text(commands, name, x, 76, 13, 'F2', slate, 'center')
        _pdf_text(commands, label, x, 60, 11, 'F1', (0.58, 0.64, 0.72), 'center')

    _pdf_text(commands, 'AURALITH BIT - Centre for Development & Training', page_width / 2, 30, 10, 'F1', (0.74, 0.77, 0.82), 'center')

    stream = '\n'.join(commands).encode('latin-1', 'replace')
    objects = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 792 612] /Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>',
        b'<< /Length ' + str(len(stream)).encode('ascii') + b' >>\nstream\n' + stream + b'\nendstream',
    ]

    pdf = bytearray(b'%PDF-1.4\n')
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f'{index} 0 obj\n'.encode('ascii'))
        pdf.extend(obj)
        pdf.extend(b'\nendobj\n')

    xref_offset = len(pdf)
    pdf.extend(f'xref\n0 {len(objects) + 1}\n'.encode('ascii'))
    pdf.extend(b'0000000000 65535 f \n')
    for offset in offsets[1:]:
        pdf.extend(f'{offset:010d} 00000 n \n'.encode('ascii'))
    pdf.extend(f'trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n'.encode('ascii'))

    with open(pdf_path, 'wb') as pdf_file:
        pdf_file.write(pdf)


@login_required
def download_certificate(request, cert_id):
    cert = get_object_or_404(Certificate, id=cert_id)

    if not has_role(request.user, SUPER_ADMIN, TEACHING_STAFF, NORMAL_STAFF):
        if not hasattr(request.user, 'student_profile') or request.user.student_profile != cert.student:
            messages.error(request, 'You do not have access to this certificate.')
            return redirect('certificates')

    force = request.GET.get('force') == '1'

    if force and cert.file and os.path.exists(cert.file.path):
        os.remove(cert.file.path)
        cert.file = None
        cert.save(update_fields=['file'])

    if cert.file and os.path.exists(cert.file.path):
        return FileResponse(open(cert.file.path, 'rb'), as_attachment=True, filename=f"{cert.certificate_number}.pdf")

    pdf_path = os.path.join(settings.MEDIA_ROOT, 'certificates', f'{cert.certificate_number}.pdf')
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)

    try:
        html_content = render_to_string('erp_app/certificate_download.html', {
            'certificate': cert,
        })

        logo_path = Path(settings.STATIC_ROOT) / 'erp_app' / 'images' / 'AURALITH_logo.png'
        if logo_path.exists():
            with open(logo_path, 'rb') as f:
                logo_b64 = b64encode(f.read()).decode('ascii')
            logo_uri = f'data:image/png;base64,{logo_b64}'
            html_content = html_content.replace(
                '/static/erp_app/images/AURALITH_logo.png', logo_uri
            )

        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(args=[
                '--disable-gpu',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
            ])
            page = browser.new_page(viewport={'width': 816, 'height': 1056})
            page.set_content(html_content, wait_until='load', timeout=30000)
            page.pdf(
                path=pdf_path,
                format='Letter',
                print_background=True,
                margin={'top': '0', 'bottom': '0', 'left': '0', 'right': '0'},
            )
            page.close()
            browser.close()

        cert.file.name = f'certificates/{cert.certificate_number}.pdf'
        cert.save(update_fields=['file'])

        return FileResponse(open(pdf_path, 'rb'), as_attachment=True, filename=f"{cert.certificate_number}.pdf")
    except Exception as e:
        messages.error(request, f'Could not generate PDF: {e}')
        return redirect('preview_certificate', cert_id=cert.id)
