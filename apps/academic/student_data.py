"""Data transkrip dan KRS mahasiswa dari API SIPAKAMASE, dengan cache.

Mengikuti TranscriptController, StudyPlanController, dan SipakamaseService::getTranscript/getKrs
di Laravel. Tidak ada tabel baru: semua data diambil dari API setiap kali dibutuhkan (atau dari cache).
"""

from datetime import date

from django.core.cache import cache

from apps.academic.sipakamase import SipakamaseClient, SipakamaseError

TRANSCRIPT_CACHE_SECONDS = 600  # 10 menit, sama dengan Laravel
KRS_CACHE_SECONDS = 1800  # 30 menit, sama dengan Laravel
CACHE_NOTE = "Data dari cache (server sedang sibuk)"


def _process_transcript(raw):
    rows = []
    for item in raw.get("transkrips") or []:
        rows.append({
            "kode": item.get("kode_mata_kuliah", ""),
            "mata_kuliah": item.get("nama_mata_kuliah", ""),
            "sks": item.get("sks", 0),
            "huruf": item.get("nilai_huruf", ""),
            "angka": item.get("nilai_angka", 0),
            "total": item.get("total_nilai", 0),
        })
    mahasiswa = raw.get("mahasiswa") or {}
    return {
        "rows": rows,
        "nama": mahasiswa.get("nama_mahasiswa") or "Tidak Tersedia",
        "nim": mahasiswa.get("nim") or "Tidak Tersedia",
        "email": mahasiswa.get("email") or "",
        "prodi": (mahasiswa.get("prodi") or {}).get("nama_resmi") or "",
        "angkatan": mahasiswa.get("angkatan"),
        "ipk": (raw.get("current_indeks_prestasi") or {}).get("indeks_prestasi_kumulatif"),
    }


def transcript_data(nim):
    """Transkrip mahasiswa. Mengembalikan dict: ok, message, from_cache, rows, nama, nim."""
    cache_key = f"transcript_{nim}"
    client = None
    try:
        client = SipakamaseClient()
        raw = client.get_transcript(nim)
        if not raw.get("transkrips") and not raw.get("mahasiswa"):
            raise SipakamaseError("Data transkrip tidak ditemukan.")
        processed = _process_transcript(raw)
        cache.set(cache_key, processed, TRANSCRIPT_CACHE_SECONDS)
        return {"ok": True, "message": "Data berhasil diambil", "from_cache": False, **processed}
    except SipakamaseError as exc:
        cached = cache.get(cache_key)
        if cached:
            return {"ok": True, "message": CACHE_NOTE, "from_cache": True, **cached}
        return {
            "ok": False,
            "message": f"Gagal mengambil data: {exc}",
            "from_cache": False,
            "rows": [], "nama": "Tidak Tersedia", "nim": nim,
        }
    finally:
        if client is not None:
            client.close()


def semester_options(nim, today=None):
    """Kode semester (YYYY1 = ganjil, YYYY2 = genap) dari tahun masuk sampai tahun berjalan.

    Tahun masuk = 2000 + NIM[4:6], sama dengan Laravel. Batas atas: tahun masuk + 7, atau tahun
    berjalan jika lebih kecil. Laravel membatasi di 2024 secara tetap; batas ini tidak ditiru.
    """
    today = today or date.today()
    digits = (nim or "")[4:6]
    if not digits.isdigit():
        return []
    start = 2000 + int(digits)
    end = min(start + 7, today.year)
    options = []
    for year in range(start, end + 1):
        options.extend([f"{year}1", f"{year}2"])
    return options


def krs_data(nim, semester):
    """KRS untuk satu semester. Mengembalikan dict: ok, message, from_cache, rows, total_sks."""
    cache_key = f"krs_{nim}_{semester}"
    client = None
    try:
        client = SipakamaseClient()
        raw = client.get_krs(nim, semester)
        if "krs" not in raw:
            raise SipakamaseError("Data KRS tidak ditemukan.")
        rows = [
            {"nama": item["nama_mata_kuliah"], "sks": item["jumlah_sks"]}
            for item in raw["krs"]
            if "nama_mata_kuliah" in item and "jumlah_sks" in item
        ]
        cache.set(cache_key, rows, KRS_CACHE_SECONDS)
        return _krs_result(True, "Data berhasil diambil", False, rows)
    except SipakamaseError as exc:
        cached = cache.get(cache_key)
        if cached is not None:
            return _krs_result(True, CACHE_NOTE, True, cached)
        return _krs_result(False, f"Data KRS tidak ditemukan atau gagal diambil: {exc}", False, [])
    finally:
        if client is not None:
            client.close()


def _krs_result(ok, message, from_cache, rows):
    return {
        "ok": ok,
        "message": message,
        "from_cache": from_cache,
        "rows": rows,
        "total_sks": sum(int(r["sks"] or 0) for r in rows),
    }
