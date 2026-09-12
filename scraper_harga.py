"""
Scraper harga sederhana.

Target: books.toscrape.com — website dummy berisi daftar "produk" lengkap
dengan nama, harga, dan stok. Sengaja dipakai karena strukturnya mirip
halaman listing marketplace beneran, tapi nggak ada anti-bot-nya.

Cara jalanin:
    python scraper_harga.py
    python scraper_harga.py --halaman 3
    python scraper_harga.py --max-harga 40 --csv hasil.csv
"""

import argparse
import csv
import sys
import time
from dataclasses import asdict, dataclass
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://books.toscrape.com/catalogue/page-{nomor}.html"
SITE_URL = "https://books.toscrape.com/"

# Rating di HTML aslinya cuma nama ("One".."Five"), kita petain ke angka.
RATING_BINTANG = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}

# 1 mata uang GBP (pound) sekitar berapa Rupiah. Ini perkiraan —
# update sendiri kalau mau angka yang bener.
KURS_GBP_IDR = 26000

HEADERS = {
    # Banyak website nolak request tanpa User-Agent. Ini bukan buat nyamar,
    # cuma ngasih tau siapa kita — sama kayak browser ngelakuin tiap hari.
    "User-Agent": "Mozilla/5.0 (belajar-scraping; kontak: kamu@email.com)"
}

REQUEST_DELAY = 1.0  # detik antar request — jangan spam server orang


@dataclass
class Produk:
    nama: str
    harga: float
    rating: str
    stok: str
    url: str


def ambil_halaman(nomor: int) -> str:
    """Download satu halaman, balikin HTML mentahnya."""
    url = BASE_URL.format(nomor=nomor)
    respons = requests.get(url, headers=HEADERS, timeout=15)

    # Kalau server nolak (403/429/503), kita berhenti duluan daripada
    # maksa dan kena blokir IP.
    if respons.status_code != 200:
        raise RuntimeError(
            f"Server balas {respons.status_code} buat {url}. "
            "Kemungkinan kita dibatasi — coba lagi nanti."
        )

    # requests default-nya nebak encoding dari HTTP header. Kalau header-nya
    # nggak nyebutin charset, dia fallback ke latin-1 — dan simbol kayak "£"
    # jadi rusak (muncul "Â£"). apparent_encoding ngusut charset dari isi
    # HTML-nya langsung (meta tag), yang jauh lebih bener.
    respons.encoding = respons.apparent_encoding
    return respons.text


def ekstrak_produk(html: str) -> list[Produk]:
    """Parse HTML listing jadi daftar Produk."""
    soup = BeautifulSoup(html, "html.parser")
    hasil = []

    # Tiap kartu produk ada di <article class="product_pod">
    for kartu in soup.select("article.product_pod"):
        link = kartu.select_one("h3 a")
        if not link:
            continue

        # Rating disimpen di class, contoh: "star-rating Three"
        kelas_rating = kartu.select_one("p.star-rating")
        rating = ""
        if kelas_rating:
            rating = next((c for c in kelas_rating.get("class", [])
                           if c != "star-rating"), "")

        # Harga formatnya "£45.00" — buang simbol mata uangnya
        teks_harga = kartu.select_one("p.price_color").get_text()
        harga = float(teks_harga.lstrip("£$€ "))

        # Stok formatnya "In stock (22 available)"
        stok_el = kartu.select_one("p.instock.availability")
        stok = stok_el.get_text(strip=True) if stok_el else ""

        # Link masih relatif, jadiin absolute
        hasil.append(Produk(
            nama=link.get("title") or link.get_text(strip=True),
            harga=harga,
            rating=rating,
            stok=stok,
            url=urljoin(SITE_URL, link.get("href", "")),
        ))

    return hasil


def simpan_csv(produk_list: list[Produk], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        penulis = csv.DictWriter(f, fieldnames=Produk.__dataclass_fields__)
        penulis.writeheader()
        penulis.writerows(asdict(p) for p in produk_list)


def main() -> int:
    # Terminal Windows default-nya pake encoding cp1252 (kode halaman lama)
    # yang nggak kenal simbol kayak ≈ atau ⭐, bikin print() meledak dengan
    # UnicodeEncodeError. Reconfigure maksa stdout pake UTF-8; karakter yang
    # tetep nggak bisa dirender diganti "?" tanpa bikin program mati.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Scraper harga")
    parser.add_argument("--halaman", type=int, default=2,
                        help="berapa halaman listing yang di-scrape (default: 2)")
    parser.add_argument("--max-harga", type=float,
                        help="cuma tampilkan produk di bawah harga ini")
    parser.add_argument("--csv", help="simpen hasil ke file CSV")
    parser.add_argument("--urut", choices=["murah", "mahal", "rating"],
                        default="murah", help="cara ngurutin (default: murah)")
    args = parser.parse_args()

    semua: list[Produk] = []
    for nomor in range(1, args.halaman + 1):
        print(f"Mengambil halaman {nomor}...", end=" ", flush=True)
        try:
            halaman = ambil_halaman(nomor)
        except requests.exceptions.RequestException as e:
            print(f"gagal: {e}")
            break

        produk = ekstrak_produk(halaman)
        print(f"{len(produk)} produk")
        semua.extend(produk)

        if nomor < args.halaman:
            time.sleep(REQUEST_DELAY)

    if not semua:
        print("Nggak ada data yang keambil.")
        return 1

    if args.max_harga is not None:
        semua = [p for p in semua if p.harga <= args.max_harga]

    # Ngurutin sesuai pilihan user
    if args.urut == "murah":
        semua.sort(key=lambda p: p.harga)
    elif args.urut == "mahal":
        semua.sort(key=lambda p: p.harga, reverse=True)
    else:  # "rating" — rating tertinggi, kalau seri urutin termurah
        semua.sort(key=lambda p: (-RATING_BINTANG.get(p.rating, 0), p.harga))

    print(f"\n{len(semua)} produk ditemukan (urut: {args.urut}):\n")
    print(f"{'GBP':>7}  {'≈ IDR':>11}  {'RATING':<6}  {'NAMA'}")
    print("-" * 70)
    for p in semua[:20]:
        nama = p.nama if len(p.nama) <= 40 else p.nama[:37] + "..."
        bintang = "⭐" * RATING_BINTANG.get(p.rating, 0)
        print(f"{p.harga:>7.2f}  {p.harga * KURS_GBP_IDR:>11,.0f}  "
              f"{bintang:<6}  {nama}")
    if len(semua) > 20:
        print(f"... dan {len(semua) - 20} lainnya")

    if args.csv:
        simpan_csv(semua, args.csv)
        print(f"\nDisimpan ke {args.csv}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
