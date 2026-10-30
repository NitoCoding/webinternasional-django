# ONPLAN – Rencana Lanjutan Migrasi Django

Terakhir diperbarui: 30 Oktober 2026

Rencana ini disusun dari `PROGRESS.md`. Urutan dibuat bertahap, dan setiap tahap diverifikasi bersama pengguna sebelum lanjut.

## Tahap 1 – Verifikasi tahap yang sudah ada (prioritas tertinggi)

Dikerjakan sebelum fitur baru. Tanpa verifikasi, status di `PROGRESS.md` belum bisa dipercaya.

1. Jalankan `manage.py check` dan `manage.py makemigrations --check` (hanya cek, tanpa test).
2. Verifikasi di browser per role:
   - Admin: daftar users (semua tab), klik nama student, Add Student, Upload CSV, Add Staff, English Score, dashboard (tiga filter status).
   - Staff: dashboard, daftar users, batas study program.
   - Student: dashboard (AJAX), transkrip, KRS, IE (daftar, detail, enroll), logbook (tambah, ubah, hapus, sertifikat).
   - Admin di halaman program: tombol View sertifikat dan Logbook.
3. Catat setiap temuan di `PROGRESS.md`.
4. Ketika pengguna mengizinkan, jalankan test `apps.dashboard`:
   - Hapus database test lama yang tertinggal, atau gunakan `--noinput`.
   - Test baru yang belum pernah jalan: `test_logbook.py`, `test_student_programs.py`, `test_student_menus.py`, `test_user_features.py`.

## Tahap 2 – Hal yang sudah disepakati tetapi belum dibuat

1. **Halaman konfirmasi Accept, Reject, dan hapus** (`confirm_action.html`, `confirm_delete.html`). Pengguna meminta ditunda. Saat diminta, ubah ke modal dengan pola yang sama seperti Add Student.
2. **Aturan PROTECT untuk hapus mahasiswa**, lalu tombol Delete di daftar users. Saat ini sengaja disembunyikan.
3. **Edit logbook** masih memakai halaman form (`form_page.html`). Jika pengguna minta, ubah ke modal seperti Add Entry.
4. **Pengecekan NIM `H07121221081`**: cek respons mentah API dan perbaiki data uji jika perlu.

## Tahap 3 – Fitur student yang belum diport

Urutan prioritas dari analisis sebelumnya:

1. **Kalender Akademik** (`CalenderController` Laravel belum dibaca). Sedang.
2. **Dashboard IE**: periksa apakah angka dashboard admin sudah sama dengan Laravel (jumlah program per jenis, peserta per tahun).
3. **Tinjau ulang aturan IE student** terhadap `ProgramController` Laravel, terutama pesan gerbang dan batas peserta.

## Tahap 4 – Pembersihan dan kualitas

1. Hapus file backup `templates/**/*.bak-before-*` setelah pengguna mengonfirmasi tampilan sudah benar.
2. `git init` di `international-django`, lalu buat commit awal setelah verifikasi Tahap 1. Commit hanya dibuat jika pengguna meminta.
3. Pastikan `.gitignore` mencakup `media/`, `private_media/`, `.venv/`, dan file `.env`.
4. Periksa konsistensi label UI: sebagian besar label masih Inggris, dokumentasi berbahasa Indonesia.
5. Tinjau ulang modul yang masih berisi logika campur (contoh: `user_views.py` dan `crud.py`), jika ukurannya terus bertambah.

## Tahap 5 – Deployment

Mengikuti skill `django-production-deployment`: nginx, gunicorn, `DEBUG=False`, static dan media, serta `ALLOWED_HOSTS`. Dilakukan setelah Tahap 1 sampai 3 selesai dan diverifikasi.

## Keputusan yang perlu diambil pengguna

- Label filter status "Inactive" di dashboard (Laravel menulis "Graduated"). Dipakai "Inactive" sampai ada keputusan lain.
- Batas deskripsi logbook 50 karakter (sama dengan Laravel). Mau dinaikkan?
- Bundle CA untuk TLS SIPAKAMASE: sementara TLS dimatikan. Perlu dibuat ulang jika ingin verifikasi kembali.
