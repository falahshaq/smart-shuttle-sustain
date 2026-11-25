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
