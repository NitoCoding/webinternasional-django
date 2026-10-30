import csv

from django.conf import settings

CSV_PATH = settings.BASE_DIR / "data" / "study_programs.csv"
CSV_COLUMNS = ["prodiId", "prodiKode", "prodiNama", "prodiNamaAsing", "prodiJenjang", "prodiKodeDikti", "prodiFakId"]


def _read_rows():
    if not CSV_PATH.exists():
        return []
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.reader(fh, delimiter=";"))


def valid_study_program_names():
    return {row[2] for row in _read_rows() if len(row) > 2}


def search_s1_programs(query):
    query = query.lower()
    results = []
    for row in _read_rows():
        row = row + [""] * (len(CSV_COLUMNS) - len(row))
        name = row[2]
        if query in name.lower() and "s1" in name.lower():
            results.append(dict(zip(CSV_COLUMNS, row)))
    return results
