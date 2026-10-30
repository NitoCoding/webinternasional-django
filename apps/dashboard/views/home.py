"""Fitur Home: dashboard per role (admin, staff, student)."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.views.generic import TemplateView

from apps.academic.models import Staff

from ..dashboard_stats import STATUS_OPTIONS, admin_dashboard_context
from .base import _is_admin


def _role_of(user):
    # Urutan pengecekan sama dengan DashboardController Laravel: admin, staff, student.
    if _is_admin(user):
        return "admin"
    if user.has_role("staff"):
        return "staff"
    if user.has_role("student"):
        return "student"
    return None


class HomeView(LoginRequiredMixin, TemplateView):
    """Dashboard per role; menolak akses untuk user tanpa peran."""

    def get_template_names(self):
        return (
            ["dashboard/student_home.html"]
            if _role_of(self.request.user) == "student"
            else ["dashboard/home.html"]
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        status = self.request.GET.get("status", "all")
        if status not in dict(STATUS_OPTIONS):
            status = "all"

        role = _role_of(user)
        if role == "admin":
            ctx.update(admin_dashboard_context(None, status, is_admin=True))
        elif role == "staff":
            staff = (
                Staff.objects.filter(user=user)
                .select_related("study_program")
                .first()
            )
            if staff is None:
                ctx.update(
                    {
                        "no_staff_profile": True,
                        "is_admin": False,
                        "status": status,
                        "status_options": STATUS_OPTIONS,
                    }
                )
            else:
                ctx.update(
                    admin_dashboard_context(
                        staff.study_program, status, is_admin=False
                    )
                )
        elif role == "student":
            ctx.update(
                {
                    "nim": user.username,
                    "name": user.name,
                    "email": user.email,
                    "data_url": reverse("dashboard:student_dashboard_data"),
                }
            )
        else:
            raise PermissionDenied
        return ctx