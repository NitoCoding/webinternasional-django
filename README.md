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

### Akses dari perangkat lain (debug di 0.0.0.0:8099)

Untuk menguji dari laptop/perangkat lain lewat hostname atau IP server, jalankan server di semua interface:

```bash
uv run python manage.py runserver 0.0.0.0:8099
```

Lalu pastikan:
- Hostname/IP yang dipakai terdaftar di `DJANGO_ALLOWED_HOSTS` di `.env` (dipisah koma), contoh: `DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,sipakamase.unhas.ac.id`.
- Port 8099 terbuka di firewall server (`sudo ufw allow 8099/tcp`). Jika server ada di belakang router/cloud, port juga harus dibuka di sana.
- Set `DJANGO_DEBUG=True` dulu saat debugging agar error tampil lengkap.

### Mode produksi (DEBUG=False)

Static file dilayani oleh WhiteNoise dari folder `staticfiles/`. Setiap kali file di `static/` berubah, jalankan:

```bash
uv run python manage.py collectstatic --noinput
```

## Deployment (produksi)

### 1. Siapkan environment produksi

```bash
uv sync               # install dependensi (termasuk gunicorn)
cp .env.example env.prod      # lalu ubah nilainya sesuai server
```

`env.prod` harus **lengkap**: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, `DJANGO_ALLOWED_HOSTS`, `DB_*`, `SIPAKAMASE_*`, dan flag keamanan (`SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_HSTS_SECONDS`, `SECURE_PROXY_SSL_HEADER`). File env dipilih lewat variabel `DJANGO_ENV_FILE` (default: `.env` di root proyek).

### 2. Migrasi dan static

```bash
uv run python manage.py migrate --noinput
uv run python manage.py collectstatic --noinput
```

### 3. Jalankan dengan gunicorn (systemd)

Contoh unit ada di `deploy/gunicorn.service`. Sesuaikan `WorkingDirectory`, `User`/`Group`, path `uv`, dan `DJANGO_ENV_FILE`, lalu:

```bash
sudo cp deploy/gunicorn.service /etc/systemd/system/<nama>.service
sudo systemctl daemon-reload
sudo systemctl enable --now <nama>
sudo journalctl -u <nama> -f
```

Setelah deploy kode baru: `sudo systemctl reload <nama>` (sinyal HUP, koneksi tidak putus).

### 4. Reverse proxy nginx (HTTPS)

Contoh konfigurasi ada di `deploy/nginx.cond` — salin ke `/etc/nginx/sites-available/`, sesuaikan `server_name` dan `proxy_pass`, lalu:

```bash
sudo ln -s /etc/nginx/sites-available/<nama> /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Saat sudah lewat nginx: ubah bind gunicorn ke `127.0.0.1:8099` dan pastikan `SECURE_SSL_REDIRECT=True` (dkk.) aktif di `env.prod`.

### 5. Backup terjadwal

[`scripts/backup.py`](scripts/backup.py) meng-archive dump MySQL + `media/` + `private_media/` ke satu ZIP:

```bash
uv run python scripts/backup.py --keep 30
```

Jadwalkan via cron/systemd timer (contoh di docstring file) — untuk rutin sekali jalan seperti ini celery beat tidak diperlukan (tidak butuh broker Redis).

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
