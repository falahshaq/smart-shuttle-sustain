# Smart Shuttle ITB Jatinangor (versi Sustainability)

Info shuttle dalam kampus ITB Jatinangor: jadwal resmi, peta rute, dan **jadwal versi komunitas**
dari laporan penumpang. Turunan dari repo `tubes2`; fitur simulasi, optimasi, adopsi, dan kelola data dihapus.

- **Terminal**: `main.py`
- **Web**: `api/index.py` (Flask), di-deploy ke Vercel

Data rute, halte, jadwal, dan jalur peta di `data/shuttle.json` diambil dari
[ModaHub PetakPeta](https://modahub.petakpeta.com/rute/kampus_jatinangor/ITBJ_SHUTTLE/shuttle-dalam-kampus-itb-jatinangor)
(Transport for Bandung, Agu 2026 · OpenStreetMap): 9 halte melingkar, berangkat dari Gerbang Utama
setiap 20 menit pukul 06:45–15:45, satu putaran sekitar 13 menit.

## Struktur folder

```
core/
  waktu.py        konversi jam <-> menit, jam WIB sekarang
  data.py         model rute dan jadwal
  penumpang.py    jadwal halte, bus berikutnya, estimasi waktu tiba
  komunitas.py    laporan penumpang + jadwal versi komunitas (median selisih)
  penyimpanan.py  baca data, simpan laporan (Redis atau file data/laporan.json)
data/shuttle.json data resmi
main.py           program terminal
api/index.py      program web (Flask)
templates/        halaman HTML
```

## Cara kerja laporan komunitas

1. Penumpang mengirim laporan di halaman **Komunitas**: bus datang di jam berbeda, bus tidak datang,
   halte salah, atau info lain. Tanpa akun.
2. Untuk laporan jam, program mencari jadwal resmi terdekat di halte itu lalu menghitung selisihnya.
3. Selisih dari laporan 30 hari terakhir dirangkum per halte dengan **median berbobot**
   (bobot = 1 + jumlah "saya juga mengalami").
4. Kalau median lebih dari 2 menit, beranda menampilkan "Kata warga: sekitar HH:MM" di samping jadwal resmi.
5. Admin bisa menghapus laporan spam dengan kata sandi `ADMIN_PASSWORD`.

## Menjalankan di laptop

Butuh Python 3.10 ke atas.

**Versi terminal** (tidak butuh library tambahan):

```bash
python main.py
```

**Versi web:**

```bash
pip install -r requirements.txt
python api/index.py
```

Lalu buka http://127.0.0.1:5000 di browser.

## Mengubah data resmi

Edit `data/shuttle.json` lalu push. Isinya: `jam_operasi`, `interval_menit`, `halte` (nama + koordinat,
urut sesuai rute), `waktu_tempuh` (menit ke halte berikutnya; yang terakhir = kembali ke halte pertama),
dan `jalur_peta` (garis rute di peta).

## Deploy ke Vercel

1. Login ke https://vercel.com pakai akun GitHub
2. **Add New → Project**, pilih repo ini, lalu klik **Deploy** (pengaturan biarkan default)
3. Setelah selesai, web bisa dibuka di `https://<nama-proyek>.vercel.app`

Setiap `git push` ke branch `main` otomatis meng-update web.

### Supaya laporan komunitas bisa disimpan

Di Vercel program tidak bisa menulis file, jadi laporan disimpan di database Redis:

1. Di dashboard project Vercel buka tab **Storage → Upstash for Redis**, buat database gratis, lalu
   **Connect** ke project ini. Variabel `KV_REST_API_URL` dan `KV_REST_API_TOKEN` otomatis ditambahkan.
   (Boleh juga memakai database yang sama dengan project tubes2; kuncinya berbeda, `sustain:*`.)
2. **Settings → Environment Variables**: tambahkan `ADMIN_PASSWORD` untuk menghapus laporan spam.
3. **Redeploy**.

Tanpa langkah ini web tetap jalan, hanya tombol kirim laporan nonaktif.

## Konsep berpikir komputasional

- **Dekomposisi**: tiap fitur jadi fungsi sendiri di modul terpisah, dipakai bersama oleh terminal dan web
- **Abstraksi**: waktu = menit sejak 00:00; rute = list halte melingkar; laporan = halte, jam, selisih
- **Algoritma**: pencarian linear (bus berikutnya, jadwal terdekat), median berbobot
