import json
import tempfile

from django.contrib.auth.models import Group, User
from django.core import signing
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .forms import StaffAccountForm, StudentForm
from .models import Course, Department, IDCard, Mentor, Student


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

    def test_state_changing_get_logout_is_rejected(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('logout')).status_code, 405)

    def test_login_rejects_external_next_url(self):
        response = self.client.post(
            f"{reverse('login')}?next=https://attacker.example/",
            {'username': self.admin.username, 'password': 'not-used'},
        )
        self.assertRedirects(response, reverse('dashboard'), fetch_redirect_response=False)

    def test_department_api_uses_existing_model_fields(self):
        department = Department.objects.create(name='Engineering', description='Product delivery')
        self.client.force_login(self.admin)
        response = self.client.get(reverse('get_departments'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [{'id': department.pk, 'name': 'Engineering', 'description': 'Product delivery'}])
