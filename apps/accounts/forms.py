from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
)
from django.contrib.auth.password_validation import validate_password

from apps.academic.models import Student

from .models import User

INPUT_CLASS = "input input-bordered w-full"


class StyledMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", INPUT_CLASS)


AUTH_INPUT_CLASS = "w-full px-4 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"


class AuthStyledMixin:
    """Gaya input halaman auth: border abu dan fokus biru, sama dengan dashboard."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", AUTH_INPUT_CLASS)


class LoginForm(AuthStyledMixin, AuthenticationForm):
    pass


class StyledPasswordResetForm(AuthStyledMixin, PasswordResetForm):
    pass


class StyledSetPasswordForm(AuthStyledMixin, SetPasswordForm):
    pass


class RegisterForm(AuthStyledMixin, forms.ModelForm):
    password1 = forms.CharField(label="Password", strip=False, widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirm password", strip=False, widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ["username", "name", "email"]
        labels = {"username": "Username", "name": "Name", "email": "Email"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].required = True
        self.fields["email"].required = True

    def clean_email(self):
        return self.cleaned_data["email"].lower()

    def clean_password1(self):
        password = self.cleaned_data.get("password1")
        if password:
            validate_password(password)
        return password

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password1") and cleaned.get("password1") != cleaned.get("password2"):
            self.add_error("password2", "Passwords do not match.")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class ProfileForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ["name", "email"]
        labels = {"name": "Name", "email": "Email"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].required = True
        self.fields["email"].required = True

    def clean_email(self):
        return self.cleaned_data["email"].lower()


class StudentProfileForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = Student
        fields = [
            "phone_number", "home_phone", "address", "postal_code", "birth_place", "birth_date",
        ]
        labels = {
            "phone_number": "Mobile Phone",
            "home_phone": "Home Phone",
            "address": "Address",
            "postal_code": "Postal Code",
            "birth_place": "Birth Place",
            "birth_date": "Birth Date",
        }
        widgets = {"birth_date": forms.DateInput(attrs={"type": "date"})}


class ChangePasswordForm(StyledMixin, PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].label = "Current Password"
        self.fields["new_password1"].label = "New Password"
        self.fields["new_password2"].label = "Confirm New Password"
