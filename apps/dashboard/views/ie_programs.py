"""Fitur IE Programs: list, create, update, detail, delete (CBV).

Self-contained: setiap view memakai generic view Django secara langsung tanpa
CrudSpec. Template default crud (list.html, form.html, detail.html) membaca
`spec.title`, sehingga konteks `spec` diisi dict polos berisi judul fitur.
"""

from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import ProtectedError
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.academic.models import IeProgram

from .. import forms as f
from .base import _cell, _detail_fields, _is_admin

IE_PROGRAM_TITLE = "IE Programs"
IE_PROGRAM_COLUMNS = ["name"]


def _ie_program_row(obj):
    return {
        "obj": obj,
        "cells": [_cell(obj, c) for c in IE_PROGRAM_COLUMNS],
        "detail_url": reverse("dashboard:ie_programs_detail", args=[obj.pk]),
        "edit_url": reverse("dashboard:ie_programs_update", args=[obj.pk]),
        "delete_url": reverse("dashboard:ie_programs_delete", args=[obj.pk]),
    }


class IeProgramAccessMixin(PermissionRequiredMixin):
    """Akses fitur IE Programs: admin, atau pemegang permission accounts.manage_program."""

    permission_required = "accounts.manage_program"

    def has_permission(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        return _is_admin(user) or user.has_perm(self.permission_required)


class IeProgramListView(IeProgramAccessMixin, ListView):
    model = IeProgram
    paginate_by = 20
    template_name = "dashboard/crud/list.html"

    def get_queryset(self):
        return IeProgram.objects.order_by("-pk")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["spec"] = {"title": IE_PROGRAM_TITLE}
        ctx["list_url"] = reverse("dashboard:ie_programs_list")
        ctx["create_url"] = reverse("dashboard:ie_programs_create")
        ctx["search"] = self.request.GET.get("search", "")
        query = self.request.GET.copy()
        query.pop("page", None)
        ctx["filter_qs"] = query.urlencode()
        ctx["has_filters"] = any(v for v in query.values())
        ctx["rows"] = [_ie_program_row(obj) for obj in self.object_list]
        ctx["headers"] = [
            IeProgram._meta.get_field(c).verbose_name.capitalize()
            for c in IE_PROGRAM_COLUMNS
        ]
        ctx["is_admin"] = _is_admin(self.request.user)
        return ctx


class IeProgramCreateView(IeProgramAccessMixin, CreateView):
    model = IeProgram
    form_class = f.IeProgramForm
    template_name = "dashboard/crud/form.html"

    def get_success_url(self):
        return reverse("dashboard:ie_programs_list")

    def form_valid(self, form):
        messages.success(self.request, "IE Programs: record added successfully.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["spec"] = {"title": IE_PROGRAM_TITLE}
        ctx["list_url"] = reverse("dashboard:ie_programs_list")
        ctx["action"] = "New"
        return ctx


class IeProgramUpdateView(IeProgramAccessMixin, UpdateView):
    model = IeProgram
    form_class = f.IeProgramForm
    template_name = "dashboard/crud/form.html"

    def get_success_url(self):
        return reverse("dashboard:ie_programs_list")

    def form_valid(self, form):
        messages.success(self.request, "IE Programs: changes saved.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["spec"] = {"title": IE_PROGRAM_TITLE}
        ctx["list_url"] = reverse("dashboard:ie_programs_list")
        ctx["action"] = "Edit"
        return ctx


# Detail hanya dibaca: staff boleh melihat semua record.
class IeProgramDetailView(IeProgramAccessMixin, DetailView):
    model = IeProgram
    template_name = "dashboard/crud/detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = self.object
        ctx["title"] = str(obj)
        ctx["spec"] = {"title": IE_PROGRAM_TITLE}
        ctx["list_url"] = reverse("dashboard:ie_programs_list")
        ctx["edit_url"] = reverse("dashboard:ie_programs_update", args=[obj.pk])
        ctx["fields"] = _detail_fields(obj)
        ctx["has_image"] = hasattr(obj, "image")
        ctx["image_url"] = obj.image.url if obj.image else None
        return ctx


class IeProgramDeleteView(IeProgramAccessMixin, DeleteView):
    model = IeProgram
    template_name = "dashboard/crud/confirm_delete.html"

    def get_success_url(self):
        return reverse("dashboard:ie_programs_list")

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
        except ProtectedError:
            messages.error(
                self.request,
                "IE Programs cannot be deleted because other records still use it.",
            )
            return redirect(self.get_success_url())
        messages.success(self.request, "IE Programs: record deleted.")
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_url"] = reverse("dashboard:ie_programs_list")
        ctx["spec"] = {"title": IE_PROGRAM_TITLE}
        return ctx