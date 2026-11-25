"""Membaca data shuttle dan menyimpan laporan komunitas.

- Data resmi (halte, jadwal, peta) dibaca dari file  data/shuttle.json.
  Sumbernya ModaHub PetakPeta; ubah file ini lalu push untuk memperbarui.
- Laporan komunitas harus bisa ditulis saat web berjalan. Di Vercel file
  tidak bisa ditulis, jadi laporan disimpan di Redis (Upstash). Di laptop,
  tanpa Redis, laporan disimpan di file  data/laporan.json.
"""

import json
import os
import urllib.request

FOLDER_PROYEK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILE_DATA = os.path.join(FOLDER_PROYEK, "data", "shuttle.json")
FILE_LAPORAN = os.path.join(FOLDER_PROYEK, "data", "laporan.json")

# Awalan kunci dibuat beda dari repo tubes2, supaya aman kalau
# kedua project Vercel memakai database Redis yang sama.
KUNCI_LAPORAN = "sustain:laporan"      # list, tiap elemen = JSON satu laporan
KUNCI_DUKUNGAN = "sustain:dukungan"    # hash id -> jumlah "saya juga mengalami"
KUNCI_DIHAPUS = "sustain:dihapus"      # set id laporan yang dihapus admin


# ---------- Redis lewat REST API (tanpa library tambahan) ----------

def _konfigurasi_redis():
    """Mengembalikan (url, token) Redis REST kalau tersedia, atau None.

    Integrasi Upstash di Vercel bisa memberi nama variabel yang berbeda-beda
    (kadang dengan awalan nama database), jadi semua kemungkinan dicek.
    """
    env = os.environ
    for nama_url, nama_token in [("KV_REST_API_URL", "KV_REST_API_TOKEN"),
                                 ("UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN")]:
        if env.get(nama_url) and env.get(nama_token):
            return env[nama_url].rstrip("/"), env[nama_token]
    # Variabel dengan awalan, contoh  SHUTTLE_SUSTAIN_KV_REST_API_URL
    for nama, nilai in env.items():
        for akhiran_url, akhiran_token in [("KV_REST_API_URL", "KV_REST_API_TOKEN"),
                                           ("REDIS_REST_URL", "REDIS_REST_TOKEN")]:
            if nama.endswith(akhiran_url) and nilai:
                token = env.get(nama[: -len(akhiran_url)] + akhiran_token)
                if token:
                    return nilai.rstrip("/"), token
    # Hanya ada alamat Redis biasa (rediss://default:TOKEN@HOST:6379) dari Upstash:
    # REST API Upstash ada di https://HOST dengan token yang sama.
    for nama, nilai in env.items():
        if (nama == "REDIS_URL" or nama.endswith("_REDIS_URL") or nama == "KV_URL" or nama.endswith("_KV_URL")) \
                and nilai.startswith("rediss://") and "upstash.io" in nilai:
            from urllib.parse import urlparse
            u = urlparse(nilai)
            if u.password and u.hostname:
                return f"https://{u.hostname}", u.password
    return None


def _url_redis_biasa():
    """Alamat Redis biasa (redis:// atau rediss://), misalnya dari integrasi Redis di Vercel."""
    for nama in ("REDIS_URL", "KV_URL"):
        nilai = os.environ.get(nama, "")
        if nilai.startswith(("redis://", "rediss://")):
            return nilai
    return None


_klien = None


def _klien_redis():
    global _klien
    if _klien is None:
        import redis  # library tambahan, hanya dipakai kalau ada REDIS_URL
        _klien = redis.from_url(_url_redis_biasa(), decode_responses=True, socket_timeout=10)
    return _klien


def _ada_redis():
    return bool(_konfigurasi_redis() or _url_redis_biasa())


def _perintah_redis(perintah):
    """Mengirim satu perintah Redis, contoh ["GET", "kunci"]."""
    if not _konfigurasi_redis():
        hasil = _klien_redis().execute_command(*perintah)
        if isinstance(hasil, dict):  # HGETALL -> samakan dengan format REST (list datar)
            datar = []
            for k, v in hasil.items():
                datar += [k, v]
            return datar
        if isinstance(hasil, set):
            return list(hasil)
        return hasil
    url, token = _konfigurasi_redis()
    permintaan = urllib.request.Request(
        url,
        data=json.dumps(perintah).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(permintaan, timeout=10) as respons:
        return json.loads(respons.read().decode("utf-8")).get("result")


# ---------- Data resmi ----------

def muat_data():
    """Membaca data shuttle (halte, jadwal, jalur peta)."""
    with open(FILE_DATA, encoding="utf-8") as f:
        return json.load(f)


# ---------- Laporan komunitas ----------

def jenis_penyimpanan():
    if _ada_redis():
        return "redis"
    return "file"


def laporan_bisa_disimpan():
    """True kalau laporan bisa disimpan permanen."""
    if _ada_redis():
        return True
    # Di Vercel tanpa Redis, sistem file hanya bisa dibaca.
    return not os.environ.get("VERCEL")


def _baca_file_laporan():
    if os.path.exists(FILE_LAPORAN):
        with open(FILE_LAPORAN, encoding="utf-8") as f:
            return json.load(f)
    return {"laporan": [], "dukungan": {}, "dihapus": []}


def _tulis_file_laporan(isi):
    with open(FILE_LAPORAN, "w", encoding="utf-8") as f:
        json.dump(isi, f, indent=2, ensure_ascii=False)


def muat_laporan():
    """List semua laporan (yang belum dihapus), lengkap dengan jumlah dukungan."""
    if _ada_redis():
        try:
            mentah = _perintah_redis(["LRANGE", KUNCI_LAPORAN, 0, -1]) or []
            dukungan_list = _perintah_redis(["HGETALL", KUNCI_DUKUNGAN]) or []
            dihapus = set(_perintah_redis(["SMEMBERS", KUNCI_DIHAPUS]) or [])
        except Exception:
            return []
        laporan = [json.loads(x) for x in mentah]
        # HGETALL lewat REST mengembalikan [kunci1, nilai1, kunci2, nilai2, ...]
        dukungan = {}
        for i in range(0, len(dukungan_list) - 1, 2):
            dukungan[dukungan_list[i]] = int(dukungan_list[i + 1])
    else:
        isi = _baca_file_laporan()
        laporan = isi["laporan"]
        dukungan = isi["dukungan"]
        dihapus = set(isi["dihapus"])

    hasil = []
    for lap in laporan:
        if lap["id"] in dihapus:
            continue
        lap["dukungan"] = dukungan.get(lap["id"], 0)
        hasil.append(lap)
    return hasil


def simpan_laporan(laporan):
    if not laporan_bisa_disimpan():
        raise PermissionError("Penyimpanan laporan belum aktif. Hubungkan Upstash Redis di tab Storage Vercel.")
    if _ada_redis():
        _perintah_redis(["RPUSH", KUNCI_LAPORAN, json.dumps(laporan, ensure_ascii=False)])
        return
    isi = _baca_file_laporan()
    isi["laporan"].append(laporan)
    _tulis_file_laporan(isi)


def tambah_dukungan(id_laporan):
    if not laporan_bisa_disimpan():
        raise PermissionError("Penyimpanan laporan belum aktif.")
    if _ada_redis():
        _perintah_redis(["HINCRBY", KUNCI_DUKUNGAN, id_laporan, 1])
        return
    isi = _baca_file_laporan()
    isi["dukungan"][id_laporan] = isi["dukungan"].get(id_laporan, 0) + 1
    _tulis_file_laporan(isi)


def hapus_laporan(id_laporan):
    if _ada_redis():
        _perintah_redis(["SADD", KUNCI_DIHAPUS, id_laporan])
        return
    isi = _baca_file_laporan()
    if id_laporan not in isi["dihapus"]:
        isi["dihapus"].append(id_laporan)
    _tulis_file_laporan(isi)
