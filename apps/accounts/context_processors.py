from apps.content.models import SiteSetting

REGISTRATION_SETTING_KEY = "allow_register"


def is_registration_open():
    """Register publik aktif jika SiteSetting `allow_register` bernilai 1 atau true."""
    return SiteSetting.get(REGISTRATION_SETTING_KEY, "0").strip().lower() in ("1", "true")


def registration_flag(request):
    """Menyediakan flag buka/tutup register ke semua template."""
    return {"allow_register": is_registration_open()}


def role_flags(request):
    """Flag role untuk template (pengganti @role di Blade)."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"is_admin": False, "is_staff": False, "is_student": False}
    is_admin = user.is_superuser or user.has_role("admin")
    return {
        "is_admin": is_admin,
        "is_staff": (not is_admin) and user.has_role("staff"),
        "is_student": (not is_admin) and user.has_role("student"),
    }
