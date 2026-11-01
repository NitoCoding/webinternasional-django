"""Fitur Agenda (kalender akademik): list, create, update, delete (CBV).

Self-contained: setiap view memakai generic view Django secara langsung tanpa
CrudSpec. List menampilkan kalender bulanan dengan filter status, search, dan
pilihan tanggal (dipertahankan dari perilaku sebelumnya).
"""

import calendar
import collections
import datetime

from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import ProtectedError
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.content.models import Agenda

from .. import forms as f
from .base import _cell, _detail_fields, _is_admin, _parse_iso_date, _qs_with

AGENDA_TITLE = "Agenda"
AGENDA_COLUMNS = ["title", "start", "end"]


def _agenda_list_filter(qs, request):
    """Filter list Agenda: status, tanggal terpilih di kalender, dan kalender bulanan."""
    now = timezone.now()
    today = timezone.localdate()
    status = request.GET.get("status", "").strip()
    selected_date = _parse_iso_date(request.GET.get("date", ""))
    month_start = _parse_iso_date(request.GET.get("month", "") + "-01")
    base = selected_date or month_start or today

    year, month = base.year, base.month
    first = datetime.date(year, month, 1)
    last = datetime.date(year, month, calendar.monthrange(year, month)[1])

    if status == "upcoming":
        qs = qs.filter(start__gt=now)
    elif status == "ongoing":
        qs = qs.filter(start__lte=now, end__gte=now)
    elif status == "finished":
        qs = qs.filter(end__lt=now)
    else:
        status = ""

    # Jumlah agenda per hari untuk mini-kalender (mengikuti search dan status).
    counts = collections.Counter()
    for agenda in qs.filter(start__date__lte=last, end__date__gte=first):
        day = max(timezone.localtime(agenda.start).date(), first)
        end_day = min(timezone.localtime(agenda.end).date(), last)
        while day <= end_day:
            counts[day] += 1
            day += datetime.timedelta(days=1)

    table_qs = qs
    if selected_date:
        table_qs = table_qs.filter(start__date__lte=selected_date, end__date__gte=selected_date)

    weeks = []
    for week in calendar.Calendar(firstweekday=0).monthdatescalendar(year, month):
        weeks.append([
            {
                "date": day,
                "in_month": day.month == month,
                "count": counts.get(day, 0),
                "is_today": day == today,
                "selected": day == selected_date,
                "href": _qs_with(
                    request,
                    month=first.strftime("%Y-%m"),
                    date=None if day == selected_date else day.isoformat(),
                ),
            }
            for day in week
        ])

    prev_first = (first - datetime.timedelta(days=1)).replace(day=1)
    next_first = last + datetime.timedelta(days=1)
    return table_qs.order_by("start"), {
        "cal_month": first.strftime("%Y-%m"),
        "cal_title": first.strftime("%B %Y"),
        "cal_weeks": weeks,
        "cal_prev": _qs_with(request, month=prev_first.strftime("%Y-%m"), date=None),
        "cal_next": _qs_with(request, month=next_first.strftime("%Y-%m"), date=None),
        "cal_today": _qs_with(request, month=today.strftime("%Y-%m"), date=None),
        "weekday_names": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "selected_date": selected_date,
        "selected_date_clear": _qs_with(request, date=None),
        "status_choices": [
            ("upcoming", "Upcoming"),
            ("ongoing", "Ongoing"),
            ("finished", "Finished"),
        ],
        "selected": {"status": status},
        "now": now,
    }


def _agenda_row(obj):
    return {
        "obj": obj,
        "cells": [_cell(obj, c) for c in AGENDA_COLUMNS],
        "detail_url": reverse("dashboard:agendas_detail", args=[obj.pk]),
        "edit_url": reverse("dashboard:agendas_update", args=[obj.pk]),
        "delete_url": reverse("dashboard:agendas_delete", args=[obj.pk]),
    }


class AgendaAccessMixin(PermissionRequiredMixin):
    """Akses fitur Agenda: admin, atau pemegang permission accounts.manage_event."""

    permission_required = "accounts.manage_event"

    def has_permission(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        return _is_admin(user) or user.has_perm(self.permission_required)


class AgendaListView(AgendaAccessMixin, ListView):
    model = Agenda
    paginate_by = 20
    template_name = "dashboard/agendas/list.html"

    def get_queryset(self):
        qs = Agenda.objects.order_by("-pk")
        search = self.request.GET.get("search", "").strip()
        if search:
            qs = qs.filter(title__icontains=search)
        qs, self.extra_ctx = _agenda_list_filter(qs, self.request)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(getattr(self, "extra_ctx", {}))
        ctx["list_url"] = reverse("dashboard:agendas_list")
        ctx["create_url"] = reverse("dashboard:agendas_create")
        ctx["search"] = self.request.GET.get("search", "")
        query = self.request.GET.copy()
        query.pop("page", None)
        ctx["filter_qs"] = query.urlencode()
        ctx["has_filters"] = any(v for v in query.values())
        ctx["rows"] = [_agenda_row(obj) for obj in ctx["object_list"]]
        ctx["headers"] = [
            Agenda._meta.get_field(c).verbose_name.capitalize()
            for c in AGENDA_COLUMNS
        ]
        ctx["is_admin"] = _is_admin(self.request.user)
        return ctx


class AgendaCreateView(AgendaAccessMixin, CreateView):
    model = Agenda
    form_class = f.AgendaForm
    template_name = "dashboard/agendas/form.html"

    def get_success_url(self):
        return reverse("dashboard:agendas_list")

    def form_valid(self, form):
        messages.success(self.request, "Agenda: record added successfully.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_url"] = reverse("dashboard:agendas_list")
        ctx["action"] = "New"
        return ctx


class AgendaUpdateView(AgendaAccessMixin, UpdateView):
    model = Agenda
    form_class = f.AgendaForm
    template_name = "dashboard/agendas/form.html"

    def get_success_url(self):
        return reverse("dashboard:agendas_list")

    def form_valid(self, form):
        messages.success(self.request, "Agenda: changes saved.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_url"] = reverse("dashboard:agendas_list")
        ctx["action"] = "Edit"
        return ctx


# Detail hanya dibaca: staff boleh melihat semua record.
# Tidak ada template detail khusus Agenda, jadi memakai crud/detail.html.
class AgendaDetailView(AgendaAccessMixin, DetailView):
    model = Agenda
    template_name = "dashboard/crud/detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = self.object
        ctx["title"] = str(obj)
        ctx["list_url"] = reverse("dashboard:agendas_list")
        ctx["edit_url"] = reverse("dashboard:agendas_update", args=[obj.pk])
        ctx["fields"] = _detail_fields(obj)
        ctx["has_image"] = hasattr(obj, "image")
        ctx["image_url"] = obj.image.url if obj.image else None
        # Template crud/detail.html bersama masih membaca `spec.title`;
        # dict polos ini menggantikan CrudSpec tanpa membuat ketergantungan.
        ctx["spec"] = {"title": AGENDA_TITLE}
        return ctx


class AgendaDeleteView(AgendaAccessMixin, DeleteView):
    model = Agenda
    template_name = "dashboard/crud/confirm_delete.html"

    def get_success_url(self):
        return reverse("dashboard:agendas_list")

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
        except ProtectedError:
            messages.error(
                self.request,
                "Agenda cannot be deleted because other records still use it.",
            )
            return redirect(self.get_success_url())
        messages.success(self.request, "Agenda: record deleted.")
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["list_url"] = reverse("dashboard:agendas_list")
        # Template confirm_delete.html bersama masih membaca `spec.title`;
        # dict polos ini menggantikan CrudSpec tanpa membuat ketergantungan.
        ctx["spec"] = {"title": AGENDA_TITLE}
        return ctx