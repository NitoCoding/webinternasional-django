from django.conf import settings
from django.db import models

from apps.academic.models import IeProgram, Student, StudyProgram
from apps.core.models import TimeStampedModel


class Program(TimeStampedModel):
    """Program internasional (tabel `programs` di Laravel)."""

    name = models.CharField(max_length=255)
    description = models.TextField()
    country = models.CharField(max_length=50)
    execution_date = models.DateField()
    end_date = models.DateField()
    participants_count = models.PositiveIntegerField()
    course_credits = models.PositiveIntegerField()
    image = models.ImageField(upload_to="programs/images/", max_length=255)
    brochure_pdf = models.FileField(upload_to="programs/brochures/", max_length=255, blank=True, null=True)
    ie_program = models.ForeignKey(IeProgram, on_delete=models.PROTECT, related_name="programs")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="programs")
    study_programs = models.ManyToManyField(StudyProgram, blank=True, related_name="programs")
    students = models.ManyToManyField(Student, through="ProgramEnrollment", related_name="programs", blank=True)

    def __str__(self):
        return self.name


class ProgramEnrollment(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name="enrollments")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="enrollments")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    is_finished = models.BooleanField(default=False)
    certificate_path = models.FileField(upload_to="programs/certificates/", max_length=255, blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["program", "student"], name="unique_program_student_enrollment"),
        ]

    def __str__(self):
        return f"{self.student} -> {self.program} ({self.status})"


class Logbook(TimeStampedModel):
    name = models.CharField(max_length=255)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    description = models.TextField()
    image = models.ImageField(upload_to="logbooks/", max_length=255, blank=True)
    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name="logbooks")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="logbooks")

    def __str__(self):
        return self.name


class Partnership(TimeStampedModel):
    class PartnershipType(models.TextChoices):
        MOU = "mou", "MoU/MoA"
        DOUBLE_DEGREE = "double_degree", "Double Degree"
        SINGLE_DEGREE = "single_degree", "Single Degree"
        JOINT_DEGREE = "joint_degree", "Joint Degree"

    partnership_type = models.CharField(max_length=20, choices=PartnershipType.choices, default=PartnershipType.MOU)
    partner_university = models.CharField(max_length=255, blank=True, null=True)
    country = models.CharField(max_length=255, blank=True, null=True)
    country_flag = models.CharField(max_length=10, blank=True, null=True)
    unhas_program = models.CharField(max_length=255, blank=True, null=True)
    partner_program = models.CharField(max_length=255, blank=True, null=True)
    specialization = models.CharField(max_length=255, blank=True, null=True)
    duration = models.CharField(max_length=255, blank=True, null=True)
    program_structure = models.TextField(blank=True, null=True)
    entry_requirements = models.TextField(blank=True, null=True)
    highlights = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to="partnerships/", max_length=255, blank=True, null=True)
    brochure_pdf = models.FileField(upload_to="partnerships/brochures/", max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    mou_moa_ia_number = models.CharField("No. MoU/MoA/IA", max_length=255, blank=True, null=True)
    title_of_cooperation = models.CharField(max_length=255, blank=True, null=True)
    validity_period = models.PositiveSmallIntegerField(blank=True, null=True)
    study_program = models.ForeignKey(
        StudyProgram, on_delete=models.SET_NULL, blank=True, null=True, related_name="partnerships"
    )

    def __str__(self):
        return self.title_of_cooperation or self.partner_university or f"Partnership #{self.pk}"

    @property
    def flag_emoji(self):
        code = (self.country_flag or "").upper()
        if len(code) != 2 or not code.isalpha():
            return ""
        code = {"UK": "GB"}.get(code, code)
        return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in code)


class OutboundLecturer(TimeStampedModel):
    class Gender(models.TextChoices):
        MALE = "Male", "Male"
        FEMALE = "Female", "Female"

    lecturer_name = models.CharField(max_length=255, blank=True, null=True)
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True, null=True)
    role_in_ki = models.CharField(max_length=255, blank=True, null=True)
    university_name = models.CharField(max_length=255, blank=True, null=True)
    activity_year = models.PositiveSmallIntegerField(blank=True, null=True)
    study_program = models.ForeignKey(
        StudyProgram, on_delete=models.SET_NULL, blank=True, null=True, related_name="outbound_lecturers"
    )

    def __str__(self):
        return self.lecturer_name or f"Outbound #{self.pk}"
