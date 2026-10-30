from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Faculty(TimeStampedModel):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50)

    class Meta:
        verbose_name_plural = "faculties"

    def __str__(self):
        return self.name


class StudyProgram(TimeStampedModel):
    faculty = models.ForeignKey(Faculty, on_delete=models.PROTECT, related_name="study_programs")
    name = models.CharField(max_length=255)
    degree = models.CharField(max_length=255)
    description = models.TextField()
    image = models.ImageField(upload_to="study_programs/", max_length=255)
    classrooms = models.PositiveIntegerField(default=0)
    lecturers = models.PositiveIntegerField(default=0)
    national_accreditation = models.CharField(max_length=255)
    international_accreditation = models.CharField(max_length=255)
    approval_sk = models.CharField(max_length=255, blank=True, null=True)
    opening_year = models.PositiveSmallIntegerField(blank=True, null=True)
    director_name = models.CharField(max_length=255, blank=True, null=True)
    director_contact = models.CharField(max_length=255, blank=True, null=True)
    ukt_fee = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    ipi_fee = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    international_exposure = models.CharField(max_length=255, blank=True, null=True)
    total_courses = models.PositiveIntegerField(default=0)
    rps_courses_in_english = models.PositiveIntegerField(default=0)
    teaching_materials_in_english = models.PositiveIntegerField(default=0)
    courses_delivered_in_english = models.PositiveIntegerField(default=0)
    courses_fully_filled_in_sikola = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.name


class IeProgram(TimeStampedModel):
    """Jenis International Exposure (ie_programs)."""

    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name


class Staff(TimeStampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="staff")
    name = models.CharField(max_length=255)
    study_program = models.ForeignKey(StudyProgram, on_delete=models.PROTECT, related_name="staff")

    def __str__(self):
        return self.name


class Student(TimeStampedModel):
    class Gender(models.TextChoices):
        MALE = "L", "Laki-laki"
        FEMALE = "P", "Perempuan"

    class Status(models.TextChoices):
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        WAITING = "waiting", "Waiting"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="student")
    name = models.CharField(max_length=100)
    student_id_number = models.CharField("NIM", max_length=20, unique=True)
    email = models.EmailField(max_length=100)
    is_active = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    gender = models.CharField(max_length=1, choices=Gender.choices, blank=True, null=True)
    english_score = models.PositiveIntegerField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, blank=True, null=True)
    nik = models.CharField(max_length=20, blank=True, null=True)
    nisn = models.CharField(max_length=20, blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    home_phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    postal_code = models.CharField(max_length=10, blank=True, null=True)
    birth_place = models.CharField(max_length=100, blank=True, null=True)
    birth_date = models.DateField(blank=True, null=True)
    study_program = models.ForeignKey(
        StudyProgram, on_delete=models.SET_NULL, blank=True, null=True, related_name="students"
    )

    def __str__(self):
        return f"{self.student_id_number} - {self.name}"
