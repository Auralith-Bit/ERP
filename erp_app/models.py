import secrets
from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
import datetime
import uuid


# ── Role Constants ──────────────────────────────────────────────
ROLES = {
    'SUPER_ADMIN': 'super_admin',
    'TEACHING_STAFF': 'teaching_staff',
    'NORMAL_STAFF': 'normal_staff',
    'STUDENT': 'student',
    'INTERN': 'intern',
}

ROLE_CHOICES = [(v, v.replace('_', ' ').title()) for v in ROLES.values()]


class Mentor(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    specialization = models.CharField(max_length=200)
    bio = models.TextField(blank=True)
    department = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True)
    joined_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Department(models.Model):
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Course(models.Model):
    STATUS_CHOICES = [
        ('live', 'Live'),
        ('upcoming', 'Upcoming'),
        ('enrollment', 'Enrollment'),
        ('completed', 'Completed'),
    ]
    CATEGORY_CHOICES = [
        ('development', 'Development'),
        ('design', 'UI/UX'),
        ('qa', 'Digital Marketing'),
        ('marketing', 'Graphic Designing'),
    ]

    name = models.CharField(max_length=200)
    mentor = models.ForeignKey(Mentor, on_delete=models.SET_NULL, null=True, blank=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='development')
    duration_weeks = models.PositiveIntegerField(default=8)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='enrollment')
    description = models.TextField(blank=True)
    syllabus = models.FileField(upload_to='syllabi/', null=True, blank=True)
    students_count = models.PositiveIntegerField(default=0)
    completion_percent = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, related_name='student_profile')
    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    photo = models.ImageField(upload_to='profile_photos/', blank=True, null=True)
    mentor = models.ForeignKey('Mentor', on_delete=models.SET_NULL, null=True, blank=True, related_name='students')
    enrolled_date = models.DateField(default=datetime.date.today, null=True, blank=True)
    is_intern = models.BooleanField(default=False)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class CourseEnrollment(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('dropped', 'Dropped'),
    ]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    total_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    enrolled_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    class Meta:
        unique_together = ['student', 'course']

    def __str__(self):
        return f"{self.student.name} -> {self.course.name}"

    def total_paid(self):
        return self.payments.aggregate(total=models.Sum('amount'))['total'] or 0

    def pending_fee(self):
        return self.total_fee - self.total_paid()

    def is_fully_paid(self):
        return self.pending_fee() <= 0

    def payment_status_text(self):
        if self.is_fully_paid():
            return 'Completed'
        if self.total_paid() > 0:
            return 'Partial'
        return 'Pending'


class Payment(models.Model):
    enrollment = models.ForeignKey(CourseEnrollment, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateTimeField(auto_now_add=True)
    transaction_id = models.CharField(max_length=100, blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ['-payment_date']

    def __str__(self):
        return f"Payment of {self.amount} for {self.enrollment}"


class Certificate(models.Model):
    CERTIFICATE_TYPES = [
        ('course', 'Course'),
        ('internship', 'Internship'),
        ('workshop', 'Workshop'),
    ]
    STATUS_CHOICES = [
        ('issued', 'Issued'),
        ('pending', 'Pending'),
        ('revoked', 'Revoked'),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='certificates')
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True, related_name='certificates')
    certificate_type = models.CharField(max_length=20, choices=CERTIFICATE_TYPES)
    certificate_number = models.CharField(max_length=50, unique=True, editable=False)
    issue_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='issued')
    file = models.FileField(upload_to='certificates/', null=True, blank=True)
    program_title = models.CharField(max_length=255, blank=True, help_text='Course, workshop, internship, or certificate program title')
    program_start_date = models.CharField(max_length=40, blank=True, help_text='Display value for the start date, e.g. 2082/11/25')
    location = models.CharField(max_length=150, default='Auralith Bit', blank=True)
    internship_details = models.TextField(blank=True, help_text='Project description, duration, or other internship details')
    authorized_signer_name = models.CharField(max_length=150, default='Supriya Dwivedi', blank=True)
    authorized_signer_title = models.CharField(max_length=150, default='Full Stack Developer', blank=True)
    authorized_signature_text = models.CharField(max_length=150, blank=True, help_text='Optional digital signature text for the dynamic signer')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-issue_date']
        permissions = [
            ('can_issue_certificates', 'Can issue certificates'),
        ]

    def __str__(self):
        return f"{self.certificate_number} - {self.student.name}"

    @property
    def effective_program_start_date(self):
        if self.program_start_date:
            return self.program_start_date
        if self.student and self.student.enrolled_date:
            return self.student.enrolled_date.strftime('%Y/%m/%d')
        if self.issue_date:
            return self.issue_date.strftime('%Y/%m/%d')
        return ''

    @property
    def ceo_founder_name(self):
        return 'Aakriti Bista'

    @property
    def ceo_founder_title(self):
        return 'CEO and Founder'

    @property
    def ceo_founder_signature(self):
        return 'Aakriti Bista'

    @property
    def dynamic_signature(self):
        return self.authorized_signature_text or self.authorized_signer_name or 'Authorized Signature'

    @property
    def mentor_signer_name(self):
        if self.student and self.student.mentor:
            return self.student.mentor.name
        return 'Mentor'

    @property
    def mentor_signer_title(self):
        if self.student and self.student.mentor and self.student.mentor.specialization:
            return self.student.mentor.specialization
        return 'Mentor'

    @property
    def display_program_title(self):
        if self.program_title:
            return self.program_title
        if self.course:
            return self.course.name
        if self.certificate_type == 'internship':
            return 'Internship Program'
        return self.get_certificate_type_display()

    @property
    def certificate_heading(self):
        if self.certificate_type == 'internship':
            return 'Certificate of Internship'
        return 'Certificate of Completion'

    @property
    def completion_sentence(self):
        if self.certificate_type == 'workshop':
            return f'has successfully completed the {self.display_program_title} workshop conducted by Auralith Bit.'
        if self.certificate_type == 'internship':
            return f'has successfully completed the {self.display_program_title} at Auralith Bit.'
        return f'has successfully completed the {self.display_program_title} course conducted by Auralith Bit.'

    @property
    def certificate_body(self):
        if self.certificate_type == 'workshop':
            return 'During this workshop, the participant demonstrated dedication, creativity and enthusiasm while learning essential frontend development concepts including HTML, CSS and JavaScript along with practical implementation to build responsive and interactive web interfaces.'
        if self.certificate_type == 'internship':
            return self.internship_details or 'During this internship, the participant demonstrated professionalism, technical ability and commitment while contributing to assigned work.'
        return 'During this course, the participant demonstrated dedication, consistency and practical understanding while strengthening their professional skills.'

    @staticmethod
    def generate_certificate_number():
        year = datetime.date.today().year
        prefix = f"CERT-{year}-"
        last = Certificate.objects.filter(certificate_number__startswith=prefix).order_by('certificate_number').last()
        if last:
            seq = int(last.certificate_number.split('-')[-1]) + 1
        else:
            seq = 1
        return f"{prefix}{seq:04d}"

    def save(self, *args, **kwargs):
        if not self.certificate_number:
            self.certificate_number = Certificate.generate_certificate_number()

        if not self.program_start_date:
            enrolled_date = getattr(self.student, 'enrolled_date', None) if self.student else None
            if isinstance(enrolled_date, str):
                try:
                    enrolled_date = datetime.datetime.strptime(enrolled_date, '%Y-%m-%d').date()
                except (TypeError, ValueError):
                    enrolled_date = None
            if enrolled_date:
                self.program_start_date = enrolled_date.strftime('%Y/%m/%d')
            elif self.issue_date:
                self.program_start_date = self.issue_date.strftime('%Y/%m/%d')

        tracked_fields = {'student_id', 'course_id', 'program_title', 'certificate_type', 'program_start_date',
                          'location', 'authorized_signer_name', 'authorized_signer_title',
                          'authorized_signature_text', 'internship_details'}

        if self.pk:
            try:
                old = Certificate.objects.get(pk=self.pk)
                for field in tracked_fields:
                    if getattr(old, field) != getattr(self, field):
                        if old.file:
                            old.file.delete(save=False)
                        self.file = None
                        break
            except Certificate.DoesNotExist:
                pass

        super().save(*args, **kwargs)


class IDCard(models.Model):
    CARD_TYPE_CHOICES = [
        ('student', 'Student'),
        ('employee', 'Employee'),
    ]
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('revoked', 'Revoked'),
    ]
    card_type = models.CharField(max_length=20, choices=CARD_TYPE_CHOICES)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, null=True, blank=True, related_name='id_cards')
    employee = models.ForeignKey('Employee', on_delete=models.CASCADE, null=True, blank=True, related_name='id_cards')
    file = models.FileField(upload_to='id_cards/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    code = models.CharField(max_length=100, blank=True, null=True)
    verify_token = models.CharField(max_length=64, unique=True, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    issued_at = models.DateTimeField(auto_now_add=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    show_contact_publicly = models.BooleanField(default=False)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        owner = self.student.name if self.card_type == 'student' and self.student else (self.employee.name if self.employee else 'Unknown')
        return f"{self.get_card_type_display()} ID for {owner}"

    @property
    def owner_name(self):
        if self.card_type == 'student' and self.student:
            return self.student.name
        if self.card_type == 'employee' and self.employee:
            return self.employee.name
        return 'Unknown'

    def generate_token(self):
        token = secrets.token_urlsafe(16)
        self.verify_token = token
        return token


class Employee(models.Model):
    EMPLOYEE_TYPES = [
        ('intern', 'Intern'),
        ('staff', 'Staff'),
        ('mentor', 'Mentor'),
        ('admin', 'Admin'),
    ]
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('resigned', 'Resigned'),
    ]
    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    employee_code = models.CharField(max_length=50, unique=True, blank=True, null=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    role = models.CharField(max_length=200, blank=True)
    photo = models.ImageField(upload_to='profile_photos/', blank=True, null=True)
    employee_type = models.CharField(max_length=20, choices=EMPLOYEE_TYPES, default='staff')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    joined_date = models.DateField(default=datetime.date.today)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def generate_employee_code(self):
        from django.utils import timezone
        year = self.joined_date.year if self.joined_date else timezone.now().year
        prefix = f'AB-{year}-'
        last = Employee.objects.filter(employee_code__startswith=prefix).order_by('employee_code').last()
        if last and last.employee_code:
            try:
                seq = int(last.employee_code.split('-')[-1]) + 1
            except Exception:
                seq = Employee.objects.filter(employee_code__startswith=prefix).count() + 1
        else:
            seq = 1
        code = f'{prefix}{seq:05d}'
        self.employee_code = code
        return code


class Notification(models.Model):
    title = models.CharField(max_length=200)
    message = models.TextField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='notifications_created')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class PasswordResetCode(models.Model):
    email = models.EmailField()
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def is_expired(self):
        from django.utils import timezone
        return (timezone.now() - self.created_at).total_seconds() > 600

    def __str__(self):
        return f"{self.email} - {self.code}"


class Project(models.Model):
    STATUS_CHOICES = [
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('on_hold', 'On Hold'),
        ('cancelled', 'Cancelled'),
    ]
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    client = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress')
    progress_percentage = models.PositiveIntegerField(default=0)
    budget = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    start_date = models.DateField(auto_now_add=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return self.name

    def amount_paid(self):
        return self.payments.aggregate(total=models.Sum('amount'))['total'] or 0

    def amount_remaining(self):
        return max(self.budget - self.amount_paid(), 0)


class ProjectPayment(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateTimeField(auto_now_add=True)
    reference = models.CharField(max_length=100, blank=True)
    remarks = models.TextField(blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-payment_date']

    def __str__(self):
        return f'{self.amount} paid for {self.project.name}'


class Expense(models.Model):
    CATEGORY_CHOICES = [
        ('rent', 'Rent'),
        ('salaries', 'Salaries'),
        ('utilities', 'Utilities'),
        ('software', 'Software & Subscriptions'),
        ('marketing', 'Marketing'),
        ('travel', 'Travel'),
        ('maintenance', 'Maintenance'),
        ('office', 'Office Supplies'),
        ('other', 'Other'),
    ]
    month = models.DateField(help_text='Select the first day of the month for this expense record.')
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='other')
    description = models.CharField(max_length=255)
    vendor = models.CharField(max_length=200, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-month', '-created_at']

    def __str__(self):
        return f'{self.get_category_display()} - {self.month:%b %Y} - Rs. {self.amount}'

    @property
    def month_label(self):
        return self.month.strftime('%B %Y')


class Bill(models.Model):
    bill_number = models.CharField(max_length=32, unique=True, editable=False)
    enrollment = models.ForeignKey(CourseEnrollment, on_delete=models.CASCADE, null=True, blank=True, related_name='bills')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, null=True, blank=True, related_name='bills')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    description = models.CharField(max_length=255)
    issued_at = models.DateTimeField(auto_now_add=True)
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-issued_at']
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(enrollment__isnull=False, project__isnull=True) | models.Q(enrollment__isnull=True, project__isnull=False)),
                name='bill_has_one_subject',
            ),
        ]

    def save(self, *args, **kwargs):
        if not self.bill_number:
            self.bill_number = f'BILL-{datetime.date.today():%Y}-{uuid.uuid4().hex[:10].upper()}'
        super().save(*args, **kwargs)

    @property
    def balance_due(self):
        return max(self.amount - self.amount_paid, 0)

    @property
    def billed_to(self):
        if self.enrollment_id:
            return self.enrollment.student.name
        return self.project.client or 'Client'


class Attendance(models.Model):
    ATTENDANCE_CHOICES = [
        ('P', 'Present'),
        ('A', 'Absent'),
        ('L', 'Late'),
    ]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendances')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='attendances')
    date = models.CharField(max_length=10)
    status = models.CharField(max_length=1, choices=ATTENDANCE_CHOICES)
    marked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['student', 'course', 'date']
        ordering = ['-date', 'student__name']

    def __str__(self):
        return f"{self.student.name} - {self.course.name} - {self.date} - {self.get_status_display()}"


class VerificationScan(models.Model):
    card = models.ForeignKey(IDCard, on_delete=models.CASCADE, related_name='verification_scans')
    scanned_at = models.DateTimeField(auto_now_add=True)
    result = models.CharField(max_length=50)

    class Meta:
        ordering = ['-scanned_at']

    def __str__(self):
        return f"{self.card} - {self.result} at {self.scanned_at}"
