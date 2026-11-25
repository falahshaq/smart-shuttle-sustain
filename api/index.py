"""Smart Shuttle ITB Jatinangor - versi web (Flask).

Jalankan di laptop:   python api/index.py   lalu buka http://127.0.0.1:5000
Di Vercel file ini otomatis dipakai sebagai serverless function.

Sama seperti main.py, file ini hanya mengurus tampilan.
Semua perhitungan memanggil fungsi yang sama dari folder core/.
"""

import os
import sys

FOLDER_PROYEK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, FOLDER_PROYEK)

from flask import Flask, make_response, redirect, render_template, request, url_for  # noqa: E402

from core.data import buat_jadwal, daftar_nama_halte, durasi_putaran, potongan_jalur  # noqa: E402
from core.komunitas import (JENIS_LAPORAN, buat_laporan, jam_versi_komunitas, ringkasan_halte,  # noqa: E402
                            tampilan_laporan)
from core.penumpang import cari_bus_berikutnya, estimasi_perjalanan, jadwal_di_halte  # noqa: E402
from core.penyimpanan import (hapus_laporan, laporan_bisa_disimpan, muat_data, muat_laporan,  # noqa: E402
                              simpan_laporan, tambah_dukungan)
from core.waktu import format_durasi, ke_jam, ke_menit, menit_sekarang  # noqa: E402

app = Flask(__name__, template_folder=os.path.join(FOLDER_PROYEK, "templates"))
app.jinja_env.filters["jam"] = ke_jam
app.jinja_env.filters["durasi"] = format_durasi


# ====================== Fungsi bantu ======================

def ambil_int(nama, bawaan, minimum=None, maksimum=None):
    """Membaca angka bulat dari query/form, dengan batas aman."""
    try:
        nilai = int(request.values.get(nama, bawaan))
    except (TypeError, ValueError):
        nilai = bawaan
    if minimum is not None and nilai < minimum:
        nilai = minimum
    if maksimum is not None and nilai > maksimum:
        nilai = maksimum
    return nilai


def ambil_jam(nama, bawaan):
    teks = request.values.get(nama, "").strip()
    if not teks:
        return bawaan
    try:
        return ke_menit(teks)
    except ValueError:
        return bawaan


def sandi_benar():
    """Kata sandi admin (untuk menghapus laporan). Di laptop tanpa sandi = boleh."""
    sandi = os.environ.get("ADMIN_PASSWORD", "")
    if not sandi:
        return not os.environ.get("VERCEL")
    return request.form.get("sandi", "") == sandi


def ringkasan_komunitas(data):
    return ringkasan_halte(data, muat_laporan())


@app.context_processor
def variabel_umum():
    return {"menu_aktif": request.endpoint}


# ====================== Halaman penumpang ======================

@app.route("/")
def beranda():
    data = muat_data()
    sekarang = menit_sekarang()
    komunitas = ringkasan_komunitas(data)
    papan = []
    for i, nama in enumerate(daftar_nama_halte(data)):
        pertama = cari_bus_berikutnya(data, i, 0, 1)
        bus = cari_bus_berikutnya(data, i, sekarang, 2)
        for b in bus:
            b["versi_komunitas"] = jam_versi_komunitas(b["waktu"], komunitas[i])
        papan.append({"indeks": i, "nama": nama, "bus": bus, "komunitas": komunitas[i],
                      "pertama": pertama[0]["waktu"] if pertama else None})
    return render_template("beranda.html", data=data, sekarang=sekarang, papan=papan,
                           halte=daftar_nama_halte(data), putaran=durasi_putaran(data),
                           jalur=data.get("jalur_peta", []))


@app.route("/rute")
def rute():
    data = muat_data()
    halte = daftar_nama_halte(data)
    sekarang = menit_sekarang()
    asal = ambil_int("asal", 0, 0, len(halte) - 1)
    tujuan = ambil_int("tujuan", 1 if len(halte) > 1 else 0, 0, len(halte) - 1)
    jam = ambil_jam("jam", sekarang)
    hasil = None
    pesan = None
    if "asal" in request.args:
        if asal == tujuan:
            pesan = "Halte asal dan tujuan sama, tidak perlu naik shuttle."
        else:
            hasil = estimasi_perjalanan(data, asal, tujuan, jam)
            if hasil is None:
                pesan = f"Tidak ada bus lagi setelah pukul {ke_jam(jam)}. Shuttle beroperasi {data['jam_operasi']['mulai']} - {data['jam_operasi']['selesai']}."
    # Titik halte untuk peta: asal hijau, tujuan merah, halte yang dilewati biru, sisanya redup.
    dipilih = "asal" in request.args and asal != tujuan
    dilewati = set()
    if dipilih:
        i = asal
        while i != tujuan:
            dilewati.add(i)
            i = (i + 1) % len(halte)
    titik_peta = []
    for i, h in enumerate(data["halte"]):
        kelas = ""
        if dipilih:
            kelas = "asal" if i == asal else "tujuan" if i == tujuan else ("" if i in dilewati else "redup")
        titik_peta.append({
            "nama": h["nama"], "lat": h["lat"], "lon": h["lon"], "kelas": kelas,
            "baris": [],
            "tautan": [{"href": url_for("rute", asal=i, tujuan=tujuan if tujuan != i else (i + 1) % len(halte)), "teks": "Berangkat dari sini"},
                       {"href": url_for("rute", asal=asal if asal != i else (i - 1) % len(halte), tujuan=i), "teks": "Tujuan ke sini"}],
        })
    sorot = potongan_jalur(data, asal, tujuan) if dipilih else None
    return render_template("rute.html", data=data, halte=halte, asal=asal, tujuan=tujuan,
                           jam=jam, hasil=hasil, pesan=pesan, titik_peta=titik_peta, sorot=sorot,
                           jalur=data.get("jalur_peta", []))


@app.route("/jadwal")
def jadwal():
    data = muat_data()
    return render_template("jadwal.html", data=data, halte=daftar_nama_halte(data),
                           jadwal=buat_jadwal(data), sekarang=menit_sekarang(),
                           putaran=durasi_putaran(data), komunitas=ringkasan_komunitas(data))


# ====================== Komunitas ======================

def id_didukung():
    """Id laporan yang sudah didukung browser ini (disimpan di cookie)."""
    return set(filter(None, request.cookies.get("didukung", "").split(",")))


@app.route("/komunitas", methods=["GET", "POST"])
def komunitas():
    data = muat_data()
    halte = daftar_nama_halte(data)
    salah = []
    ok = request.args.get("ok")
    isian = {"jenis": request.args.get("jenis", "jadwal"), "halte": request.args.get("halte", ""),
             "jam": "", "jadwal": "", "isi": "", "nama": ""}
    if request.method == "POST":
        f = request.form
        isian = {k: f.get(k, "") for k in ("jenis", "halte", "jam", "jadwal", "isi", "nama")}
        if f.get("website"):  # kolom jebakan untuk bot spam, manusia tidak melihatnya
            return redirect(url_for("komunitas", ok="1"))
        indeks = int(isian["halte"]) if isian["halte"].isdigit() else None
        jam = None
        if isian["jam"].strip():
            try:
                jam = ke_menit(isian["jam"])
            except ValueError:
                salah.append("Format jam tidak valid.")
        jam_jadwal = None
        if isian["jadwal"].strip():
            try:
                jam_jadwal = ke_menit(isian["jadwal"])
            except ValueError:
                jam_jadwal = None
        if not salah:
            laporan, salah = buat_laporan(data, isian["jenis"], indeks, jam, isian["isi"], isian["nama"], jam_jadwal)
            if not salah:
                try:
                    simpan_laporan(laporan)
                    return redirect(url_for("komunitas", ok="1") + "#daftar")
                except Exception as e:  # noqa: BLE001
                    salah = [str(e)]

    semua = muat_laporan()
    daftar = [tampilan_laporan(data, lap) for lap in reversed(semua)]
    filter_halte = request.args.get("filter", "")
    if filter_halte.isdigit():
        daftar = [lap for lap in daftar if lap.get("halte") == int(filter_halte)]
    return render_template("komunitas.html", data=data, halte=halte, jenis=JENIS_LAPORAN, isian=isian,
                           salah=salah, ok=ok, daftar=daftar, ringkas=ringkasan_halte(data, semua),
                           aktif=laporan_bisa_disimpan(), didukung=id_didukung(),
                           filter_halte=filter_halte, jumlah_total=len(semua),
                           jadwal_halte=[[ke_jam(k["waktu"]) for k in jadwal_di_halte(data, i)] for i in range(len(halte))],
                           # Hanya NAMA variabel (bukan isinya), untuk membantu cek sambungan database.
                           nama_variabel=sorted(k for k in os.environ if "REDIS" in k or k.startswith("KV") or "_KV_" in k))


@app.route("/komunitas/dukung", methods=["POST"])
def dukung():
    id_lap = request.form.get("id", "")[:20]
    sudah = id_didukung()
    tujuan = url_for("komunitas") + "#lap-" + id_lap
    if not id_lap or id_lap in sudah:
        return redirect(tujuan)
    try:
        tambah_dukungan(id_lap)
    except Exception:  # noqa: BLE001
        return redirect(tujuan)
    sudah.add(id_lap)
    respons = make_response(redirect(tujuan))
    respons.set_cookie("didukung", ",".join(sorted(sudah))[-3000:], max_age=60 * 60 * 24 * 365, samesite="Lax")
    return respons


@app.route("/komunitas/hapus", methods=["POST"])
def hapus():
    if not sandi_benar():
        return render_template("pesan.html", data=muat_data(), judul="Gagal menghapus", isi="Kata sandi admin salah.")
    hapus_laporan(request.form.get("id", "")[:20])
    return redirect(url_for("komunitas"))


@app.route("/peta")
def peta():
    return redirect(url_for("beranda") + "#peta")


@app.route("/tentang")
def tentang():
    return render_template("tentang.html", data=muat_data())


@app.errorhandler(404)
def tidak_ditemukan(e):
    return render_template("pesan.html", data=muat_data(), judul="Halaman tidak ditemukan",
                           isi="Alamat yang dibuka tidak ada."), 404


class PerbaikiPathVercel:
    """Di Vercel semua alamat diarahkan ke /api/index?__p=<alamat asli> (lihat vercel.json).
    Middleware ini mengembalikan alamat asli supaya route Flask bekerja normal."""

    def __init__(self, aplikasi):
        self.aplikasi = aplikasi

    def __call__(self, environ, start_response):
        from urllib.parse import parse_qsl, urlencode
        pasangan = parse_qsl(environ.get("QUERY_STRING", ""), keep_blank_values=True)
        sisa = []
        path_asli = None
        for k, v in pasangan:
            if k == "__p":
                path_asli = v
            else:
                sisa.append((k, v))
        if path_asli is not None:
            environ["PATH_INFO"] = "/" + path_asli.lstrip("/")
            environ["QUERY_STRING"] = urlencode(sisa)
        return self.aplikasi(environ, start_response)


app.wsgi_app = PerbaikiPathVercel(app.wsgi_app)


if __name__ == "__main__":
    app.run(debug=True)
