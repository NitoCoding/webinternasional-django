from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.academic.sipakamase import SipakamaseClient, SipakamaseError
from apps.accounts.models import User

from .crud import _is_admin, _user_list_filter
from .user_forms import AddStudentForm, CsvUploadForm, EnglishScoreForm, StaffCreateForm
from .user_services import (
    ImportResult,
    create_staff,
    import_student,
    import_students_csv,
    manageable_student,
    update_english_score,
)


def _can_manage_users(user):
    return _is_admin(user) or user.has_perm("accounts.manage_user")


def _require_manage_users(user):
    if not _can_manage_users(user):
        raise PermissionDenied


def _users_url(tab="all"):
    return f"{reverse('dashboard:users_list')}?tab={tab}"


def _flash_form_errors(request, form):
    """Form di modal tidak punya halaman sendiri, jadi error dikirim lewat flash message."""
    text = " ".join(e for errors in form.errors.values() for e in errors)
    messages.error(request, text or "Please check the form and try again.")


TAB_LABELS = {
    "all": "All Students",
    "active": "Active Students",
    "staff": "Staff",
    "waiting": "Waiting List",
}


@login_required
@require_POST
def add_student(request):
    _require_manage_users(request.user)
    tab = request.POST.get("tab", "all")
    form = AddStudentForm(request.POST)
    if not form.is_valid():
        _flash_form_errors(request, form)
        return redirect(_users_url(tab))
    try:
        api = SipakamaseClient()
    except SipakamaseError as exc:
        result = ImportResult(False, str(exc))
    else:
        try:
            result = import_student(form.cleaned_data["nim"], request.user, api)
        except SipakamaseError as exc:
            result = ImportResult(False, str(exc))
        finally:
            api.close()
    if result.ok:
        messages.success(request, result.message)
    else:
        messages.error(request, result.message)
    return redirect(_users_url(tab))


@login_required
@require_POST
def upload_csv(request):
    _require_manage_users(request.user)
    tab = request.POST.get("tab", "all")
    form = CsvUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        _flash_form_errors(request, form)
        return redirect(_users_url(tab))
    result = import_students_csv(form.cleaned_data["csv_file"], request.user)
    if result.fatal:
        messages.error(request, result.fatal)
        return redirect(_users_url(tab))
    messages.success(
        request,
        f"CSV import finished: {result.created} added, {result.updated} updated, "
        f"{len(result.errors)} failed.",
    )
    if result.errors:
        request.session["csv_errors"] = result.errors
    return redirect(_users_url(tab))


@login_required
@require_POST
def add_staff(request):
    if not _is_admin(request.user):
        # Hanya admin yang boleh membuat staff (staff tidak boleh membuat staff lain).
        raise PermissionDenied
    form = StaffCreateForm(request.POST)
    if not form.is_valid():
        _flash_form_errors(request, form)
        return redirect(_users_url("staff"))
    create_staff(request.user, form.cleaned_data, form.cleaned_data["study_program"])
    messages.success(request, "Staff added successfully.")
    return redirect(_users_url("staff"))


@login_required
@require_POST
def english_score(request, pk):
    _, student = manageable_student(request.user, pk)
    form = EnglishScoreForm(request.POST)
    tab = request.POST.get("tab", "all")
    if form.is_valid():
        update_english_score(student, form.cleaned_data["english_score"])
        messages.success(request, "English score updated.")
    else:
        messages.error(request, "English score must be a whole number from 0 to 100.")
    return redirect(_users_url(tab))


@login_required
@require_GET
def student_detail(request, pk):
    """Isi modal detail student (fragmen HTML, dimuat lewat fetch dari list)."""
    student_user, student = manageable_student(request.user, pk)
    enrollments = student.enrollments.select_related("program", "program__ie_program").order_by("-pk")
    return render(request, "dashboard/users/detail_fragment.html", {
        "student_user": student_user,
        "student": student,
        "enrollments": enrollments,
        "english_score_form": EnglishScoreForm(initial={"english_score": student.english_score}),
        "tab": request.GET.get("tab", "all"),
    })


@login_required
@require_GET
def users_print(request):
    """Versi cetak daftar users dengan filter yang sama. Simpan sebagai PDF lewat dialog cetak browser."""
    _require_manage_users(request.user)
    qs = User.objects.order_by("-pk")
    search = request.GET.get("search", "").strip()
    if search:
        # Sama dengan search_fields di spec users: name, username, email.
        qs = qs.filter(Q(name__icontains=search) | Q(username__icontains=search) | Q(email__icontains=search))
    qs, extra = _user_list_filter(qs, request)
    rows = qs.select_related("student__study_program")
    return render(request, "dashboard/users/print.html", {
        "rows": rows,
        "search": search,
        "tab": extra["tab"],
        "tab_label": TAB_LABELS.get(extra["tab"], "All Students"),
        "count": rows.count(),
    })
