"""Klien API SIPAKAMASE (data mahasiswa Universitas Hasanuddin).

Pengganti SipakamaseService di Laravel. Kredensial dibaca dari settings
(SIPAKAMASE_URL, SIPAKAMASE_USERNAME, SIPAKAMASE_PASSWORD) yang berasal dari .env.
Verifikasi TLS tidak dimatikan (Laravel memakai verify=false; tidak ditiru).
"""

import httpx
from django.conf import settings


class SipakamaseError(Exception):
    """Gagal login, konfigurasi kosong, atau API tidak bisa dihubungi."""


class SipakamaseClient:
    def __init__(self, transport=None):
        self.base_url = (settings.SIPAKAMASE_URL or "").rstrip("/")
        if not self.base_url:
            raise SipakamaseError("SIPAKAMASE_URL belum diatur di .env.")
        self._http = httpx.Client(
            timeout=settings.SIPAKAMASE_TIMEOUT,
            transport=transport,
            verify=settings.SIPAKAMASE_VERIFY_TLS,
        )
        self._token = None

    def close(self):
        self._http.close()

    def login(self):
        """Ambil access token. Dipanggil sekali per batch."""
        try:
            resp = self._http.post(
                f"{self.base_url}/login",
                json={"username": settings.SIPAKAMASE_USERNAME, "password": settings.SIPAKAMASE_PASSWORD},
            )
        except httpx.HTTPError as exc:
            raise SipakamaseError(f"Tidak dapat terhubung ke server SIPAKAMASE: {exc}") from exc
        if resp.status_code != 200:
            raise SipakamaseError(f"Login SIPAKAMASE gagal (HTTP {resp.status_code}).")
        token = resp.json().get("access_token")
        if not token:
            raise SipakamaseError("Login SIPAKAMASE tidak mengembalikan access token.")
        self._token = token

    def get_student(self, nim):
        """Data mahasiswa dari NIM, atau None jika tidak ditemukan."""
        data = self.request_json("/get_mahasiswa_by_nim", {"nim": nim})
        mahasiswas = data.get("mahasiswas") or []
        return mahasiswas[0] if mahasiswas else None

    def get_transcript(self, nim):
        """Respons mentah /get_transkrip_mahasiswa."""
        return self.request_json("/get_transkrip_mahasiswa", {"nim": nim})

    def get_krs(self, nim, semester):
        """Respons mentah /get_krs_mahasiswa untuk semester tertentu (format tahun + 1|2, mis. 20241)."""
        return self.request_json("/get_krs_mahasiswa", {"nim": nim, "semester": semester})

    def request_json(self, path, body):
        """GET dengan body JSON dan token Bearer. Token diperbarui sekali jika server menjawab 401."""
        if self._token is None:
            self.login()
        for attempt in (1, 2):
            try:
                resp = self._http.request(
                    "GET",
                    f"{self.base_url}{path}",
                    headers={"Authorization": f"Bearer {self._token}"},
                    json=body,
                )
            except httpx.HTTPError as exc:
                raise SipakamaseError(f"Tidak dapat terhubung ke server SIPAKAMASE: {exc}") from exc
            if resp.status_code == 401 and attempt == 1:
                self.login()
                continue
            if resp.status_code != 200:
                raise SipakamaseError(f"Permintaan ke {path} gagal (HTTP {resp.status_code}).")
            return resp.json()
        raise SipakamaseError(f"Permintaan ke {path} gagal.")
