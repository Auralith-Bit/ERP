from django import forms

from .models import CourseEnrollment, Payment, Project, ProjectPayment, Student


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
