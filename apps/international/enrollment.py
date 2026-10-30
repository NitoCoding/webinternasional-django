"""Aturan pendaftaran program International Exposure oleh student.

Mengikuti ProgramController@enroll di Laravel. Aturan tambahan (tidak ada di Laravel):
student harus terverifikasi dan aktif sebelum bisa mendaftar, agar URL enroll tidak bisa
dipakai melewati halaman yang sudah membatasi akses.
"""

from django.db import transaction

from apps.international.models import ProgramEnrollment

APPROVED = ProgramEnrollment.Status.APPROVED
PENDING = ProgramEnrollment.Status.PENDING
REJECTED = ProgramEnrollment.Status.REJECTED


def student_is_eligible(student):
    """Student boleh melihat dan mendaftar program: terverifikasi, aktif, dan status accepted."""
    return bool(
        student
        and student.is_verified
        and student.is_active
        and student.status == student.Status.ACCEPTED
        and student.study_program_id
    )


def enrollment_status(student, program):
    """Status student di program ini: approved, pending, rejected, atau None."""
    enrollment = student.enrollments.filter(program=program).first()
    return enrollment.status if enrollment else None


@transaction.atomic
def enroll_student(student, program):
    """Daftarkan student ke program. Mengembalikan (ok, pesan)."""
    if not student_is_eligible(student):
        return False, "You are not an active international student."

    if student.enrollments.filter(status=APPROVED, is_finished=False).exists():
        return False, "You cannot enroll in a new program while your current program is still in progress."

    existing = student.enrollments.filter(program=program).first()
    if existing:
        if existing.status == PENDING:
            return False, "Your enrollment is still pending approval. Please wait for confirmation."
        if existing.status == APPROVED:
            return False, "You are already enrolled in this program."

    approved_count = program.enrollments.filter(status=APPROVED).count()
    if approved_count >= program.participants_count:
        return False, "This program has reached its participant limit."

    if existing:
        # Pendaftaran lama berstatus rejected: ajukan lagi tanpa membuat baris baru
        # (ada unique constraint program + student).
        existing.status = PENDING
        existing.save(update_fields=["status", "updated_at"])
    else:
        ProgramEnrollment.objects.create(program=program, student=student, status=PENDING)
    return True, "Your enrollment is pending approval."
