from django import forms
from .models import PasswordEntry, Category
from .utils import encrypt_password

class PasswordEntryForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(render_value=True), label="Password", required=True, strip=False)

    class Meta:
        model = PasswordEntry
        fields = ['website', 'username', 'password', 'category']

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.filter(user=user) if user else Category.objects.none()
        self.fields['category'].required = False
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    def save(self, commit=True, user=None):
        instance = super().save(commit=False)
        instance.encrypted_password = encrypt_password(self.cleaned_data['password'])
        if user:
            instance.user = user
        if commit:
            instance.save()
        return instance

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name']
