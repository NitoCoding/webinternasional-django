import shutil
import tempfile
from datetime import datetime

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import FileSystemStorage
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.international import logbook as logbook_module
from apps.international.models import Logbook, ProgramEnrollment

from .test_student_programs import EnrollmentFixtureMixin


def _aware(y, m, d, h=9):
    return timezone.make_aware(datetime(y, m, d, h, 0))


class LogbookTestBase(EnrollmentFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        # Sertifikat ditulis ke folder sementara, bukan ke PRIVATE_MEDIA_ROOT sungguhan.
        self._tmp = tempfile.mkdtemp()
        self._orig_storage = logbook_module.private_storage
        logbook_module.private_storage = FileSystemStorage(location=self._tmp)
        self.approved = ProgramEnrollment.objects.create(
            program=self.program, student=self.student, status="approved",
        )

    def tearDown(self):
        logbook_module.private_storage = self._orig_storage
        shutil.rmtree(self._tmp, ignore_errors=True)
        super().tearDown()

    def _entry(self, user, name="Kegiatan", start=None, end=None):
        return Logbook.objects.create(
            name=name,
            start_time=start or _aware(2026, 1, 5),
            end_time=end or _aware(2026, 1, 5, 12),
            description="Deskripsi",
            program=self.program,
            user=user,
        )

    def _valid_post(self, **overrides):
        data = {
            "name": "Kunjungan",
            "start_time": "2026-01-10T09:00",
            "end_time": "2026-01-10T12:00",
            "description": "Kunjungan lapangan",
        }
        data.update(overrides)
        return data


class StudentLogbookAccessTests(LogbookTestBase):
    def test_student_without_approved_enrollment_forbidden(self):
        self.approved.status = "pending"
        self.approved.save()
        self.client.force_login(self.student_user)
        resp = self.client.get(reverse("dashboard:student_logbook_list", args=[self.program.pk]))
        self.assertEqual(resp.status_code, 403)

    def test_admin_cannot_use_student_logbook_page(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("dashboard:student_logbook_list", args=[self.program.pk]))
        self.assertEqual(resp.status_code, 403)

    def test_list_shows_only_own_entries(self):
        self._entry(self.student_user, name="Milik saya")
        other = self._student("D121211010", status="accepted", verified=True, active=True)
        self._entry(other, name="Milik orang lain")
        self.client.force_login(self.student_user)
        resp = self.client.get(reverse("dashboard:student_logbook_list", args=[self.program.pk]))
        self.assertContains(resp, "Milik saya")
        self.assertNotContains(resp, "Milik orang lain")


class StudentLogbookCrudTests(LogbookTestBase):
    def test_create_entry_within_program_dates(self):
        self.client.force_login(self.student_user)
        url = reverse("dashboard:student_logbook_create", args=[self.program.pk])
        resp = self.client.post(url, self._valid_post())
        self.assertEqual(resp.status_code, 302)
        entry = Logbook.objects.get(name="Kunjungan")
        self.assertEqual(entry.user, self.student_user)
        self.assertEqual(entry.program, self.program)

    def test_start_outside_program_dates_rejected(self):
        self.client.force_login(self.student_user)
        url = reverse("dashboard:student_logbook_create", args=[self.program.pk])
        resp = self.client.post(url, self._valid_post(start_time="2025-12-31T09:00", end_time="2025-12-31T10:00"))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Logbook.objects.filter(name="Kunjungan").exists())

    def test_end_before_start_rejected(self):
        self.client.force_login(self.student_user)
        url = reverse("dashboard:student_logbook_create", args=[self.program.pk])
        resp = self.client.post(url, self._valid_post(start_time="2026-01-10T12:00", end_time="2026-01-10T09:00"))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Logbook.objects.filter(name="Kunjungan").exists())

    def test_name_longer_than_50_rejected(self):
        self.client.force_login(self.student_user)
        url = reverse("dashboard:student_logbook_create", args=[self.program.pk])
        resp = self.client.post(url, self._valid_post(name="x" * 51))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Logbook.objects.exists())

    def test_edit_own_entry(self):
        entry = self._entry(self.student_user)
        self.client.force_login(self.student_user)
        url = reverse("dashboard:student_logbook_edit", args=[self.program.pk, entry.pk])
        resp = self.client.post(url, self._valid_post(name="Sudah diubah"))
        self.assertEqual(resp.status_code, 302)
        entry.refresh_from_db()
        self.assertEqual(entry.name, "Sudah diubah")

    def test_cannot_edit_other_students_entry(self):
        other = self._student("D121211011", status="accepted", verified=True, active=True)
        entry = self._entry(other)
        self.client.force_login(self.student_user)
        url = reverse("dashboard:student_logbook_edit", args=[self.program.pk, entry.pk])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_delete_requires_post(self):
        entry = self._entry(self.student_user)
        self.client.force_login(self.student_user)
        url = reverse("dashboard:student_logbook_delete", args=[self.program.pk, entry.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Logbook.objects.filter(pk=entry.pk).exists())
        self.client.post(url)
        self.assertFalse(Logbook.objects.filter(pk=entry.pk).exists())


class CertificateTests(LogbookTestBase):
    def test_upload_pdf_is_stored_privately(self):
        self.client.force_login(self.student_user)
        pdf = SimpleUploadedFile("sertifikat.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        url = reverse("dashboard:student_certificate_upload", args=[self.program.pk])
        self.client.post(url, {"certificate": pdf})
        self.approved.refresh_from_db()
        self.assertTrue(self.approved.certificate_path.name.startswith("certificates/"))
        self.assertTrue(logbook_module.private_storage.exists(self.approved.certificate_path.name))

    def test_non_pdf_rejected(self):
        self.client.force_login(self.student_user)
        fake = SimpleUploadedFile("sertifikat.pdf", b"not a pdf", content_type="application/pdf")
        url = reverse("dashboard:student_certificate_upload", args=[self.program.pk])
        self.client.post(url, {"certificate": fake})
        self.approved.refresh_from_db()
        self.assertFalse(self.approved.certificate_path)

    def test_view_certificate_returns_pdf(self):
        self.client.force_login(self.student_user)
        pdf = SimpleUploadedFile("sertifikat.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        self.client.post(reverse("dashboard:student_certificate_upload", args=[self.program.pk]), {"certificate": pdf})
        resp = self.client.get(reverse("dashboard:student_certificate_view", args=[self.program.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")

    def test_view_without_certificate_404(self):
        self.client.force_login(self.student_user)
        resp = self.client.get(reverse("dashboard:student_certificate_view", args=[self.program.pk]))
        self.assertEqual(resp.status_code, 404)


class AdminLogbookTests(LogbookTestBase):
    def test_admin_sees_student_entries(self):
        self._entry(self.student_user, name="Catatan mahasiswa")
        self.client.force_login(self.admin)
        url = reverse("dashboard:admin_student_logbook", args=[self.program.pk, self.student_user.pk])
        resp = self.client.get(url)
        self.assertContains(resp, "Catatan mahasiswa")

    def test_admin_certificate_404_when_missing(self):
        self.client.force_login(self.admin)
        url = reverse("dashboard:admin_certificate_view", args=[self.program.pk, self.student_user.pk])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_admin_views_uploaded_certificate(self):
        self.client.force_login(self.student_user)
        pdf = SimpleUploadedFile("sertifikat.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        self.client.post(reverse("dashboard:student_certificate_upload", args=[self.program.pk]), {"certificate": pdf})
        self.client.force_login(self.admin)
        url = reverse("dashboard:admin_certificate_view", args=[self.program.pk, self.student_user.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")

    def test_student_cannot_open_admin_logbook(self):
        self.client.force_login(self.student_user)
        url = reverse("dashboard:admin_student_logbook", args=[self.program.pk, self.student_user.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
