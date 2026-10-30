"""Fitur akademik student: transkrip, study plan, dan ringkasan dashboard."""

from datetime import date

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView

from apps.academic.student_data import krs_data, semester_options, transcript_data

from ..dashboard_stats import student_summary


def _require_student(user):
    # Menu transkrip dan study plan hanya untuk role student (Laravel: dashboard/student/*).
    if not user.has_role("student"):
        raise PermissionDenied


def _require_student_json(user):
    if not user.has_role("student"):
        return JsonResponse({"ok": False, "message": "Forbidden"}, status=403)
    return None


def _semester_label(code):
    year, term = code[:4], code[-1]
    return f"{year} {'Ganjil' if term == '1' else 'Genap'}"


class StudentPageMixin:
    """Halaman akademik student hanya untuk role student (selain role lain: 403)."""

    def dispatch(self, request, *args, **kwargs):
        _require_student(request.user)
        return super().dispatch(request, *args, **kwargs)


class StudentTranscriptView(LoginRequiredMixin, StudentPageMixin, TemplateView):
    """Halaman kosong; data transkrip dimuat lewat AJAX dari student_transcript_data."""

    template_name = "dashboard/student/transcript.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["nim"] = self.request.user.username
        ctx["data_url"] = reverse("dashboard:student_transcript_data")
        return ctx


class StudentStudyPlanView(LoginRequiredMixin, StudentPageMixin, TemplateView):
    """Halaman dengan dropdown semester; tabel KRS dimuat lewat AJAX."""

    template_name = "dashboard/student/study_plan.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        nim = self.request.user.username
        options = semester_options(nim, date.today())
        ctx["nim"] = nim
        ctx["semesters"] = [{"code": c, "label": _semester_label(c)} for c in options]
        ctx["data_url"] = reverse("dashboard:student_study_plan_data")
        return ctx


@login_required
@require_GET
def student_transcript_data(request):
    denied = _require_student_json(request.user)
    if denied:
        return denied
    result = transcript_data(request.user.username)
    return JsonResponse({
        "ok": result["ok"],
        "message": result["message"],
        "from_cache": result["from_cache"],
        "nim": result["nim"],
        "nama": result["nama"],
        "rows": result["rows"],
    })


@login_required
@require_GET
def student_dashboard_data(request):
    """Ringkasan dashboard student (IPK, SKS, masa studi), dimuat lewat AJAX setelah halaman tampil."""
    denied = _require_student_json(request.user)
    if denied:
        return denied
    return JsonResponse(student_summary(request.user.username, date.today()))


@login_required
@require_GET
def student_study_plan_data(request):
    denied = _require_student_json(request.user)
    if denied:
        return denied
    nim = request.user.username
    options = semester_options(nim, date.today())
    selected = request.GET.get("semester", "")
    if selected not in options:
        selected = options[0] if options else ""
    if not selected:
        return JsonResponse({"ok": False, "message": "No semester available for this NIM.", "rows": [],
                             "total_sks": 0, "from_cache": False, "semester": ""})
    result = krs_data(nim, selected)
    return JsonResponse({
        "ok": result["ok"],
        "message": result["message"],
        "from_cache": result["from_cache"],
        "semester": selected,
        "rows": result["rows"],
        "total_sks": result["total_sks"],
    })