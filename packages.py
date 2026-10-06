from datetime import datetime


# =========================================================
# PACKAGE
# =========================================================

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
        "price": 1500000,
        "days": 1095
    }
}


def get_active_price(package_key: str) -> int:
    """
    Mengambil harga aktif berdasarkan paket.
    Semua paket menggunakan harga tetap.
    """

    if package_key not in PACKAGE_MAP:
        raise KeyError(
            f"Package key tidak dikenali: {package_key}"
        )

    return PACKAGE_MAP[package_key]["price"]
