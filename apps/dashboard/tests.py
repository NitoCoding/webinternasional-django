from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse

from apps.academic.models import Faculty, Staff, Student, StudyProgram
from apps.international.models import IeProgram, Program, ProgramEnrollment

User = get_user_model()


class UserListFixtureMixin:
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(
            username="root", email="root@example.test", password="x-test-pass-1"
        )
        faculty = Faculty.objects.create(name="Teknik", code="T")
        cls.sp1 = StudyProgram.objects.create(
            faculty=faculty, name="Informatika", degree="S1", description="-", image="",
            national_accreditation="-", international_accreditation="-",
        )
        cls.sp2 = StudyProgram.objects.create(
            faculty=faculty, name="Sipil", degree="S1", description="-", image="",
            national_accreditation="-", international_accreditation="-",
        )
        staff_group = Group.objects.create(name="staff")
        staff_group.permissions.add(Permission.objects.get(codename="manage_user", content_type__app_label="accounts"))
        cls.staff_user = User.objects.create_user(
            username="staff1", name="Staff Satu", email="staff1@example.test", password="x-test-pass-1"
        )
        cls.staff_user.groups.add(staff_group)
        Staff.objects.create(user=cls.staff_user, name="Staff Satu", study_program=cls.sp1)

        cls.w1 = cls._student("D121211001", "Budi Santoso", cls.sp1, "waiting", False, False)
        cls.w2 = cls._student("D121211002", "Siti Aminah", cls.sp2, "waiting", False, False)
        cls.a1 = cls._student("D122211001", "Rafi Kurniawan", cls.sp1, "accepted", True, True)
        cls.a2 = cls._student("D122211002", "Dewi Lestari", cls.sp2, "accepted", True, False)

        ie = IeProgram.objects.create(name="Exchange")
        program = Program.objects.create(
            name="Summer", description="-", country="Japan", execution_date=date(2026, 1, 1),
            end_date=date(2026, 2, 1), participants_count=5, course_credits=3, image="",
            ie_program=ie, created_by=cls.admin,
        )
        ProgramEnrollment.objects.create(
            program=program, student=cls.a1.student,
            status=ProgramEnrollment.Status.APPROVED, is_finished=True,
        )

    @classmethod
    def _student(cls, nim, name, sp, status, verified, active):
        user = User.objects.create_user(
            username=nim, name=name, email=f"{nim.lower()}@example.test", password="x-test-pass-1"
        )
        Student.objects.create(
            user=user, name=name, student_id_number=nim, email=user.email,
            study_program=sp, status=status, is_verified=verified, is_active=active,
        )
        user.is_active = active
        user.save(update_fields=["is_active"])
        return user

    def usernames(self, params, as_user=None):
        self.client.force_login(as_user or self.admin)
        resp = self.client.get(reverse("dashboard:users_list"), params)
        self.assertEqual(resp.status_code, 200)
        return sorted(row["obj"].username for row in resp.context["rows"])


class UserListSearchTests(UserListFixtureMixin, TestCase):
    def test_search_by_name(self):
        self.assertEqual(self.usernames({"tab": "waiting", "search": "budi santoso"}), ["D121211001"])

    def test_search_by_username(self):
        self.assertEqual(
            self.usernames({"tab": "waiting", "search": "D12121100"}),
            ["D121211001", "D121211002"],
        )

    def test_search_by_email(self):
        self.assertEqual(self.usernames({"tab": "waiting", "search": "d121211002@"}), ["D121211002"])

    def test_search_no_match(self):
        self.assertEqual(self.usernames({"tab": "waiting", "search": "tidakada"}), [])

    def test_placeholder_matches_fields(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("dashboard:users_list"))
        self.assertContains(resp, "Search by name, username, or email...")


class UserListTabTests(UserListFixtureMixin, TestCase):
    def test_waiting_tab_admin_sees_all_waiting(self):
        self.assertEqual(self.usernames({"tab": "waiting"}), ["D121211001", "D121211002"])

    def test_waiting_tab_staff_sees_only_own_program(self):
        self.assertEqual(self.usernames({"tab": "waiting"}, as_user=self.staff_user), ["D121211001"])

    def test_active_tab_only_active_students(self):
        self.assertEqual(self.usernames({"tab": "active"}), ["D122211001"])

    def test_all_tab_only_verified_students(self):
        self.assertEqual(self.usernames({"tab": "all"}), ["D122211001", "D122211002"])

    def test_staff_tab_admin_only(self):
        self.assertEqual(self.usernames({"tab": "staff"}), ["staff1"])
        # Staff tidak punya tab Staff: diperlakukan sebagai tab All.
        self.assertEqual(self.usernames({"tab": "staff"}, as_user=self.staff_user), ["D122211001"])

    def test_waiting_empty_state_text(self):
        Student.objects.filter(status="waiting").update(status="rejected")
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("dashboard:users_list"), {"tab": "waiting"})
        self.assertContains(resp, "No students waiting for approval")

    def test_waiting_count_context(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("dashboard:users_list"), {"tab": "all"})
        self.assertEqual(resp.context["waiting_count"], 2)


class UserListFilterTests(UserListFixtureMixin, TestCase):
    def test_year_filter(self):
        # Angkatan = "20" + NIM[4:6] (sama dengan Laravel): D122211001 -> 2021.
        self.assertEqual(self.usernames({"tab": "all", "year": "2021"}), ["D122211001", "D122211002"])
        self.assertEqual(self.usernames({"tab": "all", "year": "2022"}), [])

    def test_study_program_filter_admin(self):
        self.assertEqual(self.usernames({"tab": "all", "study_program": self.sp2.pk}), ["D122211002"])

    def test_study_program_filter_limited_to_staff_scope(self):
        self.assertEqual(
            self.usernames({"tab": "all", "study_program": self.sp2.pk}, as_user=self.staff_user),
            ["D122211001"],
        )

    def test_status_completed(self):
        self.assertEqual(self.usernames({"tab": "all", "studentStatus": "completed"}), ["D122211001"])

    def test_status_not_started(self):
        self.assertEqual(self.usernames({"tab": "all", "studentStatus": "not_started"}), ["D122211002"])


class UserActionTests(UserListFixtureMixin, TestCase):
    def _refresh(self, user):
        user.refresh_from_db()
        user.student.refresh_from_db()
        return user

    def test_accept_by_admin(self):
        self.client.force_login(self.admin)
        resp = self.client.post(reverse("dashboard:user_accept", args=[self.w1.pk]))
        self.assertEqual(resp.status_code, 302)
        self._refresh(self.w1)
        self.assertEqual(self.w1.student.status, Student.Status.ACCEPTED)
        self.assertTrue(self.w1.student.is_verified)
        self.assertTrue(self.w1.is_active)
        self.assertTrue(self.w1.has_perm("accounts.choose_program"))

    def test_reject_by_admin(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("dashboard:user_reject", args=[self.w1.pk]))
        self._refresh(self.w1)
        self.assertEqual(self.w1.student.status, Student.Status.REJECTED)
        self.assertFalse(self.w1.is_active)

    def test_staff_cannot_accept_other_program(self):
        self.client.force_login(self.staff_user)
        resp = self.client.post(reverse("dashboard:user_accept", args=[self.w2.pk]))
        self.assertEqual(resp.status_code, 403)
        self._refresh(self.w2)
        self.assertEqual(self.w2.student.status, Student.Status.WAITING)

    def test_staff_can_accept_own_program(self):
        self.client.force_login(self.staff_user)
        self.client.post(reverse("dashboard:user_accept", args=[self.w1.pk]))
        self._refresh(self.w1)
        self.assertEqual(self.w1.student.status, Student.Status.ACCEPTED)

    def test_toggle_active_deactivates_student_and_user(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("dashboard:user_toggle_active", args=[self.a1.pk]), {"tab": "active"})
        self._refresh(self.a1)
        self.assertFalse(self.a1.student.is_active)
        self.assertFalse(self.a1.is_active)

    def test_get_shows_confirmation_without_changes(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("dashboard:user_accept", args=[self.w1.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Accept student?")
        self._refresh(self.w1)
        self.assertEqual(self.w1.student.status, Student.Status.WAITING)

    def test_reject_confirmation_page(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("dashboard:user_reject", args=[self.w1.pk]))
        self.assertContains(resp, "Reject student?")

    def test_not_started_excludes_pending(self):
        # Mahasiswa dengan enrollment pending tampil WAITING, bukan NOT STARTED.
        ProgramEnrollment.objects.create(
            program=Program.objects.get(), student=self.a2.student,
            status=ProgramEnrollment.Status.PENDING,
        )
        self.assertEqual(self.usernames({"tab": "all", "studentStatus": "not_started"}), [])
