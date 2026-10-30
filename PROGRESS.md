# PROGRESS – Migrasi SIPAKAMASE / International Exposure (Laravel → Django)

Terakhir diperbarui: 30 Oktober 2026

Sumber referensi (read-only): `D:\Proyek\Unhas\Internasional` (Laravel).
Target: `D:\Proyek\Unhas\international-django` (Django + GeoDjango tidak dipakai di sini, Django biasa).

## Ringkasan status

| Area | Status | Catatan |
|---|---|---|
| Dashboard admin, staff, student | Selesai (kode), belum diuji di browser | Lihat bagian Dashboard |
| Users (admin/staff): daftar, tab, filter, detail, CSV, Add Student, Add Staff, English Score | Selesai (kode), belum diuji di browser | Add Student, Upload CSV, Add Staff, English Score sudah modal |
| Konfirmasi Accept/Reject dan hapus | Selesai, memakai halaman konfirmasi | Sesuai keputusan pengguna: dibiarkan dulu |
| Student: Transkrip, Study Plan (KRS) | Selesai (kode), data via AJAX | Data dari API SIPAKAMASE |
| Student: International Exposure (daftar, detail, enroll) | Selesai (kode), tampilan tabel | Enroll dengan modal |
| Logbook student dan admin (entry, sertifikat) | Selesai (kode), belum diuji di browser | Sertifikat disimpan di `private_media/` |
| Modal UI | Konsisten (checkbox DaisyUI, `max-w-sm p-5`) | Tidak ada lagi `<dialog>` |
| Test otomatis | Ditulis, **belum dijalankan** | Pengguna melarang menjalankan test. Hanya `manage.py check` yang dijalankan |

## Dashboard per role (terbaru)

- **Admin** (`templates/dashboard/home.html`): 4 grafik (per angkatan, per program studi bertumpuk, peserta IE per tahun, IE per jenis). Filter All / Active / Inactive. Logika di `apps/dashboard/dashboard_stats.py`.
- **Staff**: data yang sama, dibatasi ke study program staff. 3 grafik (tanpa grafik garis IE). Akun tanpa profil staff menampilkan pesan.
- **Student** (`templates/dashboard/student_home.html`): kartu informasi, IPK, SKS lulus (target 144), masa studi. Data dimuat lewat AJAX dari `student/dashboard/data/`, dengan cache transkrip 600 detik.
- Pengaturan masa studi ada di `config/settings.py` (`ACADEMIC_MAX_STUDY_PERIOD_*`, `ACADEMIC_POLICY_CHANGE_YEAR`), nilainya sama dengan `config/academic.php` Laravel.

## Users (admin/staff)

- Daftar dengan tab All / Active / Staff / Waiting, pencarian, filter study program, tahun, dan status studi.
- Tabel Staff dan tabel Student dibedakan (kolom dan aksi berbeda).
- Detail student dibuka sebagai modal (dimuat lewat fetch), berisi program IE dan English Score.
- Add Student (NIM dari SIPAKAMASE), Upload CSV, Add Staff, dan English Score: semuanya modal. Error ditampilkan lewat flash modal.
- Accept, Reject: halaman konfirmasi (GET tampilkan, POST ubah data). Hanya admin dan staff dengan permission yang sesuai.
- Deactivate / Activate: langsung tanpa konfirmasi (bisa dibalik). Login diblokir lewat `User.is_active`.
- Staff hanya bisa mengelola mahasiswa di study program miliknya. Staff tidak bisa membuat atau memberi group staff.
- Print daftar users (versi cetak).

## Student

- **Transkrip** dan **Study Plan (KRS)**: halaman kosong lalu data diambil lewat AJAX dari endpoint JSON (`student/transcript/data/`, `student/study-plan/data/`). Tidak ada tabel baru.
- **International Exposure**: daftar program dalam tabel (tanpa thumbnail), banner gerbang di atas daftar, halaman detail, dan modal enroll. Aturan enroll dicek di server (`apps/international/enrollment.py`):
  - akun harus terverifikasi, aktif, dan status accepted,
  - tidak boleh mendaftar dua kali,
  - tidak boleh mendaftar program baru jika program sebelumnya belum selesai,
  - batas peserta.
  - Enrollment rejected dihidupkan lagi menjadi pending, tidak dibuat baris baru.
- **Logbook**: daftar entry per program, tambah entry lewat modal, ubah dan hapus entry sendiri, upload sertifikat PDF (maks 5 MB). Entry dan sertifikat hanya bisa dibuka jika enrollment-nya approved. Gambar entry maks 2 MB (JPG, PNG, GIF).

## Admin: IE program

- Halaman detail program menampilkan peserta yang diterima dengan tombol **View** sertifikat dan **Logbook** (read-only). Keduanya memakai view yang memeriksa hak akses. Link `/media/` sudah tidak dipakai lagi.

## Keputusan yang sudah diambil

- TLS ke SIPAKAMASE dimatikan (`SIPAKAMASE_VERIFY_TLS=False`), atas persetujuan pengguna.
- Transkrip dan KRS hanya membaca API, tanpa model baru.
- Filter "Not Started" disamakan dengan badge: enrollment pending tidak masuk Not Started.
- Angkatan = `"20" + NIM[4:6]` (sama dengan Laravel).
- Batas sertifikat 5 MB dan gambar logbook 2 MB (sama dengan Laravel).
- Deskripsi logbook maks 50 karakter (sama dengan Laravel). Perlu dikonfirmasi ulang oleh pengguna.
- Logout redirect ke `website:home`. Halaman 403 berdiri sendiri, tanpa sidebar.

## Penyimpangan dari Laravel (dicatat)

1. Status filter **inactive** di dashboard: Laravel memberi label "Graduated", padahal datanya adalah `isActive = false`. Django menampilkan "Inactive".
2. Dashboard student Django tidak menampilkan daftar IE, karena Laravel memang tidak punya.
3. Mengubah atau menghapus logbook milik orang lain memberi 404 (Laravel: 403).
4. Batas tahun semester KRS: `min(tahun masuk + 7, tahun berjalan)`. Laravel memakai tahun tetap 2024.
5. `Student.status` tidak diubah saat deactivate (Laravel menyetelnya ke `null`).

## Masalah yang diketahui / terbuka

- **Test belum dijalankan** sejak perubahan modal dan dashboard. Run `apps.dashboard` sebelumnya terputus (orphan), dan database test lama mungkin masih ada.
- **Verifikasi browser belum dilakukan** untuk: modal users, tab Staff, dashboard tiga role, transkrip, KRS, IE, logbook.
- **NIM uji `H07121221081`** tidak ditemukan di API SIPAKAMASE. Pengecekan respons mentah belum dilakukan.
- **Klik nama student**: laporan pengguna bahwa modal detail tidak terbuka. Penyebab sudah diperbaiki (event delegation), belum dikonfirmasi di browser.
- Di `templates/` masih ada file backup `*.bak-before-*` dari sesi sebelumnya. Perlu dibersihkan setelah semuanya diverifikasi.
- Repo tidak memakai git di folder ini, jadi belum ada riwayat perubahan. Disarankan `git init` sebelum tahap berikutnya.
