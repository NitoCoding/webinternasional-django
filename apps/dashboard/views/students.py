"""Fitur Students (CRUD admin): list, create, update, detail, delete (CBV).

Self-contained: setiap view memakai generic view Django secara langsung tanpa
CrudSpec. Seluruh template memakai template crud bawaan dashboard.
"""

from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import ProtectedError
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.academic.models import Student

from .. import forms as f
from .base import _cell, _detail_fields, _is_admin

STUDENT_TITLE = "Students"
STUDENT_COLUMNS = ["student_id_number", "name", "study_program", "status"]


def _student_row(obj):
    return {
        "obj": obj,
        "cells": [_cell(obj, c) for c in STUDENT_COLUMNS],
        "detail_url": reverse("dashboard:students_detail", args=[obj.pk]),
        "edit_url": reverse("dashboard:students_update", args=[obj.pk]),
        "delete_url": reverse("dashboard:students_delete", args=[obj.pk]),
    }


class StudentAccessMixin(PermissionRequiredMixin):
    """Akses fitur Students: admin, atau pemegang permission accounts.manage_user."""

    permission_required = "accounts.manage_user"

    def has_permission(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        return _is_admin(user) or user.has_perm(self.permission_required)


class StudentListView(StudentAccessMixin, ListView):
    model = Student
    paginate_by = 20
    template_name = "dashboard/crud/list.html"

    def get_queryset(self):
        return Student.objects.order_by("-pk")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_url"] = reverse("dashboard:students_list")
        ctx["create_url"] = reverse("dashboard:students_create")
        ctx["search"] = self.request.GET.get("search", "")
        query = self.request.GET.copy()
        query.pop("page", None)
        ctx["filter_qs"] = query.urlencode()
        ctx["has_filters"] = any(v for v in query.values())
        ctx["rows"] = [_student_row(obj) for obj in ctx["object_list"]]
        ctx["headers"] = [
            Student._meta.get_field(c).verbose_name.capitalize()
            for c in STUDENT_COLUMNS
        ]
        ctx["is_admin"] = _is_admin(self.request.user)
        # Template crud/list.html bersama masih membaca `spec.title`;
        # dict polos ini menggantikan CrudSpec tanpa membuat ketergantungan.
        ctx["spec"] = {"title": STUDENT_TITLE}
        return ctx


class StudentCreateView(StudentAccessMixin, CreateView):
    model = Student
    form_class = f.StudentForm
    template_name = "dashboard/crud/form.html"

    def get_success_url(self):
        return reverse("dashboard:students_list")

    def form_valid(self, form):
        messages.success(self.request, "Students: record added successfully.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_url"] = reverse("dashboard:students_list")
        ctx["action"] = "New"
        # Template crud/form.html bersama masih membaca `spec.title`.
        ctx["spec"] = {"title": STUDENT_TITLE}
        return ctx


class StudentUpdateView(StudentAccessMixin, UpdateView):
    model = Student
    form_class = f.StudentForm
    template_name = "dashboard/crud/form.html"

    def get_success_url(self):
        return reverse("dashboard:students_list")

    def form_valid(self, form):
        messages.success(self.request, "Students: changes saved.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_url"] = reverse("dashboard:students_list")
        ctx["action"] = "Edit"
        # Template crud/form.html bersama masih membaca `spec.title`.
        ctx["spec"] = {"title": STUDENT_TITLE}
        return ctx


# Detail hanya dibaca: staff boleh melihat semua record.
class StudentDetailView(StudentAccessMixin, DetailView):
    model = Student
    template_name = "dashboard/crud/detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = self.object
        ctx["title"] = str(obj)
        ctx["list_url"] = reverse("dashboard:students_list")
        ctx["edit_url"] = reverse("dashboard:students_update", args=[obj.pk])
        ctx["fields"] = _detail_fields(obj)
        ctx["has_image"] = hasattr(obj, "image")
        ctx["image_url"] = obj.image.url if obj.image else None
        # Template crud/detail.html bersama masih membaca `spec.title`.
        ctx["spec"] = {"title": STUDENT_TITLE}
        return ctx


class StudentDeleteView(StudentAccessMixin, DeleteView):
    model = Student
    template_name = "dashboard/crud/confirm_delete.html"

    def get_success_url(self):
        return reverse("dashboard:students_list")

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
        except ProtectedError:
            messages.error(
                self.request,
                "Students cannot be deleted because other records still use it.",
            )
            return redirect(self.get_success_url())
        messages.success(self.request, "Students: record deleted.")
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_url"] = reverse("dashboard:students_list")
        # Template confirm_delete.html bersama masih membaca `spec.title`;
        # dict polos ini menggantikan CrudSpec tanpa membuat ketergantungan.
        ctx["spec"] = {"title": STUDENT_TITLE}
        return ctx