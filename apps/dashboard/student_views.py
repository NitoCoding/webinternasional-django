from datetime import date

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET

from apps.academic.student_data import krs_data, semester_options, transcript_data

from .dashboard_stats import student_summary


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


@login_required
@require_GET
def student_transcript(request):
    """Halaman kosong; data transkrip dimuat lewat AJAX dari student_transcript_data."""
    _require_student(request.user)
    return render(request, "dashboard/student/transcript.html", {
        "nim": request.user.username,
        "data_url": reverse("dashboard:student_transcript_data"),
    })


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
def student_study_plan(request):
    """Halaman dengan dropdown semester; tabel KRS dimuat lewat AJAX."""
    _require_student(request.user)
    nim = request.user.username
    options = semester_options(nim, date.today())
    return render(request, "dashboard/student/study_plan.html", {
        "nim": nim,
        "semesters": [{"code": c, "label": _semester_label(c)} for c in options],
        "data_url": reverse("dashboard:student_study_plan_data"),
    })


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
