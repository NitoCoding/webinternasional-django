"""Logika impor mahasiswa, impor CSV, dan pembuatan staff untuk halaman users.

Mengikuti UserController di Laravel (storeStudent, uploadCsvStudent, store staff).
View tipis ada di apps/dashboard/user_views.py.
"""

import csv
import io
import time
from dataclasses import dataclass, field
from datetime import datetime

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404

from apps.academic.models import Staff, Student, StudyProgram
from apps.academic.sipakamase import SipakamaseClient, SipakamaseError
from apps.accounts.models import User
from apps.dashboard.views.base import _is_admin

DEFAULT_EMAIL_DOMAIN = "unhas.ac.id"
CSV_MAX_BYTES = 2 * 1024 * 1024


@dataclass
class ImportResult:
    ok: bool
    message: str


@dataclass
class CsvImportResult:
    created: int = 0
    updated: int = 0
    errors: list = field(default_factory=list)
    fatal: str = ""


def _staff_study_program_id(actor):
    staff = getattr(actor, "staff", None)
    return staff.study_program_id if staff else None


def _parse_gender(value):
    value = (value or "").strip().upper()
    return value if value in ("L", "P") else None


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _ucfirst(value):
    """Sama dengan ucfirst() di Laravel: huruf pertama kapital, sisanya tidak diubah."""
    return value[:1].upper() + value[1:]


def _cut(value, max_length):
    return (value or "")[:max_length] or None


@transaction.atomic
def _save_student_from_api(nim, data, study_program):
    """Buat akun User dan Student baru dari data API. Asumsi NIM sudah diuji tidak ada."""
    nama = data.get("nama_mahasiswa") or "No Name"
    email = data.get("email") or f"{nim}@{DEFAULT_EMAIL_DOMAIN}"
    user = User(username=nim, name=_ucfirst(nama), email=email)
    user.set_password(f"{nim}@internasional")
    user.save()
    user.groups.add(Group.objects.get_or_create(name="student")[0])
    Student.objects.create(
        user=user,
        name=_ucfirst(nama),
        student_id_number=nim,
        email=email,
        gender=_parse_gender(data.get("jenis_kelamin")),
        nik=_cut(data.get("nik"), 20),
        nisn=_cut(data.get("nisn"), 20),
        phone_number=_cut(data.get("handphone"), 20),
        home_phone=_cut(data.get("telepon"), 20),
        address=_cut(data.get("jalan"), 255),
        birth_place=_cut(data.get("tempat_lahir"), 100),
        birth_date=_parse_date(data.get("tanggal_lahir")),
        status=Student.Status.ACCEPTED,
        is_active=True,
        is_verified=True,
        study_program=study_program,
    )
    return user


def import_student(nim, actor, api):
    """Impor satu mahasiswa berdasarkan NIM. `api` punya method get_student(nim)."""
    nim = (nim or "").strip().upper()
    if not nim:
        return ImportResult(False, "NIM is required.")

    data = api.get_student(nim)
    if data is None:
        return ImportResult(False, "NIM not valid or not found.")

    prodi = (data.get("prodi") or {}).get("nama_resmi") or ""
    study_program = StudyProgram.objects.filter(name=prodi).first()
    if study_program is None:
        return ImportResult(False, "The study program is not available for the international class.")

    if not _is_admin(actor) and _staff_study_program_id(actor) != study_program.pk:
        return ImportResult(False, "The student is not under your authority.")

    existing = Student.objects.filter(student_id_number=nim).first()
    if existing:
        existing.status = Student.Status.ACCEPTED
        existing.is_active = True
        existing.is_verified = True
        existing.save()
        return ImportResult(True, "Student updated successfully.")

    if User.objects.filter(username=nim).exists():
        return ImportResult(False, f"Username {nim} is already used by another account.")
    email = data.get("email") or f"{nim}@{DEFAULT_EMAIL_DOMAIN}"
    if User.objects.filter(email__iexact=email).exists():
        return ImportResult(False, f"Email {email} is already used by another account.")

    _save_student_from_api(nim, data, study_program)
    return ImportResult(True, "Student added successfully.")


def import_students_csv(uploaded_file, actor, delay=None):
    """Impor banyak NIM dari CSV. Kolom pertama berisi NIM; baris pertama dianggap header."""
    result = CsvImportResult()
    if uploaded_file.size > CSV_MAX_BYTES:
        result.fatal = "The CSV file must be 2 MB or smaller."
        return result

    try:
        text = uploaded_file.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        result.fatal = "The CSV file must be UTF-8 encoded."
        return result

    rows = list(csv.reader(io.StringIO(text)))[1:]  # lewati header
    delay = settings.CSV_IMPORT_DELAY_SECONDS if delay is None else delay

    client = SipakamaseClient()
    try:
        client.login()
    except SipakamaseError as exc:
        result.fatal = str(exc)
        client.close()
        return result

    class _Api:
        def get_student(self, nim):
            return client.get_student(nim)

    try:
        for index, row in enumerate(rows, start=2):  # nomor baris dihitung dari header = 1
            if not row or not (row[0] or "").strip():
                continue
            nim = row[0].strip()
            if delay:
                time.sleep(delay)
            try:
                outcome = import_student(nim, actor, _Api())
            except SipakamaseError as exc:
                result.errors.append(f"Row {index}: {nim} - {exc}")
                continue
            if not outcome.ok:
                result.errors.append(f"Row {index}: {nim} - {outcome.message}")
            elif outcome.message.startswith("Student updated"):
                result.updated += 1
            else:
                result.created += 1
    finally:
        client.close()
    return result


def manageable_student(actor, pk):
    """Ambil (User, Student) yang boleh dikelola actor, atau lempar 403/404.

    Admin atau pemegang permission manage_user. Staff hanya Study Program miliknya.
    """
    if not (_is_admin(actor) or actor.has_perm("accounts.manage_user")):
        raise PermissionDenied
    student_user = get_object_or_404(User, pk=pk)
    student = getattr(student_user, "student", None)
    if student is None:
        raise Http404
    if not _is_admin(actor) and student.study_program_id != _staff_study_program_id(actor):
        raise PermissionDenied
    return student_user, student


def update_english_score(student, value):
    student.english_score = value
    student.save(update_fields=["english_score"])
    return student


@transaction.atomic
def create_staff(actor, cleaned, study_program):
    """Buat akun staff. Hanya admin yang boleh (diperiksa di view)."""
    user = User(
        username=cleaned["username"],
        name=cleaned["name"],
        email=cleaned["email"].lower(),
    )
    user.set_password(cleaned["password"])
    user.save()
    user.groups.add(Group.objects.get_or_create(name="staff")[0])
    Staff.objects.create(user=user, name=cleaned["name"], study_program=study_program)
    return user
