import datetime

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET

from apps.content.models import Agenda


def _require_student(user):
    # Kalender akademik untuk student saja (Laravel: CalenderController, cabang student).
    if not user.has_role("student"):
        raise PermissionDenied


@login_required
@require_GET
def student_calendar(request):
    _require_student(request.user)
    upcoming = []
    for agenda in Agenda.objects.filter(end__gte=timezone.now()).order_by("start"):
        upcoming.append({
            "title": agenda.title,
            "start_date": timezone.localtime(agenda.start).date(),
            "end_date": timezone.localtime(agenda.end).date(),
        })
    return render(request, "dashboard/student/calendar.html", {
        "upcoming": upcoming,
        "events_url": reverse("dashboard:student_calendar_events"),
    })


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
