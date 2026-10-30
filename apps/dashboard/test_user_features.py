from unittest import mock

import httpx
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.academic.models import Staff, Student, StudyProgram
from apps.academic.sipakamase import SipakamaseClient, SipakamaseError
from apps.dashboard.tests import UserListFixtureMixin

User = get_user_model()

API_STUDENT = {
    "nama_mahasiswa": "BUDI SANTOSO",
    "email": "budi.santoso@unhas.ac.id",
    "jenis_kelamin": "L",
    "nik": "7371000000000001",
    "nisn": "1234567890",
    "handphone": "08123456789",
    "telepon": None,
    "jalan": "Jl. Perintis Kemerdekaan",
    "tempat_lahir": "Makassar",
    "tanggal_lahir": "2003-05-01",
    "prodi": {"nama_resmi": "Informatika"},
}


class FakeApi:
    """Pengganti SipakamaseClient. data: dict NIM -> data mahasiswa (atau None)."""

    def __init__(self, data=None):
        self.data = data or {}
        self.calls = []

    def login(self):
        pass

    def get_student(self, nim):
        self.calls.append(nim)
        return self.data.get(nim)

    def close(self):
        pass


class AddStudentTests(UserListFixtureMixin, TestCase):
    def setUp(self):
        self.client.force_login(self.admin)
        self.api = FakeApi({"D123211001": dict(API_STUDENT, prodi={"nama_resmi": "Informatika"})})

    def _post_nim(self, nim, follow=False):
        with mock.patch("apps.dashboard.user_views.SipakamaseClient", return_value=self.api):
            return self.client.post(reverse("dashboard:user_add_student"), {"nim": nim}, follow=follow)

    def test_adds_student_with_api_data_and_initial_password(self):
        resp = self._post_nim("d123211001")
        self.assertRedirects(resp, reverse("dashboard:users_list") + "?tab=all", fetch_redirect_response=False)
        user = User.objects.get(username="D123211001")
        self.assertTrue(user.check_password("D123211001@internasional"))
        self.assertEqual(user.name, "BUDI SANTOSO")
        self.assertTrue(user.groups.filter(name="student").exists())
        student = user.student
        self.assertEqual(student.study_program, self.sp1)
        self.assertEqual(student.gender, "L")
        self.assertEqual(str(student.birth_date), "2003-05-01")
        self.assertEqual(student.status, Student.Status.ACCEPTED)
        self.assertTrue(student.is_verified and student.is_active)

    def test_nim_not_found_shows_form_error(self):
        resp = self._post_nim("D999999999", follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "NIM not valid or not found.")
        self.assertFalse(User.objects.filter(username="D999999999").exists())

    def test_program_not_in_international_class(self):
        self.api.data["D123211002"] = dict(API_STUDENT, prodi={"nama_resmi": "Kedokteran"})
        resp = self._post_nim("D123211002")
        self.assertContains(resp, "The study program is not available for the international class.")

    def test_existing_student_is_updated(self):
        self._post_nim("D123211001")
        resp = self._post_nim("D123211001")
        self.assertRedirects(resp, reverse("dashboard:users_list") + "?tab=all", fetch_redirect_response=False)
        self.assertEqual(User.objects.filter(username="D123211001").count(), 1)

    def test_staff_outside_program_is_refused(self):
        self.api.data["D123211003"] = dict(API_STUDENT, prodi={"nama_resmi": "Sipil"})
        self.client.force_login(self.staff_user)
        resp = self._post_nim("D123211003")
        self.assertContains(resp, "The student is not under your authority.")

    def test_api_error_shown_on_form(self):
        class Broken(FakeApi):
            def get_student(self, nim):
                raise SipakamaseError("Tidak dapat terhubung ke server SIPAKAMASE.")

        with mock.patch("apps.dashboard.user_views.SipakamaseClient", return_value=Broken()):
            resp = self.client.post(reverse("dashboard:user_add_student"), {"nim": "D1"}, follow=True)
        self.assertContains(resp, "Tidak dapat terhubung ke server SIPAKAMASE.")


class CsvImportTests(UserListFixtureMixin, TestCase):
    def setUp(self):
        self.client.force_login(self.admin)
        self.api = FakeApi({
            "D123211010": API_STUDENT,
            "D123211011": dict(API_STUDENT, prodi={"nama_resmi": "Kedokteran"}),
        })

    def _upload(self, content, name="students.csv"):
        upload = SimpleUploadedFile(name, content.encode("utf-8"), content_type="text/csv")
        with mock.patch("apps.dashboard.user_services.SipakamaseClient", return_value=self.api), \
                override_settings(CSV_IMPORT_DELAY_SECONDS=0):
            return self.client.post(reverse("dashboard:user_upload_csv"), {"csv_file": upload}, follow=True)

    def test_header_skipped_and_errors_shown_in_modal(self):
        resp = self._upload("nim\nD123211010\nD123211011\nD123211012\n\n")
        self.assertTrue(User.objects.filter(username="D123211010").exists())
        self.assertFalse(User.objects.filter(username="D123211011").exists())
        self.assertContains(resp, "Row 3: D123211011 - The study program is not available for the international class.")
        self.assertContains(resp, "Row 4: D123211012 - NIM not valid or not found.")
        self.assertContains(resp, 'id="copy-csv-errors"')

    def test_csv_errors_shown_once(self):
        self._upload("nim\nD123211011\n")
        resp = self.client.get(reverse("dashboard:users_list"), {"tab": "all"})
        self.assertNotContains(resp, 'id="csv-errors-modal"')

    def test_rejects_non_csv_extension(self):
        resp = self._upload("nim\nD1\n", name="students.xlsx")
        self.assertContains(resp, "Only .csv or .txt files are accepted.")

    def test_rejects_non_utf8(self):
        upload = SimpleUploadedFile("a.csv", "nim\n\xff\xfe".encode("latin-1"), content_type="text/csv")
        with mock.patch("apps.dashboard.user_services.SipakamaseClient", return_value=self.api):
            resp = self.client.post(reverse("dashboard:user_upload_csv"), {"csv_file": upload}, follow=True)
        self.assertContains(resp, "The CSV file must be UTF-8 encoded.")


class SipakamaseClientTests(TestCase):
    def _client(self, handler):
        transport = httpx.MockTransport(handler)
        with override_settings(SIPAKAMASE_URL="https://sipakamase.test/api/", SIPAKAMASE_USERNAME="u", SIPAKAMASE_PASSWORD="p"):
            return SipakamaseClient(transport=transport)

    def test_login_and_fetch_student(self):
        seen = {}

        def handler(request):
            if request.url.path.endswith("/login"):
                seen["login_body"] = request.content.decode()
                return httpx.Response(200, json={"access_token": "tok"})
            seen["auth"] = request.headers["Authorization"]
            seen["body"] = request.content.decode()
            return httpx.Response(200, json={"mahasiswas": [API_STUDENT]})

        with override_settings(SIPAKAMASE_URL="https://sipakamase.test/api/", SIPAKAMASE_USERNAME="u", SIPAKAMASE_PASSWORD="p"):
            client = SipakamaseClient(transport=httpx.MockTransport(handler))
            client.login()
            data = client.get_student("D123211001")
        self.assertEqual(data["nama_mahasiswa"], "BUDI SANTOSO")
        self.assertEqual(seen["auth"], "Bearer tok")
        self.assertIn('"nim":"D123211001"', seen["body"])
        self.assertIn('"username":"u"', seen["login_body"])

    def test_login_failure_raises(self):
        client = self._client(lambda request: httpx.Response(401, json={}))
        with self.assertRaises(SipakamaseError):
            client.login()

    def test_student_not_found_returns_none(self):
        def handler(request):
            if request.url.path.endswith("/login"):
                return httpx.Response(200, json={"access_token": "tok"})
            return httpx.Response(200, json={"mahasiswas": []})

        client = self._client(handler)
        client.login()
        self.assertIsNone(client.get_student("D0"))

    def test_missing_url_raises(self):
        with override_settings(SIPAKAMASE_URL=""):
            with self.assertRaises(SipakamaseError):
                SipakamaseClient(transport=httpx.MockTransport(lambda r: httpx.Response(200)))


class AddStaffTests(UserListFixtureMixin, TestCase):
    data = {
        "username": "staff2", "name": "Staff Dua", "email": "staff2@example.test",
        "password": "rahasia-123", "study_program": None,
    }

    def _data(self):
        return dict(self.data, study_program=self.sp2.pk)

    def test_admin_creates_staff_with_study_program(self):
        self.client.force_login(self.admin)
        resp = self.client.post(reverse("dashboard:user_add_staff"), self._data())
        self.assertEqual(resp.status_code, 302)
        user = User.objects.get(username="staff2")
        self.assertTrue(user.check_password("rahasia-123"))
        self.assertTrue(user.groups.filter(name="staff").exists())
        self.assertEqual(user.staff.study_program, self.sp2)

    def test_staff_cannot_open_add_staff(self):
        self.client.force_login(self.staff_user)
        self.assertEqual(self.client.post(reverse("dashboard:user_add_staff")).status_code, 403)

    def test_duplicate_username_rejected(self):
        self.client.force_login(self.admin)
        resp = self.client.post(reverse("dashboard:user_add_staff"), dict(self._data(), username="root"))
        self.assertContains(resp, "This username is already taken.")

    def test_short_password_rejected(self):
        self.client.force_login(self.admin)
        resp = self.client.post(reverse("dashboard:user_add_staff"), dict(self._data(), password="short"))
        self.assertContains(resp, "Ensure this value has at least 8 characters")


class GenericUserFormGuardTests(UserListFixtureMixin, TestCase):
    def test_staff_cannot_assign_staff_group_through_generic_form(self):
        staff_group = Group.objects.get(name="staff")
        self.client.force_login(self.staff_user)
        resp = self.client.post(reverse("dashboard:users_create"), {
            "username": "sneaky", "name": "Sneaky", "email": "sneaky@example.test",
            "password": "x-test-pass-1", "groups": [staff_group.pk], "is_active": "on",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Only admin can create or assign staff accounts.")
        self.assertFalse(User.objects.filter(username="sneaky").exists())


class EnglishScoreAndDetailTests(UserListFixtureMixin, TestCase):
    def test_admin_updates_english_score(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("dashboard:user_english_score", args=[self.a1.pk]), {"english_score": 75, "tab": "all"})
        self.a1.student.refresh_from_db()
        self.assertEqual(self.a1.student.english_score, 75)

    def test_out_of_range_score_rejected(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("dashboard:user_english_score", args=[self.a1.pk]), {"english_score": 101})
        self.a1.student.refresh_from_db()
        self.assertIsNone(self.a1.student.english_score)

    def test_staff_cannot_edit_other_program(self):
        self.client.force_login(self.staff_user)
        resp = self.client.post(reverse("dashboard:user_english_score", args=[self.a2.pk]), {"english_score": 50})
        self.assertEqual(resp.status_code, 403)

    def test_detail_fragment_lists_programs(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("dashboard:user_detail", args=[self.a1.pk]))
        self.assertContains(resp, "Summer")
        self.assertContains(resp, "Completed")
        self.assertContains(resp, "Informatika")

    def test_detail_without_program_shows_placeholder(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("dashboard:user_detail", args=[self.a2.pk]))
        self.assertContains(resp, "No program assigned")

    def test_detail_forbidden_for_other_program_staff(self):
        self.client.force_login(self.staff_user)
        self.assertEqual(self.client.get(reverse("dashboard:user_detail", args=[self.a2.pk])).status_code, 403)


class PrintTests(UserListFixtureMixin, TestCase):
    def test_print_applies_tab_and_search(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("dashboard:user_print"), {"tab": "all", "search": "dewi"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["count"], 1)
        self.assertContains(resp, "D122211002")
        self.assertContains(resp, "Print / Save as PDF")

    def test_print_staff_limited_to_own_program(self):
        self.client.force_login(self.staff_user)
        resp = self.client.get(reverse("dashboard:user_print"), {"tab": "all"})
        self.assertEqual(resp.context["count"], 1)
        self.assertContains(resp, "D122211001")
        self.assertNotContains(resp, "D122211002")

    def test_print_requires_manage_user(self):
        plain = User.objects.create_user(username="plain", password="x-test-pass-1")
        self.client.force_login(plain)
        self.assertEqual(self.client.get(reverse("dashboard:user_print")).status_code, 403)
