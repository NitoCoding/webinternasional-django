"""Fitur Programs: list, create, update, detail, delete (CBV) + aksi enrollment.

Self-contained: setiap view memakai generic view Django secara langsung tanpa
CrudSpec. `program_enrollment_action` dan `program_add_student` adalah aksi POST
satu kali pada halaman detail, dipertahankan sebagai view function di modul ini.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.academic.models import Student
from apps.international.models import IeProgram, Program, ProgramEnrollment

from .. import forms as f
from .base import _cell, _detail_fields, _is_admin, _str_limit

PROGRAM_TITLE = "Program"
PROGRAM_COLUMNS = ["name", "country", "execution_date", "participants_count"]


def _program_list_filter(qs, request):
    """Filter dropdown halaman list Programs: IE Program, Country, dan status waktu."""
    from datetime import date

    today = date.today()
    ie_id = request.GET.get("ie_program", "").strip()
    country = request.GET.get("country", "").strip()
    status = request.GET.get("status", "").strip()

    if ie_id.isdigit():
        qs = qs.filter(ie_program_id=int(ie_id))
    if country:
        qs = qs.filter(country=country)
    if status == "upcoming":
        qs = qs.filter(execution_date__gt=today)
    elif status == "ongoing":
        qs = qs.filter(execution_date__lte=today, end_date__gte=today)
    elif status == "finished":
        qs = qs.filter(end_date__lt=today)
    else:
        status = ""

    countries = (
        Program.objects.exclude(country="")
        .order_by("country")
        .values_list("country", flat=True)
        .distinct()
    )
    return qs, {
        "ie_programs": IeProgram.objects.order_by("name"),
        "countries": countries,
        "status_choices": [
            ("upcoming", "Upcoming"),
            ("ongoing", "Ongoing"),
            ("finished", "Finished"),
        ],
        "selected": {"ie_program": ie_id, "country": country, "status": status},
    }


def _program_row(obj):
    return {
        "obj": obj,
        "cells": [_cell(obj, c) for c in PROGRAM_COLUMNS],
        "detail_url": reverse("dashboard:programs_detail", args=[obj.pk]),
        "edit_url": reverse("dashboard:programs_update", args=[obj.pk]),
        "delete_url": reverse("dashboard:programs_delete", args=[obj.pk]),
    }


def _program_detail_context(obj, request):
    """Konteks halaman detail Program: daftar mahasiswa diterima dan pending."""
    accepted = (
        obj.enrollments.select_related("student")
        .filter(status="approved")
        .order_by("-pk")
    )
    pending = (
        obj.enrollments.select_related("student")
        .filter(status="pending")
        .order_by("created_at")
    )
    return {
        "accepted_page": Paginator(accepted, 10).get_page(request.GET.get("page")),
        "pending_enrollments": pending,
        "description_excerpt": _str_limit(obj.description, 150),
    }


class ProgramAccessMixin(PermissionRequiredMixin):
    """Akses fitur Programs: admin, atau pemegang permission accounts.manage_program."""

    permission_required = "accounts.manage_program"

    def has_permission(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        return _is_admin(user) or user.has_perm(self.permission_required)


class ProgramOwnerMixin:
    """Staff (non-admin) hanya bisa mengubah/menghapus program miliknya sendiri."""

    def get_queryset(self):
        qs = super().get_queryset()
        if not _is_admin(self.request.user):
            qs = qs.filter(created_by=self.request.user)
        return qs


class ProgramListView(ProgramAccessMixin, ListView):
    model = Program
    paginate_by = 20
    template_name = "dashboard/programs/list.html"

    def get_queryset(self):
        qs = Program.objects.order_by("-pk")
        search = self.request.GET.get("search", "").strip()
        if search:
            qs = qs.filter(name__icontains=search)
        qs, self.extra_ctx = _program_list_filter(qs, self.request)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(getattr(self, "extra_ctx", {}))
        ctx["list_url"] = reverse("dashboard:programs_list")
        ctx["create_url"] = reverse("dashboard:programs_create")
        ctx["search"] = self.request.GET.get("search", "")
        query = self.request.GET.copy()
        query.pop("page", None)
        ctx["filter_qs"] = query.urlencode()
        ctx["has_filters"] = any(v for v in query.values())
        ctx["rows"] = [_program_row(obj) for obj in ctx["object_list"]]
        ctx["headers"] = [
            Program._meta.get_field(c).verbose_name.capitalize()
            for c in PROGRAM_COLUMNS
        ]
        ctx["is_admin"] = _is_admin(self.request.user)
        return ctx


class ProgramCreateView(ProgramAccessMixin, CreateView):
    model = Program
    form_class = f.ProgramForm
    template_name = "dashboard/programs/form.html"

    def get_success_url(self):
        return reverse("dashboard:programs_list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Program: record added successfully.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_url"] = reverse("dashboard:programs_list")
        ctx["action"] = "New"
        return ctx


class ProgramUpdateView(ProgramAccessMixin, ProgramOwnerMixin, UpdateView):
    model = Program
    form_class = f.ProgramForm
    template_name = "dashboard/programs/form.html"

    def get_success_url(self):
        return reverse("dashboard:programs_list")

    def form_valid(self, form):
        messages.success(self.request, "Program: changes saved.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_url"] = reverse("dashboard:programs_list")
        ctx["action"] = "Edit"
        return ctx


# Detail hanya dibaca: staff boleh melihat semua record.
class ProgramDetailView(ProgramAccessMixin, DetailView):
    model = Program
    template_name = "dashboard/programs/detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_program_detail_context(self.object, self.request))
        ctx["list_url"] = reverse("dashboard:programs_list")
        ctx["edit_url"] = reverse("dashboard:programs_update", args=[self.object.pk])
        ctx["fields"] = _detail_fields(self.object)
        ctx["has_image"] = hasattr(self.object, "image")
        ctx["image_url"] = self.object.image.url if self.object.image else None
        return ctx


class ProgramDeleteView(ProgramAccessMixin, ProgramOwnerMixin, DeleteView):
    model = Program
    template_name = "dashboard/crud/confirm_delete.html"

    def get_success_url(self):
        return reverse("dashboard:programs_list")

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
        except ProtectedError:
            messages.error(
                self.request,
                "Program cannot be deleted because other records still use it.",
            )
            return redirect(self.get_success_url())
        messages.success(self.request, "Program: record deleted.")
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_url"] = reverse("dashboard:programs_list")
        # Template confirm_delete.html bersama masih membaca `spec.title`;
        # dict polos ini menggantikan CrudSpec tanpa membuat ketergantungan.
        ctx["spec"] = {"title": PROGRAM_TITLE}
        return ctx


def _manageable_program(request, pk):
    user = request.user
    if not (_is_admin(user) or user.has_perm("accounts.manage_program")):
        raise PermissionDenied
    program = get_object_or_404(Program, pk=pk)
    if not _is_admin(user) and program.created_by_id != user.pk:
        raise PermissionDenied
    return program


@login_required
@require_POST
def program_enrollment_action(request, pk, enrollment_pk):
    program = _manageable_program(request, pk)
    enrollment = get_object_or_404(ProgramEnrollment, pk=enrollment_pk, program=program)
    action = request.POST.get("action")
    status = request.POST.get("status")

    if status == ProgramEnrollment.Status.APPROVED:
        enrollment.status = ProgramEnrollment.Status.APPROVED
        enrollment.save(update_fields=["status"])
        ProgramEnrollment.objects.filter(student=enrollment.student).exclude(
            pk=enrollment.pk
        ).exclude(status=ProgramEnrollment.Status.APPROVED).delete()
        approved_count = program.enrollments.filter(
            status=ProgramEnrollment.Status.APPROVED
        ).count()
        if approved_count >= program.participants_count:
            program.enrollments.filter(status=ProgramEnrollment.Status.PENDING).delete()
        messages.success(request, "Student has been approved.")
    elif status == ProgramEnrollment.Status.REJECTED:
        enrollment.delete()
        messages.success(request, "Student has been rejected.")
    elif action in ("finish", "unfinish"):
        enrollment.is_finished = action == "finish"
        enrollment.save(update_fields=["is_finished"])
        messages.success(request, "Student status has been updated.")
    elif action == "delete":
        enrollment.delete()
        messages.success(request, "Student has been removed from the program.")
    else:
        messages.error(request, "Invalid action.")
    return redirect("dashboard:programs_detail", pk=program.pk)


@login_required
@require_POST
def program_add_student(request, pk):
    program = _manageable_program(request, pk)
    nim = request.POST.get("nim", "").strip()
    detail_url = redirect("dashboard:programs_detail", pk=program.pk)

    student = (
        Student.objects.filter(student_id_number=nim)
        .select_related("study_program")
        .first()
    )
    if not student:
        messages.error(request, "Student with this NIM was not found.")
        return detail_url

    approved_count = program.enrollments.filter(
        status=ProgramEnrollment.Status.APPROVED
    ).count()
    if approved_count >= program.participants_count:
        messages.error(
            request, "This program has reached its maximum participant limit."
        )
        return detail_url
    if program.enrollments.filter(student=student).exists():
        messages.error(request, "This student is already enrolled in this program.")
        return detail_url
    if not program.study_programs.filter(pk=student.study_program_id).exists():
        messages.error(request, "Student's study program does not match this program.")
        return detail_url

    ProgramEnrollment.objects.create(
        program=program,
        student=student,
        status=ProgramEnrollment.Status.APPROVED,
        is_finished=True,
    )
    messages.success(request, "Student has been added to the program.")
    return detail_url