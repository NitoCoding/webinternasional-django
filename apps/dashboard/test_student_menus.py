from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from apps.academic.sipakamase import SipakamaseError
from apps.academic.student_data import krs_data, semester_options, transcript_data

User = get_user_model()

TRANSCRIPT_RAW = {
    "mahasiswa": {"nama_mahasiswa": "BUDI SANTOSO", "nim": "D121211001"},
    "transkrips": [
        {"kode_mata_kuliah": "IF101", "nama_mata_kuliah": "Algoritma", "sks": 3,
         "nilai_huruf": "A", "nilai_angka": 4.0, "total_nilai": 12.0},
        {"kode_mata_kuliah": "IF102", "nama_mata_kuliah": "Basis Data", "sks": 2,
         "nilai_huruf": "B+", "nilai_angka": 3.5, "total_nilai": 7.0},
    ],
}

KRS_RAW = {"krs": [
    {"nama_mata_kuliah": "Kalkulus", "jumlah_sks": 3},
    {"nama_mata_kuliah": "Fisika", "jumlah_sks": 2},
    {"jumlah_sks": 9},  # tanpa nama: dilewati
]}


class FakeClient:
    transcript = None
    krs = None
    error = None

    def __init__(self):
        pass

    def get_transcript(self, nim):
        if FakeClient.error:
            raise FakeClient.error
        return FakeClient.transcript

    def get_krs(self, nim, semester):
        if FakeClient.error:
            raise FakeClient.error
        return FakeClient.krs

    def close(self):
        pass


class SipakamaseFakeMixin:
    def setUp(self):
        cache.clear()
        FakeClient.error = None
        FakeClient.transcript = TRANSCRIPT_RAW
        FakeClient.krs = KRS_RAW
        self.patcher = mock.patch("apps.academic.student_data.SipakamaseClient", FakeClient)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        cache.clear()


class StudentDataTests(SipakamaseFakeMixin, TestCase):
    def test_transcript_maps_rows_and_caches(self):
        result = transcript_data("D121211001")
        self.assertTrue(result["ok"])
        self.assertFalse(result["from_cache"])
        self.assertEqual(result["nama"], "BUDI SANTOSO")
        self.assertEqual([r["kode"] for r in result["rows"]], ["IF101", "IF102"])

    def test_transcript_falls_back_to_cache_when_api_down(self):
        transcript_data("D121211001")
        FakeClient.error = SipakamaseError("server down")
        result = transcript_data("D121211001")
        self.assertTrue(result["ok"])
        self.assertTrue(result["from_cache"])
        self.assertIn("cache", result["message"])
        self.assertEqual(len(result["rows"]), 2)

    def test_transcript_error_without_cache(self):
        FakeClient.error = SipakamaseError("server down")
        result = transcript_data("D121211001")
        self.assertFalse(result["ok"])
        self.assertEqual(result["rows"], [])
        self.assertIn("server down", result["message"])

    def test_transcript_empty_response_is_error(self):
        FakeClient.transcript = {"message": "not found"}
        self.assertFalse(transcript_data("D121211001")["ok"])

    def test_semester_options_from_nim_year_to_current(self):
        options = semester_options("D121211001", date(2026, 10, 30))
        self.assertEqual(options[0], "20211")
        self.assertEqual(options[1], "20212")
        self.assertEqual(options[-1], "20262")
        self.assertEqual(len(options), 12)

    def test_semester_options_capped_at_seven_years(self):
        self.assertEqual(semester_options("D121211001", date(2040, 1, 1))[-1], "20282")

    def test_semester_options_invalid_nim(self):
        self.assertEqual(semester_options("XX", date(2026, 1, 1)), [])

    def test_krs_totals_and_skips_incomplete_rows(self):
        result = krs_data("D121211001", "20251")
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["rows"]), 2)
        self.assertEqual(result["total_sks"], 5)

    def test_krs_missing_key_is_not_found(self):
        FakeClient.krs = {"message": "no"}
        self.assertFalse(krs_data("D121211001", "20251")["ok"])


class StudentPageTests(SipakamaseFakeMixin, TestCase):
    def setUp(self):
        super().setUp()
        group, _ = Group.objects.get_or_create(name="student")
        self.student = User.objects.create_user(username="D121211001", name="Budi", email="b@example.test", password="x-test-pass-1")
        self.student.groups.add(group)
        self.admin = User.objects.create_superuser(username="root", email="r@example.test", password="x-test-pass-1")

    def test_transcript_page_renders_without_calling_api(self):
        # Halaman harus render tanpa memanggil API: data dimuat lewat AJAX.
        self.client.force_login(self.student)
        with mock.patch.object(FakeClient, "get_transcript", side_effect=AssertionError("API dipanggil")):
            resp = self.client.get(reverse("dashboard:student_transcript"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, reverse("dashboard:student_transcript_data"))
        self.assertNotContains(resp, "Algoritma")

    def test_transcript_data_endpoint(self):
        self.client.force_login(self.student)
        resp = self.client.get(reverse("dashboard:student_transcript_data"))
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["nama"], "BUDI SANTOSO")
        self.assertEqual(body["rows"][0]["mata_kuliah"], "Algoritma")

    def test_data_endpoints_refused_for_admin(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("dashboard:student_transcript")).status_code, 403)
        self.assertEqual(self.client.get(reverse("dashboard:student_transcript_data")).status_code, 403)
        self.assertEqual(self.client.get(reverse("dashboard:student_study_plan_data")).status_code, 403)

    def test_pages_require_login(self):
        self.assertEqual(self.client.get(reverse("dashboard:student_transcript")).status_code, 302)
        self.assertEqual(self.client.get(reverse("dashboard:student_study_plan")).status_code, 302)

    def test_study_plan_page_renders_semester_options_without_api(self):
        self.client.force_login(self.student)
        with mock.patch.object(FakeClient, "get_krs", side_effect=AssertionError("API dipanggil")):
            resp = self.client.get(reverse("dashboard:student_study_plan"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "2021 Ganjil")
        self.assertContains(resp, reverse("dashboard:student_study_plan_data"))

    def test_study_plan_data_defaults_to_first_semester(self):
        self.client.force_login(self.student)
        body = self.client.get(reverse("dashboard:student_study_plan_data")).json()
        self.assertEqual(body["semester"], "20211")
        self.assertEqual(body["total_sks"], 5)

    def test_study_plan_data_ignores_unknown_semester(self):
        self.client.force_login(self.student)
        body = self.client.get(reverse("dashboard:student_study_plan_data"), {"semester": "19990"}).json()
        self.assertEqual(body["semester"], "20211")

    def test_study_plan_data_accepts_valid_semester(self):
        self.client.force_login(self.student)
        body = self.client.get(reverse("dashboard:student_study_plan_data"), {"semester": "20231"}).json()
        self.assertEqual(body["semester"], "20231")

    def test_menu_links_shown_only_to_student(self):
        self.client.force_login(self.student)
        self.assertContains(self.client.get(reverse("dashboard:home")), reverse("dashboard:student_transcript"))
        self.client.force_login(self.admin)
        self.assertNotContains(self.client.get(reverse("dashboard:home")), reverse("dashboard:student_transcript"))
