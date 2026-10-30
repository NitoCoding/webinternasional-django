from django import forms

from apps.academic.models import StudyProgram
from apps.accounts.models import User

from .forms import INPUT_CLASS
from .user_services import CSV_MAX_BYTES


def _styled(form):
    for field in form.fields.values():
        field.widget.attrs.setdefault("class", INPUT_CLASS)
    return form


class AddStudentForm(forms.Form):
    nim = forms.CharField(
        label="Student NIM",
        max_length=20,
        widget=forms.TextInput(attrs={"placeholder": "Enter student NIM"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _styled(self)


class CsvUploadForm(forms.Form):
    csv_file = forms.FileField(
        label="Select CSV File",
        help_text="Only .csv or .txt files are accepted. Max size: 2 MB. "
        "The first column must contain the NIM. The first row is treated as a header.",
    )

    def clean_csv_file(self):
        uploaded = self.cleaned_data["csv_file"]
        if not uploaded.name.lower().endswith((".csv", ".txt")):
            raise forms.ValidationError("Only .csv or .txt files are accepted.")
        if uploaded.size > CSV_MAX_BYTES:
            raise forms.ValidationError("The CSV file must be 2 MB or smaller.")
        return uploaded


class StaffCreateForm(forms.Form):
    username = forms.CharField(max_length=150)
    name = forms.CharField(max_length=255)
    email = forms.EmailField(max_length=254)
    password = forms.CharField(min_length=8, widget=forms.PasswordInput, help_text="At least 8 characters.")
    study_program = forms.ModelChoiceField(
        queryset=StudyProgram.objects.order_by("name"),
        empty_label="Select study program",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _styled(self)

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("This email is already taken.")
        return email


class EnglishScoreForm(forms.Form):
    english_score = forms.IntegerField(min_value=0, max_value=100, label="English Score")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _styled(self)
