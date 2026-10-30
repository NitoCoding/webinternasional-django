"""Pondasi bersama untuk view CRUD dashboard.

Berisi metadata fitur (CrudSpec), mixin akses (RoleAccessMixin, OwnerScopeMixin),
dan base class CBV (CrudListView, CrudCreateView, CrudUpdateView, CrudDetailView,
CrudDeleteView). Setiap fitur di package ini membuat view-nya sendiri dengan
menetapkan `spec` milik fitur tersebut.
"""

import datetime
import html
from dataclasses import dataclass, field
from typing import Callable, Optional

from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db import models
from django.db.models import ProtectedError, Q
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils.html import strip_tags
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView


@dataclass
class CrudSpec:
    """Konfigurasi satu fitur CRUD. Dipakai sebagai metadata view, bukan generator view."""

    key: str  # dipakai sebagai path dan prefix nama URL, mis. "study-programs"
    title: str
    model: type
    form: type
    perm: Optional[str]  # codename permission, mis. "manage_news"
    columns: list  # field yang ditampilkan di tabel list
    owner_field: Optional[str] = (
        None  # field pemilik; staff hanya boleh ubah miliknya sendiri
    )
    admin_only: bool = False
    list_template: str = "dashboard/crud/list.html"
    search_field: Optional[str] = (
        None  # field yang dicari lewat ?search= di halaman list
    )
    search_fields: tuple = ()  # beberapa field, dicari dengan OR; dipakai jika diisi
    form_template: str = "dashboard/crud/form.html"
    base_filter: dict = field(
        default_factory=dict
    )  # filter tetap untuk daftar, mis. hanya degree program
    detail_template: str = "dashboard/crud/detail.html"
    detail_context: Optional[Callable] = (
        None  # (obj, request) -> dict konteks tambahan untuk halaman detail
    )
    list_filter: Optional[Callable] = (
        None  # (qs, request) -> (qs, dict konteks): filter dropdown di halaman list
    )
    url_name: str = field(init=False)

    def __post_init__(self):
        self.url_name = self.key.replace("-", "_")


def _is_admin(user):
    return user.is_superuser or user.has_role("admin")


def _str_limit(text, limit, end="..."):
    """Pengganti Str::limit(html_entity_decode(strip_tags($text)), $limit, $end) di Laravel."""
    clean = html.unescape(strip_tags(text or ""))
    return clean[:limit] + end if len(clean) > limit else clean


def _parse_iso_date(value):
    """Parse YYYY-MM-DD dari query string; None jika kosong atau tidak valid."""
    try:
        return datetime.date.fromisoformat((value or "").strip())
    except ValueError:
        return None


def _qs_with(request, **changes):
    """Query string dari request saat ini dengan perubahan parameter (None = hapus)."""
    query = request.GET.copy()
    query.pop("page", None)
    for key, value in changes.items():
        if value is None:
            query.pop(key, None)
        else:
            query[key] = value
    return "?" + query.urlencode() if query else "?"


class RoleAccessMixin(PermissionRequiredMixin):
    """Akses berdasarkan permission; admin_only membatasi ke role admin."""

    spec: CrudSpec = None

    def has_permission(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        if _is_admin(user):
            return True
        if self.spec.admin_only:
            return False
        return user.has_perm(f"accounts.{self.spec.perm}")


class OwnerScopeMixin:
    """Staff (non-admin) hanya bisa mengubah/menghapus data miliknya sendiri."""

    def get_queryset(self):
        qs = super().get_queryset()
        owner = self.spec.owner_field
        if owner and not _is_admin(self.request.user):
            qs = qs.filter(**{owner: self.request.user})
        return qs


def _base_ctx(spec):
    return {"spec": spec, "list_url": reverse(f"dashboard:{spec.url_name}_list")}


def _cell(obj, name):
    getter = getattr(obj, f"get_{name}_display", None)
    return getter() if getter else getattr(obj, name)


DETAIL_HIDDEN_FIELDS = {"id", "created_at", "updated_at", "password"}


def _detail_fields(obj):
    """Pasangan (label, nilai) untuk halaman detail; field gambar/berkas ditangani terpisah."""
    fields = []
    for fld in obj._meta.concrete_fields:
        if fld.name in DETAIL_HIDDEN_FIELDS or isinstance(
            fld, (models.ImageField, models.FileField)
        ):
            continue
        value = _cell(obj, fld.name)
        if isinstance(value, bool):
            value = "Yes" if value else "No"
        fields.append(
            {
                "label": fld.verbose_name.capitalize(),
                "value": value if value not in (None, "") else "-",
                "long": isinstance(fld, models.TextField),
            }
        )
    return fields


class CrudListView(RoleAccessMixin, ListView):
    paginate_by = 20
    spec: CrudSpec = None
    permission_required = None

    def get_template_names(self):
        return [self.spec.list_template]

    def get_queryset(self):
        qs = self.spec.model.objects.filter(**self.spec.base_filter).order_by("-pk")
        search = self.request.GET.get("search", "").strip()
        if self.spec.search_fields and search:
            cond = Q()
            for name in self.spec.search_fields:
                cond |= Q(**{f"{name}__icontains": search})
            qs = qs.filter(cond)
        elif self.spec.search_field and search:
            qs = qs.filter(**{f"{self.spec.search_field}__icontains": search})
        self.extra_ctx = {}
        if self.spec.list_filter:
            qs, self.extra_ctx = self.spec.list_filter(qs, self.request)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_base_ctx(self.spec))
        ctx.update(getattr(self, "extra_ctx", {}))
        ctx["search"] = self.request.GET.get("search", "")
        query = self.request.GET.copy()
        query.pop("page", None)
        ctx["filter_qs"] = query.urlencode()
        ctx["has_filters"] = any(v for v in query.values())
        n = self.spec.url_name
        ctx["create_url"] = reverse(f"dashboard:{n}_create")
        ctx["rows"] = [
            {
                "obj": o,
                "cells": [_cell(o, c) for c in self.spec.columns],
                "detail_url": reverse(f"dashboard:{n}_detail", args=[o.pk]),
                "edit_url": reverse(f"dashboard:{n}_update", args=[o.pk]),
                "delete_url": reverse(f"dashboard:{n}_delete", args=[o.pk]),
            }
            for o in ctx["object_list"]
        ]
        ctx["headers"] = [
            self.spec.model._meta.get_field(c).verbose_name.capitalize()
            for c in self.spec.columns
        ]
        ctx["is_admin"] = _is_admin(self.request.user)
        return ctx


class CrudCreateView(RoleAccessMixin, CreateView):
    spec: CrudSpec = None
    permission_required = None

    def get_template_names(self):
        return [self.spec.form_template]

    def get_form_class(self):
        return self.spec.form

    def get_success_url(self):
        return reverse_lazy(f"dashboard:{self.spec.url_name}_list")

    def form_valid(self, form):
        if self.spec.owner_field:
            setattr(form.instance, self.spec.owner_field, self.request.user)
        messages.success(
            self.request, f"{self.spec.title}: record added successfully."
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_base_ctx(self.spec))
        ctx["action"] = "New"
        return ctx


class CrudUpdateView(RoleAccessMixin, OwnerScopeMixin, UpdateView):
    spec: CrudSpec = None
    permission_required = None

    def get_template_names(self):
        return [self.spec.form_template]

    def get_form_class(self):
        return self.spec.form

    def get_success_url(self):
        return reverse_lazy(f"dashboard:{self.spec.url_name}_list")

    def form_valid(self, form):
        messages.success(self.request, f"{self.spec.title}: changes saved.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_base_ctx(self.spec))
        ctx["action"] = "Edit"
        return ctx


# Detail hanya dibaca: staff boleh melihat semua record (seperti ProgramController@show Laravel).
class CrudDetailView(RoleAccessMixin, DetailView):
    spec: CrudSpec = None
    permission_required = None

    def get_template_names(self):
        return [self.spec.detail_template]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = ctx["object"]
        image = getattr(obj, "image", None)
        ctx.update(_base_ctx(self.spec))
        if self.spec.detail_context:
            ctx.update(self.spec.detail_context(obj, self.request))
        ctx["edit_url"] = reverse(
            f"dashboard:{self.spec.url_name}_update", args=[obj.pk]
        )
        ctx["fields"] = _detail_fields(obj)
        ctx["has_image"] = hasattr(obj, "image")
        ctx["image_url"] = image.url if image else None
        ctx["title"] = str(obj)
        return ctx


class CrudDeleteView(RoleAccessMixin, OwnerScopeMixin, DeleteView):
    template_name = "dashboard/crud/confirm_delete.html"
    spec: CrudSpec = None
    permission_required = None

    def get_success_url(self):
        return reverse_lazy(f"dashboard:{self.spec.url_name}_list")

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
        except ProtectedError:
            messages.error(
                self.request,
                f"{self.spec.title} cannot be deleted because other records still use it.",
            )
            return redirect(self.get_success_url())
        messages.success(self.request, f"{self.spec.title}: record deleted.")
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_base_ctx(self.spec))
        return ctx