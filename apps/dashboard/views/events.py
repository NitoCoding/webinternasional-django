"""Fitur Events: list, create, update, detail, delete (CBV).

Self-contained: setiap view memakai generic view Django secara langsung tanpa
CrudSpec. Filter list (Study Program dan status Upcoming/Finished) dipertahankan.
"""

from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import ProtectedError
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.academic.models import StudyProgram
from apps.content.models import Event

from .. import forms as f
from .base import _cell, _detail_fields, _is_admin

EVENT_TITLE = "Events"
EVENT_COLUMNS = ["title", "study_program", "event_date"]


def _event_list_filter(qs, request):
    """Filter list Events: Study Program dan status (Upcoming / Finished) berdasarkan event_date."""
    now = timezone.now()
    program_id = request.GET.get("study_program", "").strip()
    status = request.GET.get("status", "").strip()
    if program_id.isdigit():
        qs = qs.filter(study_program_id=int(program_id))
    if status == "upcoming":
        qs = qs.filter(event_date__gte=now)
    elif status == "finished":
        qs = qs.filter(event_date__lt=now)
    else:
        status = ""
    return qs, {
        "study_programs": StudyProgram.objects.order_by("name"),
        "status_choices": [("upcoming", "Upcoming"), ("finished", "Finished")],
        "selected": {"study_program": program_id, "status": status},
    }


def _event_row(obj):
    return {
        "obj": obj,
        "cells": [_cell(obj, c) for c in EVENT_COLUMNS],
        "detail_url": reverse("dashboard:events_detail", args=[obj.pk]),
        "edit_url": reverse("dashboard:events_update", args=[obj.pk]),
        "delete_url": reverse("dashboard:events_delete", args=[obj.pk]),
    }


class EventAccessMixin(PermissionRequiredMixin):
    """Akses fitur Events: admin, atau pemegang permission accounts.manage_event."""

    permission_required = "accounts.manage_event"

    def has_permission(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        return _is_admin(user) or user.has_perm(self.permission_required)


class EventOwnerMixin:
    """Staff (non-admin) hanya bisa mengubah/menghapus event miliknya sendiri."""

    def get_queryset(self):
        qs = super().get_queryset()
        if not _is_admin(self.request.user):
            qs = qs.filter(user=self.request.user)
        return qs


class EventListView(EventAccessMixin, ListView):
    model = Event
    paginate_by = 20
    template_name = "dashboard/events/list.html"

    def get_queryset(self):
        qs = Event.objects.order_by("-pk")
        search = self.request.GET.get("search", "").strip()
        if search:
            qs = qs.filter(title__icontains=search)
        qs, self.extra_ctx = _event_list_filter(qs, self.request)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(getattr(self, "extra_ctx", {}))
        ctx["list_url"] = reverse("dashboard:events_list")
        ctx["create_url"] = reverse("dashboard:events_create")
        ctx["search"] = self.request.GET.get("search", "")
        query = self.request.GET.copy()
        query.pop("page", None)
        ctx["filter_qs"] = query.urlencode()
        ctx["has_filters"] = any(v for v in query.values())
        ctx["rows"] = [_event_row(obj) for obj in self.object_list]
        ctx["headers"] = [
            Event._meta.get_field(c).verbose_name.capitalize()
            for c in EVENT_COLUMNS
        ]
        ctx["is_admin"] = _is_admin(self.request.user)
        return ctx


class EventCreateView(EventAccessMixin, CreateView):
    model = Event
    form_class = f.EventForm
    template_name = "dashboard/events/form.html"

    def get_success_url(self):
        return reverse("dashboard:events_list")

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, "Events: record added successfully.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_url"] = reverse("dashboard:events_list")
        ctx["action"] = "New"
        return ctx


class EventUpdateView(EventAccessMixin, EventOwnerMixin, UpdateView):
    model = Event
    form_class = f.EventForm
    template_name = "dashboard/events/form.html"

    def get_success_url(self):
        return reverse("dashboard:events_list")

    def form_valid(self, form):
        messages.success(self.request, "Events: changes saved.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_url"] = reverse("dashboard:events_list")
        ctx["action"] = "Edit"
        return ctx


# Detail hanya dibaca: staff boleh melihat semua record.
class EventDetailView(EventAccessMixin, DetailView):
    model = Event
    template_name = "dashboard/events/detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = self.object
        ctx["title"] = str(obj)
        ctx["list_url"] = reverse("dashboard:events_list")
        ctx["edit_url"] = reverse("dashboard:events_update", args=[obj.pk])
        ctx["fields"] = _detail_fields(obj)
        ctx["has_image"] = hasattr(obj, "image")
        ctx["image_url"] = obj.image.url if obj.image else None
        return ctx


class EventDeleteView(EventAccessMixin, EventOwnerMixin, DeleteView):
    model = Event
    template_name = "dashboard/crud/confirm_delete.html"

    def get_success_url(self):
        return reverse("dashboard:events_list")

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
        except ProtectedError:
            messages.error(
                self.request,
                "Events cannot be deleted because other records still use it.",
            )
            return redirect(self.get_success_url())
        messages.success(self.request, "Events: record deleted.")
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_url"] = reverse("dashboard:events_list")
        # Template confirm_delete.html bersama masih membaca `spec.title`;
        # dict polos ini menggantikan CrudSpec tanpa membuat ketergantungan.
        ctx["spec"] = {"title": EVENT_TITLE}
        return ctx