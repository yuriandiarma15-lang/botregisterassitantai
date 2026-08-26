import asyncio
import logging
import re

from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    FSInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.exceptions import TelegramBadRequest

from config import (
    BOT_TOKEN,
    PAYMENT_GROUP_ID,
    PUBLIC_CHANNEL_ID,
    SIGNAL_BOT,
    ADMIN_IDS
)

from packages import PACKAGE_MAP
from spreadsheet import save_member


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s "
        "[%(levelname)s] "
        "%(name)s: "
        "%(message)s"
    )
)

logger = logging.getLogger("main")


# =========================================================
# BOT
# =========================================================

bot = Bot(
    token=BOT_TOKEN
)

dp = Dispatcher()


# =========================================================
# PERFORMANCE SETTINGS
# =========================================================

# Lot default performance
LOT_SIZE = 0.01

# XAUUSD:
# 1 pip = 0.01 harga
# 100 pips = $10 untuk lot 0.01
PIP_SIZE = 0.01

# Nilai 1 pip untuk lot 0.01
# 1.00 harga = $1 untuk lot 0.01
DOLLAR_PER_PRICE = 1.0


# =========================================================
# TEMP STORAGE
# =========================================================

user_packages = {}
user_proofs = {}


# =========================================================
# HELPER
# =========================================================

def is_admin(user_id: int) -> bool:
    """
    Mengecek apakah Telegram ID adalah admin.
    """

    try:
        return int(user_id) in [
            int(x)
            for x in ADMIN_IDS
        ]

    except Exception:
        return False


# =========================================================
# SAFE CALLBACK ANSWER
# =========================================================

async def safe_callback_answer(
    callback: CallbackQuery,
    text: str = "",
    show_alert: bool = False
):
    """
    Menghindari error:
    query is too old
    response timeout expired
    """

    try:

        await callback.answer(
            text,
            show_alert=show_alert
        )

    except TelegramBadRequest as e:

        error_text = str(e).lower()

        if (
            "query is too old" in error_text
            or
            "response timeout" in error_text
            or
            "query id is invalid" in error_text
        ):

            logger.warning(
                "Callback sudah expired: %s",
                e
            )

        else:

            logger.warning(
                "Callback error: %s",
                e
            )

    except Exception as e:

        logger.warning(
            "Callback error: %s",
            e
        )


# =========================================================
# SAFE REMOVE KEYBOARD
# =========================================================

async def remove_keyboard(
    message: Message
):
    """
    Menghapus inline keyboard tanpa membuat bot crash
    jika keyboard sudah tidak ada.
    """

    try:

        await message.edit_reply_markup(
            reply_markup=None
        )

    except TelegramBadRequest as e:

        error_text = str(e).lower()

        if (
            "message is not modified"
            not in error_text
        ):

            logger.warning(
                "Gagal menghapus keyboard: %s",
                e
            )

    except Exception as e:

        logger.warning(
            "Gagal edit reply markup: %s",
            e
        )


# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def start(
    message: Message
):

    logger.info(
        "START diterima | user_id=%s | username=%s",
        message.from_user.id,
        message.from_user.username
    )

    keyboard = InlineKeyboardMarkup(

        inline_keyboard=[

            [

                InlineKeyboardButton(
                    text="🤖 AKTIFKAN AI ASSISTANT",
                    callback_data="activate"
                )

            ]

        ]

    )

    photo = FSInputFile(
        "assets/ai_example.jpg"
    )

    text = f"""
🤖 <b>XAU AI ASSISTANT GOLD</b>

👋 Halo <b>{message.from_user.first_name}</b>

Selamat datang di layanan
<b>XAU AI Assistant Gold</b>.

<blockquote>
"Partner AI pribadi untuk membantu Anda
membaca market Gold lebih cepat,
lebih terstruktur, dan tanpa noise."
</blockquote>

━━━━━━━━━━━━━━━━━━

🚀 <b>FITUR PREMIUM</b>

📈 Analisa XAUUSD Premium
🧠 Smart Money Concept
⚡ Market Intelligence
🤖 AI Assistant Telegram

━━━━━━━━━━━━━━━━━━

💎 <b>KENAPA BERBEDA?</b>

❌ Tidak perlu membaca ratusan chat signal
❌ Tidak perlu mencari informasi penting
❌ Tidak perlu takut kehilangan momentum
❌ Tidak perlu mengikuti FOMO market

Semua informasi dirangkum
langsung oleh AI Assistant Anda.

━━━━━━━━━━━━━━━━━━

🔐 <b>AKTIFKAN AKSES</b>

Dapatkan akses AI Assistant Gold
untuk membantu analisa XAUUSD
secara lebih cepat dan terstruktur.

Klik tombol di bawah untuk memulai.
"""

    await message.answer_photo(

        photo=photo,

        caption=text,

        reply_markup=keyboard,

        parse_mode="HTML"

    )


# =========================================================
# PILIH PACKAGE
# =========================================================

@dp.callback_query(
    F.data == "activate"
)
async def choose_package(
    callback: CallbackQuery
):

    await remove_keyboard(
        callback.message
    )

    keyboard = InlineKeyboardMarkup(

        inline_keyboard=[

            [

                InlineKeyboardButton(
                    text="🥇 STARTER • 1 Bulan | Rp250.000",
                    callback_data="pkg_1month"
                )

            ],

            [

                InlineKeyboardButton(
                    text="🥈 PRO • 6 Bulan | Rp500.000",
                    callback_data="pkg_6month"
                )

            ],

            [

                InlineKeyboardButton(
                    text="🥉 ELITE • 12 Bulan | Rp850.000",
                    callback_data="pkg_12month"
                )

            ],

            [

                InlineKeyboardButton(
                    text="👑 LIFETIME | Rp1.500.000",
                    callback_data="pkg_permanent"
                )

            ]

        ]

    )

    text = """
💎 <b>PILIH MEMBERSHIP PLAN</b>

<blockquote>
"Pilih paket akses yang sesuai
dengan kebutuhan trading Anda."
</blockquote>

━━━━━━━━━━━━━━━━━━

🥇 <b>STARTER</b>
📅 1 Bulan
💰 Rp250.000

🥈 <b>PRO</b>
📅 6 Bulan
💰 Rp500.000

🥉 <b>ELITE</b>
📅 12 Bulan
💰 Rp850.000

👑 <b>LIFETIME</b>
♾️ Permanent
💰 Rp1.500.000

━━━━━━━━━━━━━━━━━━

✨ <b>Semua paket mendapatkan:</b>

✅ AI Assistant Telegram
✅ Analisa XAUUSD
✅ Smart Money Analysis

Silakan pilih paket untuk melanjutkan.
"""

    await callback.message.answer(

        text,

        reply_markup=keyboard,

        parse_mode="HTML"

    )

    await safe_callback_answer(
        callback,
        "Silakan pilih paket membership"
    )


# =========================================================
# QRIS PAYMENT
# =========================================================

@dp.callback_query(
    F.data.startswith("pkg_")
)
async def show_payment(
    callback: CallbackQuery
):

    await remove_keyboard(
        callback.message
    )

    package_key = callback.data.replace(
        "pkg_",
        ""
    )

    if package_key not in PACKAGE_MAP:

        await safe_callback_answer(
            callback,
            "Paket tidak ditemukan.",
            True
        )

        return

    user_packages[
        callback.from_user.id
    ] = package_key

    data = PACKAGE_MAP[
        package_key
    ]

    payment_text = f"""
💳 <b>AKTIVASI MEMBERSHIP</b>

<blockquote>
"Selangkah lagi menuju akses
AI Assistant Gold Anda."
</blockquote>

━━━━━━━━━━━━━━━━━━

📦 <b>Paket</b>
{data['label']}

💰 <b>Total</b>
Rp {data['price']:,}

━━━━━━━━━━━━━━━━━━

📌 <b>INSTRUKSI PEMBAYARAN</b>

1️⃣ Scan QRIS
2️⃣ Lakukan pembayaran
3️⃣ Kirim bukti pembayaran ke chat ini

📸 Screenshot pembayaran
harus terlihat jelas.

━━━━━━━━━━━━━━━━━━

⏳ Admin akan melakukan
verifikasi pembayaran Anda.

Terima kasih telah bergabung
bersama <b>XAU AI Assistant Gold</b>.
"""

    await callback.message.answer_photo(

        photo=FSInputFile(
            "assets/qris.jpg"
        ),

        caption=payment_text,

        parse_mode="HTML"

    )

    await safe_callback_answer(
        callback,
        "Paket berhasil dipilih"
    )


# =========================================================
# UPLOAD REQUEST
# =========================================================

@dp.callback_query(
    F.data == "upload"
)
async def upload_request(
    callback: CallbackQuery
):

    text = """
📸 <b>UPLOAD BUKTI PEMBAYARAN</b>

<blockquote>
"Pastikan bukti pembayaran terlihat jelas
agar proses aktivasi berjalan cepat."
</blockquote>

━━━━━━━━━━━━━━━━━━

Silakan kirim:

✅ Screenshot pembayaran
atau
✅ Foto bukti transfer QRIS

Admin akan melakukan pengecekan
setelah bukti diterima.
"""

    await callback.message.answer(
        text,
        parse_mode="HTML"
    )

    await safe_callback_answer(
        callback,
        "Silakan upload bukti pembayaran"
    )


# =========================================================
# RECEIVE PAYMENT
# =========================================================

@dp.message(
    F.photo
)
async def receive_payment(
    message: Message
):

    user_proofs[
        message.from_user.id
    ] = message.photo[-1].file_id

    keyboard = InlineKeyboardMarkup(

        inline_keyboard=[

            [

                InlineKeyboardButton(
                    text="✅ KIRIM KE ADMIN",
                    callback_data="verify"
                )

            ]

        ]

    )

    text = """
✅ <b>BUKTI PEMBAYARAN DITERIMA</b>

<blockquote>
"Data pembayaran Anda sudah siap
untuk dikirim ke Admin."
</blockquote>

━━━━━━━━━━━━━━━━━━

🟡 <b>Status:</b>
Menunggu verifikasi Admin

Klik tombol di bawah untuk
mengirim permintaan pengecekan.
"""

    await message.answer(

        text,

        reply_markup=keyboard,

        parse_mode="HTML"

    )


# =========================================================
# VERIFY PAYMENT
# =========================================================

@dp.callback_query(
    F.data == "verify"
)
async def verify(
    callback: CallbackQuery
):

    user_id = callback.from_user.id

    package_key = user_packages.get(
        user_id
    )

    proof = user_proofs.get(
        user_id
    )

    if not package_key or not proof:

        await safe_callback_answer(
            callback,
            "⚠️ Data belum lengkap",
            True
        )

        return

    await remove_keyboard(
        callback.message
    )

    data = PACKAGE_MAP[
        package_key
    ]

    admin_keyboard = InlineKeyboardMarkup(

        inline_keyboard=[

            [

                InlineKeyboardButton(
                    text="✅ APPROVE",
                    callback_data=f"approve_{user_id}"
                ),

                InlineKeyboardButton(
                    text="❌ REJECT",
                    callback_data=f"reject_{user_id}"
                )

            ]

        ]

    )

    username = (

        f"@{callback.from_user.username}"

        if callback.from_user.username

        else "-"

    )

    admin_text = f"""
📥 <b>PAYMENT VERIFICATION</b>

<blockquote>
"Member baru menunggu pengecekan
aktivasi membership."
</blockquote>

━━━━━━━━━━━━━━━━━━

👤 <b>Nama</b>
{callback.from_user.full_name}

🔹 <b>Username</b>
{username}

🆔 <b>Telegram ID</b>
<code>{user_id}</code>

━━━━━━━━━━━━━━━━━━

📦 <b>Paket</b>
{data['label']}

💰 <b>Total</b>
Rp {data['price']:,}

━━━━━━━━━━━━━━━━━━

⚡ Silakan lakukan verifikasi.
"""

    await bot.send_photo(

        chat_id=PAYMENT_GROUP_ID,

        photo=proof,

        caption=admin_text,

        reply_markup=admin_keyboard,

        parse_mode="HTML"

    )

    await callback.message.answer(

        """
⏳ <b>VERIFIKASI TERKIRIM</b>

Admin sedang melakukan pengecekan
pembayaran Anda.

🟡 Status: Menunggu approval

Anda akan menerima notifikasi
setelah membership aktif.
""",

        parse_mode="HTML"

    )

    await safe_callback_answer(
        callback,
        "Dikirim ke Admin"
    )


# =========================================================
# APPROVE MEMBER
# =========================================================

@dp.callback_query(
    F.data.startswith("approve_")
)
async def approve(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user.id
    ):

        await safe_callback_answer(
            callback,
            "Anda bukan admin.",
            True
        )

        return

    await remove_keyboard(
        callback.message
    )

    user_id = int(
        callback.data.split("_")[1]
    )

    package_key = user_packages.get(
        user_id
    )

    if not package_key:

        await safe_callback_answer(
            callback,
            "Data paket tidak ditemukan",
            True
        )

        return

    try:

        user = await bot.get_chat(
            user_id
        )

    except Exception as e:

        logger.exception(
            "Gagal mengambil data user: %s",
            e
        )

        await safe_callback_answer(
            callback,
            "Gagal mengambil data user.",
            True
        )

        return

    data = PACKAGE_MAP[
        package_key
    ]

    if data["days"] == 9999:

        expired = "PERMANENT ACCESS"

    else:

        expired = (

            datetime.now()

            + timedelta(
                days=data["days"]
            )

        ).strftime(
            "%d-%m-%Y"
        )

    save_member({

        "telegram_id":
            user_id,

        "username":
            user.username or "",

        "nama":
            user.full_name,

        "paket":
            data["label"],

        "harga":
            data["price"],

        "register":
            datetime.now().strftime(
                "%d-%m-%Y"
            ),

        "expired":
            expired,

        "status":
            "ACTIVE"

    })

    button = InlineKeyboardMarkup(

        inline_keyboard=[

            [

                InlineKeyboardButton(
                    text="🤖 MASUK AI ASSISTANT",
                    url=SIGNAL_BOT
                )

            ]

        ]

    )

    member_text = f"""
🎉 <b>MEMBERSHIP AKTIF</b>

<blockquote>
"Selamat! Anda resmi menjadi bagian
dari XAU AI Assistant Gold."
</blockquote>

━━━━━━━━━━━━━━━━━━

📦 <b>Paket</b>
{data['label']}

⏳ <b>Masa Aktif</b>
{expired}

━━━━━━━━━━━━━━━━━━

🚀 <b>AKSES PREMIUM</b>

✅ AI Assistant Telegram
✅ Analisa XAUUSD
✅ Smart Money Concept
✅ Market Intelligence

━━━━━━━━━━━━━━━━━━

Klik tombol di bawah untuk mulai
menggunakan AI Assistant.

Selamat trading bersama
<b>XAU AI Assistant Gold</b> 🤖
"""

    await bot.send_message(

        chat_id=user_id,

        text=member_text,

        reply_markup=button,

        parse_mode="HTML"

    )

    await callback.message.answer(

        """
✅ <b>MEMBER BERHASIL DIAKTIFKAN</b>

Data membership telah tersimpan
dan user sudah menerima akses.
""",

        parse_mode="HTML"

    )

    await safe_callback_answer(
        callback,
        "Member aktif"
    )


# =========================================================
# REJECT MEMBER
# =========================================================

@dp.callback_query(
    F.data.startswith("reject_")
)
async def reject(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user.id
    ):

        await safe_callback_answer(
            callback,
            "Anda bukan admin.",
            True
        )

        return

    await remove_keyboard(
        callback.message
    )

    user_id = int(
        callback.data.split("_")[1]
    )

    reject_text = """
❌ <b>PEMBAYARAN BELUM DIVERIFIKASI</b>

<blockquote>
"Terjadi kendala saat melakukan
pengecekan pembayaran Anda."
</blockquote>

━━━━━━━━━━━━━━━━━━

Mohon:

📌 Periksa kembali bukti pembayaran
📌 Pastikan nominal sesuai
📌 Hubungi Admin jika membutuhkan bantuan

Admin siap membantu proses aktivasi Anda.
"""

    await bot.send_message(

        chat_id=user_id,

        text=reject_text,

        parse_mode="HTML"

    )

    await callback.message.answer(

        """
❌ <b>PAYMENT DITOLAK</b>

User telah menerima notifikasi
bahwa pembayaran belum dapat
diverifikasi.
""",

        parse_mode="HTML"

    )

    await safe_callback_answer(
        callback,
        "Payment rejected"
    )


# =========================================================
# ADMIN: SEND MESSAGE
# =========================================================

@dp.message(
    F.text.startswith("/sent")
)
async def sent_to_user(
    message: Message
):

    if not is_admin(
        message.from_user.id
    ):

        return

    parts = message.text.split(
        maxsplit=2
    )

    if len(parts) < 3:

        await message.answer(

            "⚠️ Format salah.\n\n"
            "Gunakan:\n"
            "<code>/sent [telegram_id] [pesan]</code>",

            parse_mode="HTML"

        )

        return

    target_id_str = parts[1]

    text_to_send = parts[2]

    if not target_id_str.isdigit():

        await message.answer(
            "⚠️ Telegram ID harus berupa angka."
        )

        return

    target_id = int(
        target_id_str
    )

    try:

        await bot.send_message(

            chat_id=target_id,

            text=text_to_send

        )

        await message.answer(

            f"""
✅ <b>PESAN BERHASIL DIKIRIM</b>

🆔 Target:
<code>{target_id}</code>

💬 Pesan:
{text_to_send}
""",

            parse_mode="HTML"

        )

    except Exception as e:

        await message.answer(

            f"""
❌ <b>PESAN GAGAL DIKIRIM</b>

🆔 Target:
<code>{target_id}</code>

⚠️ Error:
<code>{e}</code>
""",

            parse_mode="HTML"

        )


# =========================================================
# PERFORMANCE PARSER
# =========================================================

def parse_date_from_text(
    text: str
):
    """
    Membaca tanggal dari:

    📅 26 Agustus 2026

    atau:

    📅 26 August 2026

    Jika tidak ditemukan,
    menggunakan tanggal hari ini.
    """

    pattern = re.compile(
        r"(\d{1,2})\s+"
        r"(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember|"
        r"January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+(\d{4})",
        re.IGNORECASE
    )

    match = pattern.search(
        text
    )

    if not match:

        return datetime.now()

    day = int(
        match.group(1)
    )

    month_name = (
        match.group(2).lower()
    )

    year = int(
        match.group(3)
    )

    months = {

        "januari": 1,
        "februari": 2,
        "maret": 3,
        "april": 4,
        "mei": 5,
        "juni": 6,
        "juli": 7,
        "agustus": 8,
        "september": 9,
        "oktober": 10,
        "november": 11,
        "desember": 12,

        "january": 1,
        "february": 2,
        "march": 3,
        "may": 5,
        "june": 6,
        "july": 7,
        "august": 8,
        "october": 10,
        "december": 12
    }

    month = months.get(
        month_name
    )

    if not month:

        return datetime.now()

    try:

        return datetime(
            year,
            month,
            day
        )

    except ValueError:

        return datetime.now()


# =========================================================
# PERFORMANCE PARSER
# =========================================================

def parse_performance(
    text: str
):
    """
    Membaca beberapa format:

    🕐 07:00 → Entry 4637.00 → TP1 4647.00

    🕐 08:00 → Entry 4637.00 → TP2 4657.00

    🕐 09:00 → Entry 4637.00 → SL 4627.00

    🕐 10:00 → PENDING

    🕐 11:00 → NO SIGNAL

    Hasil:

    [
        {
            "time": "07:00",
            "status": "TP1",
            "entry": 4637.00,
            "target": 4647.00
        }
    ]
    """

    results = []

    lines = text.splitlines()

    for line in lines:

        line = line.strip()

        if not line:

            continue

        # -------------------------------------------------
        # JAM
        # -------------------------------------------------

        time_match = re.search(
            r"(\d{1,2}:\d{2})",
            line
        )

        if not time_match:

            continue

        signal_time = time_match.group(1)

        # -------------------------------------------------
        # NO SIGNAL
        # -------------------------------------------------

        if re.search(
            r"\bNO\s*SIGNAL\b",
            line,
            re.IGNORECASE
        ):

            results.append({

                "time":
                    signal_time,

                "status":
                    "NO SIGNAL",

                "entry":
                    None,

                "target":
                    None

            })

            continue

        # -------------------------------------------------
        # PENDING
        # -------------------------------------------------

        if re.search(
            r"\bPENDING\b",
            line,
            re.IGNORECASE
        ):

            # Coba ambil entry jika ada
            entry_match = re.search(

                r"(?:ENTRY|Entry)"
                r"\s*[:=]?\s*"
                r"(\d+(?:\.\d+)?)",

                line,
                re.IGNORECASE

            )

            entry = (

                float(
                    entry_match.group(1)
                )

                if entry_match

                else None

            )

            results.append({

                "time":
                    signal_time,

                "status":
                    "PENDING",

                "entry":
                    entry,

                "target":
                    None

            })

            continue

        # -------------------------------------------------
        # ENTRY
        # -------------------------------------------------

        entry_match = re.search(

            r"(?:ENTRY|Entry)"
            r"\s*[:=]?\s*"
            r"(\d+(?:\.\d+)?)",

            line,

            re.IGNORECASE

        )

        entry = (

            float(
                entry_match.group(1)
            )

            if entry_match

            else None

        )

        # -------------------------------------------------
        # TP1
        # -------------------------------------------------

        tp1_match = re.search(

            r"(?:TP1|TP\s*1)"
            r"\s*[:=]?\s*"
            r"(\d+(?:\.\d+)?)",

            line,

            re.IGNORECASE

        )

        if tp1_match:

            results.append({

                "time":
                    signal_time,

                "status":
                    "TP1",

                "entry":
                    entry,

                "target":
                    float(
                        tp1_match.group(1)
                    )

            })

            continue

        # -------------------------------------------------
        # TP2
        # -------------------------------------------------

        tp2_match = re.search(

            r"(?:TP2|TP\s*2)"
            r"\s*[:=]?\s*"
            r"(\d+(?:\.\d+)?)",

            line,

            re.IGNORECASE

        )

        if tp2_match:

            results.append({

                "time":
                    signal_time,

                "status":
                    "TP2",

                "entry":
                    entry,

                "target":
                    float(
                        tp2_match.group(1)
                    )

            })

            continue

        # -------------------------------------------------
        # SL
        # -------------------------------------------------

        sl_match = re.search(

            r"\bSL\b"
            r"\s*[:=]?\s*"
            r"(\d+(?:\.\d+)?)",

            line,

            re.IGNORECASE

        )

        if sl_match:

            results.append({

                "time":
                    signal_time,

                "status":
                    "SL",

                "entry":
                    entry,

                "target":
                    float(
                        sl_match.group(1)
                    )

            })

            continue

    return results


# =========================================================
# CALCULATE PIPS
# =========================================================

def calculate_pips(
    entry,
    target,
    status
):
    """
    Menghitung jarak Entry -> target.

    XAUUSD:
    1 pip = 0.01

    Contoh:

    Entry 4637
    TP 4647

    Jarak = 10.00
    Pips = 1000

    PNL lot 0.01 = +$10.00

    Untuk SELL/BUY kita gunakan jarak absolut.
    """

    if entry is None or target is None:

        return 0.0

    distance = abs(
        target - entry
    )

    pips = distance / PIP_SIZE

    # TP = positif
    if status in (
        "TP1",
        "TP2"
    ):

        return pips

    # SL = negatif
    if status == "SL":

        return -pips

    return 0.0


# =========================================================
# CALCULATE PNL USD
# =========================================================

def calculate_pnl_usd(
    pips: float
):
    """
    Untuk XAUUSD lot 0.01:

    100 pips = $1?

    Catatan:
    Kita mengikuti definisi user:
    100 pips = $10 untuk lot 0.01.

    Jadi:
    $10 / 100 pips
    = $0.10 per pip.
    """

    return pips * 0.10


# =========================================================
# FORMAT PRICE
# =========================================================

def format_price(
    price
):

    if price is None:

        return "-"

    return f"{price:.2f}"


# =========================================================
# FORMAT PIPS
# =========================================================

def format_pips(
    pips
):

    if pips > 0:

        return f"+{pips:.0f}"

    if pips < 0:

        return f"{pips:.0f}"

    return "0"


# =========================================================
# FORMAT USD
# =========================================================

def format_usd(
    amount
):

    if amount > 0:

        return f"+${amount:.2f}"

    if amount < 0:

        return f"-${abs(amount):.2f}"

    return "$0.00"


# =========================================================
# BUILD PERFORMANCE MESSAGE
# =========================================================

def build_performance_message(
    performance,
    original_text
):

    total = len(
        performance
    )

    wins = sum(

        1

        for item in performance

        if item["status"] in (
            "TP1",
            "TP2"
        )

    )

    losses = sum(

        1

        for item in performance

        if item["status"] == "SL"

    )

    pending = sum(

        1

        for item in performance

        if item["status"] == "PENDING"

    )

    no_signal = sum(

        1

        for item in performance

        if item["status"] == "NO SIGNAL"

    )

    closed_signals = (
        wins
        +
        losses
    )

    if closed_signals:

        winrate = (
            wins
            /
            closed_signals
        ) * 100

    else:

        winrate = 0

    total_pips = 0.0
    total_pnl = 0.0

    date_value = parse_date_from_text(
        original_text
    )

    # -----------------------------------------------------
    # TANGGAL INDONESIA
    # -----------------------------------------------------

    months = {

        1: "Januari",
        2: "Februari",
        3: "Maret",
        4: "April",
        5: "Mei",
        6: "Juni",
        7: "Juli",
        8: "Agustus",
        9: "September",
        10: "Oktober",
        11: "November",
        12: "Desember"

    }

    weekdays = {

        0: "Senin",
        1: "Selasa",
        2: "Rabu",
        3: "Kamis",
        4: "Jumat",
        5: "Sabtu",
        6: "Minggu"

    }

    date_text = (
        f"{weekdays[date_value.weekday()]}, "
        f"{date_value.day} "
        f"{months[date_value.month]} "
        f"{date_value.year}"
    )

    # -----------------------------------------------------
    # BUILD SIGNAL LINES
    # -----------------------------------------------------

    lines = []

    for item in performance:

        signal_time = item["time"]

        status = item["status"]

        entry = item["entry"]

        target = item["target"]

        # ---------------------------------------------
        # TP1
        # ---------------------------------------------

        if status == "TP1":

            pips = calculate_pips(
                entry,
                target,
                status
            )

            pnl = calculate_pnl_usd(
                pips
            )

            total_pips += pips
            total_pnl += pnl

            lines.append(

                f"🕐 <b>{signal_time}</b> → "
                f"Entry <code>{format_price(entry)}</code>\n"
                f"🎯 TP1 <code>{format_price(target)}</code> "
                f"→ ✅ <b>HIT</b> "
                f"({format_pips(pips)} Pips / "
                f"{format_usd(pnl)})"

            )

        # ---------------------------------------------
        # TP2
        # ---------------------------------------------

        elif status == "TP2":

            pips = calculate_pips(
                entry,
                target,
                status
            )

            pnl = calculate_pnl_usd(
                pips
            )

            total_pips += pips
            total_pnl += pnl

            lines.append(

                f"🕐 <b>{signal_time}</b> → "
                f"Entry <code>{format_price(entry)}</code>\n"
                f"🎯 TP2 <code>{format_price(target)}</code> "
                f"→ ✅ <b>HIT</b> "
                f"({format_pips(pips)} Pips / "
                f"{format_usd(pnl)})"

            )

        # ---------------------------------------------
        # SL
        # ---------------------------------------------

        elif status == "SL":

            pips = calculate_pips(
                entry,
                target,
                status
            )

            pnl = calculate_pnl_usd(
                pips
            )

            total_pips += pips
            total_pnl += pnl

            lines.append(

                f"🕐 <b>{signal_time}</b> → "
                f"Entry <code>{format_price(entry)}</code>\n"
                f"🛑 SL <code>{format_price(target)}</code> "
                f"→ ❌ <b>HIT</b> "
                f"({format_pips(pips)} Pips / "
                f"{format_usd(pnl)})"

            )

        # ---------------------------------------------
        # PENDING
        # ---------------------------------------------

        elif status == "PENDING":

            if entry is not None:

                lines.append(

                    f"🕐 <b>{signal_time}</b> → "
                    f"⏳ <b>PENDING</b>\n"
                    f"📌 Entry <code>{format_price(entry)}</code>"

                )

            else:

                lines.append(

                    f"🕐 <b>{signal_time}</b> → "
                    f"⏳ <b>PENDING</b>"

                )

        # ---------------------------------------------
        # NO SIGNAL
        # ---------------------------------------------

        elif status == "NO SIGNAL":

            lines.append(

                f"🕐 <b>{signal_time}</b> → "
                f"⚪ <b>NO SIGNAL</b>"

            )

    performance_lines = "\n".join(
        lines
    )

    # -----------------------------------------------------
    # PNL TEXT
    # -----------------------------------------------------

    pnl_text = format_usd(
        total_pnl
    )

    pips_text = format_pips(
        total_pips
    )

    # -----------------------------------------------------
    # FINAL MESSAGE
    # -----------------------------------------------------

    return f"""
📊 <b>XAU AI ASSISTANT GOLD</b>
━━━━━━━━━━━━━━━━━━
<b>PERFORMANCE {total} SIGNAL</b>

📅 <b>{date_text}</b>

{performance_lines}

━━━━━━━━━━━━━━━━━━

📈 <b>HASIL PERFORMANCE</b>

📊 Total Signal : <b>{total}</b>
✅ Win          : <b>{wins}</b>
❌ Loss         : <b>{losses}</b>
⏳ Pending      : <b>{pending}</b>
⚪ No Signal    : <b>{no_signal}</b>

🎯 Winrate      : <b>{winrate:.0f}%</b>

📏 Total Pips   : <b>{pips_text} Pips</b>
💰 PNL          : <b>{pnl_text}</b>

📦 Lot          : <b>0.01</b>

━━━━━━━━━━━━━━━━━━

🤖 <b>AKTIFKAN AI ASSISTANT GOLD</b>

Dapatkan akses AI Assistant Gold
untuk membantu membaca market
XAUUSD secara lebih terstruktur.

👉 <b>@Intradayxauusd_bot</b>
"""


# =========================================================
# PERFORMANCE ADMIN
# =========================================================

@dp.message(
    F.text
)
async def performance_to_channel(
    message: Message
):

    # Jangan proses command
    if message.text.startswith("/"):

        return

    # Hanya admin
    if not is_admin(
        message.from_user.id
    ):

        return

    text = message.text.strip()

    performance = parse_performance(
        text
    )

    # Tidak ada data performance
    if not performance:

        return

    logger.info(
        "Performance diterima | admin=%s | signal=%s",
        message.from_user.id,
        len(performance)
    )

    try:

        final_message = build_performance_message(

            performance,

            text

        )

        await bot.send_message(

            chat_id=PUBLIC_CHANNEL_ID,

            text=final_message,

            parse_mode="HTML"

        )

        logger.info(

            "Performance berhasil dikirim | "
            "signals=%s | channel=%s",

            len(performance),

            PUBLIC_CHANNEL_ID

        )

        # ---------------------------------------------
        # KONFIRMASI ADMIN
        # ---------------------------------------------

        closed = sum(

            1

            for item in performance

            if item["status"] in (
                "TP1",
                "TP2",
                "SL"
            )

        )

        await message.answer(

            f"""
✅ <b>PERFORMANCE TERKIRIM</b>

📊 Total : <b>{len(performance)}</b>
📈 Closed : <b>{closed}</b>

📢 Channel:
<code>{PUBLIC_CHANNEL_ID}</code>

Performance berhasil diposting
ke Channel Umum.
""",

            parse_mode="HTML"

        )

    except Exception as e:

        logger.exception(
            "Gagal mengirim performance ke channel."
        )

        await message.answer(

            f"""
❌ <b>GAGAL MENGIRIM PERFORMANCE</b>

⚠️ Error:
<code>{e}</code>

Pastikan bot sudah menjadi
<b>ADMIN</b> di Channel Umum
dan memiliki izin posting.
""",

            parse_mode="HTML"

        )


# =========================================================
# MAIN
# =========================================================

async def main():

    logger.info(
        "🤖 XAU AI Assistant Bot Running..."
    )

    logger.info(
        "📊 Performance → Channel aktif"
    )

    logger.info(
        "📢 Public Channel ID: %s",
        PUBLIC_CHANNEL_ID
    )

    logger.info(
        "💳 Payment Group ID: %s",
        PAYMENT_GROUP_ID
    )

    logger.info(
        "👨‍💼 Admin IDs: %s",
        ADMIN_IDS
    )

    logger.info(
        "📦 Performance Lot: %.2f",
        LOT_SIZE
    )

    await dp.start_polling(
        bot
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        logger.info(
            "Bot dihentikan manual."
        )
