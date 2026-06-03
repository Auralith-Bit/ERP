from django.contrib import admin
from django.db.models import Count
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.utils.html import format_html, strip_tags
from .models import Mentor, Department, Course, Student, CourseEnrollment, Employee, Project, Notification, IDCard, Certificate, Payment


class CourseEnrollmentInline(admin.TabularInline):
    model = CourseEnrollment
    extra = 1


@admin.register(Mentor)
class MentorAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'department', 'specialization', 'course_count', 'joined_date']
    list_filter = ['department']
    search_fields = ['name', 'email', 'specialization']

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(course_count=Count('course'))

    def course_count(self, obj):
        return obj.course_count
    course_count.short_description = 'Courses'


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'employee_count']
    search_fields = ['name']

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(employee_count=Count('employee'))

    def employee_count(self, obj):
        return obj.employee_count
    employee_count.short_description = 'Employees'


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['name', 'mentor', 'category', 'status', 'enrolled_students_count', 'duration_weeks']
    list_filter = ['status', 'category']
    search_fields = ['name', 'mentor__name']
    inlines = [CourseEnrollmentInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(enrollment_count=Count('enrollments'))

    def enrolled_students_count(self, obj):
        return obj.enrollment_count
    enrolled_students_count.short_description = 'Enrolled'


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'created_by', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['title', 'message', 'created_by__username']


@admin.register(IDCard)
class IDCardAdmin(admin.ModelAdmin):
    list_display = ['card_type', 'owner_name', 'file', 'uploaded_at']
    list_filter = ['card_type', 'uploaded_at']
    search_fields = ['student__name', 'employee__name']


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'phone', 'is_intern', 'enrolled_date', 'course_count']
    list_filter = ['is_intern']
    search_fields = ['name', 'email']

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(course_count=Count('enrollments'))

    def course_count(self, obj):
        return obj.course_count
    course_count.short_description = 'Courses'


@admin.register(CourseEnrollment)
class CourseEnrollmentAdmin(admin.ModelAdmin):
    list_display = ['student', 'course', 'total_fee', 'total_paid_display', 'pending_fee_display', 'payment_status_display', 'enrolled_date', 'status']
    list_filter = ['status']
    search_fields = ['student__name', 'course__name']
    actions = ['send_receipt']

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('payments')

    def total_paid_display(self, obj):
        return obj.total_paid()
    total_paid_display.short_description = 'Paid'

    def pending_fee_display(self, obj):
        return obj.pending_fee()
    pending_fee_display.short_description = 'Pending'

    def payment_status_display(self, obj):
        status = obj.payment_status_text()
        colors = {'Completed': 'green', 'Partial': 'orange', 'Pending': 'red'}
        color = colors.get(status, 'gray')
        return format_html('<span style="color:{};font-weight:600;">{}</span>', color, status)
    payment_status_display.short_description = 'Payment'

    def send_receipt(self, request, queryset):
        sent = 0
        for enrollment in queryset.select_related('student', 'course').prefetch_related('payments'):
            payments = enrollment.payments.all()
            subject = f'Payment Receipt — {enrollment.course.name}'
            html_message = render_to_string('erp_app/email/payment_receipt.html', {
                'enrollment': enrollment,
                'payments': payments,
            })
            plain_message = strip_tags(html_message)
            try:
                send_mail(subject, plain_message, None, [enrollment.student.email], html_message=html_message)
                Notification.objects.create(
                    title='Receipt Sent',
                    message=f'Payment receipt for {enrollment.course.name} sent to {enrollment.student.name}.',
                    created_by=request.user,
                )
                sent += 1
            except Exception as e:
                self.message_user(request, f'Failed for {enrollment.student.email}: {e}', level='ERROR')
        self.message_user(request, f'Receipt sent to {sent} student(s).')
    send_receipt.short_description = 'Send payment receipt to selected enrollments'


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['enrollment', 'amount', 'payment_date', 'transaction_id']
    list_filter = ['payment_date']
    search_fields = ['enrollment__student__name', 'enrollment__course__name', 'transaction_id']


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'department', 'role', 'employee_type', 'joined_date']
    list_filter = ['employee_type', 'department']
    search_fields = ['name', 'email', 'role']

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['extra_mentors'] = Mentor.objects.annotate(course_count=Count('course')).all()
        return super().changelist_view(request, extra_context)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'client', 'status', 'progress_percentage']
    list_filter = ['status']
    search_fields = ['name', 'client']


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ['certificate_number', 'student', 'certificate_type', 'display_program_title', 'issue_date', 'status']
    list_filter = ['certificate_type', 'status', 'issue_date']
    search_fields = ['certificate_number', 'student__name', 'course__name', 'program_title', 'authorized_signer_name']
    readonly_fields = ['certificate_number', 'issue_date', 'created_at']
    fieldsets = [
        (None, {'fields': ['student', 'certificate_type', 'course', 'status']}),
        ('Certificate Info', {'fields': ['certificate_number', 'issue_date', 'program_title', 'program_start_date', 'location']}),
        ('Internship Details', {'fields': ['internship_details'], 'classes': ['collapse']}),
        ('Dynamic Signer', {'fields': ['authorized_signer_name', 'authorized_signer_title', 'authorized_signature_text']}),
        ('File', {'fields': ['file']}),
        ('Metadata', {'fields': ['created_at'], 'classes': ['collapse']}),
    ]
    actions = ['revoke_certificates', 'reissue_certificates']

    def revoke_certificates(self, request, queryset):
        updated = queryset.update(status='revoked')
        self.message_user(request, f'{updated} certificate(s) revoked.')
    revoke_certificates.short_description = 'Revoke selected certificates'

    def reissue_certificates(self, request, queryset):
        updated = queryset.update(status='issued')
        self.message_user(request, f'{updated} certificate(s) re-issued.')
    reissue_certificates.short_description = 'Re-issue selected certificates'
