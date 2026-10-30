"""View per fitur dashboard.

Setiap fitur memiliki modul view sendiri di package ini agar modular:
- base              : CrudSpec, mixin akses, dan base class CBV bersama
- home              : dashboard per role (admin / staff / student)
- site_settings     : pengaturan situs
- news / events / agendas / study_programs / faculties / ie_programs /
  programs / partnerships / outbound_lecturers / students : CRUD masing-masing
- users             : kelola akun user (list, tab, aksi, modal)
- student_academic  : transkrip, KRS, ringkasan dashboard student
- student_programs  : daftar/detail/enroll program IE sisi student
- student_calendar  : kalender akademik student
- student_logbook   : logbook dan sertifikat (student dan admin)

`urls.py` mengimpor langsung dari modul fitur.
"""