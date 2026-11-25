"""Model rute dan jadwal shuttle.

Abstraksi rute:
- Halte disimpan berurutan dalam list. Bus berangkat dari halte pertama,
  berhenti di setiap halte sesuai urutan, lalu kembali ke halte pertama (rute melingkar).
- waktu_tempuh[i] = menit perjalanan dari halte i ke halte berikutnya
  (yang terakhir = dari halte terakhir kembali ke halte pertama).
- waktu_henti = menit bus berhenti di setiap halte.

Indeks "perhentian" 0..n-1 adalah halte, dan indeks n berarti
"kembali ke halte pertama" (akhir satu putaran).
"""

import math

from core.waktu import ke_menit


def jumlah_halte(data):
    return len(data["halte"])


def nama_halte(data, indeks):
    """Nama halte untuk indeks perhentian (indeks n = halte pertama lagi)."""
    n = jumlah_halte(data)
    return data["halte"][indeks % n]["nama"]


def daftar_nama_halte(data):
    nama = []
    for halte in data["halte"]:
        nama.append(halte["nama"])
    return nama


def selisih_waktu_halte(data):
    """List menit dari keberangkatan di halte pertama sampai tiba di tiap perhentian.

    Panjang list = n + 1. Elemen terakhir = lama satu putaran penuh.
    """
    hasil = [0]
    for i in range(jumlah_halte(data)):
        hasil.append(hasil[-1] + data["waktu_tempuh"][i] + data["waktu_henti"])
    return hasil


def durasi_putaran(data):
    """Menit yang dibutuhkan satu bus untuk satu putaran penuh."""
    return selisih_waktu_halte(data)[-1]


def interval_efektif(data, interval, jumlah_bus):
    """Interval yang benar-benar bisa dicapai dengan armada yang ada.

    Satu bus baru bisa berangkat lagi setelah menyelesaikan satu putaran.
    Jadi dengan B bus dan putaran T menit, interval minimal = ceil(T / B).
    """
    minimal = math.ceil(durasi_putaran(data) / jumlah_bus)
    if interval < minimal:
        return minimal
    return interval


def buat_jadwal(data, interval=None, jumlah_bus=None):
    """Membuat daftar perjalanan (trip) dalam satu hari.

    Setiap trip berisi: nomor, bus, berangkat, dan list waktu tiba
    di setiap perhentian (panjang n + 1).
    """
    if interval is None:
        interval = data["interval_menit"]
    if jumlah_bus is None:
        jumlah_bus = data["armada"]["jumlah_bus"]

    jeda = interval_efektif(data, interval, jumlah_bus)
    selisih = selisih_waktu_halte(data)
    mulai = ke_menit(data["jam_operasi"]["mulai"])
    selesai = ke_menit(data["jam_operasi"]["selesai"])

    jadwal = []
    berangkat = mulai
    nomor = 0
    while berangkat <= selesai:
        tiba = []
        for s in selisih:
            tiba.append(berangkat + s)
        jadwal.append({
            "nomor": nomor + 1,
            "bus": (nomor % jumlah_bus) + 1,
            "berangkat": berangkat,
            "tiba": tiba,
        })
        nomor += 1
        berangkat += jeda
    return jadwal


def validasi_data(data):
    """Memeriksa data. Mengembalikan list pesan kesalahan (kosong = data benar)."""
    salah = []
    try:
        mulai = ke_menit(data["jam_operasi"]["mulai"])
        selesai = ke_menit(data["jam_operasi"]["selesai"])
        if selesai < mulai:
            salah.append("Jam selesai harus setelah jam mulai.")
    except (KeyError, ValueError) as e:
        salah.append(f"Jam operasi tidak valid: {e}")

    n = len(data.get("halte", []))
    if n < 2:
        salah.append("Minimal harus ada 2 halte.")
    for i, halte in enumerate(data.get("halte", [])):
        if not str(halte.get("nama", "")).strip():
            salah.append(f"Halte ke-{i + 1} belum punya nama.")

    tempuh = data.get("waktu_tempuh", [])
    if len(tempuh) != n:
        salah.append(f"Jumlah waktu tempuh ({len(tempuh)}) harus sama dengan jumlah halte ({n}).")
    for t in tempuh:
        # Boleh 0: dua halte yang sangat dekat bisa ditempuh kurang dari satu menit.
        if not isinstance(t, (int, float)) or t < 0:
            salah.append("Setiap waktu tempuh harus angka 0 atau lebih.")
            break
    if sum(tempuh) + data.get("waktu_henti", 0) * n <= 0:
        salah.append("Lama satu putaran harus lebih dari 0 menit.")

    if data.get("waktu_henti", -1) < 0:
        salah.append("Waktu henti tidak boleh negatif.")
    if data.get("interval_menit", 0) <= 0:
        salah.append("Interval keberangkatan harus lebih dari 0 menit.")
    if data.get("armada", {}).get("jumlah_bus", 0) < 1:
        salah.append("Jumlah bus minimal 1.")
    return salah


def _proyeksi(titik, p1, p2):
    """Titik terdekat dari `titik` pada ruas garis p1-p2, dan kuadrat jaraknya."""
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    panjang2 = dx * dx + dy * dy
    t = 0.0
    if panjang2 > 0:
        t = ((titik[0] - p1[0]) * dx + (titik[1] - p1[1]) * dy) / panjang2
        t = max(0.0, min(1.0, t))
    proyeksi = [p1[0] + t * dx, p1[1] + t * dy]
    jarak2 = (proyeksi[0] - titik[0]) ** 2 + (proyeksi[1] - titik[1]) ** 2
    return proyeksi, jarak2, t


def jalur_dengan_halte(data):
    """Garis peta yang sudah disisipi titik halte, plus indeks tiap halte di garis itu.

    Tiap halte ditempelkan ke ruas garis terdekat, dengan syarat urutannya
    mengikuti urutan rute (halte ke-i tidak boleh berada sebelum halte ke-(i-1)).
    Syarat ini penting karena rute melingkar bisa lewat dekat halte yang sama dua kali.
    Pilihan ruas dicari dengan pemrograman dinamis supaya total jaraknya paling kecil.
    """
    jalur = data.get("jalur_peta", [])
    halte = [[h["lat"], h["lon"]] for h in data["halte"]]
    n_ruas = len(jalur) - 1
    if n_ruas < 1:
        return jalur, [0] * len(halte)

    # biaya[i][r] = jarak halte i ke ruas r (pakai nilai t untuk urutan dalam ruas yang sama)
    info = [[_proyeksi(h, jalur[r], jalur[r + 1]) for r in range(n_ruas)] for h in halte]
    tak_hingga = float("inf")
    total = [[tak_hingga] * n_ruas for _ in halte]
    asal = [[0] * n_ruas for _ in halte]
    for r in range(n_ruas):
        total[0][r] = info[0][r][1] if r == 0 else tak_hingga  # halte pertama = awal rute
    for i in range(1, len(halte)):
        terbaik, ruas_terbaik = tak_hingga, 0
        for r in range(n_ruas):
            if total[i - 1][r] < terbaik:
                terbaik, ruas_terbaik = total[i - 1][r], r
            total[i][r] = terbaik + info[i][r][1]
            asal[i][r] = ruas_terbaik
    ruas = [0] * len(halte)
    ruas[-1] = min(range(n_ruas), key=lambda r: total[-1][r])
    for i in range(len(halte) - 1, 0, -1):
        ruas[i - 1] = asal[i][ruas[i]]

    # Sisipkan titik proyeksi halte ke dalam garis.
    hasil = []
    indeks = [0] * len(halte)
    for r in range(n_ruas):
        hasil.append(jalur[r])
        sisip = sorted((info[i][r][2], i) for i in range(len(halte)) if ruas[i] == r)
        for _, i in sisip:
            hasil.append(info[i][r][0])
            indeks[i] = len(hasil) - 1
    hasil.append(jalur[-1])
    return hasil, indeks


def potongan_jalur(data, asal, tujuan):
    """Bagian garis peta dari halte asal sampai halte tujuan (mengikuti arah rute)."""
    jalur, idx = jalur_dengan_halte(data)
    if not jalur:
        return []
    a, b = idx[asal], idx[tujuan]
    if b >= a:
        return jalur[a:b + 1]
    # Tujuan ada di belakang asal: lewati akhir rute (kembali ke halte pertama) lalu lanjut.
    return jalur[a:] + jalur[1:b + 1]
