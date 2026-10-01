from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError

from .models import Certificate, CourseEnrollment, Payment, Project, ProjectPayment, Student

User = get_user_model()


class StaffAccountForm(forms.ModelForm):
    role = forms.ChoiceField(choices=[
        ('super_admin', 'Administrator'),
        ('teaching_staff', 'Teaching staff'),
        ('normal_staff', 'Office staff'),
    ])
    password = forms.CharField(required=False, widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}), help_text='Leave blank when editing to keep the current password.')
    confirm_password = forms.CharField(required=False, widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}), label='Confirm password')

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'is_active']
        labels = {'is_active': 'Account is active'}

    def __init__(self, *args, **kwargs):
        self.is_create = kwargs.get('instance') is None
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'erp-form-control')
        self.fields['role'].widget.attrs['class'] = 'erp-form-control'
        self.fields['is_active'].widget.attrs['class'] = 'erp-checkbox'
        if self.instance and self.instance.pk:
            self.fields['role'].initial = self.instance.groups.filter(name__in=['super_admin', 'teaching_staff', 'normal_staff']).values_list('name', flat=True).first() or 'normal_staff'
        else:
            self.fields['role'].initial = 'normal_staff'
        self.fields['password'].required = self.is_create
        self.fields['confirm_password'].required = self.is_create

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        users = User.objects.filter(username__iexact=username)
        if self.instance.pk:
            users = users.exclude(pk=self.instance.pk)
        if users.exists():
            raise forms.ValidationError('That username is already in use.')
        if username and username[0].isdigit():
            raise forms.ValidationError('Username must not start with a number.')
        return username

    def clean_email(self):
        email = self.cleaned_data['email'].strip()
        users = User.objects.filter(email__iexact=email)
        if self.instance.pk:
            users = users.exclude(pk=self.instance.pk)
        if users.exists():
            raise forms.ValidationError('That email address is already in use.')
        return email

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get('password')
        confirmation = cleaned.get('confirm_password')
        if password or confirmation:
            if password != confirmation:
                self.add_error('confirm_password', 'Passwords do not match.')
            elif password:
                try:
                    validate_password(password, self.instance if self.instance.pk else None)
                except ValidationError as error:
                    self.add_error('password', error)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            user.set_password(password)
        if commit:
            user.save()
            group, _ = Group.objects.get_or_create(name=self.cleaned_data['role'])
            user.groups.set([group])
        return user


class ERPForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'erp-form-control')


class StudentForm(ERPForm):
    class Meta:
        model = Student
        fields = ['name', 'email', 'phone', 'is_intern']


class ProjectForm(ERPForm):
    client = forms.CharField(max_length=200, widget=forms.TextInput(attrs={'placeholder': 'Client or company'}))
    description = forms.CharField(widget=forms.Textarea(attrs={'rows': 4, 'placeholder': 'Project scope, deliverables, and what the client needs'}))

    class Meta:
        model = Project
        fields = ['name', 'client', 'description', 'budget', 'status', 'progress_percentage']
        widgets = {
            'budget': forms.NumberInput(attrs={'min': '0', 'step': '0.01'}),
            'progress_percentage': forms.NumberInput(attrs={'min': '0', 'max': '100'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['budget'].label = 'Agreed client price'
        self.fields['progress_percentage'].label = 'Progress (%)'

    def clean_budget(self):
        amount = self.cleaned_data['budget']
        if amount < 0:
            raise forms.ValidationError('Project price cannot be negative.')
        return amount

    def clean_progress_percentage(self):
        percentage = self.cleaned_data['progress_percentage']
        if percentage > 100:
            raise forms.ValidationError('Progress must be between 0 and 100 percent.')
        return percentage


class PaymentForm(ERPForm):
    class Meta:
        model = Payment
        fields = ['amount', 'transaction_id', 'remarks']
        widgets = {'amount': forms.NumberInput(attrs={'min': '0.01', 'step': '0.01'})}

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount <= 0:
            raise forms.ValidationError('Payment amount must be greater than zero.')
        return amount


class ProjectPaymentForm(ERPForm):
    class Meta:
        model = ProjectPayment
        fields = ['amount', 'reference', 'remarks']
        widgets = {'amount': forms.NumberInput(attrs={'min': '0.01', 'step': '0.01'})}

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount <= 0:
            raise forms.ValidationError('Payment amount must be greater than zero.')
        return amount


class CourseEnrollmentForm(ERPForm):
    class Meta:
        model = CourseEnrollment
        fields = ['course', 'total_fee']
        widgets = {'total_fee': forms.NumberInput(attrs={'min': '0', 'step': '0.01'})}

    def clean_total_fee(self):
        amount = self.cleaned_data['total_fee']
        if amount < 0:
            raise forms.ValidationError('Course fee cannot be negative.')
        return amount


class EnrollmentFeeForm(forms.Form):
    total_fee = forms.DecimalField(min_value=0, max_digits=10, decimal_places=2, widget=forms.NumberInput(attrs={'min': '0', 'step': '0.01', 'class': 'erp-form-control'}))


class StudentCertificateForm(ERPForm):
    class Meta:
        model = Certificate
        fields = [
            'certificate_type', 'course', 'program_title', 'program_start_date',
            'location', 'internship_details', 'authorized_signer_name',
            'authorized_signer_title', 'authorized_signature_text',
        ]
        widgets = {'internship_details': forms.Textarea(attrs={'rows': 3})}

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('certificate_type') in ('course', 'workshop') and not cleaned.get('course') and not cleaned.get('program_title'):
            raise forms.ValidationError('Choose a course or enter a program title.')
        return cleaned
