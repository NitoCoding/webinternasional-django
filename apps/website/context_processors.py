from apps.content.models import SiteSetting

FOOTER_DEFAULTS = {
    "footer_address": "Jl. Perintis Kemerdekaan Km.10 Tamalanrea, Makassar Sulawesi Selatan Indonesia",
    "footer_phone": "0411 542156",
    "footer_email": "internationalClassUH@gmail.com",
}


def site_footer(request):
    """Menyediakan alamat, telepon, dan email footer ke semua template."""
    return {"footer": SiteSetting.get_all_with_defaults(FOOTER_DEFAULTS)}
