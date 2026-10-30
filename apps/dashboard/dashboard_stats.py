"""Data dashboard per role, mengikuti DashboardController Laravel.

- Admin: semua mahasiswa terverifikasi, dengan filter status.
- Staff: sama, tetapi hanya mahasiswa di study program staff.
- Student: ringkasan dari API transkrip SIPAKAMASE (IPK, SKS lulus, masa studi).
"""

import re
from datetime import date

from django.conf import settings
from django.db.models import Count
from django.db.models.functions import ExtractYear

from apps.academic.models import Student
from apps.academic.student_data import transcript_data
from apps.international.models import Program, ProgramEnrollment

# Sama dengan Laravel: [A-NR]\d{3}(\d{2})\d{3}. Grup kedua adalah dua digit angkatan.
NIM_ANGKATAN_RE = re.compile(r"[A-NR]\d{3}(\d{2})\d{3}")
# Nilai huruf yang dihitung sebagai SKS lulus (sama dengan Laravel).
PASSING_GRADES = ("A", "A-", "B+", "B", "B-", "C+", "C", "D")
STUDENT_SKS_TARGET = 144
STATUS_OPTIONS = (
    ("all", "All Students"),
    ("active", "Active"),
    ("inactive", "Inactive"),
)
# Warna chart per angkatan, sama dengan generateChartColors() di Laravel.
CHART_COLORS = ("#36B9CC", "#FF6B9A", "#FFB84D", "#0077FF")


def angkatan_from_nim(nim):
    """Angkatan = "20" + dua digit dari NIM. Mengembalikan None jika format NIM tidak cocok."""
    match = NIM_ANGKATAN_RE.search(nim or "")
    return f"20{match.group(1)}" if match else None


def _verified_students(study_program=None, status="all"):
    qs = Student.objects.filter(is_verified=True).select_related("study_program")
    if study_program is not None:
        qs = qs.filter(study_program=study_program)
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "inactive":
        qs = qs.filter(is_active=False)
    return qs


def student_batch_stats(study_program=None, status="all"):
    """Jumlah mahasiswa per angkatan, dan per program studi lalu angkatan."""
    batches = {}
    by_program = {}
    rows = _verified_students(study_program, status).values_list(
        "student_id_number", "study_program__name"
    )
    for nim, program_name in rows:
        angkatan = angkatan_from_nim(nim)
        if not angkatan:
            continue
        batches[angkatan] = batches.get(angkatan, 0) + 1
        per_year = by_program.setdefault(program_name or "-", {})
        per_year[angkatan] = per_year.get(angkatan, 0) + 1
    return {
        "batches": dict(sorted(batches.items())),
        "by_program": by_program,
        "years": sorted(batches),
    }


def ie_program_counts(study_program=None):
    """Jumlah program IE per jenis (Laravel: getProgramCounts)."""
    qs = Program.objects.all()
    if study_program is not None:
        qs = qs.filter(study_programs=study_program)
    rows = (
        qs.values("ie_program__name")
        .annotate(count=Count("id", distinct=True))
        .order_by("ie_program__name")
    )
    return [{"label": r["ie_program__name"], "count": r["count"]} for r in rows]


def ie_counts_by_year(study_program=None):
    """Jumlah peserta IE yang disetujui, per tahun pelaksanaan program (Laravel: getStudentCountsByYear)."""
    qs = ProgramEnrollment.objects.filter(status=ProgramEnrollment.Status.APPROVED)
    if study_program is not None:
        qs = qs.filter(student__study_program=study_program)
    rows = (
        qs.annotate(year=ExtractYear("program__execution_date"))
        .values("year")
        .annotate(count=Count("id"))
        .order_by("year")
    )
    return [{"year": r["year"], "count": r["count"]} for r in rows]


def build_chart_payload(stats, ie_counts=None, year_counts=None):
    """Data untuk Chart.js. Nama kunci mengikuti dashboard Laravel."""
    programs = sorted(stats["by_program"])
    datasets = []
    for index, year in enumerate(stats["years"]):
        color = CHART_COLORS[index % len(CHART_COLORS)]
        datasets.append({
            "label": year,
            "data": [stats["by_program"][p].get(year, 0) for p in programs],
            "backgroundColor": color,
            "borderColor": color,
            "borderWidth": 1,
        })
    payload = {
        "batchLabels": list(stats["batches"].keys()),
        "batchCounts": list(stats["batches"].values()),
        "programLabels": programs,
        "datasets": datasets,
    }
    if ie_counts is not None:
        payload["ieLabels"] = [row["label"] for row in ie_counts]
        payload["ieCounts"] = [row["count"] for row in ie_counts]
    if year_counts is not None:
        payload["yearLabels"] = [str(row["year"]) for row in year_counts]
        payload["yearCounts"] = [row["count"] for row in year_counts]
    return payload


def admin_dashboard_context(study_program, status, is_admin):
    stats = student_batch_stats(study_program, status)
    ie_counts = ie_program_counts(study_program)
    year_counts = ie_counts_by_year(study_program) if is_admin else None
    return {
        "is_admin": is_admin,
        "status": status,
        "status_options": STATUS_OPTIONS,
        "study_program": study_program,
        "total": sum(stats["batches"].values()),
        "ie_counts": ie_counts,
        "chart": build_chart_payload(stats, ie_counts, year_counts),
    }


def student_semester_summary(angkatan, today=None):
    """Semester berjalan dan sisa masa studi, sama dengan processStudentTranscript() di Laravel.

    Tahun ajaran dimulai Agustus. Agustus-Desember = Ganjil, Januari = Ganjil tahun sebelumnya,
    Februari-Juli = Genap tahun sebelumnya.
    """
    today = today or date.today()
    if today.month >= 8:
        tahun_ajaran, offset = today.year, 1
    elif today.month == 1:
        tahun_ajaran, offset = today.year - 1, 1
    else:
        tahun_ajaran, offset = today.year - 1, 2
    semester = (tahun_ajaran - angkatan) * 2 + offset
    if angkatan <= settings.ACADEMIC_POLICY_CHANGE_YEAR:
        max_period = settings.ACADEMIC_MAX_STUDY_PERIOD_DEFAULT
    else:
        max_period = settings.ACADEMIC_MAX_STUDY_PERIOD_FROM_2023
    return {"semester": semester, "max_period": max_period, "remaining": max_period - semester}


def _to_int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def student_summary(nim, today=None):
    """Ringkasan dashboard student dari transkrip SIPAKAMASE (memakai cache transcript_data)."""
    result = transcript_data(nim)
    base = {"message": result["message"], "from_cache": result["from_cache"]}
    if not result["ok"]:
        return {"ok": False, **base}
    rows = result["rows"]
    if not rows:
        return {"ok": False, "message": "Data transkrip tidak ditemukan", "from_cache": result["from_cache"]}

    angkatan = _to_int(result.get("angkatan")) or _to_int(angkatan_from_nim(nim))
    if not angkatan:
        return {"ok": False, "message": "Angkatan mahasiswa tidak diketahui", "from_cache": result["from_cache"]}

    semester = student_semester_summary(angkatan, today)
    sks_lulus = sum(_to_int(r["sks"]) for r in rows if r["huruf"] in PASSING_GRADES)
    return {
        "ok": True,
        **base,
        "nama": result["nama"],
        "nim": result["nim"],
        "email": result.get("email", ""),
        "prodi": result.get("prodi", ""),
        "ipk": result.get("ipk"),
        "sks_dilulusi": sks_lulus,
        "sks_target": STUDENT_SKS_TARGET,
        **semester,
    }
