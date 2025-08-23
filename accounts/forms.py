from django import forms
from .models import BankAccount
import re

class BankAccountForm(forms.ModelForm):
    class Meta:
        model = BankAccount
        fields = ['account_name', 'account_number', 'bank_name', 'ifsc_code', 'branch']
        widgets = {
            'account_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Account Holder Name'
            }),
            'account_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Account Number'
            }),
            'bank_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Bank Name'
            }),
            'ifsc_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'IFSC Code',
                'style': 'text-transform: uppercase;'
            }),
            'branch': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Branch (Optional)'
            })
        }

    def clean_account_number(self):
        account_number = self.cleaned_data.get('account_number')
        if not account_number.isdigit():
            raise forms.ValidationError('Account number must contain only numbers')
        return account_number

    def clean_ifsc_code(self):
        ifsc_code = self.cleaned_data.get('ifsc_code', '').strip().upper()
        if not re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', ifsc_code):
            raise forms.ValidationError('Invalid IFSC code format. Expected format: ABCD0123456')
        return ifsc_code
