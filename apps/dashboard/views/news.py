"""Fitur News: list, create, update, detail, delete (CBV).

Self-contained: setiap view memakai generic view Django secara langsung
(ListView, CreateView, UpdateView, DetailView, DeleteView) tanpa CrudSpec.
Konteks template dipertahankan persis seperti sebelumnya.
"""

from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import ProtectedError
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.academic.models import StudyProgram
from apps.content.models import News

from .. import forms as f
from .base import _cell, _detail_fields, _is_admin

NEWS_COLUMNS = ["title", "study_program", "publication_date", "views"]


def _news_list_filter(qs, request):
    """Filter list News: Study Program dan status publikasi (Published / Scheduled)."""
    now = timezone.now()
    program_id = request.GET.get("study_program", "").strip()
    status = request.GET.get("status", "").strip()
    if program_id.isdigit():
        qs = qs.filter(study_program_id=int(program_id))
    if status == "published":
        qs = qs.filter(publication_date__lte=now)
    elif status == "scheduled":
        qs = qs.filter(publication_date__gt=now)
    else:
        status = ""
    return qs, {
        "study_programs": StudyProgram.objects.order_by("name"),
        "status_choices": [("published", "Published"), ("scheduled", "Scheduled")],
        "selected": {"study_program": program_id, "status": status},
    }


def _news_row(obj):
    return {
        "obj": obj,
        "cells": [_cell(obj, c) for c in NEWS_COLUMNS],
        "detail_url": reverse("dashboard:news_detail", args=[obj.pk]),
        "edit_url": reverse("dashboard:news_update", args=[obj.pk]),
        "delete_url": reverse("dashboard:news_delete", args=[obj.pk]),
    }


class NewsAccessMixin(PermissionRequiredMixin):
    """Akses fitur News: admin, atau pemegang permission accounts.manage_news."""

    permission_required = "accounts.manage_news"

    def has_permission(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        return _is_admin(user) or user.has_perm(self.permission_required)


class NewsOwnerMixin:
    """Staff (non-admin) hanya bisa mengubah/menghapus berita miliknya sendiri."""

    def get_queryset(self):
        qs = super().get_queryset()
        if not _is_admin(self.request.user):
            qs = qs.filter(user=self.request.user)
        return qs


class NewsListView(NewsAccessMixin, ListView):
    model = News
    paginate_by = 20
    template_name = "dashboard/news/list.html"

    def get_queryset(self):
        qs = News.objects.order_by("-pk")
        search = self.request.GET.get("search", "").strip()
        if search:
            qs = qs.filter(title__icontains=search)
        qs, self.extra_ctx = _news_list_filter(qs, self.request)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(getattr(self, "extra_ctx", {}))
        ctx["list_url"] = reverse("dashboard:news_list")
        ctx["create_url"] = reverse("dashboard:news_create")
        ctx["search"] = self.request.GET.get("search", "")
        query = self.request.GET.copy()
        query.pop("page", None)
        ctx["filter_qs"] = query.urlencode()
        ctx["has_filters"] = any(v for v in query.values())
        ctx["rows"] = [_news_row(obj) for obj in ctx["object_list"]]
        ctx["headers"] = [
            News._meta.get_field(c).verbose_name.capitalize() for c in NEWS_COLUMNS
        ]
        ctx["is_admin"] = _is_admin(self.request.user)
        return ctx


class NewsCreateView(NewsAccessMixin, CreateView):
    model = News
    form_class = f.NewsForm
    template_name = "dashboard/news/form.html"

    def get_success_url(self):
        return reverse("dashboard:news_list")

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, "News: record added successfully.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_url"] = reverse("dashboard:news_list")
        ctx["action"] = "New"
        return ctx


class NewsUpdateView(NewsAccessMixin, NewsOwnerMixin, UpdateView):
    model = News
    form_class = f.NewsForm
    template_name = "dashboard/news/form.html"

    def get_success_url(self):
        return reverse("dashboard:news_list")

    def form_valid(self, form):
        messages.success(self.request, "News: changes saved.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_url"] = reverse("dashboard:news_list")
        ctx["action"] = "Edit"
        return ctx


# Detail hanya dibaca: staff boleh melihat semua record.
class NewsDetailView(NewsAccessMixin, DetailView):
    model = News
    template_name = "dashboard/news/detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = self.object
        ctx["title"] = str(obj)
        ctx["list_url"] = reverse("dashboard:news_list")
        ctx["edit_url"] = reverse("dashboard:news_update", args=[obj.pk])
        ctx["fields"] = _detail_fields(obj)
        ctx["has_image"] = hasattr(obj, "image")
        ctx["image_url"] = obj.image.url if obj.image else None
        return ctx


class NewsDeleteView(NewsAccessMixin, NewsOwnerMixin, DeleteView):
    model = News
    template_name = "dashboard/crud/confirm_delete.html"

    def get_success_url(self):
        return reverse("dashboard:news_list")

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
        except ProtectedError:
            messages.error(
                self.request,
                "News cannot be deleted because other records still use it.",
            )
            return redirect(self.get_success_url())
        messages.success(self.request, "News: record deleted.")
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_url"] = reverse("dashboard:news_list")
        # Template confirm_delete.html bersama masih membaca `spec.title`;
        # dict polos ini menggantikan CrudSpec tanpa membuat ketergantungan.
        ctx["spec"] = {"title": "News"}
        return ctx