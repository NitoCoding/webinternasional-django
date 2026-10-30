# International Class – Hasanuddin University (Django)

Aplikasi web International Class Universitas Hasanuddin: dashboard admin, staff, dan student, serta website publik (berita, event, program studi, International Exposure, dan Double/Joint Degree). Proyek ini adalah hasil migrasi dari aplikasi Laravel.

## Kebutuhan

- Python 3.12
- [uv](https://docs.astral.sh/uv/) untuk mengelola dependensi dan virtualenv
- MariaDB atau MySQL, dengan database yang sudah dibuat
- Akses jaringan ke server SIPAKAMASE (untuk data mahasiswa)

## Setup pertama kali

```bash
# 1. Pasang dependensi (membuat .venv otomatis)
uv sync

# 2. Buat file .env di folder proyek (lihat bagian "Konfigurasi" di bawah)

# 3. Jalankan migrasi
uv run python manage.py migrate

# 4. Buat akun admin
uv run python manage.py createsuperuser
```

## Menjalankan server

```bash
# Mode pengembangan (DEBUG=True di .env)
uv run python manage.py runserver

# Dengan tool tambahan dari django-extensions (hanya saat DEBUG=True)
uv run python manage.py runserver_plus
```

Buka `http://127.0.0.1:8000/`.

### Mode produksi (DEBUG=False)

Static file dilayani oleh WhiteNoise dari folder `staticfiles/`. Setiap kali file di `static/` berubah, jalankan:

```bash
uv run python manage.py collectstatic --noinput
```

## Konfigurasi (.env)

File `.env` tidak masuk repository. Isi variabel berikut:

| Variabel | Keterangan |
|---|---|
| `DJANGO_SECRET_KEY` | Kunci rahasia Django (wajib, jangan dipakai bersama) |
| `DJANGO_DEBUG` | `True` untuk pengembangan, `False` untuk produksi |
| `DJANGO_ALLOWED_HOSTS` | Daftar host, dipisah koma |
| `DB_DATABASE` | Nama database |
| `DB_USERNAME` / `DB_PASSWORD` | Akun database |
| `DB_HOST` / `DB_PORT` | Default `127.0.0.1` dan `3306` |
| `SIPAKAMASE_URL`, `SIPAKAMASE_USERNAME`, `SIPAKAMASE_PASSWORD` | Akses API SIPAKAMASE |
| `SIPAKAMASE_TIMEOUT` | Batas waktu request ke SIPAKAMASE (detik) |
| `SIPAKAMASE_VERIFY_TLS` | Lihat catatan TLS di bawah |
| `CSV_IMPORT_DELAY_SECONDS` | Jeda antar baris saat import CSV |
| `DEFAULT_FROM_EMAIL` | Alamat pengirim email |

**Catatan TLS:** verifikasi TLS ke SIPAKAMASE dikendalikan oleh `SIPAKAMASE_VERIFY_TLS`. Periksa nilai default di `config/settings.py` dan pastikan sesuai kebutuhan server sebelum produksi.

## Database

Proyek memakai engine `django.db.backends.mysql`. Driver yang dipakai adalah **PyMySQL**, dipasang sebagai pengganti `MySQLdb` lewat `config/__init__.py`. Tidak perlu memasang `mysqlclient`.

## Perintah berguna

```bash
uv run python manage.py check                 # cek konfigurasi
uv run python manage.py makemigrations --check
uv run python manage.py shell_plus           # shell dengan model otomatis (django-extensions)
uv run python manage.py show_urls            # daftar semua URL (django-extensions)
```

## Test

```bash
uv run python manage.py test apps.dashboard --noinput
```

`--noinput` menjalankan test tanpa konfirmasi interaktif, termasuk saat database test lama harus dihapus.

## Struktur singkat

- `config/` : settings, URL utama, dan shim PyMySQL
- `apps/accounts` : model User dan autentikasi
- `apps/academic` : Student, Staff, StudyProgram, dan klien SIPAKAMASE
- `apps/international` : Program (IE), enrollment, dan logbook
- `apps/content` : News, Event, dan Agenda
- `apps/website` : halaman publik
- `apps/dashboard` : dashboard admin, staff, dan student
- `templates/` : template Django (publik di `website/`, dashboard di `dashboard/`)
- `static/` : aset static sumber; hasil `collectstatic` ada di `staticfiles/`
