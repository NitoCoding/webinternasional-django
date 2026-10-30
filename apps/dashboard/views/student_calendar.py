"""Fitur student: kalender akademik dan data event untuk FullCalendar."""

import datetime

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView

from apps.content.models import Agenda


class StudentCalendarView(LoginRequiredMixin, TemplateView):
    """Kalender akademik untuk student saja (Laravel: CalenderController, cabang student)."""

    template_name = "dashboard/student/calendar.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_role("student"):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        upcoming = []
        for agenda in Agenda.objects.filter(end__gte=timezone.now()).order_by("start"):
            upcoming.append({
                "title": agenda.title,
                "start_date": timezone.localtime(agenda.start).date(),
                "end_date": timezone.localtime(agenda.end).date(),
            })
        ctx["upcoming"] = upcoming
        ctx["events_url"] = reverse("dashboard:student_calendar_events")
        return ctx


@login_required
@require_GET
def student_calendar_events(request):
    if not request.user.has_role("student"):
        return JsonResponse({"ok": False, "message": "Forbidden"}, status=403)
    events = []
    for agenda in Agenda.objects.order_by("start"):
        start = timezone.localtime(agenda.start).date()
        end = max(timezone.localtime(agenda.end).date(), start)
        events.append({
            "id": agenda.pk,
            "title": agenda.title,
            # FullCalendar memakai end yang eksklusif untuk event sehari penuh.
            "start": start.isoformat(),
            "end": (end + datetime.timedelta(days=1)).isoformat(),
            "allDay": True,
            "extendedProps": {
                "description": agenda.description,
                "startDate": start.strftime("%d %B %Y"),
                "endDate": end.strftime("%d %B %Y"),
            },
        })
    return JsonResponse(events, safe=False)