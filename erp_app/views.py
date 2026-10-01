import json
import io
import logging
import random
import string
import qrcode
from functools import wraps
from pathlib import Path
from base64 import b64encode
from datetime import datetime, date as EnglishDate
from .nepali_utils import today_bs
from PIL import Image
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Count, Prefetch, Q
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Group
from django.contrib import messages
from django.apps import apps
from django.urls import reverse, NoReverseMatch
from django.http import JsonResponse, HttpResponse, FileResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods, require_POST
from django.core.mail import send_mail
from django.core.files.base import ContentFile
from django.utils.html import strip_tags
from .models import Course, Mentor, Student, Project, Employee, Department, Notification, IDCard, Certificate, CourseEnrollment, Payment, PasswordResetCode, Attendance
from .models import ProjectPayment
from .forms import CourseEnrollmentForm, EnrollmentFeeForm, PaymentForm, ProjectForm, ProjectPaymentForm, StudentForm
logger = logging.getLogger(__name__)
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
    form_data = {}
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')
        email = request.POST.get('email', '').strip()
        form_data = {'username': username, 'email': email}
        errors = []
        if not username:
            errors.append('Username is required.')
        elif username[0].isdigit():
            errors.append('Username must not start with a number.')
        elif User.objects.filter(username=username).exists():
            errors.append('Username already exists. Please choose another.')
        if not email:
            errors.append('Email is required.')
        if not password:
            errors.append('Password is required.')
        elif len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        if password != password2:
            errors.append('Passwords do not match.')
        if not errors:
            user = User.objects.create_user(username=username, password=password, email=email)
            student = Student.objects.create(user=user, name=username, email=email)
            try:
                student_group = Group.objects.get(name='student')
                user.groups.add(student_group)
            except Group.DoesNotExist:
                pass
            messages.success(request, 'Account created successfully. Please sign in.')
            return redirect('login')
        for error in errors:
            messages.error(request, error)
    return render(request, 'erp_app/register.html', {'form_data': form_data})

    #staff registration view with code verification and role assignment
def staff_register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        email = request.POST.get('email', '').strip()
        staff_type = request.POST.get('staff_type', '')
        staff_code = request.POST.get('staff_code', '').strip()

        expected_code = getattr(settings, 'STAFF_REGISTRATION_CODE', 'STAFF2024')
        errors = []
        if staff_code != expected_code:
            errors.append('Invalid staff registration code.')
        if not username:
            errors.append('Username is required.')
        elif username[0].isdigit():
            errors.append('Username must not start with a number.')
        elif User.objects.filter(username=username).exists():
            errors.append('Username already exists.')
        if not password:
            errors.append('Password is required.')
        elif len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        if staff_type not in ('teaching', 'normal'):
            errors.append('Invalid staff type.')
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'erp_app/staff_register.html')

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
        email = request.POST.get('email', '').strip()
        if not User.objects.filter(email=email).exists():
            messages.error(request, 'No account found with this email address.')
            return render(request, 'erp_app/password_reset.html')
        code = ''.join(random.choices(string.digits, k=6))
        PasswordResetCode.objects.create(email=email, code=code)
        subject = 'Password Reset Code — Auralith ERP'
        html_message = render_to_string('erp_app/email/password_reset_code.html', {
            'code': code,
        })
        plain_message = strip_tags(html_message)
        try:
            send_mail(subject, plain_message, None, [email], html_message=html_message)
        except Exception as e:
            logger.exception('Password reset email send failed: %s', e)
            messages.error(request, 'Failed to send reset code. Please try again.')
            return render(request, 'erp_app/password_reset.html')
        request.session['reset_email'] = email
        messages.success(request, 'A 6-digit code has been sent to your email.')
        return redirect('password_reset_verify')
    return render(request, 'erp_app/password_reset.html')


def password_reset_verify(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    email = request.session.get('reset_email')
    if not email:
        return redirect('password_reset')
    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        reset_code = PasswordResetCode.objects.filter(email=email, code=code, is_used=False).last()
        if not reset_code or reset_code.is_expired():
            messages.error(request, 'Invalid or expired code. Please request a new one.')
            return redirect('password_reset')
        request.session['reset_code_id'] = reset_code.id
        return redirect('password_reset_confirm')
    return render(request, 'erp_app/password_reset_verify.html')


def password_reset_confirm(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    code_id = request.session.get('reset_code_id')
    email = request.session.get('reset_email')
    if not code_id or not email:
        return redirect('password_reset')
    reset_code = PasswordResetCode.objects.filter(id=code_id, email=email, is_used=False).last()
    if not reset_code or reset_code.is_expired():
        messages.error(request, 'Session expired. Please request a new code.')
        return redirect('password_reset')
    if request.method == 'POST':
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')
        if not password or len(password) < 8:
            messages.error(request, 'Password must be at least 8 characters.')
            return render(request, 'erp_app/password_reset_confirm.html')
        if password != password2:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'erp_app/password_reset_confirm.html')
        user = User.objects.get(email=email)
        user.set_password(password)
        user.save()
        reset_code.is_used = True
        reset_code.save()
        del request.session['reset_email']
        del request.session['reset_code_id']
        messages.success(request, 'Password has been reset successfully. Please sign in.')
        return redirect('login')
    return render(request, 'erp_app/password_reset_confirm.html')


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


def _can_manage_company_records(user):
    return has_role(user, SUPER_ADMIN, NORMAL_STAFF)


@login_required
def students(request):
    if not _can_manage_company_records(request.user):
        messages.error(request, 'You do not have permission to manage students.')
        return redirect('dashboard')
    query = request.GET.get('q', '').strip()
    items = Student.objects.prefetch_related(
        Prefetch('enrollments', queryset=CourseEnrollment.objects.prefetch_related('payments'))
    )
    if query:
        items = items.filter(Q(name__icontains=query) | Q(email__icontains=query) | Q(phone__icontains=query))
    for student in items:
        enrollments = list(student.enrollments.all())
        for enrollment in enrollments:
            enrollment.paid_amount = sum((payment.amount for payment in enrollment.payments.all()), 0)
        student.total_fees = sum((enrollment.total_fee for enrollment in enrollments), 0)
        student.paid_total = sum((enrollment.paid_amount for enrollment in enrollments), 0)
        student.remaining_total = max(student.total_fees - student.paid_total, 0)
    return render(request, 'erp_app/students.html', {'students': items, 'query': query, 'is_admin': True})


@login_required
@require_http_methods(['GET', 'POST'])
def student_add(request):
    if not _can_manage_company_records(request.user):
        messages.error(request, 'You do not have permission to add students.')
        return redirect('dashboard')
    student_form = StudentForm(request.POST or None)
    enrollment_form = CourseEnrollmentForm(request.POST or None, prefix='enrollment')
    if request.method == 'POST' and student_form.is_valid():
        has_course = bool(request.POST.get('enrollment-course'))
        if has_course and not enrollment_form.is_valid():
            return render(request, 'erp_app/student_form.html', {'form': student_form, 'enrollment_form': enrollment_form, 'is_edit': False})
        with transaction.atomic():
            student = student_form.save()
            if has_course:
                enrollment = enrollment_form.save(commit=False)
                enrollment.student = student
                enrollment.save()
        messages.success(request, f'Student {student.name} was added.')
        return redirect('student_detail', student_id=student.id)
    return render(request, 'erp_app/student_form.html', {'form': student_form, 'enrollment_form': enrollment_form, 'is_edit': False})


@login_required
@require_http_methods(['GET', 'POST'])
def student_edit(request, student_id):
    if not _can_manage_company_records(request.user):
        messages.error(request, 'You do not have permission to edit students.')
        return redirect('dashboard')
    student = get_object_or_404(Student, pk=student_id)
    form = StudentForm(request.POST or None, instance=student)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            student = form.save()
            if student.user:
                student.user.email = student.email
                student.user.first_name = student.name.split(' ', 1)[0]
                student.user.last_name = student.name.split(' ', 1)[1] if ' ' in student.name else ''
                student.user.save(update_fields=['email', 'first_name', 'last_name'])
        messages.success(request, f'Student {student.name} was updated.')
        return redirect('student_detail', student_id=student.id)
    return render(request, 'erp_app/student_form.html', {'form': form, 'is_edit': True, 'student': student})


@login_required
def student_detail(request, student_id):
    if not _can_manage_company_records(request.user):
        messages.error(request, 'You do not have permission to view student financial records.')
        return redirect('dashboard')
    student = get_object_or_404(Student, pk=student_id)
    enrollments = CourseEnrollment.objects.filter(student=student).select_related('course').prefetch_related('payments')
    total_fees = paid_total = 0
    for enrollment in enrollments:
        enrollment.paid_amount = sum((payment.amount for payment in enrollment.payments.all()), 0)
        enrollment.remaining_amount = max(enrollment.total_fee - enrollment.paid_amount, 0)
        total_fees += enrollment.total_fee
        paid_total += enrollment.paid_amount
    return render(request, 'erp_app/student_detail.html', {
        'student': student, 'enrollments': enrollments, 'total_fees': total_fees,
        'paid_total': paid_total, 'remaining_total': max(total_fees - paid_total, 0),
        'enrollment_form': CourseEnrollmentForm(), 'payment_form': PaymentForm(), 'is_admin': True,
    })


@login_required
@require_POST
def student_finance_action(request, student_id):
    if not _can_manage_company_records(request.user):
        messages.error(request, 'You do not have permission to change student fees or payments.')
        return redirect('dashboard')
    student = get_object_or_404(Student, pk=student_id)
    action = request.POST.get('action')
    if action == 'add_enrollment':
        form = CourseEnrollmentForm(request.POST)
        if form.is_valid():
            enrollment = form.save(commit=False)
            enrollment.student = student
            try:
                with transaction.atomic():
                    enrollment.save()
                messages.success(request, f'{enrollment.course.name} was added to {student.name}.')
            except IntegrityError:
                messages.error(request, 'This student is already enrolled in that course.')
        else:
            messages.error(request, form.errors.as_text())
    elif action in ('record_payment', 'update_fee'):
        form = PaymentForm(request.POST) if action == 'record_payment' else EnrollmentFeeForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                enrollment = get_object_or_404(CourseEnrollment.objects.select_for_update(), pk=request.POST.get('enrollment_id'), student=student)
                paid = enrollment.total_paid()
                if action == 'record_payment':
                    remaining = max(enrollment.total_fee - paid, 0)
                    if form.cleaned_data['amount'] > remaining:
                        messages.error(request, f'Payment exceeds the remaining balance of Rs. {remaining}.')
                    else:
                        payment = form.save(commit=False)
                        payment.enrollment = enrollment
                        payment.save()
                        messages.success(request, f'Payment of Rs. {payment.amount} recorded.')
                elif form.cleaned_data['total_fee'] < paid:
                    messages.error(request, 'Course fee cannot be less than the amount already paid.')
                else:
                    enrollment.total_fee = form.cleaned_data['total_fee']
                    enrollment.save(update_fields=['total_fee'])
                    messages.success(request, 'Course fee updated.')
        else:
            messages.error(request, form.errors.as_text())
    else:
        messages.error(request, 'Choose a valid student finance action.')
    return redirect('student_detail', student_id=student.id)


@login_required
@require_POST
def student_delete(request, student_id):
    if not _can_manage_company_records(request.user):
        messages.error(request, 'You do not have permission to delete students.')
        return redirect('dashboard')
    student = get_object_or_404(Student, pk=student_id)
    name = student.name
    for card in student.id_cards.all():
        card.file.delete(save=False)
    for certificate in student.certificates.all():
        if certificate.file:
            certificate.file.delete(save=False)
    student.delete()
    messages.success(request, f'Student {name} and associated enrollment/payment records were deleted.')
    return redirect('students')

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

class _MentorRow:
    """Wraps a Mentor model instance to look like an Employee for the table template."""
    def __init__(self, mentor):
        self.name = mentor.name
        self.email = mentor.email
        self.department = mentor.department
        self.role = mentor.specialization
        self.employee_type = 'mentor'
        self.joined_date = mentor.joined_date
    def get_employee_type_display(self):
        return 'Mentor'

@login_required
def employees(request):
    employee_type = request.GET.get('type', '')
    emp_list = list(Employee.objects.select_related('department').all())
    mentor_rows = [_MentorRow(m) for m in Mentor.objects.annotate(course_count=Count('course')).all()]

    if employee_type:
        if employee_type == 'mentor':
            combined = mentor_rows
        else:
            combined = [e for e in emp_list if e.employee_type == employee_type]
    else:
        combined = sorted(emp_list + mentor_rows, key=lambda e: e.name.lower())

    context = {
        'employees': combined,
        'types': Employee.EMPLOYEE_TYPES,
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
        if request.POST.get('action') == 'generate':
            try:
                card = _generate_saved_id_card(card_type, request.POST.get('owner_id'), request.POST.get('course_id'))
                Notification.objects.create(
                    title=f'{card.get_card_type_display()} ID generated',
                    message=f'{card.get_card_type_display()} ID card for {card.owner_name} has been generated.',
                    created_by=request.user,
                )
                messages.success(request, f'{card.get_card_type_display()} ID card generated for {card.owner_name}.')
            except (Student.DoesNotExist, Employee.DoesNotExist, Course.DoesNotExist, ValueError) as error:
                messages.error(request, str(error))
            return redirect('id_generation')
        uploaded_file = request.FILES.get('id_card_file')
        owner_id = request.POST.get('owner_id')

        if not card_type or not owner_id or not uploaded_file:
            messages.error(request, 'Please select a valid user and upload an ID card image.')
        elif uploaded_file.size > 10 * 1024 * 1024:
            messages.error(request, 'ID card images must be 10 MB or smaller.')
        elif not uploaded_file.content_type.startswith('image/'):
            messages.error(request, 'Choose a valid image file for the ID card.')
        else:
            try:
                image = Image.open(uploaded_file)
                image.verify()
                uploaded_file.seek(0)
            except Exception:
                messages.error(request, 'The selected file is not a readable image.')
                return redirect('id_generation')
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


def _generate_saved_id_card(card_type, owner_id, course_id=None):
    if card_type == 'student':
        try:
            student = Student.objects.get(pk=int(owner_id))
        except (Student.DoesNotExist, TypeError, ValueError) as error:
            raise Student.DoesNotExist('Select a valid student.') from error
        if not course_id:
            raise ValueError('Select a course for the student ID card.')
        try:
            course = Course.objects.get(pk=int(course_id))
        except (Course.DoesNotExist, TypeError, ValueError) as error:
            raise Course.DoesNotExist('Select a valid course.') from error
        code = f'STU-{student.pk:05d}-{course.pk:05d}'
        owner = student
        details = [student.email, student.phone or 'N/A', course.name]
        qr_data = {
            'type': 'STUDENT_ID', 'id': code, 'name': student.name,
            'email': student.email, 'phone': student.phone or 'N/A',
            'course': course.name, 'category': course.get_category_display(),
            'enrolled_date': student.enrolled_date.isoformat(),
        }
    elif card_type == 'employee':
        try:
            employee = Employee.objects.select_related('department').get(pk=int(owner_id))
        except (Employee.DoesNotExist, TypeError, ValueError) as error:
            raise Employee.DoesNotExist('Select a valid employee.') from error
        code = f'EMP-{employee.pk:05d}'
        owner = employee
        details = [employee.email, employee.role or employee.get_employee_type_display(),
                   employee.department.name if employee.department else 'Auralith Bit']
        qr_data = {
            'type': 'EMPLOYEE_ID', 'id': code, 'name': employee.name,
            'email': employee.email, 'role': employee.role or 'N/A',
            'department': employee.department.name if employee.department else 'N/A',
            'employee_type': employee.get_employee_type_display(),
            'joined_date': employee.joined_date.isoformat(),
        }
    else:
        raise ValueError('Choose a valid card type.')

    from PIL import ImageDraw, ImageFont
    image = Image.new('RGB', (1011, 638), '#F7F9FC')
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((8, 8, 1002, 630), radius=34, fill='#FFFFFF', outline='#1A4B8D', width=10)
    draw.rounded_rectangle((14, 14, 996, 112), radius=25, fill='#1A4B8D')
    font_dir = Path(ImageFont.__file__).parent / 'fonts'
    regular_fonts = [Path('C:/Windows/Fonts/arial.ttf'), font_dir / 'DejaVuSans.ttf',
                     Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
                     Path('/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf')]
    bold_fonts = [Path('C:/Windows/Fonts/arialbd.ttf'), font_dir / 'DejaVuSans-Bold.ttf',
                  Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),
                  Path('/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf')]
    def choose_font(candidates, size):
        for candidate in candidates:
            if candidate.exists():
                return ImageFont.truetype(str(candidate), size)
        return ImageFont.load_default()
    def draw_label(position, text, fill, font):
        try:
            draw.text(position, text, fill=fill, font=font)
        except UnicodeEncodeError:
            draw.text(position, text.encode('latin-1', 'replace').decode('latin-1'), fill=fill, font=ImageFont.load_default())
    draw_label((48, 37), 'AURALITH BIT', '#FFFFFF', choose_font(bold_fonts, 37))
    draw_label((50, 125), f'{card_type.upper()} IDENTITY CARD', '#9A7136', choose_font(regular_fonts, 19))
    draw_label((50, 184), owner.name[:32], '#153D68', choose_font(bold_fonts, 42))
    body_font = choose_font(regular_fonts, 25)
    y = 260
    for line in details:
        for wrapped in _wrap_words(line, 34)[:2]:
            draw_label((55, y), wrapped, '#334155', body_font)
            y += 43
        y += 7
    qr = qrcode.QRCode(box_size=7, border=2)
    qr.add_data(json.dumps(qr_data, ensure_ascii=False))
    qr.make(fit=True)
    image.paste(qr.make_image(fill_color='#153D68', back_color='white').convert('RGB').resize((240, 240)), (720, 200))
    draw_label((762, 455), code, '#1A4B8D', choose_font(regular_fonts, 19))
    draw.line((48, 562, 963, 562), fill='#D9B55D', width=3)
    draw_label((50, 577), 'DESIGN | DEVELOP | DELIVER', '#64748B', choose_font(regular_fonts, 19))
    output = io.BytesIO()
    image.save(output, format='PNG', optimize=True)
    card = IDCard(card_type=card_type, student=owner if card_type == 'student' else None,
                  employee=owner if card_type == 'employee' else None)
    card.file.save(f'{code}.png', ContentFile(output.getvalue()), save=True)
    return card

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
        card.file.delete(save=False)
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
    enrollments = CourseEnrollment.objects.prefetch_related('payments')
    course_fees = sum((enrollment.total_fee for enrollment in enrollments), 0)
    student_payments = sum((payment.amount for enrollment in enrollments for payment in enrollment.payments.all()), 0)
    project_list = Project.objects.prefetch_related('payments')
    projects = []
    for project in project_list:
        project.paid_total = sum((payment.amount for payment in project.payments.all()), 0)
        project.remaining_total = max(project.budget - project.paid_total, 0)
        projects.append(project)
    project_value = sum((project.budget for project in projects), 0)
    project_paid = sum((project.paid_total for project in projects), 0)
    context = {
        'course_fees': course_fees,
        'student_payments': student_payments,
        'student_remaining': max(course_fees - student_payments, 0),
        'projects': projects,
        'project_value': project_value,
        'project_paid': project_paid,
        'project_remaining': sum((project.remaining_total for project in projects), 0),
        'is_admin': has_role(request.user, SUPER_ADMIN, NORMAL_STAFF),
    }
    return render(request, 'erp_app/budget_fees.html', context)


@login_required
@require_http_methods(['GET', 'POST'])
def projects(request):
    if not _can_manage_company_records(request.user):
        messages.error(request, 'You do not have permission to manage client projects.')
        return redirect('dashboard')
    form = ProjectForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        project = form.save()
        messages.success(request, f'Client project {project.name} was added.')
        return redirect('project_detail', project_id=project.id)
    items = Project.objects.prefetch_related('payments')
    totals = {'price': 0, 'paid': 0, 'remaining': 0}
    for project in items:
        project.paid_total = sum((payment.amount for payment in project.payments.all()), 0)
        project.remaining_total = max(project.budget - project.paid_total, 0)
        totals['price'] += project.budget
        totals['paid'] += project.paid_total
        totals['remaining'] += project.remaining_total
    return render(request, 'erp_app/projects.html', {'projects': items, 'form': form, 'totals': totals, 'is_admin': True})


@login_required
@require_http_methods(['GET', 'POST'])
def project_edit(request, project_id):
    if not _can_manage_company_records(request.user):
        messages.error(request, 'You do not have permission to edit client projects.')
        return redirect('dashboard')
    project = get_object_or_404(Project.objects.prefetch_related('payments'), pk=project_id)
    form = ProjectForm(request.POST or None, instance=project)
    if request.method == 'POST' and form.is_valid():
        paid = sum((payment.amount for payment in project.payments.all()), 0)
        if form.cleaned_data['budget'] < paid:
            form.add_error('budget', f'Project price cannot be less than the Rs. {paid} already received.')
        else:
            form.save()
            messages.success(request, f'Client project {project.name} was updated.')
            return redirect('project_detail', project_id=project.id)
    return render(request, 'erp_app/project_form.html', {'form': form, 'project': project, 'is_edit': True})


@login_required
@require_http_methods(['GET', 'POST'])
def project_detail(request, project_id):
    if not _can_manage_company_records(request.user):
        messages.error(request, 'You do not have permission to view client project financials.')
        return redirect('dashboard')
    project = get_object_or_404(Project.objects.prefetch_related('payments'), pk=project_id)
    if request.method == 'POST':
        form = ProjectPaymentForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                project = get_object_or_404(Project.objects.select_for_update(), pk=project_id)
                paid = project.amount_paid()
                remaining = max(project.budget - paid, 0)
                if form.cleaned_data['amount'] > remaining:
                    form.add_error('amount', f'Payment cannot exceed the remaining balance of Rs. {remaining}.')
                else:
                    payment = form.save(commit=False)
                    payment.project = project
                    payment.recorded_by = request.user
                    payment.save()
                    messages.success(request, f'Payment of Rs. {payment.amount} recorded for {project.name}.')
                    return redirect('project_detail', project_id=project.id)
    else:
        form = ProjectPaymentForm()
    project.paid_total = sum((payment.amount for payment in project.payments.all()), 0)
    project.remaining_total = max(project.budget - project.paid_total, 0)
    return render(request, 'erp_app/project_detail.html', {'project': project, 'form': form, 'is_admin': True})


@login_required
@require_POST
def project_delete(request, project_id):
    if not _can_manage_company_records(request.user):
        messages.error(request, 'You do not have permission to delete client projects.')
        return redirect('dashboard')
    project = get_object_or_404(Project, pk=project_id)
    name = project.name
    project.delete()
    messages.success(request, f'Client project {name} and its payment history were deleted.')
    return redirect('projects')

@login_required
def attendance(request):
    if not has_role(request.user, SUPER_ADMIN, TEACHING_STAFF):
        return redirect('dashboard')

    courses = Course.objects.all()
    selected_course_id = request.GET.get('course_id') or request.POST.get('course_id')
    selected_date = request.GET.get('date') or request.POST.get('date') or today_bs()

    enrollments = []
    existing_records = {}

    if selected_course_id:
        enrollments = CourseEnrollment.objects.filter(
            course_id=selected_course_id,
            status='active'
        ).select_related('student', 'course')

        existing = Attendance.objects.filter(
            course_id=selected_course_id,
            date=selected_date
        )
        for rec in existing:
            existing_records[rec.student_id] = rec.status

    if request.method == 'POST':
        course_id = request.POST.get('course_id')
        att_date = request.POST.get('date')

        if course_id and att_date:
            active_enrollments = CourseEnrollment.objects.filter(
                course_id=course_id,
                status='active'
            ).select_related('student')

            saved = 0
            for enrollment in active_enrollments:
                sid = str(enrollment.student_id)
                status = request.POST.get(f'status_{sid}')
                if status in ('P', 'A', 'L'):
                    Attendance.objects.update_or_create(
                        student_id=enrollment.student_id,
                        course_id=course_id,
                        date=att_date,
                        defaults={
                            'status': status,
                            'marked_by': request.user,
                        }
                    )
                    saved += 1
            if saved:
                messages.success(request, f'Attendance saved for {saved} student(s).')
            return redirect(f'{reverse("attendance")}?course_id={course_id}&date={att_date}')

    context = {
        'courses': courses,
        'selected_course_id': int(selected_course_id) if selected_course_id else None,
        'selected_date': selected_date,
        'enrollments': enrollments,
        'existing_records': existing_records,
        'is_admin': has_role(request.user, SUPER_ADMIN, TEACHING_STAFF),
    }
    return render(request, 'erp_app/attendance.html', context)

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
        valid_types = {choice[0] for choice in Certificate.CERTIFICATE_TYPES}
        if not student_id:
            messages.error(request, 'Please select a student.')
        elif certificate_type not in valid_types:
            messages.error(request, 'Choose a valid certificate type.')
        else:
            student = Student.objects.filter(id=student_id).first()
            if not student:
                messages.error(request, 'The selected student was not found.')
                return redirect('issue_certificate')
            course = None
            if course_id:
                course = Course.objects.filter(id=course_id).first()
                if not course:
                    messages.error(request, 'The selected course was not found.')
                    return redirect('issue_certificate')
            if certificate_type in ('course', 'workshop') and not course and not request.POST.get('program_title', '').strip():
                messages.error(request, 'Select a course or enter a program title.')
                return redirect('issue_certificate')

            uploaded_file = request.FILES.get('certificate_file')
            if uploaded_file and (not uploaded_file.name.lower().endswith('.pdf') or uploaded_file.content_type != 'application/pdf'):
                messages.error(request, 'The uploaded certificate must be a PDF file.')
                return redirect('issue_certificate')
            if uploaded_file and uploaded_file.size > 10 * 1024 * 1024:
                messages.error(request, 'The uploaded PDF must be 10 MB or smaller.')
                return redirect('issue_certificate')

            cert = Certificate.objects.create(
                student=student,
                course=course if certificate_type in ('course', 'workshop') else None,
                certificate_type=certificate_type,
                status='issued',
                file=uploaded_file,
                program_title=request.POST.get('program_title', '').strip(),
                program_start_date=request.POST.get('program_start_date', '').strip(),
                location=request.POST.get('location', '').strip() or 'Auralith Bit',
                internship_details=internship_details,
                authorized_signer_name=request.POST.get('authorized_signer_name', '').strip() or 'Authorized Signatory',
                authorized_signer_title=request.POST.get('authorized_signer_title', '').strip() or 'Company Representative',
                authorized_signature_text=request.POST.get('authorized_signature_text', '').strip(),
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

    if cert.status != 'issued':
        messages.error(request, 'This certificate is not currently valid for viewing.')
        return redirect('certificates')

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

def _write_simple_certificate_pdf(certificate):
    page_width, page_height = 792, 612
    blue = (26 / 255, 75 / 255, 141 / 255)
    pink = (222 / 255, 43 / 255, 93 / 255)
    slate = (30 / 255, 41 / 255, 59 / 255)
    muted = (100 / 255, 116 / 255, 139 / 255)
    light = (226 / 255, 232 / 255, 240 / 255)
    gold = (217 / 255, 181 / 255, 93 / 255)

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
        f'{blue[0]:.3f} {blue[1]:.3f} {blue[2]:.3f} rg 0 0 792 612 re f',
        f'{gold[0]:.3f} {gold[1]:.3f} {gold[2]:.3f} RG 3 w 18 18 756 576 re S',
        '1 1 1 rg 28 28 736 556 re f',
        f'{light[0]:.3f} {light[1]:.3f} {light[2]:.3f} RG 1 w 38 38 716 536 re S',
    ]

    _pdf_text(commands, 'AURALITH BIT', page_width / 2, 516, 13, 'F2', blue, 'center')
    _pdf_text(commands, 'Design | Develop | Deliver', page_width / 2, 486, 18, 'F2', blue, 'center')
    commands.append(f'{pink[0]:.3f} {pink[1]:.3f} {pink[2]:.3f} rg 356 464 80 3 re f')

    _pdf_text(commands, certificate.certificate_heading, page_width / 2, 422, 26, 'F2', slate, 'center')
    _pdf_text(commands, 'PRESENTED TO', page_width / 2, 386, 11, 'F1', (0.58, 0.64, 0.72), 'center')
    _pdf_text(commands, certificate.student.name, page_width / 2, 346, 34, 'F2', blue, 'center')
    _pdf_text(commands, description_map.get(certificate.certificate_type, description_map['course']), page_width / 2, 316, 14, 'F1', muted, 'center')

    y = 286
    if certificate.certificate_type in ('course', 'workshop'):
        _pdf_text(commands, certificate.display_program_title, page_width / 2, y, 20, 'F2', pink, 'center')
        y -= 30
    elif certificate.certificate_type == 'internship' and certificate.internship_details:
        for line in _wrap_words(certificate.internship_details, 78)[:4]:
            _pdf_text(commands, line, page_width / 2, y, 12, 'F1', muted, 'center')
            y -= 18
        y -= 8

    _pdf_text(commands, note_map.get(certificate.certificate_type, note_map['course']), page_width / 2, y, 13, 'F1', muted, 'center')

    detail_y = 188
    details = [
        ('Starting Date', certificate.program_start_date or certificate.issue_date.strftime('%Y/%m/%d')),
        ('Location', certificate.location or 'Auralith Bit'),
        ('Certificate No.', certificate.certificate_number),
    ]
    for x, (label, value) in zip((210, 396, 582), details):
        _pdf_text(commands, label.upper(), x, detail_y, 9, 'F1', (0.58, 0.64, 0.72), 'center')
        _pdf_text(commands, value, x, detail_y - 22, 14, 'F2', slate, 'center')

    commands.append(f'{light[0]:.3f} {light[1]:.3f} {light[2]:.3f} RG 1 w 172 122 m 620 122 l S')
    for x, name, label in ((250, certificate.authorized_signer_name or 'Authorized Signatory', certificate.authorized_signer_title or 'Company Representative'), (542, certificate.ceo_founder_name, certificate.ceo_founder_title)):
        signature_text = certificate.dynamic_signature if x == 250 else certificate.ceo_founder_signature
        _pdf_text(commands, signature_text, x, 112, 13, 'F2', blue, 'center')
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

    return bytes(pdf)


@login_required
def download_certificate(request, cert_id):
    cert = get_object_or_404(Certificate, id=cert_id)

    if cert.status != 'issued':
        messages.error(request, 'This certificate is not currently valid for download.')
        return redirect('certificates')

    if not has_role(request.user, SUPER_ADMIN, TEACHING_STAFF, NORMAL_STAFF):
        if not hasattr(request.user, 'student_profile') or request.user.student_profile != cert.student:
            messages.error(request, 'You do not have access to this certificate.')
            return redirect('certificates')

    if cert.file and request.GET.get('force') != '1':
        try:
            cert.file.open('rb')
            return FileResponse(cert.file, as_attachment=True, filename=f'{cert.certificate_number}.pdf')
        except (FileNotFoundError, OSError):
            cert.file = None

    if cert.file:
        cert.file.delete(save=False)
        cert.file = None
    try:
        pdf_content = _write_simple_certificate_pdf(cert)
        cert.file.save(f'{cert.certificate_number}.pdf', ContentFile(pdf_content), save=True)
        cert.file.open('rb')
        return FileResponse(cert.file, as_attachment=True, filename=f'{cert.certificate_number}.pdf')
    except Exception as e:
        messages.error(request, f'Could not generate PDF: {e}')
        return redirect('preview_certificate', cert_id=cert.id)


@login_required
def my_courses(request):
    if not hasattr(request.user, 'student_profile'):
        messages.error(request, 'Only students can access this page.')
        return redirect('dashboard')
    student = request.user.student_profile
    enrollments = CourseEnrollment.objects.filter(
        student=student, status__in=['active', 'completed']
    ).select_related('course').prefetch_related('payments')
    if not enrollments:
        messages.info(request, 'You are not enrolled in any courses yet.')
    roles = get_user_roles(request.user)
    context = {
        'enrollments': enrollments,
        'is_any_staff': has_role(request.user, SUPER_ADMIN, TEACHING_STAFF, NORMAL_STAFF),
        'is_super_admin': SUPER_ADMIN in roles,
        'is_teaching_staff': TEACHING_STAFF in roles,
        'is_normal_staff': NORMAL_STAFF in roles,
    }
    return render(request, 'erp_app/my_courses.html', context)


def send_payment_receipt(request, enrollment_id):
    if not request.user.is_authenticated:
        return redirect('login')
    if not has_role(request.user, SUPER_ADMIN, TEACHING_STAFF, NORMAL_STAFF):
        messages.error(request, 'You do not have permission to send receipts.')
        return redirect('dashboard')

    enrollment = get_object_or_404(
        CourseEnrollment.objects.select_related('student', 'course').prefetch_related('payments'),
        id=enrollment_id
    )
    payments = enrollment.payments.all()

    try:
        subject = f'Payment Receipt — {enrollment.course.name}'
        html_message = render_to_string('erp_app/email/payment_receipt.html', {
            'enrollment': enrollment,
            'payments': payments,
        })
        plain_message = strip_tags(html_message)
        recipient = enrollment.student.email

        send_mail(subject, plain_message, None, [recipient], html_message=html_message)
        Notification.objects.create(
            title='Receipt Sent',
            message=f'Payment receipt for {enrollment.course.name} sent to {enrollment.student.name} ({recipient}).',
            created_by=request.user,
        )
        messages.success(request, f'Receipt sent to {enrollment.student.email}')
    except Exception as e:
        logger.exception('Failed to send payment receipt for enrollment %s: %s', enrollment_id, e)
        messages.error(request, f'Failed to send receipt: {e}')

    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))
