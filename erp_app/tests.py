import json
import tempfile
from datetime import datetime

from django.contrib.auth.models import Group, User
from django.core import signing
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .forms import StaffAccountForm, StudentForm
from .context_processors import sidebar_stats
from .models import Certificate, Course, CourseEnrollment, Department, Expense, IDCard, Mentor, Payment, Project, ProjectPayment, Student


class ErpSecurityRegressionTests(TestCase):
    def setUp(self):
        self.media_dir = tempfile.TemporaryDirectory()
        self.media_settings = override_settings(MEDIA_ROOT=self.media_dir.name)
        self.media_settings.enable()
        self.addCleanup(self.media_settings.disable)
        self.addCleanup(self.media_dir.cleanup)

        self.student_user = User.objects.create_user('student_a', 'student-a@example.test', 'not-used')
        self.student = Student.objects.create(user=self.student_user, name='Student A', email='student-a@example.test')
        self.other_student_user = User.objects.create_user('student_b', 'student-b@example.test', 'not-used')
        self.other_student = Student.objects.create(user=self.other_student_user, name='Student B', email='student-b@example.test')
        self.card = IDCard.objects.create(
            card_type='student', student=self.student,
            file=ContentFile(b'private card data', name='student-a.png'),
        )
        self.admin = User.objects.create_superuser('audit_admin', 'audit-admin@example.test', 'not-used')

    def test_media_requires_login_and_is_scoped_to_student(self):
        url = reverse('protected_media', kwargs={'file_path': self.card.file.name})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

        self.client.force_login(self.other_student_user)
        self.assertEqual(self.client.get(url).status_code, 404)

        self.client.force_login(self.student_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), b'private card data')

    def test_student_cannot_open_finance_or_database_workbench(self):
        self.client.force_login(self.student_user)
        self.assertEqual(self.client.get(reverse('budget_fees')).status_code, 302)
        self.assertEqual(self.client.get(reverse('workbench')).status_code, 302)
        self.assertEqual(self.client.get(reverse('id_generation')).status_code, 302)

    def test_student_dashboard_renders_my_courses_link(self):
        self.client.force_login(self.student_user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('my_courses'))

    def test_courses_departments_and_my_courses_pages_render(self):
        course = Course.objects.create(name='Navigation Test Course')
        department = Department.objects.create(name='Navigation Test Department')

        self.client.force_login(self.admin)
        courses_response = self.client.get(reverse('courses'))
        self.assertEqual(courses_response.status_code, 200)
        self.assertContains(courses_response, reverse('course_syllabus', args=[course.pk]))

        departments_response = self.client.get(reverse('departments'))
        self.assertEqual(departments_response.status_code, 200)
        self.assertContains(departments_response, reverse('department_edit', args=[department.pk]))
        self.assertContains(departments_response, reverse('department_delete', args=[department.pk]))

        CourseEnrollment.objects.create(student=self.student, course=course, total_fee=1000)
        self.client.force_login(self.student_user)
        my_courses_response = self.client.get(reverse('my_courses'))
        self.assertEqual(my_courses_response.status_code, 200)

    def test_id_card_delete_uses_registered_delete_endpoint(self):
        self.client.force_login(self.admin)
        page = self.client.get(reverse('id_generation'))
        delete_url = reverse('delete_id_card', args=[self.card.pk])
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, f'data-delete-url="{delete_url}"')

        response = self.client.delete(delete_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')
        self.assertFalse(IDCard.objects.filter(pk=self.card.pk).exists())
        self.assertFalse(self.card.file.storage.exists(self.card.file.name))

    def test_id_verification_uses_signed_database_identity(self):
        course = Course.objects.create(name='Audit Course')
        qr_payload = {
            'type': 'STUDENT_ID',
            'id': f'STU-{self.student.pk:05d}-{course.pk:05d}',
            'name': self.student.name,
            'email': self.student.email,
            'phone': 'N/A',
            'course': course.name,
            'category': course.category,
            'enrolled_date': self.student.enrolled_date.isoformat(),
        }
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('verify_id_card'),
            data=json.dumps({'qr_data': signing.dumps(qr_payload, salt='auralith-erp.id-card', compress=True)}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertEqual(response.json()['email'], self.student.email)

        qr_payload['name'] = 'Forged Name'
        response = self.client.post(
            reverse('verify_id_card'),
            data=json.dumps({'qr_data': json.dumps(qr_payload)}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_staff_account_form_saves_password_and_role(self):
        form = StaffAccountForm(data={
            'username': 'audit_staff',
            'email': 'audit-staff@example.test',
            'first_name': 'Audit',
            'last_name': 'Staff',
            'role': 'normal_staff',
            'password': 'Audit-Strong-4829!q',
            'confirm_password': 'Audit-Strong-4829!q',
            'is_active': 'on',
        })
        self.assertTrue(form.is_valid(), form.errors)
        account = form.save()
        account.refresh_from_db()
        self.assertTrue(account.check_password('Audit-Strong-4829!q'))
        self.assertTrue(account.groups.filter(name='normal_staff').exists())

    def test_student_form_supports_manual_enrollment_date_and_mentor_assignment(self):
        mentor = Mentor.objects.create(
            name='Mentor One',
            email='mentor-one@example.test',
            specialization='Frontend Development',
            department=Department.objects.create(name='Design & Development', description='Training'),
        )

        form = StudentForm(data={
            'name': 'New Student',
            'email': 'new-student@example.test',
            'phone': '9800000000',
            'mentor': mentor.pk,
            'enrolled_date': '2026-10-01',
            'is_intern': 'on',
        })

        self.assertTrue(form.is_valid(), form.errors)
        student = form.save()
        self.assertEqual(student.mentor, mentor)
        self.assertEqual(student.enrolled_date.isoformat(), '2026-10-01')

    def test_teaching_staff_can_manage_students_and_id_cards(self):
        teaching_staff = User.objects.create_user('mentor_admin', 'mentor-admin@example.test', 'not-used')
        teaching_staff.groups.add(Group.objects.get_or_create(name='teaching_staff')[0])
        course = Course.objects.create(name='Audit Course')

        self.client.force_login(teaching_staff)
        self.assertEqual(self.client.get(reverse('students')).status_code, 200)
        self.assertEqual(self.client.get(reverse('student_detail', args=[self.student.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('id_generation')).status_code, 200)
        self.assertEqual(self.client.post(reverse('verify_id_card'), data=json.dumps({'qr_data': signing.dumps({
            'type': 'STUDENT_ID',
            'id': f'STU-{self.student.pk:05d}-{course.pk:05d}',
            'name': self.student.name,
            'email': self.student.email,
            'phone': self.student.phone or 'N/A',
            'course': course.name,
            'category': course.category,
            'enrolled_date': self.student.enrolled_date.isoformat(),
        }, salt='auralith-erp.id-card', compress=True)}), content_type='application/json').status_code, 200)

    def test_employee_page_renders_mentor_rows_without_500(self):
        Mentor.objects.create(
            name='Mentor Row',
            email='mentor-row@example.test',
            specialization='UI/UX Design',
            department=Department.objects.create(name='Design Team', description='Design training'),
            joined_date='2026-01-15',
        )
        self.client.force_login(self.admin)
        response = self.client.get(reverse('employees'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Mentor Row')

        all_response = self.client.get(f"{reverse('employees')}?type=all")
        self.assertEqual(all_response.status_code, 200)
        self.assertContains(all_response, 'Mentor Row')

    def test_state_changing_get_logout_is_rejected(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('logout')).status_code, 405)

    def test_login_rejects_external_next_url(self):
        response = self.client.post(
            f"{reverse('login')}?next=https://attacker.example/",
            {'username': self.admin.username, 'password': 'not-used'},
        )
        self.assertRedirects(response, reverse('dashboard'), fetch_redirect_response=False)

    def test_certificate_uses_enrollment_date_when_no_start_date_is_set(self):
        course = Course.objects.create(name='Audit Course')
        self.student.enrolled_date = '2026-09-18'
        self.student.save(update_fields=['enrolled_date'])

        cert = Certificate.objects.create(
            student=self.student,
            course=course,
            certificate_type='course',
            program_title='Audit Course',
            program_start_date='',
            location='Auralith Bit',
        )

        self.assertEqual(cert.program_start_date, '2026/09/18')

    def test_certificate_preview_has_no_preprinted_signature_text(self):
        course = Course.objects.create(name='Audit Course')
        cert = Certificate.objects.create(
            student=self.student,
            course=course,
            certificate_type='course',
            program_title='Audit Course',
            program_start_date='2026/09/18',
            location='Auralith Bit',
            authorized_signer_name='Authorized Signatory',
            authorized_signer_title='Company Representative',
            authorized_signature_text='Digital Signature Text',
        )
        self.client.force_login(self.admin)
        response = self.client.get(reverse('preview_certificate', args=[cert.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Digital Signature Text')
        self.assertNotContains(response, 'Authorized Signatory')
        self.assertNotContains(response, 'Company Representative')
        self.assertContains(response, 'Mentor')
        self.assertContains(response, 'Aakriti Bista')

    def test_student_photo_field_supports_id_card_portrait_upload(self):
        image_bytes = b'fake-image-data'
        self.student.photo.save('student-portrait.png', ContentFile(image_bytes), save=True)
        self.assertTrue(self.student.photo)
        self.assertIn('student-portrait.png', self.student.photo.name)

    def test_generated_student_id_card_with_photo_does_not_raise_bad_transparency_mask(self):
        from PIL import Image
        from io import BytesIO

        image = Image.new('RGBA', (60, 60), (255, 0, 0, 255))
        buffer = BytesIO()
        image.save(buffer, format='PNG')
        buffer.seek(0)
        self.student.photo.save('student-portrait.png', ContentFile(buffer.getvalue()), save=True)

        course = Course.objects.create(name='Photo Card Course')
        card = self.client.post(
            reverse('id_generation'),
            {'action': 'generate', 'card_type': 'student', 'owner_id': self.student.pk, 'course_id': course.pk, 'photo': ContentFile(buffer.getvalue(), 'student-portrait.png')},
            follow=True,
        )
        self.assertEqual(card.status_code, 200)
        self.assertTrue(IDCard.objects.filter(student=self.student, card_type='student').exists())

    def test_superuser_display_name_uses_admin_label(self):
        self.admin.first_name = 'Anshu'
        self.admin.last_name = 'Thapa'
        self.admin.save(update_fields=['first_name', 'last_name'])

        context = sidebar_stats(type('Req', (), {'user': self.admin, 'path': '/dashboard/'} )())
        self.assertEqual(context['user_display_name'], 'Auralith Bit Admin')

    def test_monthly_expenses_page_allows_admin_management(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('monthly_expenses'))
        self.assertEqual(response.status_code, 200)

        response = self.client.post(reverse('monthly_expenses'), {
            'month': '2026-10-01',
            'category': 'rent',
            'description': 'Office rent',
            'vendor': 'Auralith Bit Office',
            'amount': '35000',
            'notes': 'Monthly office rent',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Expense.objects.filter(description='Office rent', amount='35000').exists())

        expense = Expense.objects.get(description='Office rent')
        self.assertIn('2026-10', response.url)
        self.assertEqual(self.client.get(f"{reverse('monthly_expenses')}?month=2026-10").context['monthly_totals'][0]['total'], 35000)

        delete_response = self.client.post(reverse('delete_monthly_expense', args=[expense.pk]))
        self.assertEqual(delete_response.status_code, 302)
        self.assertFalse(Expense.objects.filter(pk=expense.pk).exists())

    def test_monthly_expense_dashboard_shows_income_expense_and_balance(self):
        course = Course.objects.create(name='Monthly Finance Course')
        enrollment = CourseEnrollment.objects.create(student=self.student, course=course, total_fee=5000)
        Payment.objects.create(
            enrollment=enrollment,
            amount=5000,
            payment_date=datetime(2026, 10, 5),
            transaction_id='TX-1',
        )
        project = Project.objects.create(name='Auralith Growth', client='Auralith Bit', budget=20000)
        ProjectPayment.objects.create(
            project=project,
            amount=9000,
            payment_date=datetime(2026, 10, 12),
            reference='INV-1001',
        )
        Expense.objects.create(
            month='2026-10-01',
            category='rent',
            description='Office rent',
            vendor='Auralith Bit Office',
            amount=35000,
            recorded_by=self.admin,
        )

        self.client.force_login(self.admin)
        response = self.client.get(f"{reverse('monthly_expenses')}?month=2026-10")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['month_income'], 14000)
        self.assertEqual(response.context['month_expense_total'], 35000)
        self.assertEqual(response.context['month_balance'], -21000)

    def test_department_api_uses_existing_model_fields(self):
        department = Department.objects.create(name='Engineering', description='Product delivery')
        self.client.force_login(self.admin)
        response = self.client.get(reverse('get_departments'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [{'id': department.pk, 'name': 'Engineering', 'description': 'Product delivery'}])

    def test_hr_and_payment_records_support_edit_and_delete(self):
        department = Department.objects.create(name='Operations', description='Ops')
        mentor = Mentor.objects.create(
            name='Mentor Edit',
            email='mentor-edit@example.test',
            specialization='QA & Testing',
            department=department,
        )
        course = Course.objects.create(name='Course CRUD', mentor=mentor, status='live', description='Test course')
        enrollment = CourseEnrollment.objects.create(student=self.student, course=course, total_fee=1500)
        payment = Payment.objects.create(enrollment=enrollment, amount=500, transaction_id='TX-EDIT')

        self.client.force_login(self.admin)

        response = self.client.post(reverse('mentor_edit', args=[mentor.pk]), {
            'name': 'Mentor Updated',
            'email': 'mentor-edit@example.test',
            'specialization': 'Quality Assurance',
            'bio': 'Mentor for QA',
            'department': department.pk,
            'joined_date': '2026-01-01',
        })
        self.assertEqual(response.status_code, 302)
        mentor.refresh_from_db()
        self.assertEqual(mentor.name, 'Mentor Updated')

        response = self.client.post(reverse('payment_edit', args=[payment.pk]), {
            'amount': '750',
            'transaction_id': 'TX-UPDATED',
            'remarks': 'Adjusted payment',
        })
        self.assertEqual(response.status_code, 302)
        payment.refresh_from_db()
        self.assertEqual(float(payment.amount), 750.0)
        self.assertEqual(payment.transaction_id, 'TX-UPDATED')

        response = self.client.post(reverse('payment_delete', args=[payment.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Payment.objects.filter(pk=payment.pk).exists())

        response = self.client.post(reverse('course_delete', args=[course.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Course.objects.filter(pk=course.pk).exists())
