"""Fungsi bantu untuk mengolah waktu.

Abstraksi: semua waktu di program disimpan sebagai "menit sejak pukul 00:00".
Contoh: 07:30 -> 450. Dengan begitu perbandingan dan penjumlahan waktu
cukup memakai operasi bilangan bulat biasa.
"""

from datetime import datetime, timedelta, timezone

# Indonesia bagian barat tidak memakai daylight saving, jadi cukup UTC+7.
WIB = timezone(timedelta(hours=7))


def ke_menit(teks_jam):
    """Mengubah teks "HH:MM" menjadi menit sejak 00:00. Contoh "07:30" -> 450."""
    bagian = teks_jam.strip().split(":")
    if len(bagian) != 2:
        raise ValueError(f"Format jam harus HH:MM, bukan '{teks_jam}'")
    jam = int(bagian[0])
    menit = int(bagian[1])
    if jam < 0 or jam > 23 or menit < 0 or menit > 59:
        raise ValueError(f"Jam tidak valid: '{teks_jam}'")
    return jam * 60 + menit


def ke_jam(menit):
    """Mengubah menit sejak 00:00 menjadi teks "HH:MM". Contoh 450 -> "07:30"."""
    menit = int(round(menit))
    hari_lewat = menit // (24 * 60)
    menit = menit % (24 * 60)
    teks = f"{menit // 60:02d}:{menit % 60:02d}"
    if hari_lewat > 0:
        teks += " (+1 hari)"
    return teks


def menit_sekarang():
    """Waktu sekarang dalam WIB, dalam satuan menit sejak 00:00.

    Server (misalnya Vercel) biasanya memakai jam UTC, jadi waktu
    harus dikonversi dulu ke WIB.
    """
    sekarang = datetime.now(WIB)
    return sekarang.hour * 60 + sekarang.minute


def format_durasi(menit):
    """Menulis durasi dengan rapi. Contoh 75 -> "1 jam 15 menit"."""
    menit = int(round(menit))
    if menit < 60:
        return f"{menit} menit"
    jam = menit // 60
    sisa = menit % 60
    if sisa == 0:
        return f"{jam} jam"
    return f"{jam} jam {sisa} menit"


def waktu_sekarang_wib():
    """datetime sekarang dalam WIB."""
    return datetime.now(WIB)
