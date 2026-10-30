from django import forms

from apps.international.logbook import (
    CERTIFICATE_MAX_BYTES,
    LOGBOOK_IMAGE_EXTENSIONS,
    LOGBOOK_IMAGE_MAX_BYTES,
)
from apps.international.models import Logbook

from .forms import INPUT_CLASS

DATETIME_INPUT_FORMATS = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"]


class LogbookForm(forms.ModelForm):
    start_time = forms.DateTimeField(
        label="Start Time",
        input_formats=DATETIME_INPUT_FORMATS,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": INPUT_CLASS}, format="%Y-%m-%dT%H:%M"),
    )
    end_time = forms.DateTimeField(
        label="End Time",
        input_formats=DATETIME_INPUT_FORMATS,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": INPUT_CLASS}, format="%Y-%m-%dT%H:%M"),
    )
    name = forms.CharField(label="Activity Name", max_length=50, widget=forms.TextInput(attrs={"class": INPUT_CLASS}))
    description = forms.CharField(
        label="Description",
        max_length=50,
        widget=forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3}),
    )
    image = forms.ImageField(
        label="Image (optional)",
        required=False,
        help_text="JPG, PNG, or GIF. Max 2 MB.",
    )

    class Meta:
        model = Logbook
        fields = ["name", "start_time", "end_time", "description", "image"]

    def __init__(self, *args, program=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.program = program

    def clean_start_time(self):
        start = self.cleaned_data["start_time"]
        if self.program and not (self.program.execution_date <= start.date() <= self.program.end_date):
            raise forms.ValidationError(
                f"Start Time must be within the program dates "
                f"({self.program.execution_date:%d %b %Y} – {self.program.end_date:%d %b %Y})."
            )
        return start

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_time")
        end = cleaned.get("end_time")
        if start and end:
            if end <= start:
                self.add_error("end_time", "End Time must be after Start Time.")
            elif self.program and end.date() > self.program.end_date:
                self.add_error(
                    "end_time",
                    f"End Time must be on or before the program end date ({self.program.end_date:%d %b %Y}).",
                )
        return cleaned

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if not image:
            return image
        if not image.name.lower().endswith(LOGBOOK_IMAGE_EXTENSIONS):
            raise forms.ValidationError("Only JPG, PNG, or GIF images are accepted.")
        if image.size > LOGBOOK_IMAGE_MAX_BYTES:
            raise forms.ValidationError("The image must be 2 MB or smaller.")
        return image


class CertificateUploadForm(forms.Form):
    certificate = forms.FileField(label="Certificate (PDF)", help_text="PDF only. Max 5 MB.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["certificate"].widget.attrs.update({"class": INPUT_CLASS, "accept": ".pdf"})

    def clean_certificate(self):
        uploaded = self.cleaned_data["certificate"]
        if not uploaded.name.lower().endswith(".pdf"):
            raise forms.ValidationError("Only PDF files are accepted.")
        if uploaded.size > CERTIFICATE_MAX_BYTES:
            raise forms.ValidationError("The certificate must be 5 MB or smaller.")
        header = uploaded.read(5)
        uploaded.seek(0)
        if header != b"%PDF-":
            raise forms.ValidationError("The file is not a valid PDF.")
        return uploaded
