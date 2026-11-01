"""Fitur Faculties: list, create, update, detail, delete (CBV).

Self-contained: setiap view memakai generic view Django secara langsung
(ListView, CreateView, UpdateView, DetailView, DeleteView) tanpa CrudSpec.
Konteks template dipertahankan persis seperti sebelumnya.
"""

from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import ProtectedError
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.academic.models import Faculty

from .. import forms as f
from .base import _cell, _detail_fields, _is_admin

FACULTY_COLUMNS = ["name", "code"]


def _faculty_row(obj):
    return {
        "obj": obj,
        "cells": [_cell(obj, c) for c in FACULTY_COLUMNS],
        "detail_url": reverse("dashboard:faculties_detail", args=[obj.pk]),
        "edit_url": reverse("dashboard:faculties_update", args=[obj.pk]),
        "delete_url": reverse("dashboard:faculties_delete", args=[obj.pk]),
    }


class FacultyAccessMixin(PermissionRequiredMixin):
    """Akses fitur Faculties: admin, atau pemegang permission accounts.manage_program."""

    permission_required = "accounts.manage_program"

    def has_permission(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        return _is_admin(user) or user.has_perm(self.permission_required)


class FacultyListView(FacultyAccessMixin, ListView):
    model = Faculty
    paginate_by = 20
    template_name = "dashboard/faculties/list.html"

    def get_queryset(self):
        qs = Faculty.objects.order_by("-pk")
        search = self.request.GET.get("search", "").strip()
        if search:
            qs = qs.filter(name__icontains=search)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_url"] = reverse("dashboard:faculties_list")
        ctx["create_url"] = reverse("dashboard:faculties_create")
        ctx["search"] = self.request.GET.get("search", "")
        query = self.request.GET.copy()
        query.pop("page", None)
        ctx["filter_qs"] = query.urlencode()
        ctx["has_filters"] = any(v for v in query.values())
        ctx["rows"] = [_faculty_row(obj) for obj in ctx["object_list"]]
        ctx["headers"] = [
            Faculty._meta.get_field(c).verbose_name.capitalize()
            for c in FACULTY_COLUMNS
        ]
        ctx["is_admin"] = _is_admin(self.request.user)
        return ctx


class FacultyCreateView(FacultyAccessMixin, CreateView):
    model = Faculty
    form_class = f.FacultyForm
    template_name = "dashboard/faculties/form.html"

    def get_success_url(self):
        return reverse("dashboard:faculties_list")

    def form_valid(self, form):
        messages.success(self.request, "Faculties: record added successfully.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_url"] = reverse("dashboard:faculties_list")
        ctx["action"] = "New"
        return ctx


class FacultyUpdateView(FacultyAccessMixin, UpdateView):
    model = Faculty
    form_class = f.FacultyForm
    template_name = "dashboard/faculties/form.html"

    def get_success_url(self):
        return reverse("dashboard:faculties_list")

    def form_valid(self, form):
        messages.success(self.request, "Faculties: changes saved.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_url"] = reverse("dashboard:faculties_list")
        ctx["action"] = "Edit"
        return ctx


# Detail hanya dibaca: staff boleh melihat semua record.
class FacultyDetailView(FacultyAccessMixin, DetailView):
    model = Faculty
    template_name = "dashboard/faculties/detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = self.object
        ctx["title"] = str(obj)
        ctx["list_url"] = reverse("dashboard:faculties_list")
        ctx["edit_url"] = reverse("dashboard:faculties_update", args=[obj.pk])
        ctx["fields"] = _detail_fields(obj)
        ctx["has_image"] = hasattr(obj, "image")
        ctx["image_url"] = obj.image.url if obj.image else None
        # Template detail bersama membaca `spec.title`; dict polos menggantikan CrudSpec.
        ctx["spec"] = {"title": "Faculties"}
        return ctx


class FacultyDeleteView(FacultyAccessMixin, DeleteView):
    model = Faculty
    template_name = "dashboard/crud/confirm_delete.html"

    def get_success_url(self):
        return reverse("dashboard:faculties_list")

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
        except ProtectedError:
            messages.error(
                self.request,
                "Faculties cannot be deleted because other records still use it.",
            )
            return redirect(self.get_success_url())
        messages.success(self.request, "Faculties: record deleted.")
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_url"] = reverse("dashboard:faculties_list")
        ctx["spec"] = {"title": "Faculties"}
        return ctx