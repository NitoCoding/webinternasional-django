from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from apps.academic.models import Faculty, Student, StudyProgram
from apps.international.enrollment import enroll_student
from apps.international.models import IeProgram, Program, ProgramEnrollment

User = get_user_model()


class EnrollmentFixtureMixin:
    def setUp(self):
        faculty = Faculty.objects.create(name="Teknik", code="T")
        self.sp = StudyProgram.objects.create(
            faculty=faculty, name="Informatika", degree="S1", description="-", image="",
            national_accreditation="-", international_accreditation="-",
        )
        self.ie = IeProgram.objects.create(name="Exchange")
        self.admin = User.objects.create_superuser(username="root", email="r@example.test", password="x-test-pass-1")
        self.program = Program.objects.create(
            name="Summer", description="-", country="Japan", execution_date=date(2026, 1, 1),
            end_date=date(2026, 2, 1), participants_count=2, course_credits=3, image="",
            ie_program=self.ie, created_by=self.admin,
        )
        self.program.study_programs.add(self.sp)
        self.student_user = self._student("D121211001", status="accepted", verified=True, active=True)
        self.student = self.student_user.student

    def _student(self, nim, status, verified, active, sp=None):
        user = User.objects.create_user(username=nim, name=nim, email=f"{nim.lower()}@example.test", password="x-test-pass-1")
        group, _ = Group.objects.get_or_create(name="student")
        user.groups.add(group)
        Student.objects.create(
            user=user, name=nim, student_id_number=nim, email=user.email,
            study_program=sp or self.sp, status=status, is_verified=verified, is_active=active,
        )
        return user


class EnrollRuleTests(EnrollmentFixtureMixin, TestCase):
    def test_eligible_student_enrolls_as_pending(self):
        ok, _ = enroll_student(self.student, self.program)
        self.assertTrue(ok)
        self.assertEqual(self.student.enrollments.get(program=self.program).status, "pending")

    def test_cannot_enroll_twice_while_pending(self):
        enroll_student(self.student, self.program)
        ok, message = enroll_student(self.student, self.program)
        self.assertFalse(ok)
        self.assertIn("pending", message)

    def test_cannot_enroll_while_another_program_in_progress(self):
        other = Program.objects.create(
            name="Winter", description="-", country="Korea", execution_date=date(2026, 3, 1),
            end_date=date(2026, 4, 1), participants_count=5, course_credits=3, image="",
            ie_program=self.ie, created_by=self.admin,
        )
        ProgramEnrollment.objects.create(program=other, student=self.student, status="approved", is_finished=False)
        ok, message = enroll_student(self.student, self.program)
        self.assertFalse(ok)
        self.assertIn("still in progress", message)

    def test_participant_limit(self):
        for nim in ("D121211002", "D121211003"):
            other = self._student(nim, status="accepted", verified=True, active=True)
            ProgramEnrollment.objects.create(program=self.program, student=other.student, status="approved")
        ok, message = enroll_student(self.student, self.program)
        self.assertFalse(ok)
        self.assertIn("participant limit", message)

    def test_rejected_enrollment_can_reapply_without_duplicate_row(self):
        ProgramEnrollment.objects.create(program=self.program, student=self.student, status="rejected")
        ok, _ = enroll_student(self.student, self.program)
        self.assertTrue(ok)
        self.assertEqual(ProgramEnrollment.objects.filter(program=self.program, student=self.student).count(), 1)
        self.assertEqual(self.student.enrollments.get(program=self.program).status, "pending")

    def test_not_verified_student_refused(self):
        user = self._student("D121211004", status=None, verified=False, active=False)
        ok, _ = enroll_student(user.student, self.program)
        self.assertFalse(ok)


class StudentProgramPageTests(EnrollmentFixtureMixin, TestCase):
    def test_list_shows_program_for_own_study_program(self):
        self.client.force_login(self.student_user)
        resp = self.client.get(reverse("dashboard:student_programs"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Summer")

    def test_list_hides_program_of_other_study_program(self):
        other_sp = StudyProgram.objects.create(
            faculty=self.sp.faculty, name="Sipil", degree="S1", description="-", image="",
            national_accreditation="-", international_accreditation="-",
        )
        self.program.study_programs.set([other_sp])
        self.client.force_login(self.student_user)
        resp = self.client.get(reverse("dashboard:student_programs"))
        self.assertNotContains(resp, "Summer")

    def test_not_eligible_shows_banner_and_program_with_disabled_enroll(self):
        user = self._student("D121211005", status="waiting", verified=True, active=True)
        self.client.force_login(user)
        resp = self.client.get(reverse("dashboard:student_programs"))
        self.assertContains(resp, "You are currently waiting for admin verification.")
        self.assertContains(resp, "Summer")
        self.assertNotContains(resp, 'class="js-enroll')

    def test_enroll_post_creates_pending(self):
        self.client.force_login(self.student_user)
        self.client.post(reverse("dashboard:student_program_enroll", args=[self.program.pk]))
        self.assertTrue(self.student.enrollments.filter(program=self.program, status="pending").exists())

    def test_enroll_outside_study_program_is_404(self):
        other_sp = StudyProgram.objects.create(
            faculty=self.sp.faculty, name="Sipil", degree="S1", description="-", image="",
            national_accreditation="-", international_accreditation="-",
        )
        self.program.study_programs.set([other_sp])
        self.client.force_login(self.student_user)
        resp = self.client.post(reverse("dashboard:student_program_enroll", args=[self.program.pk]))
        self.assertEqual(resp.status_code, 404)

    def test_enroll_get_not_allowed(self):
        self.client.force_login(self.student_user)
        resp = self.client.get(reverse("dashboard:student_program_enroll", args=[self.program.pk]))
        self.assertEqual(resp.status_code, 405)

    def test_register_sets_waiting(self):
        user = self._student("D121211006", status=None, verified=False, active=False)
        self.client.force_login(user)
        self.client.post(reverse("dashboard:student_register"))
        user.student.refresh_from_db()
        self.assertEqual(user.student.status, "waiting")

    def test_admin_refused_student_page(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("dashboard:student_programs")).status_code, 403)
