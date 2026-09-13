"""
Harga Tokped — pantau harga & promo produk di Tokopedia.

Cara kerja:
  1. Buka halaman pencarian Tokopedia pake browser asli (Playwright),
     jadi JavaScript-nya jalan dan produk beneran ke-render.
  2. Ambil nama + harga + harga coret (kalau ada) tiap produk.
  3. Simpen snapshot ke file JSON per kata kunci.
  4. Bandingin sama snapshot sebelumnya → produk yang turun harga
     ditandai sebagai PROMO, lengkap sama persen turunnya.

Cara jalanin:
    python harga_tokped.py "sepatu futsal"
    python harga_tokped.py "earphone bluetooth" --tampil

Catatan etika: ini scraping data publik pake rate rendah (sekali jalan =
1 kunjungan), cuma buat pemakaian pribadi. Jangan dijadiin cronjob tiap menit.
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

from playwright.sync_api import sync_playwright

SYS_DIR = Path(__file__).parent / "snapshots"

POLA_HARGA = re.compile(r"^Rp\s?([\d.]{4,12})$")


def harga_ke_angka(teks: str) -> float:
    """'Rp299.500' → 299500.0"""
    return float(POLA_HARGA.match(teks).group(1).replace(".", ""))


def scrape(kata_kunci: str, tanpa_jendela: bool) -> dict:
    """Buka Tokopedia via browser, balikin {nama_produk: data}."""
    url = f"https://www.tokopedia.com/search?q={kata_kunci.replace(' ', '+')}"
    print(f"Membuka {url} ...")

    with sync_playwright() as p:
        # PENTING: hasil eksperimen, Tokopedia nge-blok headless Chrome
        # (ERR_HTTP2_PROTOCOL_ERROR), tapi ngelolosin yang jendelanya tampil.
        # Makanya default-nya browser kebuka; --tanpa-jendela buat yang mau
        # diem-diem (riskan).
        browser = p.chromium.launch(headless=tanpa_jendela)
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
            locale="id-ID",
        )
        page.goto(url, wait_until="domcontentloaded", timeout=45000)

        # Tunggu produknya beneran ke-render — ini keunggulan Playwright:
        # kita nunggu, bukan maksa baca HTML mentah.
        page.wait_for_selector("text=/menampilkan \\d+ - \\d+/i", timeout=30000)
        page.wait_for_timeout(2000)  # sisa produk yang loading belakangan

        teks = page.inner_text("body")
        browser.close()

    return parse_hasil(teks)


def parse_hasil(teks: str) -> dict:
    """
    Ubah teks halaman pencarian jadi data produk.

    Struktur tiap kartu di inner_text selalu:
        <nama produk>
        Rp<harga sekarang>
        [Rp<harga coret>]        ← cuma ada kalau lagi diskon
        ...
    Kita jalan baris per baris; harga pertama = harga jual,
    harga kedua beruntun = harga coret.
    """
    hasil = {}
    baris = [b.strip() for b in teks.splitlines() if b.strip()]

    for i, b in enumerate(baris):
        m = POLA_HARGA.match(b)
        if not m or i == 0:
            continue

        # Nama produk = baris teks panjang sebelum blok harga.
        # Baris pendek kayak "Bisa COD" / "5.0" / "40+ terjual" dilewatin.
        nama = ""
        for j in range(i - 1, max(i - 6, -1), -1):
            kandidat = baris[j]
            if len(kandidat) > 20 and not POLA_HARGA.match(kandidat):
                nama = kandidat
                break
        if not nama or nama in hasil:
            continue

        produk = {"harga": harga_ke_angka(b)}

        # Cek harga coret: harga berikutnya yang nempel (selisih maks 2 baris)
        for k in range(i + 1, min(i + 3, len(baris))):
            if POLA_HARGA.match(baris[k]):
                aslinya = harga_ke_angka(baris[k])
                if aslinya > produk["harga"]:
                    produk["harga_asli"] = aslinya
                break

        hasil[nama] = produk

    return hasil


def muat_snapshot(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Pantau harga Tokopedia")
    parser.add_argument("kata_kunci", nargs="*", default=["sepatu futsal"],
                        help="apa yang mau dicari")
    parser.add_argument("--tanpa-jendela", action="store_true",
                        help="jalan diem-diem tanpa browser kebuka (riskan diblok)")
    args = parser.parse_args()
    kata = " ".join(args.kata_kunci) or "sepatu futsal"

    produk = scrape(kata, args.tanpa_jendela)
    if not produk:
        print("Nggak ada produk ketemu — mungkin kena verifikasi. "
              "Coba lagi nanti atau pake --tampil buat ngeliat halaman aslinya.")
        return 1

    # Snapshot lama = data run SEBELUM hari ini (buat bandingin).
    SYS_DIR.mkdir(exist_ok=True)
    nama_file = re.sub(r"[^\w]+", "_", kata.lower())
    path = SYS_DIR / f"tokped_{nama_file}.json"
    lama = muat_snapshot(path)

    hari_ini = date.today().isoformat()
    promo, turun = [], []
    for nama, p in produk.items():
        # Promo vs harga normal → bandingin ama harga sebelumnya di snapshot.
        if "harga_asli" in p:
            diskon = (1 - p["harga"] / p["harga_asli"]) * 100
            promo.append((nama, p["harga"], p["harga_asli"], diskon, "coret"))
        prev = lama.get(nama, {}).get("harga")
        if prev and p["harga"] < prev:
            turun.append((nama, p["harga"], prev,
                          (1 - p["harga"] / prev) * 100, "turun"))

    # Simpen snapshot hari ini (harga saat ini jadi pembanding run berikutnya).
    path.write_text(json.dumps(produk, ensure_ascii=False, indent=2),
                    encoding="utf-8")

    print(f"\n{len(produk)} produk '{kata}' — snapshot disimpan ke {path.name}")
    print(f"(Snapshot sebelumnya: {'ada' if lama else 'belum ada — run berikut baru bisa bandingin'})\n")

    tampilkan("🔥 DISKON (harga coret dari Tokopedia)", promo)
    tampilkan("📉 TURUN dari pantauan sebelumnya", turun)

    if not promo and not turun:
        print("Belum ada promo keliatan hari ini.")
    return 0


def tampilkan(judul: str, isi: list) -> None:
    if not isi:
        return
    print(judul)
    for nama, sekarang, dulu, persen, jenis in sorted(isi, key=lambda x: -x[3])[:8]:
        nama_pendek = nama if len(nama) <= 55 else nama[:52] + "..."
        print(f"  {nama_pendek}")
        print(f"    Rp{dulu:,.0f} → Rp{sekarang:,.0f}  ({persen:.0f}% lebih murah, {jenis})")
    print()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
