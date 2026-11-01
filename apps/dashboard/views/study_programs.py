"""Fitur Study Programs: list, create, update, detail, delete (CBV) + aksi tambahan.

Lima view CRUD memakai generic view Django secara langsung tanpa CrudSpec.
Autocomplete, tambah Partnership, dan tambah Outbound Lecturer tetap sebagai
view function karena merupakan aksi POST/JSON satu kali, bukan CRUD generik.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import ProtectedError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.academic.models import Faculty, StudyProgram
from apps.academic.study_program_csv import search_s1_programs
from apps.international.models import OutboundLecturer, Partnership

from .. import forms as f
from .base import _cell, _detail_fields, _is_admin

STUDY_PROGRAM_COLUMNS = ["name", "faculty", "degree"]


def _study_program_list_filter(qs, request):
    """Filter dropdown halaman list Study Programs: Faculty."""
    faculty_id = request.GET.get("faculty", "").strip()
    if faculty_id.isdigit():
        qs = qs.filter(faculty_id=int(faculty_id))
    else:
        faculty_id = ""
    return qs, {
        "faculties": Faculty.objects.order_by("name"),
        "selected": {"faculty": faculty_id},
    }


def _study_program_detail_context(obj, request):
    return {
        # number_format($x, 0, ',', '.') di Laravel: tanpa desimal
        "ukt_fee": f"{int(obj.ukt_fee or 0):,}".replace(",", "."),
        "ipi_fee": f"{int(obj.ipi_fee or 0):,}".replace(",", "."),
        "partnerships": obj.partnerships.all(),
        "outbound_lecturers": obj.outbound_lecturers.all(),
    }


def _study_program_row(obj):
    return {
        "obj": obj,
        "cells": [_cell(obj, c) for c in STUDY_PROGRAM_COLUMNS],
        "detail_url": reverse("dashboard:study_programs_detail", args=[obj.pk]),
        "edit_url": reverse("dashboard:study_programs_update", args=[obj.pk]),
        "delete_url": reverse("dashboard:study_programs_delete", args=[obj.pk]),
    }


class StudyProgramAccessMixin(PermissionRequiredMixin):
    """Akses fitur Study Programs: admin, atau pemegang permission accounts.manage_program."""

    permission_required = "accounts.manage_program"

    def has_permission(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        return _is_admin(user) or user.has_perm(self.permission_required)


class StudyProgramListView(StudyProgramAccessMixin, ListView):
    model = StudyProgram
    paginate_by = 20
    template_name = "dashboard/study_programs/list.html"

    def get_queryset(self):
        qs = StudyProgram.objects.order_by("-pk")
        search = self.request.GET.get("search", "").strip()
        if search:
            qs = qs.filter(name__icontains=search)
        qs, self.extra_ctx = _study_program_list_filter(qs, self.request)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(getattr(self, "extra_ctx", {}))
        ctx["list_url"] = reverse("dashboard:study_programs_list")
        ctx["create_url"] = reverse("dashboard:study_programs_create")
        ctx["search"] = self.request.GET.get("search", "")
        query = self.request.GET.copy()
        query.pop("page", None)
        ctx["filter_qs"] = query.urlencode()
        ctx["has_filters"] = any(v for v in query.values())
        ctx["rows"] = [_study_program_row(obj) for obj in ctx["object_list"]]
        ctx["headers"] = [
            StudyProgram._meta.get_field(c).verbose_name.capitalize()
            for c in STUDY_PROGRAM_COLUMNS
        ]
        ctx["is_admin"] = _is_admin(self.request.user)
        return ctx


class StudyProgramCreateView(StudyProgramAccessMixin, CreateView):
    model = StudyProgram
    form_class = f.StudyProgramForm
    template_name = "dashboard/study_programs/form.html"

    def get_success_url(self):
        return reverse("dashboard:study_programs_list")

    def form_valid(self, form):
        messages.success(self.request, "Study Programs: record added successfully.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_url"] = reverse("dashboard:study_programs_list")
        ctx["action"] = "New"
        return ctx


class StudyProgramUpdateView(StudyProgramAccessMixin, UpdateView):
    model = StudyProgram
    form_class = f.StudyProgramForm
    template_name = "dashboard/study_programs/form.html"

    def get_success_url(self):
        return reverse("dashboard:study_programs_list")

    def form_valid(self, form):
        messages.success(self.request, "Study Programs: changes saved.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_url"] = reverse("dashboard:study_programs_list")
        ctx["action"] = "Edit"
        return ctx


# Detail hanya dibaca: staff boleh melihat semua record.
class StudyProgramDetailView(StudyProgramAccessMixin, DetailView):
    model = StudyProgram
    template_name = "dashboard/study_programs/detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = self.object
        ctx.update(_study_program_detail_context(obj, self.request))
        ctx["title"] = str(obj)
        ctx["list_url"] = reverse("dashboard:study_programs_list")
        ctx["edit_url"] = reverse("dashboard:study_programs_update", args=[obj.pk])
        ctx["fields"] = _detail_fields(obj)
        ctx["has_image"] = hasattr(obj, "image")
        ctx["image_url"] = obj.image.url if obj.image else None
        return ctx


class StudyProgramDeleteView(StudyProgramAccessMixin, DeleteView):
    model = StudyProgram
    template_name = "dashboard/crud/confirm_delete.html"

    def get_success_url(self):
        return reverse("dashboard:study_programs_list")

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
        except ProtectedError:
            messages.error(
                self.request,
                "Study Programs cannot be deleted because other records still use it.",
            )
            return redirect(self.get_success_url())
        messages.success(self.request, "Study Programs: record deleted.")
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_url"] = reverse("dashboard:study_programs_list")
        # Template confirm_delete.html bersama masih membaca `spec.title`;
        # dict polos ini menggantikan CrudSpec tanpa membuat ketergantungan.
        ctx["spec"] = {"title": "Study Programs"}
        return ctx


@login_required
def study_program_autocomplete(request):
    user = request.user
    if not (_is_admin(user) or user.has_perm("accounts.manage_program")):
        return JsonResponse({"detail": "Forbidden"}, status=403)
    return JsonResponse(search_s1_programs(request.GET.get("query", "")), safe=False)


def _study_program_detail_redirect(pk):
    return redirect("dashboard:study_programs_detail", pk=pk)


@login_required
@require_POST
def study_program_add_partnership(request, pk):
    if not _is_admin(request.user) and not request.user.has_perm(
        "accounts.manage_program"
    ):
        raise PermissionDenied
    study_program = get_object_or_404(StudyProgram, pk=pk)
    number = request.POST.get("mou_moa_ia_number", "").strip()
    title = request.POST.get("title_of_cooperation", "").strip()
    validity = request.POST.get("validity_period", "").strip()
    if not (number and title and validity):
        messages.error(request, "All fields are required.")
    elif not validity.isdigit() or int(validity) > 32767:
        messages.error(request, "Validity Period must be a whole number.")
    else:
        Partnership.objects.create(
            study_program=study_program,
            mou_moa_ia_number=number,
            title_of_cooperation=title,
            validity_period=int(validity),
        )
        messages.success(request, "Partnership added successfully")
    return _study_program_detail_redirect(study_program.pk)


@login_required
@require_POST
def study_program_add_outbound_lecturer(request, pk):
    if not _is_admin(request.user) and not request.user.has_perm(
        "accounts.manage_program"
    ):
        raise PermissionDenied
    study_program = get_object_or_404(StudyProgram, pk=pk)
    data = {
        key: request.POST.get(key, "").strip()
        for key in (
            "lecturer_name",
            "gender",
            "role_in_ki",
            "university_name",
            "activity_year",
        )
    }
    if not all(data.values()):
        messages.error(request, "All fields are required.")
    elif data["gender"] not in ("Male", "Female"):
        messages.error(request, "Gender must be Male or Female.")
    elif not data["activity_year"].isdigit() or int(data["activity_year"]) > 32767:
        messages.error(request, "Activity Year must be a whole number.")
    else:
        OutboundLecturer.objects.create(
            study_program=study_program,
            lecturer_name=data["lecturer_name"],
            gender=data["gender"],
            role_in_ki=data["role_in_ki"],
            university_name=data["university_name"],
            activity_year=int(data["activity_year"]),
        )
        messages.success(request, "Outbound Lecturer added successfully")
    return _study_program_detail_redirect(study_program.pk)