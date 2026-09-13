"""
Probe kecil: buktiin Playwright bisa ngeliat harga yang requests nggak bisa.

Cara jalanin:
    python probe_tokped.py "sepatu futsal"
"""

import re
import sys

from playwright.sync_api import sync_playwright


def main() -> int:
    kata = " ".join(sys.argv[1:]) or "sepatu futsal"
    url = f"https://www.tokopedia.com/search?q={kata.replace(' ', '+')}"
    print(f"Buka: {url}")

    with sync_playwright() as p:
        # headless=False biar lo LIAT browsernya kebuka dan jalan sendiri —
        # ini bedanya paling berasa sama requests yang kerjanya diem-dieman.
        browser = p.chromium.launch(headless=False)
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
            locale="id-ID",
        )
        page.goto(url, wait_until="domcontentloaded", timeout=30000)

        #Inti dari browser automation: TUNGGU elemennya beneran muncul,
        #bukan langsung baca HTML mentah. JavaScript-nya dikasih waktu jalan.
        try:
            page.wait_for_selector("[data-testid='product-card']", timeout=15000)
        except Exception:
            print("Selector kartu produk nggak muncul — kemungkinan kena "
                  "halaman verifikasi/captcha.")
            print("Judul halaman:", page.title())

        teks = page.inner_text("body")
        bersihkan = re.sub(r"\s+", " ", teks)
        # cari pola harga rupiah: "Rp123.456"
        harga = re.findall(r"Rp[\d.]{5,12}", bersihkan)
        print(f"Harga rupiah yang keliatan di browser: {len(harga)} buah")
        print("Contoh:", harga[:10])
        print("1000 char pertama teks halaman:")
        print(bersihkan[:1000])

        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
