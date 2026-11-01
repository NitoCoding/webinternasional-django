"""Fitur Users: list, create, update, detail, delete (CBV) + aksi pengguna.

Self-contained: setiap view memakai generic view Django secara langsung tanpa
CrudSpec. Menampung filter/tab list, aksi accept/reject/toggle-active, dan
formulir tambahan (add student, upload CSV, add staff, english score, detail
fragment, versi cetak) yang tadinya tersebar di urls.py dan user_views.py.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.db.models import Exists, OuterRef, Q
from django.db.models.functions import Substr
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import DeleteView, DetailView, ListView, UpdateView
from django.views.generic.edit import CreateView

from apps.academic.models import Staff, Student, StudyProgram
from apps.academic.sipakamase import SipakamaseClient, SipakamaseError
from apps.accounts.models import User
from apps.international.models import ProgramEnrollment

from .. import forms as f
from ..user_forms import (
    AddStudentForm,
    CsvUploadForm,
    EnglishScoreForm,
    StaffCreateForm,
)
from ..user_services import (
    ImportResult,
    create_staff,
    import_student,
    import_students_csv,
    manageable_student,
    update_english_score,
)
from .base import _detail_fields, _is_admin

USER_TABS = ("all", "active", "staff", "waiting")

TAB_LABELS = {
    "all": "All Students",
    "active": "Active Students",
    "staff": "Staff",
    "waiting": "Waiting List",
}


def _user_enrollment_flags():
    """Penanda status program per user (pengganti logika whereHas Laravel)."""
    enr = ProgramEnrollment.objects.filter(student_id=OuterRef("student__pk"))
    return {
        "has_completed": Exists(enr.filter(status=ProgramEnrollment.Status.APPROVED, is_finished=True)),
        "has_in_progress": Exists(enr.filter(status=ProgramEnrollment.Status.APPROVED, is_finished=False)),
        "has_pending": Exists(enr.filter(status=ProgramEnrollment.Status.PENDING)),
        "has_any_enrollment": Exists(enr),
    }


def _user_list_filter(qs, request):
    """Tab (All, Active, Staff, Waiting), filter, dan jumlah waiting untuk list users.

    Mengikuti UserController@index di Laravel. Staff hanya melihat mahasiswa
    dari Study Program miliknya dan tidak melihat tab Staff.
    """
    user = request.user
    is_admin = _is_admin(user)
    staff = getattr(user, "staff", None)
    staff_sp = staff.study_program_id if staff else None

    tab = request.GET.get("tab", "all")
    if tab not in USER_TABS or (tab == "staff" and not is_admin):
        tab = "all"

    qs = qs.exclude(username="admin").annotate(**_user_enrollment_flags())

    waiting_scope = Student.objects.filter(status=Student.Status.WAITING, study_program__isnull=False)
    if not is_admin:
        if staff_sp is None:
            qs = qs.none()
            waiting_scope = waiting_scope.none()
        else:
            qs = qs.filter(student__study_program_id=staff_sp)
            waiting_scope = waiting_scope.filter(study_program_id=staff_sp)

    if tab == "all":
        qs = qs.filter(student__is_verified=True)
    elif tab == "active":
        qs = qs.filter(student__is_active=True)
    elif tab == "staff":
        qs = qs.filter(groups__name="staff")
    elif tab == "waiting":
        qs = qs.filter(student__status=Student.Status.WAITING, student__study_program__isnull=False)

    show_filters = tab in ("all", "active")
    study_program = request.GET.get("study_program", "") if is_admin else ""
    year = request.GET.get("year", "").strip()
    student_status = request.GET.get("studentStatus", "")

    if show_filters:
        if study_program:
            qs = qs.filter(student__study_program_id=study_program)
        if year:
            qs = qs.annotate(nim_year=Substr("student__student_id_number", 5, 2)).filter(
                nim_year=year[-2:]
            )
        if student_status == "completed":
            qs = qs.filter(has_completed=True)
        elif student_status == "in_progress":
            qs = qs.filter(has_in_progress=True)
        elif student_status == "not_started":
            # Sama dengan badge NOT STARTED: tanpa completed, in progress, atau pending.
            qs = qs.filter(has_completed=False, has_in_progress=False, has_pending=False)

    years = []
    if show_filters:
        year_scope = Student.objects.all()
        if not is_admin:
            year_scope = year_scope.filter(study_program_id=staff_sp) if staff_sp else year_scope.none()
        years = [
            "20" + y["year"]
            for y in year_scope.annotate(year=Substr("student_id_number", 5, 2))
            .values("year")
            .distinct()
            .order_by("-year")
            if y["year"]
        ]

    ctx = {
        "tab": tab,
        "is_admin": is_admin,
        "csv_errors": (
            request.session.pop("csv_errors", [])
            if request.resolver_match and request.resolver_match.url_name == "users_list"
            else []
        ),
        "waiting_count": waiting_scope.count(),
        "show_filters": show_filters,
        "study_programs": StudyProgram.objects.order_by("name") if is_admin else [],
        "years": years,
        "selected_study_program": study_program,
        "selected_year": year,
        "selected_student_status": student_status,
    }
    return qs, ctx


USER_TITLE = "Users"
USER_COLUMNS = ["username", "name", "email", "is_active"]
USER_SEARCH_FIELDS = ("name", "username", "email")


def _user_row(obj):
    return {
        "obj": obj,
        "cells": [],
        "detail_url": reverse("dashboard:users_detail", args=[obj.pk]),
        "edit_url": reverse("dashboard:users_update", args=[obj.pk]),
        "delete_url": reverse("dashboard:users_delete", args=[obj.pk]),
    }


class UsersAccessMixin(PermissionRequiredMixin):
    """Akses fitur Users: admin, atau pemegang permission accounts.manage_user."""

    permission_required = "accounts.manage_user"

    def has_permission(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        return _is_admin(user) or user.has_perm(self.permission_required)


class UsersListView(UsersAccessMixin, ListView):
    model = User
    paginate_by = 20
    template_name = "dashboard/users/list.html"

    def get_queryset(self):
        qs = User.objects.order_by("-pk").select_related(
            "student__study_program", "staff__study_program"
        )
        search = self.request.GET.get("search", "").strip()
        if search:
            cond = Q()
            for name in USER_SEARCH_FIELDS:
                cond |= Q(**{f"{name}__icontains": search})
            qs = qs.filter(cond)
        qs, self.extra_ctx = _user_list_filter(qs, self.request)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(getattr(self, "extra_ctx", {}))
        ctx["list_url"] = reverse("dashboard:users_list")
        ctx["create_url"] = reverse("dashboard:users_create")
        ctx["search"] = self.request.GET.get("search", "")
        query = self.request.GET.copy()
        query.pop("page", None)
        ctx["filter_qs"] = query.urlencode()
        ctx["has_filters"] = any(v for v in query.values())
        ctx["rows"] = [_user_row(obj) for obj in ctx["object_list"]]
        ctx["headers"] = [
            User._meta.get_field(c).verbose_name.capitalize()
            for c in USER_COLUMNS
        ]
        return ctx


class UsersCreateView(UsersAccessMixin, CreateView):
    model = User
    form_class = f.UserForm
    template_name = "dashboard/crud/form.html"

    def get_success_url(self):
        return reverse("dashboard:users_list")

    def form_valid(self, form):
        if _blocks_staff_assignment(self.request, form):
            return self.form_invalid(form)
        messages.success(self.request, "Users: record added successfully.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_url"] = reverse("dashboard:users_list")
        ctx["action"] = "New"
        # Template crud/form.html bersama masih membaca `spec.title`;
        # dict polos ini menggantikan CrudSpec tanpa membuat ketergantungan.
        ctx["spec"] = {"title": USER_TITLE}
        return ctx


class UsersUpdateView(UsersAccessMixin, UpdateView):
    model = User
    form_class = f.UserForm
    template_name = "dashboard/crud/form.html"

    def get_success_url(self):
        return reverse("dashboard:users_list")

    def form_valid(self, form):
        if _blocks_staff_assignment(self.request, form):
            return self.form_invalid(form)
        messages.success(self.request, "Users: changes saved.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_url"] = reverse("dashboard:users_list")
        ctx["action"] = "Edit"
        # Template crud/form.html bersama masih membaca `spec.title`;
        # dict polos ini menggantikan CrudSpec tanpa membuat ketergantungan.
        ctx["spec"] = {"title": USER_TITLE}
        return ctx


class UsersDetailView(UsersAccessMixin, DetailView):
    # Route `users_detail` dipertahankan untuk menjaga nama URL lama; template
    # memakai detail_generik crud (detail user sesungguhnya lewat student_detail).
    model = User
    template_name = "dashboard/crud/detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = self.object
        ctx["title"] = str(obj)
        ctx["list_url"] = reverse("dashboard:users_list")
        ctx["edit_url"] = reverse("dashboard:users_update", args=[obj.pk])
        ctx["fields"] = _detail_fields(obj)
        ctx["has_image"] = hasattr(obj, "image")
        ctx["image_url"] = obj.image.url if obj.image else None
        # Template crud/detail.html bersama masih membaca `spec.title`;
        # dict polos ini menggantikan CrudSpec tanpa membuat ketergantungan.
        ctx["spec"] = {"title": USER_TITLE}
        return ctx


class UsersDeleteView(UsersAccessMixin, DeleteView):
    model = User
    template_name = "dashboard/crud/confirm_delete.html"

    def get_success_url(self):
        return reverse("dashboard:users_list")

    def form_valid(self, form):
        from django.db.models import ProtectedError

        try:
            response = super().form_valid(form)
        except ProtectedError:
            messages.error(
                self.request,
                "Users cannot be deleted because other records still use it.",
            )
            return redirect(self.get_success_url())
        messages.success(self.request, "Users: record deleted.")
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_url"] = reverse("dashboard:users_list")
        # Template confirm_delete.html bersama masih membaca `spec.title`;
        # dict polos ini menggantikan CrudSpec tanpa membuat ketergantungan.
        ctx["spec"] = {"title": USER_TITLE}
        return ctx


def _blocks_staff_assignment(request, form):
    """Staff tidak boleh membuat atau memberi role staff (lewat form generik users)."""
    if _is_admin(request.user):
        return False
    groups = form.cleaned_data.get("groups") or []
    if any(group.name == "staff" for group in groups):
        form.add_error("groups", "Only admin can create or assign staff accounts.")
        return True
    return False


def _can_manage_users(user):
    return _is_admin(user) or user.has_perm("accounts.manage_user")


def _require_manage_users(user):
    if not _can_manage_users(user):
        raise PermissionDenied


def _users_url(tab="all"):
    return f"{reverse('dashboard:users_list')}?tab={tab}"


def _back_to_users(request, tab):
    if tab not in USER_TABS:
        tab = "all"
    return redirect(f"{reverse('dashboard:users_list')}?tab={tab}")


def _flash_form_errors(request, form):
    """Form di modal tidak punya halaman sendiri, jadi error dikirim lewat flash message."""
    text = " ".join(e for errors in form.errors.values() for e in errors)
    messages.error(request, text or "Please check the form and try again.")


def _manageable_student(request, pk):
    return manageable_student(request.user, pk)


def _choose_program_permission():
    return Permission.objects.get(codename="choose_program", content_type__app_label="accounts")


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
    rows = qs.select_related("student__study_program", "staff__study_program")
    return render(request, "dashboard/users/print.html", {
        "rows": rows,
        "search": search,
        "tab": extra["tab"],
        "tab_label": TAB_LABELS.get(extra["tab"], "All Students"),
        "count": rows.count(),
    })


@login_required
@require_POST
def user_accept(request, pk):
    student_user, student = _manageable_student(request, pk)
    student.status = Student.Status.ACCEPTED
    student.is_verified = True
    student.is_active = True
    student.save()
    student_user.is_active = True
    student_user.save(update_fields=["is_active"])
    student_user.user_permissions.add(_choose_program_permission())
    messages.success(request, "Student has been accepted.")
    return _back_to_users(request, "waiting")


@login_required
@require_POST
def user_reject(request, pk):
    student_user, student = _manageable_student(request, pk)
    student.status = Student.Status.REJECTED
    student.is_verified = False
    student.is_active = False
    student.save()
    student_user.is_active = False
    student_user.save(update_fields=["is_active"])
    student_user.user_permissions.remove(_choose_program_permission())
    messages.success(request, "Student has been rejected.")
    return _back_to_users(request, "waiting")


@login_required
@require_POST
def user_toggle_active(request, pk):
    student_user, student = _manageable_student(request, pk)
    new_state = not student.is_active
    student.is_active = new_state
    student.save()
    student_user.is_active = new_state
    student_user.save(update_fields=["is_active"])
    messages.success(request, "Student has been activated." if new_state else "Student has been deactivated.")
    return _back_to_users(request, request.POST.get("tab", "all"))