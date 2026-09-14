from datetime import datetime


# =========================================================
# PROMO PAKET 3 TAHUN
#
# Berlaku sampai tanggal & jam ini (waktu server / WIB).
# NILAI INI HARUS SAMA dengan target countdown di landing
# page (getTargetDate() di script landing.html), supaya
# harga di website dan harga QRIS di bot selalu sinkron.
# =========================================================

PROMO_3YEAR_DEADLINE = datetime(2026, 9, 30, 23, 59, 59)
PROMO_3YEAR_PRICE = 999000
NORMAL_3YEAR_PRICE = 1500000


PACKAGE_MAP = {
    "1month": {
        "label": "1 Bulan",
        "price": 299000,
        "days": 30
    },
    "6month": {
        "label": "6 Bulan",
        "price": 500000,
        "days": 180
    },
    "12month": {
        "label": "12 Bulan",
        "price": 900000,
        "days": 365
    },
    "permanent": {
        "label": "3 Tahun",
        "price": NORMAL_3YEAR_PRICE,   # harga normal / fallback setelah promo berakhir
        "days": 1095
    }
}


def get_active_price(package_key: str) -> int:
    """
    Hitung harga AKTIF untuk sebuah paket saat ini.

    Untuk paket "permanent" (3 Tahun), selama waktu sekarang
    masih sebelum PROMO_3YEAR_DEADLINE, harga otomatis
    Rp999.000. Setelah lewat deadline, otomatis kembali ke
    harga normal Rp1.500.000 — tidak perlu ubah kode lagi
    tiap kali promo berakhir.

    Paket lain memakai harga tetap dari PACKAGE_MAP.
    """

    if package_key not in PACKAGE_MAP:
        raise KeyError(f"Package key tidak dikenali: {package_key}")

    if package_key == "permanent" and datetime.now() <= PROMO_3YEAR_DEADLINE:
        return PROMO_3YEAR_PRICE

    return PACKAGE_MAP[package_key]["price"]


def is_promo_3year_active() -> bool:
    """Cek apakah promo 3 Tahun sedang berjalan (dipakai untuk badge/teks di bot)."""

    return datetime.now() <= PROMO_3YEAR_DEADLINE
