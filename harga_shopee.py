"""
Harga Shopee — pantau harga & promo produk di Shopee.

Sama kayak harga_tokped.py, tapi buat Shopee:
  1. Buka halaman pencarian pake browser asli (Playwright, headful).
  2. Shopee nyimpen data produk di atribut data-sqe — kita panen per kartu.
  3. Snapshot ke snapshots/shopee_<kata>.json, bandingin run sebelumnya.

Cara jalanin:
    python harga_shopee.py "sepatu futsal"
    python harga_shopee.py "earphone bluetooth" --tanpa-jendela

Catatan etika: scraping data publik, rate rendah, pemakaian pribadi.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import sync_playwright

SYS_DIR = Path(__file__).parent / "snapshots"

POLA_HARGA = re.compile(r"^Rp\s?([\d.]{4,12})$")


def harga_ke_angka(teks: str) -> float:
    """'Rp299.500' → 299500.0"""
    return float(POLA_HARGA.match(teks).group(1).replace(".", ""))


PROFIL_DIR = Path(__file__).parent / ".shopee_profil"


def scrape(kata_kunci: str, tanpa_jendela: bool) -> list:
    """Buka pencarian Shopee, balikin list {teks_kartu, href} per produk."""
    url = f"https://shopee.co.id/search?keyword={quote(kata_kunci)}"
    print(f"Membuka {url} ...")

    with sync_playwright() as p:
        # Persistent context = profil browser beneran yang nyimpen cookie
        # di folder. Shopee ngeliat search tanpa login sebagai tamu dan
        # nebak "ini robot" → dibuang ke halaman login. Makanya: run
        # pertama lo login manual sekali di jendela yang kebuka, abis itu
        # sesi lo kepake terus buat run berikutnya.
        # channel="chrome" = pake Google Chrome yang beneran keinstall di
        # PC lo, bukan Chromium murni bawaan Playwright. Chrome asli punya
        # fingerprint mesin lo sendiri (sebagai browser biasa), jadi anti-bot
        # Shopee jauh lebih susah nebak kita robot.
        ctx = p.chromium.launch_persistent_context(
            str(PROFIL_DIR),
            headless=tanpa_jendela,
            locale="id-ID",
            channel="chrome",
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=45000)

        # Dua gerbang yang mungkin dilewatin manual sama user:
        # login (kalau sesi habis) dan captcha (kalau Shopee curiga).
        # Dua-duanya tinggal diselesaiin di jendela browser, script nungguin.
        for halaman, pesan in [
            ("/buyer/login", "login dulu (QR/password)"),
            ("/verify/", "selesaiin captchanya (klik gambar sesuai instruksi)"),
        ]:
            if halaman in page.url:
                print(f"\n⚠️  Shopee minta {pesan}.")
                print("    Kerjain di jendela browser — nunggu maks 3 menit...")
                try:
                    page.wait_for_url("**/search**", timeout=180000)
                    print("    Udah lewat, lanjut scrape!\n")
                except Exception:
                    print("    Kelewat 3 menit, batal.")
                    ctx.close()
                    return []

        # Link produk Shopee selalu berformat ".../nama-barang-i.<toko>.<id>".
        # Nunggu salah satu muncul = produk udah ke-render.
        try:
            page.wait_for_selector("a[href*='-i.']", timeout=25000)
        except Exception:
            print("Produk nggak muncul — kemungkinan kena captcha.")
            ctx.close()
            return []

        page.wait_for_timeout(3000)  # sisain buat kartu yang telat render

        # Panen per kartu produk. innerText kartu isinya:
        #   <nama> \n Rp<harga> \n [-12%] \n Rp<harga coret> \n ...
        kartu = page.eval_on_selector_all(
            "li",
            """els => els
                .filter(el => el.querySelector("a[href*='-i.']"))
                .map(el => ({
                    teks: el.innerText,
                    href: el.querySelector("a[href*='-i.']").href,
                }))""",
        )
        ctx.close()

    return kartu


def parse_kartu(kartu: list) -> dict:
    """Balikin {nama: {harga, [harga_asli], url}} dari kartu mentah."""
    hasil = {}
    for k in kartu:
        baris = [b.strip() for b in k["teks"].splitlines() if b.strip()]
        harga_list = [b for b in baris if POLA_HARGA.match(b)]
        if not harga_list:
            continue

        # Nama = baris terpanjang yang bukan angka/label ("Rp...", "-12%",
        # "4.8", "1rb+ terjual") — nama produk Shopee selalu paling panjang.
        nama = ""
        for b in baris:
            if (len(b) > 15 and not POLA_HARGA.match(b)
                    and not re.fullmatch(r"-?\d+%?", b)
                    and "terjual" not in b and b[0] not in "Rp"):
                nama = b
                break
        if not nama or nama in hasil:
            continue

        produk = {"harga": harga_ke_angka(harga_list[0]),
                  "url": k["href"].split("?")[0]}

        # Harga ke-2 yang lebih gede = harga coret (diskon).
        if len(harga_list) > 1:
            kedua = harga_ke_angka(harga_list[1])
            if kedua > produk["harga"]:
                produk["harga_asli"] = kedua

        hasil[nama] = produk
    return hasil


def muat_snapshot(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def tampilkan(judul: str, isi: list) -> None:
    if not isi:
        return
    print(judul)
    for nama, skrg, dulu, persen, jenis, url in sorted(isi, key=lambda x: -x[3])[:8]:
        pendek = nama if len(nama) <= 55 else nama[:52] + "..."
        print(f"  {pendek}")
        print(f"    Rp{dulu:,.0f} → Rp{skrg:,.0f}  ({persen:.0f}% lebih murah, {jenis})")
        if url:
            print(f"    {url}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Pantau harga Shopee")
    parser.add_argument("kata_kunci", nargs="*", default=["sepatu futsal"])
    parser.add_argument("--tanpa-jendela", action="store_true",
                        help="headless (riskan diblok Shopee)")
    args = parser.parse_args()
    kata = " ".join(args.kata_kunci) or "sepatu futsal"

    produk = parse_kartu(scrape(kata, args.tanpa_jendela))
    if not produk:
        print("Nggak ada produk ketemu — Shopee cukup galak soal bot; "
              "coba lagi nanti (jangan bolak-balik tiap menit).")
        return 1

    SYS_DIR.mkdir(exist_ok=True)
    # Catatan: backslash di dalam {kurung} f-string baru boleh di Python 3.12+.
    # Di Python 3.10 (punya lo) harus dihitung di luar dulu.
    nama_file = re.sub(r"[^\w]+", "_", kata.lower())
    path = SYS_DIR / f"shopee_{nama_file}.json"
    lama = muat_snapshot(path)

    promo, turun = [], []
    for nama, p in produk.items():
        if "harga_asli" in p:
            diskon = (1 - p["harga"] / p["harga_asli"]) * 100
            promo.append((nama, p["harga"], p["harga_asli"], diskon,
                          "coret", p.get("url", "")))
        prev = lama.get(nama, {}).get("harga")
        if prev and p["harga"] < prev:
            turun.append((nama, p["harga"], prev,
                          (1 - p["harga"] / prev) * 100, "turun",
                          p.get("url", "")))

    path.write_text(json.dumps(produk, ensure_ascii=False, indent=2),
                    encoding="utf-8")

    print(f"\n{len(produk)} produk '{kata}' — snapshot: {path.name} "
          f"(pembanding sebelumnya: {'ada' if lama else 'belum ada'})\n")

    termurah = sorted(produk.items(), key=lambda kv: kv[1]["harga"])
    print("SEMUA PRODUK (urut dari termurah):\n")
    for nama, p in termurah:
        pendek = nama if len(nama) <= 55 else nama[:52] + "..."
        print(f"  Rp{p['harga']:>10,.0f}  {pendek}")
        if p.get("url"):
            print(f"               {p['url']}")
    print()

    tampilkan("🔥 DISKON (harga coret dari Shopee)", promo)
    tampilkan("📉 TURUN dari pantauan sebelumnya", turun)
    if not promo and not turun:
        print("Belum ada promo keliatan hari ini.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
