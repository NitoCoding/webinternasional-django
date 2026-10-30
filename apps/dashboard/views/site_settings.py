"""Fitur Site Settings: konfigurasi halaman about dan footer."""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.urls import reverse_lazy
from django.views.generic.edit import FormView

from apps.content.models import SiteSetting
from apps.website.context_processors import FOOTER_DEFAULTS
from apps.website.views import SETTING_DEFAULTS, about_image_url

from ..forms import SiteSettingsForm
from .base import _is_admin


class SiteSettingsView(LoginRequiredMixin, FormView):
    """Halaman pengaturan situs; hanya admin."""

    template_name = "dashboard/site_settings/index.html"
    form_class = SiteSettingsForm
    success_url = reverse_lazy("dashboard:site_settings_list")

    def dispatch(self, request, *args, **kwargs):
        if not _is_admin(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        defaults = {**SETTING_DEFAULTS, **FOOTER_DEFAULTS}
        return SiteSetting.get_all_with_defaults(defaults)

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Settings saved successfully!")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        image_path = SiteSetting.get("about_image", SETTING_DEFAULTS["about_image"])
        ctx["image_url"] = about_image_url(image_path)
        return ctx