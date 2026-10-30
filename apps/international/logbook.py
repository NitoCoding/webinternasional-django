"""Penyimpanan sertifikat program (PDF) dan batas ukuran file logbook.

Sertifikat disimpan di PRIVATE_MEDIA_ROOT, bukan di MEDIA_ROOT, sehingga tidak bisa diakses lewat URL publik.
Mengikuti LogbookController di Laravel (certificate disk, PDF maksimal 5 MB; gambar logbook maksimal 2 MB).
"""

import uuid

from django.conf import settings
from django.core.files.storage import FileSystemStorage

CERTIFICATE_MAX_BYTES = 5 * 1024 * 1024
LOGBOOK_IMAGE_MAX_BYTES = 2 * 1024 * 1024
LOGBOOK_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif")

private_storage = FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT)


def certificate_exists(enrollment):
    name = enrollment.certificate_path.name if enrollment.certificate_path else ""
    return bool(name) and private_storage.exists(name)


def save_certificate(enrollment, uploaded):
    """Simpan PDF sertifikat dan ganti yang lama (jika ada)."""
    old = enrollment.certificate_path.name if enrollment.certificate_path else ""
    name = private_storage.save(f"certificates/{uuid.uuid4().hex}.pdf", uploaded)
    enrollment.certificate_path = name
    enrollment.save(update_fields=["certificate_path", "updated_at"])
    if old and private_storage.exists(old):
        private_storage.delete(old)
    return name


def open_certificate(enrollment):
    """File sertifikat untuk dibaca, atau None jika belum ada."""
    if not certificate_exists(enrollment):
        return None
    return private_storage.open(enrollment.certificate_path.name, "rb")
