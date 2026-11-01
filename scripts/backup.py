"""Backup database MySQL + media + private_media ke satu arsip ZIP.

Pemakaian:
    python scripts/backup.py                # backup penuh (retensi default 7 hari)
    python scripts/backup.py --keep 30      # simpan 30 hari terakhir
    python scripts/backup.py --out /srv/backups

Arsip disimpan di <OUT>/backup_YYYYMMDD_HHMMSS.zip berisi:
    db.sql          — dump MySQL (mysqldump)
    media/          — salinan MEDIA_ROOT
    private_media/  — salinan PRIVATE_MEDIA_ROOT

Penjadwalan:
    Cron  (setiap 02:30)        ->  30 2 * * *  cd /srv/international-django && uv run python scripts/backup.py
    Systemd timer (disarankan)  ->  deploy/backup.service + deploy/backup.timer (lihat file deploy/)

Tidak perlu celery beat: untuk rutin sekali jalan seperti ini, cron/systemd timer
lebih sederhana (tanpa broker Redis) dan dieksekusi oleh proses terpisah yang
mudah di-debug dari log.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _db_config():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()
    from django.conf import settings

    return settings.DATABASES["default"], settings.MEDIA_ROOT, settings.PRIVATE_MEDIA_ROOT


def _dump_mysql(db, dest):
    """Dump via mysqldump memakai --defaults-extra-file agar password tidak bocor ke ps/argv."""
    with tempfile.NamedTemporaryFile("w", suffix=".cnf", delete=False, encoding="utf-8") as f:
        f.write("[client]\n")
        f.write(f"host={db['HOST']}\n")
        f.write(f"port={db['PORT'] or 3306}\n")
        f.write(f"user={db['USER']}\n")
        f.write(f"password={db['PASSWORD']}\n")
        f.write("default-character-set=utf8mb4\n")
        defaults_file = f.name
    try:
        with open(dest, "wb") as out:
            subprocess.run(
                ["mysqldump", f"--defaults-extra-file={defaults_file}", "--single-transaction", "--routines", "--triggers", db["NAME"]],
                check=True,
                stdout=out,
            )
    finally:
        os.unlink(defaults_file)


def _copy_dir(src, dest_dir):
    if not src.exists():
        print(f"  (skip) {src} tidak ditemukan", flush=True)
        return
    shutil.copytree(src, dest_dir / src.name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(ROOT / "backups"), help="Folder tujuan arsip (default: <proyek>/backups)")
    parser.add_argument("--keep", type=int, default=7, help="Hapus arsip lebih lama dari N hari (default: 7)")
    args = parser.parse_args()

    db, media_root, private_root = _db_config()

    backup_dir = Path(args.out).expanduser().resolve()
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work = backup_dir / f"work_{stamp}"  # dir sementara, di-zip lalu dibuang
    work.mkdir()

    print(f"-> dump database {db['ENGINE']}", flush=True)
    if "mysql" in db["ENGINE"]:
        _dump_mysql(db, work / "db.sql")
    else:
        print("  Database engine selain MySQL belum didukung script ini.", file=sys.stderr)
        shutil.rmtree(work, ignore_errors=True)
        sys.exit(1)

    print(f"-> salin {media_root}", flush=True)
    _copy_dir(Path(media_root), work)
    print(f"-> salin {private_root}", flush=True)
    _copy_dir(Path(private_root), work)

    archive_path = shutil.make_archive(str(backup_dir / f"backup_{stamp}"), "zip", work)
    shutil.rmtree(work, ignore_errors=True)
    print(f"-> {archive_path} ({_human_size(Path(archive_path).stat().st_size)})", flush=True)

    _prune_old(backup_dir, args.keep)


def _prune_old(backup_dir, keep_days):
    cutoff = datetime.now() - timedelta(days=keep_days)
    removed = 0
    for f in backup_dir.glob("backup_*.zip"):
        if datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
            f.unlink()
            removed += 1
    if removed:
        print(f"-> hapus {removed} arsip lama (> {keep_days} hari)", flush=True)


def _human_size(num):
    for unit in ("B", "KB", "MB", "GB"):
        if abs(num) < 1024:
            return f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} TB"


if __name__ == "__main__":
    main()