"""Laporan komunitas: penumpang melapor kalau jadwal atau data di lapangan berbeda.

Ide utamanya:
- Penumpang mengirim laporan, misalnya "di halte GKU 1 bus datang jam 07:32".
- Pelapor memilih jadwal resmi yang ia tunggu (misalnya 07:27). Kalau tidak
  dipilih, program menebak jadwal terakhir sebelum jam bus datang. Lalu
  dihitung selisihnya (+5 menit = terlambat 5 menit).
- Selisih dari banyak laporan dirangkum dengan median per halte. Median dipakai
  (bukan rata-rata) supaya satu laporan yang ngawur tidak merusak hasil.
- Hasilnya jadi "jadwal versi komunitas": jadwal resmi + selisih median.
"""

import uuid
from datetime import timedelta

from core.data import daftar_nama_halte, jumlah_halte
from core.penumpang import jadwal_di_halte
from core.waktu import ke_jam, waktu_sekarang_wib

JENIS_LAPORAN = {
    "jadwal": "Bus datang di jam berbeda",
    "tidak_datang": "Bus tidak datang",
    "halte": "Nama/lokasi halte salah",
    "lainnya": "Info lain",
}

BATAS_HARI = 30          # laporan yang lebih tua tidak dipakai untuk perkiraan
BATAS_SESUAI = 2         # selisih <= 2 menit dianggap "sesuai jadwal"
MAKS_ISI = 300
MAKS_NAMA = 40


def jadwal_terdekat(data, indeks_halte, menit):
    """Waktu jadwal resmi di halte yang paling dekat dengan `menit` (linear search)."""
    terdekat = None
    for kedatangan in jadwal_di_halte(data, indeks_halte):
        if terdekat is None or abs(kedatangan["waktu"] - menit) < abs(terdekat - menit):
            terdekat = kedatangan["waktu"]
    return terdekat


def jadwal_sebelum(data, indeks_halte, menit):
    """Jadwal resmi terakhir yang <= `menit` (bus lebih sering telat daripada kecepetan).

    Kalau `menit` lebih awal dari jadwal pertama, pakai jadwal pertama.
    """
    pilihan = None
    for kedatangan in jadwal_di_halte(data, indeks_halte):
        if kedatangan["waktu"] <= menit:
            pilihan = kedatangan["waktu"]
        else:
            if pilihan is None:
                pilihan = kedatangan["waktu"]
            break
    return pilihan


def buat_laporan(data, jenis, indeks_halte, jam_menit, isi, nama, jam_jadwal=None):
    """Memeriksa isian lalu menyusun satu laporan (dict).

    `jam_jadwal` = jadwal resmi yang ditunggu pelapor (dipilih di form). Kalau kosong,
    program menebak: jadwal terakhir sebelum jam bus datang.

    Mengembalikan (laporan, daftar_kesalahan). Kalau ada kesalahan, laporan = None.
    """
    salah = []
    if jenis not in JENIS_LAPORAN:
        salah.append("Pilih jenis laporan.")
    if indeks_halte is not None and not (0 <= indeks_halte < jumlah_halte(data)):
        indeks_halte = None
    if jenis in ("jadwal", "tidak_datang") and indeks_halte is None:
        salah.append("Pilih halte tempat kamu menunggu.")
    if jenis == "jadwal" and jam_menit is None:
        salah.append("Isi jam bus benar-benar datang.")
    if jenis == "tidak_datang" and jam_menit is None and jam_jadwal is None:
        salah.append("Pilih jadwal bus yang kamu tunggu.")
    if jam_jadwal is not None and indeks_halte is not None:
        resmi = [k["waktu"] for k in jadwal_di_halte(data, indeks_halte)]
        if jam_jadwal not in resmi:
            jam_jadwal = None  # tidak cocok dengan jadwal halte ini: tebak otomatis
    isi = (isi or "").strip()[:MAKS_ISI]
    if jenis in ("halte", "lainnya") and len(isi) < 5:
        salah.append("Tulis keterangan singkat (minimal 5 huruf).")
    nama = (nama or "").strip()[:MAKS_NAMA] or "Anonim"
    if salah:
        return None, salah

    sekarang = waktu_sekarang_wib()
    laporan = {
        "id": uuid.uuid4().hex[:10],
        "dikirim": sekarang.strftime("%Y-%m-%d %H:%M"),
        "tanggal": sekarang.strftime("%Y-%m-%d"),
        "jenis": jenis,
        "halte": indeks_halte,
        "jam": jam_menit,
        "jam_jadwal": None,
        "selisih": None,
        "isi": isi,
        "nama": nama,
    }
    if indeks_halte is not None and jenis in ("jadwal", "tidak_datang"):
        if jam_jadwal is None and jam_menit is not None:
            if jenis == "jadwal":
                jam_jadwal = jadwal_sebelum(data, indeks_halte, jam_menit)
            else:
                jam_jadwal = jadwal_terdekat(data, indeks_halte, jam_menit)
        laporan["jam_jadwal"] = jam_jadwal
        if jenis == "jadwal" and jam_jadwal is not None:
            laporan["selisih"] = jam_menit - jam_jadwal
    return laporan, []


def median_berbobot(pasangan):
    """Median dari list (nilai, bobot). Bobot = 1 + jumlah dukungan."""
    urut = sorted(pasangan)
    total = sum(b for _, b in urut)
    jalan = 0
    for nilai, bobot in urut:
        jalan += bobot
        if jalan * 2 >= total:
            return nilai
    return 0


def masih_berlaku(laporan, hari_ini):
    try:
        y, m, d = (int(x) for x in laporan["tanggal"].split("-"))
    except (KeyError, ValueError):
        return False
    return (hari_ini - hari_ini.replace(year=y, month=m, day=d)) <= timedelta(days=BATAS_HARI)


def ringkasan_halte(data, semua_laporan):
    """Rangkuman laporan per halte untuk jadwal versi komunitas.

    Hasil: list (satu per halte) berisi jumlah laporan, selisih median,
    status, dan jumlah laporan "bus tidak datang".
    """
    hari_ini = waktu_sekarang_wib()
    hasil = []
    for i, nama in enumerate(daftar_nama_halte(data)):
        pasangan = []
        tidak_datang = 0
        for lap in semua_laporan:
            if lap.get("halte") != i or not masih_berlaku(lap, hari_ini):
                continue
            if lap["jenis"] == "jadwal" and lap.get("selisih") is not None:
                pasangan.append((lap["selisih"], 1 + lap.get("dukungan", 0)))
            elif lap["jenis"] == "tidak_datang":
                tidak_datang += 1 + lap.get("dukungan", 0)
        ringkas = {"indeks": i, "nama": nama, "jumlah": len(pasangan), "tidak_datang": tidak_datang,
                   "selisih": None, "status": "belum ada laporan"}
        if pasangan:
            s = median_berbobot(pasangan)
            ringkas["selisih"] = s
            ringkas["status"] = teks_selisih(s)
        hasil.append(ringkas)
    return hasil


def teks_selisih(selisih):
    if selisih is None:
        return "belum ada laporan"
    if abs(selisih) <= BATAS_SESUAI:
        return "sesuai jadwal"
    if selisih > 0:
        return f"terlambat ±{selisih} menit"
    return f"lebih cepat ±{-selisih} menit"


def jam_versi_komunitas(menit_resmi, ringkas):
    """Jam perkiraan menurut komunitas, atau None kalau belum ada laporan / sesuai jadwal."""
    if ringkas is None or ringkas["selisih"] is None or abs(ringkas["selisih"]) <= BATAS_SESUAI:
        return None
    return menit_resmi + ringkas["selisih"]


def tampilan_laporan(data, laporan):
    """Menambahkan teks siap tampil ke laporan (nama halte, jam, jenis)."""
    halte = daftar_nama_halte(data)
    lap = dict(laporan)
    lap["nama_jenis"] = JENIS_LAPORAN.get(lap["jenis"], lap["jenis"])
    lap["nama_halte"] = halte[lap["halte"]] if lap.get("halte") is not None and lap["halte"] < len(halte) else None
    lap["teks_jam"] = ke_jam(lap["jam"]) if lap.get("jam") is not None else None
    lap["teks_jadwal"] = ke_jam(lap["jam_jadwal"]) if lap.get("jam_jadwal") is not None else None
    lap["teks_selisih"] = teks_selisih(lap.get("selisih")) if lap.get("selisih") is not None else None
    return lap
