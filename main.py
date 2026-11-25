"""Smart Shuttle ITB Jatinangor - versi terminal.

Jalankan:  python main.py

File ini hanya mengurus tampilan (input/print). Semua perhitungan
ada di folder core/, sehingga bisa dipakai bersama oleh versi web.
"""

from core.data import daftar_nama_halte
from core.komunitas import JENIS_LAPORAN, buat_laporan, ringkasan_halte, tampilan_laporan
from core.penumpang import cari_bus_berikutnya, estimasi_perjalanan, jadwal_di_halte
from core.penyimpanan import laporan_bisa_disimpan, muat_data, muat_laporan, simpan_laporan
from core.waktu import format_durasi, ke_jam, ke_menit, menit_sekarang


# ====================== Fungsi bantu input ======================

def garis(judul=""):
    print()
    print("=" * 60)
    if judul:
        print(judul.center(60))
        print("=" * 60)


def jeda():
    input("\nTekan Enter untuk lanjut...")


def input_angka(pesan, minimum=None, maksimum=None, bawaan=None, desimal=False):
    """Meminta angka dari pengguna, diulang sampai valid."""
    while True:
        teks = input(pesan).strip()
        if teks == "" and bawaan is not None:
            return bawaan
        try:
            angka = float(teks.replace(",", ".")) if desimal else int(teks)
        except ValueError:
            print("  ! Masukkan angka yang benar.")
            continue
        if minimum is not None and angka < minimum:
            print(f"  ! Minimal {minimum}.")
        elif maksimum is not None and angka > maksimum:
            print(f"  ! Maksimal {maksimum}.")
        else:
            return angka


def input_jam(pesan, bawaan=None, boleh_kosong=False):
    """Meminta jam format HH:MM. Mengembalikan menit sejak 00:00 (atau None kalau boleh kosong)."""
    while True:
        teks = input(pesan).strip()
        if teks == "" and (bawaan is not None or boleh_kosong):
            return bawaan
        try:
            return ke_menit(teks)
        except ValueError as e:
            print(f"  ! {e}")


def pilih_halte(data, pesan="Pilih halte"):
    """Menampilkan daftar halte dan mengembalikan indeks yang dipilih."""
    nama = daftar_nama_halte(data)
    for i, n in enumerate(nama, start=1):
        print(f"  {i}. {n}")
    return input_angka(f"{pesan} (1-{len(nama)}): ", 1, len(nama)) - 1


def pilih_menu(pilihan):
    """Menampilkan menu dan mengembalikan kode pilihan."""
    for kode, teks in pilihan:
        print(f"  [{kode}] {teks}")
    kode_valid = [k for k, _ in pilihan]
    while True:
        p = input("Pilihan: ").strip()
        if p in kode_valid:
            return p
        print("  ! Pilihan tidak ada.")


# ====================== Layanan penumpang ======================

def menu_jadwal_halte(data):
    garis("JADWAL DI HALTE")
    h = pilih_halte(data)
    jadwal = jadwal_di_halte(data, h)
    print(f"\nBus tiba di {data['halte'][h]['nama']} ({len(jadwal)} kali sehari):")
    for i, k in enumerate(jadwal):
        print(f"  {ke_jam(k['waktu'])}", end="")
        print() if (i + 1) % 4 == 0 else print("   ", end="")
    print()


def menu_bus_berikutnya(data):
    garis("BUS BERIKUTNYA")
    h = pilih_halte(data)
    sekarang = menit_sekarang()
    sekarang = input_jam(f"Jam keberangkatan (HH:MM, Enter = sekarang {ke_jam(sekarang)}): ", sekarang)
    hasil = cari_bus_berikutnya(data, h, sekarang, 3)
    if not hasil:
        print("\nTidak ada bus lagi hari ini di halte ini.")
        return
    print(f"\nBus berikutnya di {data['halte'][h]['nama']} setelah {ke_jam(sekarang)}:")
    for k in hasil:
        print(f"  - {ke_jam(k['waktu'])}  (tunggu {format_durasi(k['tunggu'])})")


def menu_estimasi(data):
    garis("ESTIMASI WAKTU TIBA")
    print("Halte asal:")
    asal = pilih_halte(data, "Asal")
    print("Halte tujuan:")
    tujuan = pilih_halte(data, "Tujuan")
    if asal == tujuan:
        print("\nAsal dan tujuan sama, tidak perlu naik shuttle.")
        return
    sekarang = menit_sekarang()
    sekarang = input_jam(f"Jam berangkat (HH:MM, Enter = sekarang {ke_jam(sekarang)}): ", sekarang)
    e = estimasi_perjalanan(data, asal, tujuan, sekarang)
    if e is None:
        print("\nTidak ada bus lagi hari ini.")
        return
    print(f"\nRute     : {' -> '.join(e['rute'])}")
    print(f"Bus      : datang pukul {ke_jam(e['waktu_bus_datang'])}")
    print(f"Menunggu : {format_durasi(e['lama_tunggu'])}")
    print(f"Di bus   : {format_durasi(e['lama_perjalanan'])}")
    print(f"Tiba     : pukul {ke_jam(e['waktu_tiba'])} (total {format_durasi(e['total_waktu'])})")


def menu_penumpang(data):
    while True:
        garis("LAYANAN PENUMPANG")
        p = pilih_menu([("1", "Lihat jadwal di halte"), ("2", "Cari bus berikutnya"),
                        ("3", "Estimasi waktu tiba"), ("0", "Kembali")])
        if p == "0":
            return
        if p == "1":
            menu_jadwal_halte(data)
        elif p == "2":
            menu_bus_berikutnya(data)
        elif p == "3":
            menu_estimasi(data)
        jeda()


# ====================== Komunitas ======================

def menu_ringkasan_komunitas(data):
    garis("JADWAL VERSI KOMUNITAS")
    for r in ringkasan_halte(data, muat_laporan()):
        teks = r["status"] if r["jumlah"] else "belum ada laporan"
        tambahan = f", {r['tidak_datang']}x bus tidak datang" if r["tidak_datang"] else ""
        print(f"  {r['nama']:<30} {teks} ({r['jumlah']} laporan{tambahan})")


def menu_daftar_laporan(data):
    garis("LAPORAN TERBARU")
    semua = muat_laporan()
    if not semua:
        print("Belum ada laporan.")
        return
    for lap in reversed(semua[-10:]):
        t = tampilan_laporan(data, lap)
        print(f"- [{t['dikirim']}] {t['nama_jenis']}" + (f" @ {t['nama_halte']}" if t["nama_halte"] else ""))
        if t["teks_jam"]:
            print(f"    jam {t['teks_jam']} (jadwal {t['teks_jadwal']})" + (f" -> {t['teks_selisih']}" if t["teks_selisih"] else ""))
        if t["isi"]:
            print(f"    {t['isi']}")
        print(f"    oleh {t['nama']} · {t['dukungan']} dukungan")


def menu_kirim_laporan(data):
    garis("KIRIM LAPORAN")
    if not laporan_bisa_disimpan():
        print("Penyimpanan laporan belum aktif.")
        return
    daftar_jenis = list(JENIS_LAPORAN.items())
    for i, (_, teks) in enumerate(daftar_jenis, start=1):
        print(f"  {i}. {teks}")
    jenis = daftar_jenis[input_angka(f"Jenis (1-{len(daftar_jenis)}): ", 1, len(daftar_jenis)) - 1][0]
    halte = None
    if jenis in ("jadwal", "tidak_datang"):
        halte = pilih_halte(data)
    jam = input_jam("Jam bus datang / jam jadwal yang ditunggu (HH:MM, Enter = lewati): ", None, boleh_kosong=True)
    isi = input("Keterangan: ")
    nama = input("Nama (Enter = Anonim): ")
    laporan, salah = buat_laporan(data, jenis, halte, jam, isi, nama)
    if salah:
        for s in salah:
            print(f"  ! {s}")
        return
    simpan_laporan(laporan)
    print("Terima kasih, laporan tersimpan.")
    if laporan["selisih"] is not None:
        print(f"Jadwal resmi terdekat {ke_jam(laporan['jam_jadwal'])}, selisih {laporan['selisih']:+d} menit.")


def menu_komunitas(data):
    while True:
        garis("KOMUNITAS")
        p = pilih_menu([("1", "Jadwal versi komunitas"), ("2", "Laporan terbaru"),
                        ("3", "Kirim laporan"), ("0", "Kembali")])
        if p == "0":
            return
        if p == "1":
            menu_ringkasan_komunitas(data)
        elif p == "2":
            menu_daftar_laporan(data)
        elif p == "3":
            menu_kirim_laporan(data)
        jeda()


# ====================== Program utama ======================

def main():
    data = muat_data()
    while True:
        garis(data["nama_layanan"].upper())
        print(f"Sekarang pukul {ke_jam(menit_sekarang())} WIB")
        if data.get("catatan"):
            print(f"Catatan: {data['catatan']}")
        print()
        p = pilih_menu([("1", "Layanan penumpang"), ("2", "Komunitas (laporan jadwal)"),
                        ("0", "Keluar")])
        if p == "0":
            print("Terima kasih telah memakai Smart Shuttle!")
            break
        if p == "1":
            menu_penumpang(data)
        elif p == "2":
            menu_komunitas(data)


if __name__ == "__main__":
    main()
