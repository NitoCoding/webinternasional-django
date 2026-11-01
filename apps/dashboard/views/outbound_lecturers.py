"""Fitur Outbound Lecturers: list, create, update, detail, delete (CBV).

Self-contained: setiap view memakai generic view Django secara langsung tanpa
CrudSpec. Seluruh template memakai template crud bawaan dashboard.
"""

from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import ProtectedError
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.international.models import OutboundLecturer

from .. import forms as f
from .base import _cell, _detail_fields, _is_admin

OUTBOUND_LECTURER_TITLE = "Outbound Lecturers"
OUTBOUND_LECTURER_COLUMNS = ["lecturer_name", "university_name", "activity_year"]


def _outbound_lecturer_row(obj):
    return {
        "obj": obj,
        "cells": [_cell(obj, c) for c in OUTBOUND_LECTURER_COLUMNS],
        "detail_url": reverse("dashboard:outbound_lecturers_detail", args=[obj.pk]),
        "edit_url": reverse("dashboard:outbound_lecturers_update", args=[obj.pk]),
        "delete_url": reverse("dashboard:outbound_lecturers_delete", args=[obj.pk]),
    }


class OutboundLecturerAccessMixin(PermissionRequiredMixin):
    """Akses fitur Outbound Lecturers: admin, atau pemegang permission accounts.manage_program."""

    permission_required = "accounts.manage_program"

    def has_permission(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        return _is_admin(user) or user.has_perm(self.permission_required)


class OutboundLecturerListView(OutboundLecturerAccessMixin, ListView):
    model = OutboundLecturer
    paginate_by = 20
    template_name = "dashboard/crud/list.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_url"] = reverse("dashboard:outbound_lecturers_list")
        ctx["create_url"] = reverse("dashboard:outbound_lecturers_create")
        ctx["search"] = self.request.GET.get("search", "")
        query = self.request.GET.copy()
        query.pop("page", None)
        ctx["filter_qs"] = query.urlencode()
        ctx["has_filters"] = any(v for v in query.values())
        ctx["rows"] = [_outbound_lecturer_row(obj) for obj in ctx["object_list"]]
        ctx["headers"] = [
            OutboundLecturer._meta.get_field(c).verbose_name.capitalize()
            for c in OUTBOUND_LECTURER_COLUMNS
        ]
        ctx["is_admin"] = _is_admin(self.request.user)
        # Template crud/list.html bersama masih membaca `spec.title`;
        # dict polos ini menggantikan CrudSpec tanpa membuat ketergantungan.
        ctx["spec"] = {"title": OUTBOUND_LECTURER_TITLE}
        return ctx


class OutboundLecturerCreateView(OutboundLecturerAccessMixin, CreateView):
    model = OutboundLecturer
    form_class = f.OutboundLecturerForm
    template_name = "dashboard/crud/form.html"

    def get_success_url(self):
        return reverse("dashboard:outbound_lecturers_list")

    def form_valid(self, form):
        messages.success(self.request, "Outbound Lecturers: record added successfully.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_url"] = reverse("dashboard:outbound_lecturers_list")
        ctx["action"] = "New"
        # Template crud/form.html bersama masih membaca `spec.title`.
        ctx["spec"] = {"title": OUTBOUND_LECTURER_TITLE}
        return ctx


class OutboundLecturerUpdateView(OutboundLecturerAccessMixin, UpdateView):
    model = OutboundLecturer
    form_class = f.OutboundLecturerForm
    template_name = "dashboard/crud/form.html"

    def get_success_url(self):
        return reverse("dashboard:outbound_lecturers_list")

    def form_valid(self, form):
        messages.success(self.request, "Outbound Lecturers: changes saved.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_url"] = reverse("dashboard:outbound_lecturers_list")
        ctx["action"] = "Edit"
        # Template crud/form.html bersama masih membaca `spec.title`.
        ctx["spec"] = {"title": OUTBOUND_LECTURER_TITLE}
        return ctx


# Detail hanya dibaca: staff boleh melihat semua record.
class OutboundLecturerDetailView(OutboundLecturerAccessMixin, DetailView):
    model = OutboundLecturer
    template_name = "dashboard/crud/detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = self.object
        ctx["title"] = str(obj)
        ctx["list_url"] = reverse("dashboard:outbound_lecturers_list")
        ctx["edit_url"] = reverse("dashboard:outbound_lecturers_update", args=[obj.pk])
        ctx["fields"] = _detail_fields(obj)
        ctx["has_image"] = hasattr(obj, "image")
        ctx["image_url"] = obj.image.url if obj.image else None
        # Template crud/detail.html bersama masih membaca `spec.title`.
        ctx["spec"] = {"title": OUTBOUND_LECTURER_TITLE}
        return ctx


class OutboundLecturerDeleteView(OutboundLecturerAccessMixin, DeleteView):
    model = OutboundLecturer
    template_name = "dashboard/crud/confirm_delete.html"

    def get_success_url(self):
        return reverse("dashboard:outbound_lecturers_list")

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
        except ProtectedError:
            messages.error(
                self.request,
                "Outbound Lecturers cannot be deleted because other records still use it.",
            )
            return redirect(self.get_success_url())
        messages.success(self.request, "Outbound Lecturers: record deleted.")
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_url"] = reverse("dashboard:outbound_lecturers_list")
        # Template confirm_delete.html bersama masih membaca `spec.title`;
        # dict polos ini menggantikan CrudSpec tanpa membuat ketergantungan.
        ctx["spec"] = {"title": OUTBOUND_LECTURER_TITLE}
        return ctx