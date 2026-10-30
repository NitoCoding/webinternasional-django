"""Fitur logbook: catatan kegiatan dan sertifikat (student dan admin)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from django.views.generic import TemplateView

from apps.academic.models import Student
from apps.international.enrollment import APPROVED
from apps.international.logbook import open_certificate, save_certificate
from apps.international.models import Logbook, Program, ProgramEnrollment

from ..logbook_forms import CertificateUploadForm, LogbookForm
from ..user_services import manageable_student


def _student_enrollment(user, program):
    """Enrollment approved milik student yang login. Selain itu 403 (logbook hanya untuk peserta yang disetujui)."""
    student = Student.objects.filter(user=user).first()
    if student is None:
        raise PermissionDenied
    enrollment = ProgramEnrollment.objects.filter(program=program, student=student, status=APPROVED).first()
    if enrollment is None:
        raise PermissionDenied
    return enrollment


def _program_logbook_url(program):
    return reverse("dashboard:student_logbook_list", args=[program.pk])


def _certificate_file_response(enrollment, filename):
    handle = open_certificate(enrollment)
    if handle is None:
        raise Http404
    return FileResponse(handle, content_type="application/pdf", filename=filename)


class StudentLogbookListView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/student/logbook/list.html"

    def dispatch(self, request, *args, **kwargs):
        self.program = get_object_or_404(Program, pk=kwargs["pk"])
        self.enrollment = _student_enrollment(request.user, self.program)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        program = self.program
        ctx.update({
            "program": program,
            "student": self.enrollment.student,
            "logbooks": Logbook.objects.filter(program=program, user=self.request.user).order_by("start_time"),
            "has_certificate": bool(self.enrollment.certificate_path),
            "certificate_form": CertificateUploadForm(),
            "certificate_url": reverse("dashboard:student_certificate_view", args=[program.pk]),
            "upload_url": reverse("dashboard:student_certificate_upload", args=[program.pk]),
            "create_url": reverse("dashboard:student_logbook_create", args=[program.pk]),
            "back_url": reverse("dashboard:student_program_show", args=[program.pk]),
        })
        return ctx


class AdminStudentLogbookView(LoginRequiredMixin, TemplateView):
    """Laporan logbook satu student (read-only) untuk admin, atau staff di Study Program yang sama."""

    template_name = "dashboard/admin/logbook/list.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        program = get_object_or_404(Program, pk=kwargs["pk"])
        student_user, student = manageable_student(self.request.user, kwargs["uid"])
        enrollment = get_object_or_404(ProgramEnrollment, program=program, student=student)
        ctx.update({
            "program": program,
            "student_user": student_user,
            "student": student,
            "logbooks": Logbook.objects.filter(program=program, user=student_user).order_by("start_time"),
            "has_certificate": bool(enrollment.certificate_path),
            "certificate_url": reverse("dashboard:admin_certificate_view", args=[program.pk, student_user.pk]),
            "back_url": reverse("dashboard:users_list") + "?tab=all",
        })
        return ctx


@login_required
@require_POST
def student_logbook_create(request, pk):
    program = get_object_or_404(Program, pk=pk)
    _student_enrollment(request.user, program)
    form = LogbookForm(request.POST, request.FILES, program=program)
    if not form.is_valid():
        # Form ada di modal, jadi error dikirim lewat flash message.
        messages.error(request, " ".join(e for errors in form.errors.values() for e in errors))
        return redirect(_program_logbook_url(program))
    entry = form.save(commit=False)
    entry.program = program
    entry.user = request.user
    entry.save()
    messages.success(request, "Logbook entry added successfully.")
    return redirect(_program_logbook_url(program))


@login_required
@require_POST
def student_logbook_edit(request, pk, lid):
    # Form edit ada di modal di halaman daftar, jadi hanya menerima POST (error lewat flash message).
    program = get_object_or_404(Program, pk=pk)
    _student_enrollment(request.user, program)
    # Hanya pemilik yang bisa mengubah. Entry milik orang lain dianggap tidak ada.
    entry = get_object_or_404(Logbook, pk=lid, program=program, user=request.user)
    form = LogbookForm(request.POST, request.FILES, instance=entry, program=program)
    if not form.is_valid():
        messages.error(request, " ".join(e for errors in form.errors.values() for e in errors))
        return redirect(_program_logbook_url(program))
    if form.cleaned_data.get("image") and entry.image:
        entry.image.delete(save=False)
    form.save()
    messages.success(request, "Logbook entry updated successfully.")
    return redirect(_program_logbook_url(program))


@login_required
@require_http_methods(["GET", "POST"])
def student_logbook_delete(request, pk, lid):
    program = get_object_or_404(Program, pk=pk)
    _student_enrollment(request.user, program)
    entry = get_object_or_404(Logbook, pk=lid, program=program, user=request.user)
    if request.method == "POST":
        if entry.image:
            entry.image.delete(save=False)
        entry.delete()
        messages.success(request, "Logbook entry deleted successfully.")
        return redirect(_program_logbook_url(program))
    return render(request, "dashboard/confirm_page.html", {
        "title": "Delete logbook entry?",
        "message": "This logbook entry and its image will be permanently deleted.",
        "detail": entry.name,
        "button": "Yes, delete",
        "button_class": "bg-red-600 hover:bg-red-700",
        "action_url": request.path,
        "cancel_url": _program_logbook_url(program),
    })


@login_required
@require_POST
def student_certificate_upload(request, pk):
    program = get_object_or_404(Program, pk=pk)
    enrollment = _student_enrollment(request.user, program)
    form = CertificateUploadForm(request.POST, request.FILES)
    if form.is_valid():
        save_certificate(enrollment, form.cleaned_data["certificate"])
        messages.success(request, "Certificate uploaded successfully.")
    else:
        messages.error(request, " ".join(e for errors in form.errors.values() for e in errors))
    return redirect(_program_logbook_url(program))


@login_required
@require_GET
def student_certificate_view(request, pk):
    program = get_object_or_404(Program, pk=pk)
    enrollment = _student_enrollment(request.user, program)
    return _certificate_file_response(enrollment, f"certificate-{program.pk}.pdf")


@login_required
@require_GET
def admin_certificate_view(request, pk, uid):
    program = get_object_or_404(Program, pk=pk)
    student_user, student = manageable_student(request.user, uid)
    enrollment = get_object_or_404(ProgramEnrollment, program=program, student=student)
    return _certificate_file_response(enrollment, f"certificate-{student_user.username}-{program.pk}.pdf")