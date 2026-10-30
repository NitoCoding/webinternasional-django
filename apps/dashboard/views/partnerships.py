"""Fitur Partnerships (Double/Joint Degree): list, create, update, detail, delete (CBV).

Self-contained: setiap view memakai generic view Django secara langsung tanpa
CrudSpec. List hanya menampilkan partnership tipe Double Degree dan Joint Degree
(base_filter), filter dropdown (type/status/country) dipertahankan.
"""

from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import ProtectedError
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.international.models import Partnership

from .. import forms as f
from .base import _cell, _detail_fields, _is_admin

PARTNERSHIP_TITLE = "Degree Program"
PARTNERSHIP_COLUMNS = ["partner_university", "partnership_type", "country", "is_active"]
PARTNERSHIP_TYPES = ["double_degree", "joint_degree"]


def _partnership_list_filter(qs, request):
    """Filter dropdown halaman list Partnerships: Type, Status, dan Country."""
    ptype = request.GET.get("type", "").strip()
    status = request.GET.get("status", "").strip()
    country = request.GET.get("country", "").strip()

    if ptype in PARTNERSHIP_TYPES:
        qs = qs.filter(partnership_type=ptype)
    else:
        ptype = ""
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "inactive":
        qs = qs.filter(is_active=False)
    else:
        status = ""
    if country:
        qs = qs.filter(country=country)

    countries = (
        Partnership.objects.filter(partnership_type__in=PARTNERSHIP_TYPES)
        .exclude(country__isnull=True)
        .exclude(country="")
        .order_by("country")
        .values_list("country", flat=True)
        .distinct()
    )
    return qs, {
        "type_choices": [(t, "Double Degree" if t == "double_degree" else "Joint Degree") for t in PARTNERSHIP_TYPES],
        "status_choices": [("active", "Active"), ("inactive", "Inactive")],
        "countries": countries,
        "selected": {"type": ptype, "status": status, "country": country},
    }


def _partnership_row(obj):
    return {
        "obj": obj,
        "cells": [_cell(obj, c) for c in PARTNERSHIP_COLUMNS],
        "detail_url": reverse("dashboard:partnerships_detail", args=[obj.pk]),
        "edit_url": reverse("dashboard:partnerships_update", args=[obj.pk]),
        "delete_url": reverse("dashboard:partnerships_delete", args=[obj.pk]),
    }


class PartnershipAccessMixin(PermissionRequiredMixin):
    """Akses fitur Partnerships: admin, atau pemegang permission accounts.manage_program."""

    permission_required = "accounts.manage_program"

    def has_permission(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        return _is_admin(user) or user.has_perm(self.permission_required)


class PartnershipListView(PartnershipAccessMixin, ListView):
    model = Partnership
    paginate_by = 20
    template_name = "dashboard/partnerships/list.html"

    def get_queryset(self):
        qs = Partnership.objects.filter(
            partnership_type__in=PARTNERSHIP_TYPES
        ).order_by("-pk")
        search = self.request.GET.get("search", "").strip()
        if search:
            qs = qs.filter(partner_university__icontains=search)
        qs, self.extra_ctx = _partnership_list_filter(qs, self.request)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(getattr(self, "extra_ctx", {}))
        ctx["list_url"] = reverse("dashboard:partnerships_list")
        ctx["create_url"] = reverse("dashboard:partnerships_create")
        ctx["search"] = self.request.GET.get("search", "")
        query = self.request.GET.copy()
        query.pop("page", None)
        ctx["filter_qs"] = query.urlencode()
        ctx["has_filters"] = any(v for v in query.values())
        ctx["rows"] = [_partnership_row(obj) for obj in self.object_list]
        ctx["headers"] = [
            Partnership._meta.get_field(c).verbose_name.capitalize()
            for c in PARTNERSHIP_COLUMNS
        ]
        ctx["is_admin"] = _is_admin(self.request.user)
        return ctx


class PartnershipCreateView(PartnershipAccessMixin, CreateView):
    model = Partnership
    form_class = f.PartnershipForm
    template_name = "dashboard/partnerships/form.html"

    def get_success_url(self):
        return reverse("dashboard:partnerships_list")

    def form_valid(self, form):
        messages.success(self.request, "Degree Program: record added successfully.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_url"] = reverse("dashboard:partnerships_list")
        ctx["action"] = "New"
        return ctx


class PartnershipUpdateView(PartnershipAccessMixin, UpdateView):
    model = Partnership
    form_class = f.PartnershipForm
    template_name = "dashboard/partnerships/form.html"

    def get_success_url(self):
        return reverse("dashboard:partnerships_list")

    def form_valid(self, form):
        messages.success(self.request, "Degree Program: changes saved.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_url"] = reverse("dashboard:partnerships_list")
        ctx["action"] = "Edit"
        return ctx


# Detail hanya dibaca: staff boleh melihat semua record.
class PartnershipDetailView(PartnershipAccessMixin, DetailView):
    model = Partnership
    template_name = "dashboard/partnerships/detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = self.object
        ctx["title"] = str(obj)
        ctx["list_url"] = reverse("dashboard:partnerships_list")
        ctx["edit_url"] = reverse("dashboard:partnerships_update", args=[obj.pk])
        ctx["fields"] = _detail_fields(obj)
        ctx["has_image"] = hasattr(obj, "image")
        ctx["image_url"] = obj.image.url if obj.image else None
        return ctx


class PartnershipDeleteView(PartnershipAccessMixin, DeleteView):
    model = Partnership
    template_name = "dashboard/crud/confirm_delete.html"

    def get_success_url(self):
        return reverse("dashboard:partnerships_list")

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
        except ProtectedError:
            messages.error(
                self.request,
                "Degree Program cannot be deleted because other records still use it.",
            )
            return redirect(self.get_success_url())
        messages.success(self.request, "Degree Program: record deleted.")
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_url"] = reverse("dashboard:partnerships_list")
        # Template confirm_delete.html bersama masih membaca `spec.title`;
        # dict polos ini menggantikan CrudSpec tanpa membuat ketergantungan.
        ctx["spec"] = {"title": PARTNERSHIP_TITLE}
        return ctx