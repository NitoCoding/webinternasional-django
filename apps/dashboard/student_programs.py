from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.academic.models import Student
from apps.international.enrollment import (
    APPROVED,
    enroll_student,
    enrollment_status,
    student_is_eligible,
)
from apps.international.models import IeProgram, Program


def _student_of(user):
    student = Student.objects.filter(user=user).select_related("study_program").first()
    if student is None:
        raise PermissionDenied
    return student


def _gate_message(student):
    """Pesan dan tombol untuk student yang belum bisa mendaftar (urutan sama dengan Laravel)."""
    if not student.study_program_id:
        return {"text": "Your study program is not available for international classes.", "action": None}
    if not student.is_verified and student.status is None:
        return {"text": "You are not verified as an international student.", "action": "Register Now"}
    if student.is_verified and student.status is None:
        return {"text": "You are not an active student.", "action": "Activate Now"}
    if student.status == Student.Status.WAITING:
        return {"text": "You are currently waiting for admin verification.", "action": None}
    if student.status == Student.Status.REJECTED:
        return {"text": "You have been rejected as an international student.", "action": "Reapply Now"}
    if student.status == Student.Status.ACCEPTED and not student.is_active:
        # Tidak ada di Laravel: akun accepted tetapi nonaktif. Diberi pesan sendiri agar tidak membingungkan.
        return {"text": "Your account is inactive. Please contact the administrator.", "action": None}
    return {"text": "You are not an international student. Register now!", "action": "Register Now"}


def _visible_programs(student):
    # Laravel: program hanya dari Study Program student.
    return Program.objects.filter(study_programs=student.study_program_id)


def _can_enroll(eligible, status, approved_count, participants_count, in_progress):
    """Tombol Enroll aktif hanya jika student eligible, belum terdaftar, tidak ada program berjalan, dan belum penuh."""
    if not eligible or in_progress:
        return False
    if status in ("approved", "pending"):
        return False
    return approved_count < participants_count


def _in_progress_enrollment(student):
    return (
        student.enrollments.filter(status=APPROVED, is_finished=False)
        .select_related("program")
        .first()
    )


@login_required
@require_GET
def student_program_list(request):
    student = _student_of(request.user)
    eligible = student_is_eligible(student)
    ie_program_id = request.GET.get("ie_program_id", "")

    programs = _visible_programs(student)
    if ie_program_id.isdigit():
        programs = programs.filter(ie_program_id=int(ie_program_id))
    programs = (
        programs.select_related("ie_program")
        .annotate(approved_count=Count("enrollments", filter=Q(enrollments__status=APPROVED), distinct=True))
        .distinct()
        .order_by("-pk")
    )
    page = Paginator(programs, 10).get_page(request.GET.get("page"))

    statuses = dict(student.enrollments.filter(program__in=[p.pk for p in page]).values_list("program_id", "status"))
    current = _in_progress_enrollment(student)
    rows = []
    for p in page:
        status = statuses.get(p.pk)
        rows.append({
            "program": p,
            "approved": p.approved_count,
            "full": p.approved_count >= p.participants_count,
            "status": status,
            "can_enroll": _can_enroll(eligible, status, p.approved_count, p.participants_count, current is not None),
            "enroll_url": reverse("dashboard:student_program_enroll", args=[p.pk]),
        })

    gate = None if eligible else _gate_message(student)
    return render(request, "dashboard/student/programs/index.html", {
        "eligible": eligible,
        "gate": gate,
        "current": current,
        "page": page,
        "rows": rows,
        "ie_programs": IeProgram.objects.order_by("-created_at"),
        "selected_ie": ie_program_id,
        "register_url": reverse("dashboard:student_register"),
    })


@login_required
@require_GET
def student_program_show(request, pk):
    student = _student_of(request.user)
    program = get_object_or_404(Program.objects.select_related("ie_program").prefetch_related("study_programs"), pk=pk)
    if not _visible_programs(student).filter(pk=program.pk).exists():
        raise Http404
    eligible = student_is_eligible(student)
    approved = program.enrollments.filter(status=APPROVED).count()
    status = enrollment_status(student, program)
    current = _in_progress_enrollment(student)
    return render(request, "dashboard/student/programs/show.html", {
        "program": program,
        "approved": approved,
        "full": approved >= program.participants_count,
        "status": status,
        "eligible": eligible,
        "can_enroll": _can_enroll(eligible, status, approved, program.participants_count, current is not None),
        "current": current,
        "gate": None if eligible else _gate_message(student),
        "study_programs": program.study_programs.all(),
        "back_url": reverse("dashboard:student_programs"),
        "enroll_url": reverse("dashboard:student_program_enroll", args=[program.pk]),
        "register_url": reverse("dashboard:student_register"),
    })


@login_required
@require_POST
def student_program_enroll(request, pk):
    student = _student_of(request.user)
    program = get_object_or_404(Program, pk=pk)
    if not _visible_programs(student).filter(pk=program.pk).exists():
        raise Http404
    ok, message = enroll_student(student, program)
    (messages.success if ok else messages.error)(request, message)
    return redirect("dashboard:student_programs")


@login_required
@require_POST
def student_register(request):
    """Tombol Register / Activate / Reapply: ajukan ulang status menjadi waiting (sama dengan Laravel)."""
    student = _student_of(request.user)
    if student.status == Student.Status.WAITING:
        messages.info(request, "Your status is already waiting for verification.")
    else:
        student.status = Student.Status.WAITING
        student.save(update_fields=["status", "updated_at"])
        messages.success(request, "Request has been submitted successfully.")
    return redirect("dashboard:student_programs")
