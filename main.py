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

from packages import PACKAGE_MAP, get_active_price

from spreadsheet import (
    save_member,
    get_expired_group_members,
    update_member_status
)


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
# PRIVATE GROUP
# =========================================================

# Grup Diskusi & Sharing
PRIVATE_GROUP_ID = -1003949834371


# =========================================================
# TEMP STORAGE
# =========================================================

# Paket yang dipilih user
user_packages = {}

# Bukti pembayaran
user_proofs = {}

# Data Nama / Broker / Gmail
#
# Data ini HANYA disimpan sementara.
# TIDAK disimpan ke Google Sheets.
#
user_broker_data = {}

# Menandakan user sedang diminta
# mengirim data Nama / Broker / Gmail
user_profile_pending = {}


# =========================================================
# PERFORMANCE SETTINGS
# =========================================================

PERFORMANCE_LOT = 0.01

DOLLAR_PER_PIP_LOT_001 = 0.10


# =========================================================
# PERFORMANCE RESULT
# =========================================================

TP1_PIPS = 70
TP2_PIPS = 150
SL_PIPS = 50


# =========================================================
# PACKAGE ACCESS
# =========================================================

def package_has_group_access(
    package_key: str
) -> bool:

    return package_key in (
        "6month",
        "12month",
        "permanent"
    )


# =========================================================
# PACKAGE DATA
# =========================================================

def get_package_data(
    package_key: str
) -> dict:

    data = dict(
        PACKAGE_MAP[package_key]
    )

    data["price"] = get_active_price(
        package_key
    )

    return data


# =========================================================
# ADMIN
# =========================================================

def is_admin(
    user_id: int
) -> bool:

    try:

        return int(user_id) in [
            int(x)
            for x in ADMIN_IDS
        ]

    except Exception:

        return False


# =========================================================
# SAFE CALLBACK
# =========================================================

async def safe_callback_answer(
    callback: CallbackQuery,
    text: str = "",
    show_alert: bool = False
):

    try:

        await callback.answer(
            text,
            show_alert=show_alert
        )

    except TelegramBadRequest:

        pass

    except Exception:

        pass


# =========================================================
# REMOVE KEYBOARD
# =========================================================

async def remove_keyboard(
    message: Message
):

    try:

        await message.edit_reply_markup(
            reply_markup=None
        )

    except TelegramBadRequest as e:

        error_text = str(e).lower()

        if "message is not modified" not in error_text:

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
# FORMAT RUPIAH
# =========================================================

def format_rupiah(
    value
):

    try:

        return f"{int(value):,}".replace(
            ",",
            "."
        )

    except Exception:

        return str(value)


# =========================================================
# FORMAT USD
# =========================================================

def format_usd(
    value
):

    if value > 0:

        return f"+${value:.2f}"

    if value < 0:

        return f"-${abs(value):.2f}"

    return "$0.00"


# =========================================================
# FORMAT PRICE
# =========================================================

def format_price(
    value
):

    if value is None:

        return "-"

    return f"{value:.2f}"


# =========================================================
# MONTH INDONESIA
# =========================================================

MONTHS_ID = {

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


def format_date_indonesia(
    date_obj
):

    return (
        f"{date_obj.day} "
        f"{MONTHS_ID[date_obj.month]} "
        f"{date_obj.year}"
    )


# =========================================================
# PARSE DATE
# =========================================================

def parse_performance_date(
    text: str
):

    patterns = [

        r"(\d{2})-(\d{2})-(\d{4})",

        r"(\d{2})/(\d{2})/(\d{4})",

        r"(\d{4})-(\d{2})-(\d{2})",

        r"(\d{4})/(\d{2})/(\d{2})"

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text
        )

        if not match:

            continue

        try:

            values = [
                int(x)
                for x in match.groups()
            ]

            if len(values) != 3:

                continue

            if values[0] > 31:

                year = values[0]
                month = values[1]
                day = values[2]

            else:

                day = values[0]
                month = values[1]
                year = values[2]

            return datetime(
                year,
                month,
                day
            )

        except ValueError:

            return None

    return None


# =========================================================
# PARSE PERFORMANCE
# =========================================================

def parse_performance(
    text: str
):

    results = []

    lines = text.splitlines()

    for raw_line in lines:

        line = raw_line.strip()

        if not line:

            continue

        line = line.replace(
            "📅",
            ""
        )

        line = line.replace(
            "`",
            ""
        )

        line = line.strip()

        # =================================================
        # SKIP DATE ONLY
        # =================================================

        if re.search(
            r"\d{2}[-/]\d{2}[-/]\d{4}",
            line
        ):

            if not re.search(
                r"\d{1,2}:\d{2}",
                line
            ):

                continue

        # =================================================
        # PENDING
        # =================================================

        pending_match = re.search(

            r"(?P<time>\d{1,2}:\d{2})"
            r"\s*(?:\||-)?\s*"
            r"PENDING",

            line,

            re.IGNORECASE

        )

        if pending_match:

            results.append({

                "direction": None,

                "time":
                    pending_match.group(
                        "time"
                    ),

                "entry": None,

                "hit_price": None,

                "result":
                    "PENDING"

            })

            continue

        # =================================================
        # NO SIGNAL
        # =================================================

        no_signal_match = re.search(

            r"(?P<time>\d{1,2}:\d{2})"
            r"\s*(?:\||-)?\s*"
            r"NO\s*SIGNAL",

            line,

            re.IGNORECASE

        )

        if no_signal_match:

            results.append({

                "direction": None,

                "time":
                    no_signal_match.group(
                        "time"
                    ),

                "entry": None,

                "hit_price": None,

                "result":
                    "NO SIGNAL"

            })

            continue

        # =================================================
        # SIGNAL
        # =================================================

        signal_match = re.search(

            r"^\s*"

            r"(?P<direction>[BS])"

            r"\s+"

            r"(?P<time>\d{1,2}:\d{2})"

            r"\s*\|\s*"

            r"(?P<entry>\d+(?:\.\d+)?)"

            r"\s*\|\s*"

            r"(?P<hit>\d+(?:\.\d+)?)"

            r"\s*\|\s*"

            r"(?P<result>TP1|TP2|SL)"

            r"\s*$",

            line,

            re.IGNORECASE

        )

        if signal_match:

            try:

                entry = float(
                    signal_match.group(
                        "entry"
                    )
                )

                hit_price = float(
                    signal_match.group(
                        "hit"
                    )
                )

            except Exception:

                logger.warning(
                    "Harga tidak valid: %s",
                    line
                )

                continue

            results.append({

                "direction":
                    signal_match.group(
                        "direction"
                    ).upper(),

                "time":
                    signal_match.group(
                        "time"
                    ),

                "entry":
                    entry,

                "hit_price":
                    hit_price,

                "result":
                    signal_match.group(
                        "result"
                    ).upper()

            })

            continue

        logger.warning(
            "Performance line tidak dikenali: %s",
            line
        )

    return results


# =========================================================
# RESULT PIPS
# =========================================================

def get_result_pips(
    direction,
    entry,
    hit_price
):

    try:

        direction = str(
            direction
        ).upper().strip()

        entry = float(entry)
        hit_price = float(hit_price)

        if direction == "B":

            return round(
                (hit_price - entry) * 10
            )

        if direction == "S":

            return round(
                (entry - hit_price) * 10
            )

        return 0

    except Exception:

        return 0


# =========================================================
# RESULT PNL
# =========================================================

def get_result_pnl(
    direction,
    entry,
    hit_price
):

    pips = get_result_pips(
        direction,
        entry,
        hit_price
    )

    return (
        pips
        * DOLLAR_PER_PIP_LOT_001
    )


# =========================================================
# BUILD PERFORMANCE
# =========================================================

def build_performance_message(
    performance,
    performance_date=None
):

    signals = [

        item

        for item in performance

        if item["result"] in (
            "TP1",
            "TP2",
            "SL"
        )

    ]

    total = len(
        signals
    )

    tp1_count = sum(

        1

        for item in signals

        if item["result"] == "TP1"

    )

    tp2_count = sum(

        1

        for item in signals

        if item["result"] == "TP2"

    )

    sl_count = sum(

        1

        for item in signals

        if item["result"] == "SL"

    )

    pending_count = sum(

        1

        for item in performance

        if item["result"] == "PENDING"

    )

    no_signal_count = sum(

        1

        for item in performance

        if item["result"] == "NO SIGNAL"

    )

    wins = (
        tp1_count
        + tp2_count
    )

    if total > 0:

        winrate = (
            wins / total
        ) * 100

    else:

        winrate = 0

    total_pips = sum(

        get_result_pips(
            item["direction"],
            item["entry"],
            item["hit_price"]
        )

        for item in signals

    )

    pnl = sum(

        get_result_pnl(
            item["direction"],
            item["entry"],
            item["hit_price"]
        )

        for item in signals

    )

    if performance_date is None:

        performance_date = datetime.now()

    date_text = format_date_indonesia(
        performance_date
    )

    lines = []

    for item in performance:

        direction = item["direction"]
        time = item["time"]
        result = item["result"]

        if result == "PENDING":

            lines.append(
                f"- 🕐 {time} | "
                f"⏳ <b>PENDING</b>"
            )

            continue

        if result == "NO SIGNAL":

            lines.append(
                f"- 🕐 {time} | "
                f"⚪ <b>NO SIGNAL</b>"
            )

            continue

        entry = format_price(
            item["entry"]
        )

        hit_price = format_price(
            item["hit_price"]
        )

        if result == "TP1":

            result_icon = "✅ TP1"

        elif result == "TP2":

            result_icon = "🏆 TP2"

        else:

            result_icon = "❌ SL"

        lines.append(

            f"{direction} 🕐 {time} | "
            f"{entry} → {hit_price} | "
            f"{result_icon}"

        )

    performance_lines = "\n".join(
        lines
    )

    pnl_text = format_usd(
        pnl
    )

    return f"""
📊 <b>XAU AI ASSISTANT GOLD</b>
━━━━━━━━━━━━━━━━━━
<b>PERFORMANCE {total} SIGNAL</b>

📅 <b>{date_text}</b>

{performance_lines}

━━━━━━━━━━━━━━━━━━
📈 <b>HASIL</b>

📊 Signal      : <b>{total}</b>
✅ TP1         : <b>{tp1_count}</b>
🏆 TP2         : <b>{tp2_count}</b>
❌ SL          : <b>{sl_count}</b>
⏳ Pending     : <b>{pending_count}</b>
⚪ No Signal   : <b>{no_signal_count}</b>

🎯 Winrate     : <b>{winrate:.0f}%</b>
📏 Total       : <b>{total_pips:+d} Pips</b>
💰 PNL         : <b>{pnl_text}</b>

━━━━━━━━━━━━━━━━━━
🤖 <b>AI ASSISTANT GOLD</b>

Analisa XAUUSD berbasis AI
+ Smart Money Concept.

🚀 <b>Dapatkan signal AI Assistant Gold
secara realtime dan terstruktur.</b>
"""


# =========================================================
# PACKAGE KEYBOARD
# =========================================================

def build_package_keyboard() -> InlineKeyboardMarkup:

    harga_3tahun = format_rupiah(
        get_active_price("permanent")
    )

    return InlineKeyboardMarkup(

        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text=(
                        "🥇 STARTER • 1 Bulan | "
                        "Rp299.000"
                    ),
                    callback_data="pkg_1month"
                )
            ],

            [
                InlineKeyboardButton(
                    text=(
                        "🥈 PRO • 6 Bulan | "
                        "Rp500.000"
                    ),
                    callback_data="pkg_6month"
                )
            ],

            [
                InlineKeyboardButton(
                    text=(
                        "🥉 ELITE • 12 Bulan | "
                        "Rp850.000"
                    ),
                    callback_data="pkg_12month"
                )
            ],

            [
                InlineKeyboardButton(
                    text=(
                        f"👑 3 TAHUN | "
                        f"Rp{harga_3tahun}"
                    ),
                    callback_data="pkg_permanent"
                )
            ]

        ]

    )


# =========================================================
# PACKAGE CHOICE TEXT
# =========================================================

def build_package_choice_text() -> str:

    harga_3tahun = format_rupiah(
        get_active_price("permanent")
    )

    return f"""
💎 <b>PILIH MEMBERSHIP PLAN</b>

━━━━━━━━━━━━━━━━━━

🥇 <b>STARTER</b>
📅 1 Bulan
💰 <b>Rp299.000</b>

🤖 AI Assistant Telegram

━━━━━━━━━━━━━━━━━━

🥈 <b>PRO</b>
📅 6 Bulan
💰 <b>Rp500.000</b>

🤖 AI Assistant
👥 Grup Diskusi &amp; Sharing

━━━━━━━━━━━━━━━━━━

🥉 <b>ELITE</b>
📅 12 Bulan
💰 <b>Rp850.000</b>

🤖 AI Assistant
👥 Grup Diskusi &amp; Sharing

━━━━━━━━━━━━━━━━━━

👑 <b>3 TAHUN</b>
📅 3 Tahun
💰 <b>Rp{harga_3tahun}</b>

🤖 AI Assistant
👥 Grup Diskusi &amp; Sharing

━━━━━━━━━━━━━━━━━━

✨ <b>Semua paket mendapatkan:</b>

✅ AI Assistant Telegram
✅ Analisa XAUUSD
✅ Smart Money Analysis

👥 Paket 6 Bulan, 12 Bulan &amp;
3 Tahun mendapatkan akses
Grup Diskusi &amp; Sharing.

Silakan pilih paket.
"""


# =========================================================
# SEND PAYMENT INFO
# =========================================================

async def send_payment_info(
    user_id: int,
    chat_id: int,
    package_key: str
) -> bool:

    if package_key not in PACKAGE_MAP:

        logger.warning(
            "Package key tidak dikenali: %s",
            package_key
        )

        return False

    user_packages[
        user_id
    ] = package_key

    # Reset state pembayaran sebelumnya
    user_proofs.pop(
        user_id,
        None
    )

    user_broker_data.pop(
        user_id,
        None
    )

    user_profile_pending.pop(
        user_id,
        None
    )

    data = get_package_data(
        package_key
    )

    group_text = ""

    if package_has_group_access(
        package_key
    ):

        group_text = """
👥 <b>Grup Diskusi &amp; Sharing</b>
Akses grup diberikan setelah pembayaran
disetujui Admin.
"""

    payment_text = f"""
💳 <b>AKTIVASI MEMBERSHIP</b>

━━━━━━━━━━━━━━━━━━

📦 <b>Paket</b>
{data['label']}

💰 <b>Total</b>
Rp {format_rupiah(data['price'])}

━━━━━━━━━━━━━━━━━━

🤖 <b>AI ASSISTANT</b>

Akses AI Assistant Telegram
untuk analisa XAUUSD.

{group_text}
━━━━━━━━━━━━━━━━━━

📌 <b>INSTRUKSI PEMBAYARAN</b>

1️⃣ Scan QRIS
2️⃣ Lakukan pembayaran
3️⃣ Kirim bukti pembayaran ke chat ini

📸 Screenshot pembayaran
harus terlihat jelas.

━━━━━━━━━━━━━━━━━━

⏳ Setelah bukti diterima,
kamu akan diminta mengisi data
Nama, Broker dan Gmail.

Terima kasih telah bergabung
bersama <b>XAU AI Assistant Gold</b>.
"""

    await bot.send_photo(

        chat_id=chat_id,

        photo=FSInputFile(
            "assets/qris.jpg"
        ),

        caption=payment_text,

        parse_mode="HTML"

    )

    return True


# =========================================================
# START
# =========================================================

@dp.message(
    CommandStart()
)
async def start(
    message: Message
):

    logger.info(
        "START diterima | user_id=%s | username=%s | text=%s",
        message.from_user.id,
        message.from_user.username,
        message.text
    )

    payload = None

    if message.text and " " in message.text:

        payload = message.text.split(
            maxsplit=1
        )[1].strip()

    if payload and payload in PACKAGE_MAP:

        logger.info(
            "Deep-link paket | user_id=%s | package=%s",
            message.from_user.id,
            payload
        )

        sent = await send_payment_info(

            user_id=message.from_user.id,

            chat_id=message.chat.id,

            package_key=payload

        )

        if sent:

            return

    await message.answer(

        build_package_choice_text(),

        reply_markup=build_package_keyboard(),

        parse_mode="HTML"

    )


# =========================================================
# PILIH PACKAGE
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

    sent = await send_payment_info(

        user_id=callback.from_user.id,

        chat_id=callback.message.chat.id,

        package_key=package_key

    )

    if not sent:

        await safe_callback_answer(

            callback,

            "Paket tidak ditemukan.",

            True

        )

        return

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

━━━━━━━━━━━━━━━━━━

Silakan kirim:

✅ Screenshot pembayaran
atau
✅ Foto bukti transfer QRIS

Pastikan bukti pembayaran terlihat jelas.

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
# PARSE USER PROFILE
# =========================================================

def parse_user_profile(
    text: str
):

    if not text:

        return None

    # -----------------------------------------------------
    # Nama
    # -----------------------------------------------------

    nama_match = re.search(

        r"(?:^|\n)\s*"
        r"Nama\s*:\s*(.+?)(?=\n|$)",

        text,

        re.IGNORECASE

    )

    # -----------------------------------------------------
    # Broker
    #
    # Bisa:
    # Broker:
    # Broker yang digunakan:
    # -----------------------------------------------------

    broker_match = re.search(

        r"(?:^|\n)\s*"
        r"(?:Broker\s+yang\s+digunakan|Broker)"
        r"\s*:\s*(.+?)(?=\n|$)",

        text,

        re.IGNORECASE

    )

    # -----------------------------------------------------
    # Gmail
    # -----------------------------------------------------

    gmail_match = re.search(

        r"(?:^|\n)\s*"
        r"Gmail\s*:\s*(.+?)(?=\n|$)",

        text,

        re.IGNORECASE

    )

    if not nama_match:

        return None

    if not broker_match:

        return None

    if not gmail_match:

        return None

    nama = nama_match.group(
        1
    ).strip()

    broker = broker_match.group(
        1
    ).strip()

    gmail = gmail_match.group(
        1
    ).strip()

    if not nama:

        return None

    if not broker:

        return None

    if not gmail:

        return None

    # -----------------------------------------------------
    # VALIDASI EMAIL
    # -----------------------------------------------------

    email_pattern = (
        r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    )

    if not re.match(
        email_pattern,
        gmail
    ):

        return None

    return {

        "nama":
            nama,

        "broker":
            broker,

        "gmail":
            gmail

    }


# =========================================================
# RECEIVE PAYMENT
#
# PERUBAHAN UTAMA:
#
# Setelah foto diterima:
# → simpan foto
# → langsung minta Nama/Broker/Gmail
#
# Tidak ada lagi tombol "KIRIM KE ADMIN".
# =========================================================

@dp.message(
    F.photo
)
async def receive_payment(
    message: Message
):

    user_id = message.from_user.id

    # -----------------------------------------------------
    # CEK PAKET
    # -----------------------------------------------------

    package_key = user_packages.get(
        user_id
    )

    if not package_key:

        await message.answer(

            """
⚠️ <b>PAKET BELUM DIPILIH</b>

Silakan pilih paket terlebih dahulu
melalui /start.
""",

            parse_mode="HTML"

        )

        return

    # -----------------------------------------------------
    # SIMPAN BUKTI
    # -----------------------------------------------------

    user_proofs[
        user_id
    ] = message.photo[-1].file_id

    # -----------------------------------------------------
    # AKTIFKAN PROFILE PENDING
    # -----------------------------------------------------

    user_profile_pending[
        user_id
    ] = True

    logger.info(
        "Bukti pembayaran diterima | "
        "user_id=%s | "
        "username=%s | "
        "package=%s",
        user_id,
        message.from_user.username,
        package_key
    )

    # -----------------------------------------------------
    # MINTA DATA USER
    # -----------------------------------------------------

    text = """
✅ <b>BUKTI PEMBAYARAN DITERIMA</b>

━━━━━━━━━━━━━━━━━━

Untuk menyesuaikan <b>AI dengan Spread dari Broker yang kamu gunakan</b>, silakan isi data berikut:

<b>Nama:</b>
<b>Broker yang digunakan:</b>
<b>Gmail:</b>

━━━━━━━━━━━━━━━━━━

📌 <b>Contoh pengisian:</b>

<code>Nama: Budi
Broker yang digunakan: XM
Gmail: budi@gmail.com</code>

━━━━━━━━━━━━━━━━━━

Silakan <b>kirim format tersebut kembali ke sini</b>.

Data ini akan dikirim kepada Admin
bersamaan dengan bukti pembayaran
untuk proses verifikasi.

🔒 Data Broker dan Gmail <b>tidak disimpan ke Google Sheets</b>.
"""

    await message.answer(

        text,

        parse_mode="HTML"

    )


# =========================================================
# RECEIVE USER PROFILE
#
# USER:
#
# Nama: Budi
# Broker yang digunakan: XM
# Gmail: budi@gmail.com
#
# → BOT KIRIM KE PAYMENT_GROUP_ID
# =========================================================

@dp.message(
    F.text
)
async def receive_profile(
    message: Message
):

    user_id = message.from_user.id

    text = message.text or ""

    # -----------------------------------------------------
    # COMMAND
    # -----------------------------------------------------

    if text.startswith("/"):

        return

    # -----------------------------------------------------
    # HANYA JIKA SEDANG MENUNGGU PROFILE
    # -----------------------------------------------------

    if not user_profile_pending.get(
        user_id,
        False
    ):

        # Kalau bukan profile,
        # biarkan handler performance
        # menangani pesan admin.
        if is_admin(user_id):

            await process_performance_message(
                message
            )

        return

    # -----------------------------------------------------
    # PARSE PROFILE
    # -----------------------------------------------------

    profile = parse_user_profile(
        text
    )

    if not profile:

        await message.answer(

            """
❌ <b>FORMAT BELUM SESUAI</b>

Silakan kirim dengan format:

<code>Nama: Budi
Broker yang digunakan: XM
Gmail: budi@gmail.com</code>

Pastikan:

✅ Nama diisi
✅ Broker diisi
✅ Gmail diisi dengan email yang valid
""",

            parse_mode="HTML"

        )

        return

    # -----------------------------------------------------
    # CEK BUKTI
    # -----------------------------------------------------

    proof = user_proofs.get(
        user_id
    )

    if not proof:

        await message.answer(

            """
❌ Bukti pembayaran tidak ditemukan.

Silakan kirim ulang foto bukti pembayaran.
""",

        )

        user_profile_pending.pop(
            user_id,
            None
        )

        return

    # -----------------------------------------------------
    # CEK PAKET
    # -----------------------------------------------------

    package_key = user_packages.get(
        user_id
    )

    if not package_key:

        await message.answer(

            """
❌ Paket pembayaran tidak ditemukan.

Silakan mulai kembali melalui /start.
""",

        )

        user_profile_pending.pop(
            user_id,
            None
        )

        return

    # -----------------------------------------------------
    # PACKAGE DATA
    # -----------------------------------------------------

    try:

        data = get_package_data(
            package_key
        )

    except Exception:

        await message.answer(

            "❌ Data paket tidak ditemukan."

        )

        return

    # -----------------------------------------------------
    # SIMPAN SEMENTARA
    #
    # TIDAK MASUK SHEETS
    # -----------------------------------------------------

    user_broker_data[
        user_id
    ] = profile

    # -----------------------------------------------------
    # ADMIN KEYBOARD
    # -----------------------------------------------------

    admin_keyboard = InlineKeyboardMarkup(

        inline_keyboard=[

            [

                InlineKeyboardButton(

                    text="✅ APPROVE",

                    callback_data=(
                        f"approve_{user_id}"
                    )

                ),

                InlineKeyboardButton(

                    text="❌ REJECT",

                    callback_data=(
                        f"reject_{user_id}"
                    )

                )

            ]

        ]

    )

    # -----------------------------------------------------
    # USERNAME
    # -----------------------------------------------------

    username = (

        f"@{message.from_user.username}"

        if message.from_user.username

        else "-"

    )

    # -----------------------------------------------------
    # GROUP ACCESS
    # -----------------------------------------------------

    group_access = (

        "✅ Ya"

        if package_has_group_access(
            package_key
        )

        else "❌ Tidak"

    )

    # -----------------------------------------------------
    # ADMIN CAPTION
    # -----------------------------------------------------

    admin_text = f"""
📥 <b>PAYMENT VERIFICATION</b>

━━━━━━━━━━━━━━━━━━

👤 <b>DATA USER</b>

Nama:
<b>{profile['nama']}</b>

Username:
<b>{username}</b>

Telegram ID:
<code>{user_id}</code>

━━━━━━━━━━━━━━━━━━

🏦 <b>BROKER</b>

<b>{profile['broker']}</b>

📧 <b>GMAIL</b>

<b>{profile['gmail']}</b>

━━━━━━━━━━━━━━━━━━

📦 <b>PAKET</b>

{data['label']}

💰 <b>TOTAL</b>

Rp {format_rupiah(data['price'])}

👥 <b>AKSES GRUP</b>

{group_access}

━━━━━━━━━━━━━━━━━━

📸 Bukti pembayaran terlampir
pada pesan ini.

ℹ️ Broker dan Gmail hanya dikirim
ke Admin untuk kebutuhan penyesuaian
AI dengan spread broker.

🔒 <b>Broker/Gmail tidak disimpan
ke Google Sheets.</b>

━━━━━━━━━━━━━━━━━━

Silakan pilih tindakan:
"""

    # -----------------------------------------------------
    # KIRIM KE PAYMENT GROUP
    # -----------------------------------------------------

    try:

        await bot.send_photo(

            chat_id=PAYMENT_GROUP_ID,

            photo=proof,

            caption=admin_text,

            reply_markup=admin_keyboard,

            parse_mode="HTML"

        )

        logger.info(

            "Payment verification dikirim | "
            "user=%s | "
            "package=%s | "
            "broker=%s | "
            "gmail=%s",

            user_id,

            package_key,

            profile["broker"],

            profile["gmail"]

        )

    except Exception as e:

        logger.exception(

            "Gagal mengirim payment verification "
            "ke PAYMENT_GROUP_ID | user=%s",
            user_id

        )

        await message.answer(

            f"""
❌ <b>GAGAL MENGIRIM DATA KE ADMIN</b>

Silakan coba lagi beberapa saat.

⚠️ Error:
<code>{e}</code>
""",

            parse_mode="HTML"

        )

        return

    # -----------------------------------------------------
    # PROFILE SUDAH TERKIRIM
    # -----------------------------------------------------

    user_profile_pending.pop(
        user_id,
        None
    )

    # -----------------------------------------------------
    # USER CONFIRMATION
    # -----------------------------------------------------

    await message.answer(

        """
✅ <b>DATA BERHASIL DIKIRIM</b>

━━━━━━━━━━━━━━━━━━

📸 Bukti pembayaran
👤 Nama
🏦 Broker
📧 Gmail

semuanya sudah dikirim ke Admin.

🟡 <b>Status: MENUNGGU VERIFIKASI</b>

Setelah Admin menyetujui pembayaran,
membership kamu akan langsung diaktifkan.

Mohon tunggu konfirmasi Admin.
""",

        parse_mode="HTML"

    )


# =========================================================
# CREATE ONE-TIME GROUP INVITE
#
# 1 ORANG SAJA
# EXPIRED OTOMATIS 24 JAM
# =========================================================

async def create_group_invite(
    user_id: int
):

    try:

        expire_at = int(
            (
                datetime.now()
                + timedelta(hours=24)
            ).timestamp()
        )

        invite = await bot.create_chat_invite_link(

            chat_id=PRIVATE_GROUP_ID,

            name=f"Member {user_id}",

            # Hanya satu orang yang bisa menggunakan
            member_limit=1,

            # Link expired setelah 24 jam
            expire_date=expire_at

        )

        logger.info(
            "Invite grup dibuat | "
            "user=%s | "
            "expire=24 jam | "
            "invite=%s",
            user_id,
            invite.invite_link
        )

        return invite.invite_link

    except Exception:

        logger.exception(
            "Gagal membuat invite grup | user=%s",
            user_id
        )

        return None


# =========================================================
# KICK EXPIRED MEMBER
#
# BAN SEBENTAR → UNBAN
#
# Efeknya seperti KICK.
# User tidak permanent banned.
# =========================================================

async def kick_expired_member(
    telegram_id: int
):

    try:

        telegram_id = int(
            telegram_id
        )

        logger.info(
            "[EXPIRED] Mencoba mengeluarkan user=%s",
            telegram_id
        )

        # -------------------------------------------------
        # BAN
        # -------------------------------------------------

        await bot.ban_chat_member(

            chat_id=PRIVATE_GROUP_ID,

            user_id=telegram_id

        )

        logger.info(
            "[EXPIRED] User %s berhasil dikeluarkan.",
            telegram_id
        )

        # -------------------------------------------------
        # UNBAN
        # -------------------------------------------------

        try:

            await bot.unban_chat_member(

                chat_id=PRIVATE_GROUP_ID,

                user_id=telegram_id,

                only_if_banned=True

            )

            logger.info(
                "[EXPIRED] User %s berhasil di-unban.",
                telegram_id
            )

        except Exception as e:

            logger.warning(
                "[EXPIRED] Gagal unban user=%s: %s",
                telegram_id,
                e
            )

        return True

    except Exception as e:

        logger.exception(
            "[EXPIRED] Gagal kick user=%s: %s",
            telegram_id,
            e
        )

        return False


# =========================================================
# CHECK EXPIRED MEMBERS
#
# Google Sheets → cek expired → kick grup
# =========================================================

async def check_expired_members():

    logger.info(
        "=========================================="
    )

    logger.info(
        "[EXPIRED CHECK] Mulai pengecekan Google Sheets"
    )

    try:

        # -------------------------------------------------
        # AMBIL MEMBER EXPIRED
        # -------------------------------------------------

        expired_members = await asyncio.to_thread(

            get_expired_group_members

        )

        if not expired_members:

            logger.info(
                "[EXPIRED CHECK] "
                "Tidak ada member expired."
            )

            return

        logger.info(
            "[EXPIRED CHECK] "
            "Ditemukan %s member expired.",
            len(expired_members)
        )

        # -------------------------------------------------
        # PROSES MEMBER
        # -------------------------------------------------

        for member in expired_members:

            telegram_id = member.get(
                "telegram_id"
            )

            username = member.get(
                "username",
                ""
            )

            nama = member.get(
                "nama",
                ""
            )

            paket = member.get(
                "paket",
                ""
            )

            expired = member.get(
                "expired",
                ""
            )

            logger.info(
                "[EXPIRED] "
                "ID=%s | "
                "username=%s | "
                "nama=%s | "
                "paket=%s | "
                "expired=%s",
                telegram_id,
                username,
                nama,
                paket,
                expired
            )

            # -------------------------------------------------
            # VALIDATE ID
            # -------------------------------------------------

            try:

                telegram_id = int(
                    telegram_id
                )

            except Exception:

                logger.warning(
                    "[EXPIRED] "
                    "Telegram ID tidak valid: %s",
                    telegram_id
                )

                continue

            # -------------------------------------------------
            # KICK
            # -------------------------------------------------

            kicked = await kick_expired_member(
                telegram_id
            )

            # -------------------------------------------------
            # UPDATE SHEET
            # -------------------------------------------------

            if kicked:

                try:

                    updated = await asyncio.to_thread(

                        update_member_status,

                        telegram_id,

                        "EXPIRED"

                    )

                    if updated is False:

                        logger.warning(
                            "[SHEET] "
                            "User %s gagal update EXPIRED.",
                            telegram_id
                        )

                    else:

                        logger.info(
                            "[SHEET] "
                            "User %s -> EXPIRED",
                            telegram_id
                        )

                except Exception as e:

                    logger.exception(
                        "[SHEET ERROR] "
                        "user=%s | %s",
                        telegram_id,
                        e
                    )

            else:

                logger.warning(
                    "[EXPIRED] "
                    "User %s gagal dikeluarkan. "
                    "Status Sheets tidak diubah.",
                    telegram_id
                )

    except Exception as e:

        logger.exception(
            "[EXPIRED CHECK ERROR] %s",
            e
        )

    logger.info(
        "=========================================="
    )


# =========================================================
# EXPIRED MONITOR
#
# CHECK SETIAP 10 MENIT
# =========================================================

async def expired_monitor():

    logger.info(
        "=========================================="
    )

    logger.info(
        "⏳ EXPIRED MONITOR STARTED"
    )

    logger.info(
        "📊 Google Sheets → Check setiap 10 menit"
    )

    logger.info(
        "👥 Private Group ID: %s",
        PRIVATE_GROUP_ID
    )

    logger.info(
        "=========================================="
    )

    # Tunggu bot startup
    await asyncio.sleep(
        10
    )

    while True:

        try:

            await check_expired_members()

        except Exception as e:

            logger.exception(
                "[EXPIRED MONITOR ERROR] %s",
                e
            )

        # -------------------------------------------------
        # 10 MENIT
        # -------------------------------------------------

        await asyncio.sleep(
            600
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

    data = get_package_data(
        package_key
    )

    # =====================================================
    # EXPIRED
    # =====================================================

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

    # =====================================================
    # SAVE MEMBER
    #
    # TETAP SAMA
    #
    # Broker dan Gmail SENGAJA TIDAK DIMASUKKAN.
    # =====================================================

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

    logger.info(
        "Member disimpan ke Google Sheets | "
        "user=%s | package=%s",
        user_id,
        package_key
    )

    # =====================================================
    # AI BUTTON
    # =====================================================

    buttons = [

        [

            InlineKeyboardButton(

                text="🤖 MASUK AI ASSISTANT",

                url=SIGNAL_BOT

            )

        ]

    ]

    # =====================================================
    # GROUP INVITE
    # =====================================================

    invite_link = None

    if package_has_group_access(
        package_key
    ):

        invite_link = await create_group_invite(
            user_id
        )

        if invite_link:

            buttons.append(

                [

                    InlineKeyboardButton(

                        text=(
                            "👥 GABUNG GRUP "
                            "DISKUSI & SHARING"
                        ),

                        url=invite_link

                    )

                ]

            )

    # =====================================================
    # KEYBOARD
    # =====================================================

    member_keyboard = InlineKeyboardMarkup(

        inline_keyboard=buttons

    )

    # =====================================================
    # MEMBER MESSAGE
    # =====================================================

    if package_has_group_access(
        package_key
    ):

        if invite_link:

            group_access_text = """
👥 <b>GRUP DISKUSI &amp; SHARING</b>

Anda mendapatkan akses grup private.
Gunakan tombol di bawah untuk bergabung.

⚠️ Link ini hanya dapat digunakan
untuk <b>1 anggota</b> dan berlaku
selama <b>24 jam</b>.
"""

        else:

            group_access_text = """
👥 <b>GRUP DISKUSI &amp; SHARING</b>

Pembayaran aktif, tetapi link grup
belum berhasil dibuat.

Silakan hubungi Admin.
"""

    else:

        group_access_text = """
🤖 <b>AKSES AI ASSISTANT</b>

Paket 1 Bulan mendapatkan akses
AI Assistant Telegram.

ℹ️ Paket ini tidak termasuk akses
Grup Diskusi &amp; Sharing.
"""

    member_text = f"""
🎉 <b>MEMBERSHIP AKTIF</b>

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

{group_access_text}

Klik tombol di bawah untuk mulai.

Selamat trading bersama
<b>XAU AI Assistant Gold</b> 🤖
"""

    # =====================================================
    # SEND MEMBER ACCESS
    # =====================================================

    try:

        await bot.send_message(

            chat_id=user_id,

            text=member_text,

            reply_markup=member_keyboard,

            parse_mode="HTML"

        )

    except Exception as e:

        logger.exception(
            "Gagal mengirim akses member: %s",
            e
        )

        await callback.message.answer(

            f"""
⚠️ <b>MEMBERSHIP TERSIMPAN</b>

Member sudah disimpan ke database,
tetapi pesan akses gagal dikirim.

User ID:
<code>{user_id}</code>

Error:
<code>{e}</code>
""",

            parse_mode="HTML"

        )

        return

    # =====================================================
    # ADMIN CONFIRMATION
    # =====================================================

    if package_has_group_access(
        package_key
    ):

        if invite_link:

            admin_group_status = (
                "✅ Invite grup berhasil dibuat"
            )

        else:

            admin_group_status = (
                "⚠️ Invite grup gagal dibuat"
            )

    else:

        admin_group_status = (
            "ℹ️ Paket 1 Bulan — tanpa akses grup"
        )

    await callback.message.answer(

        f"""
✅ <b>MEMBER BERHASIL DIAKTIFKAN</b>

Data membership telah tersimpan
dan user sudah menerima akses.

📦 Paket:
<b>{data['label']}</b>

👥 Grup:
{admin_group_status}
""",

        parse_mode="HTML"

    )

    await safe_callback_answer(

        callback,

        "Member aktif"

    )

    # =====================================================
    # CLEANUP TEMP DATA
    # =====================================================

    user_packages.pop(
        user_id,
        None
    )

    user_proofs.pop(
        user_id,
        None
    )

    user_broker_data.pop(
        user_id,
        None
    )

    user_profile_pending.pop(
        user_id,
        None
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

━━━━━━━━━━━━━━━━━━

Mohon:

📌 Periksa kembali bukti pembayaran
📌 Pastikan nominal sesuai
📌 Hubungi Admin jika membutuhkan bantuan

Admin siap membantu proses aktivasi Anda.
"""

    try:

        await bot.send_message(

            chat_id=user_id,

            text=reject_text,

            parse_mode="HTML"

        )

    except Exception as e:

        logger.warning(
            "Gagal mengirim reject ke user %s: %s",
            user_id,
            e
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

    # =====================================================
    # CLEANUP
    # =====================================================

    user_packages.pop(
        user_id,
        None
    )

    user_proofs.pop(
        user_id,
        None
    )

    user_broker_data.pop(
        user_id,
        None
    )

    user_profile_pending.pop(
        user_id,
        None
    )


# =========================================================
# ADMIN SEND MESSAGE
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

            f"✅ <b>Pesan berhasil dikirim</b>\n\n"
            f"🆔 Target: <code>{target_id}</code>\n"
            f"💬 Isi: {text_to_send}",

            parse_mode="HTML"

        )

    except Exception as e:

        await message.answer(

            f"❌ <b>Pesan gagal dikirim</b>\n\n"
            f"🆔 Target: <code>{target_id}</code>\n"
            f"⚠️ Error: <code>{e}</code>",

            parse_mode="HTML"

        )


# =========================================================
# PERFORMANCE PROCESSOR
# =========================================================

async def process_performance_message(
    message: Message
):

    if not is_admin(
        message.from_user.id
    ):

        return

    text = message.text or ""

    if not text:

        return

    # =====================================================
    # DATE
    # =====================================================

    performance_date = parse_performance_date(
        text
    )

    # =====================================================
    # PARSE
    # =====================================================

    performance = parse_performance(
        text
    )

    if not performance:

        await message.answer(

            """
⚠️ <b>FORMAT PERFORMANCE TIDAK TERBACA</b>

Gunakan format:

<code>📅 26-08-2026

S 07:00 | 4652 | 4645 | TP1
B 08:00 | 4636 | 4651 | TP2
09:00 | PENDING
10:00 | PENDING
12:00 | NO SIGNAL
B 13:00 | 4637 | 4632 | SL</code>
""",

            parse_mode="HTML"

        )

        return

    # =====================================================
    # COUNT SIGNAL
    # =====================================================

    signal_count = sum(

        1

        for item in performance

        if item["result"] in (
            "TP1",
            "TP2",
            "SL"
        )

    )

    logger.info(

        "Performance diterima | "
        "admin=%s | total_rows=%s | signals=%s | date=%s",

        message.from_user.id,

        len(performance),

        signal_count,

        performance_date

    )

    # =====================================================
    # BUILD
    # =====================================================

    final_message = build_performance_message(

        performance,

        performance_date

    )

    # =====================================================
    # CTA
    # =====================================================

    cta_keyboard = InlineKeyboardMarkup(

        inline_keyboard=[

            [

                InlineKeyboardButton(

                    text="🚀 AKTIFKAN AI ASSISTANT GOLD",

                    url=SIGNAL_BOT

                )

            ]

        ]

    )

    # =====================================================
    # SEND CHANNEL
    # =====================================================

    try:

        await bot.send_message(

            chat_id=PUBLIC_CHANNEL_ID,

            text=final_message,

            reply_markup=cta_keyboard,

            parse_mode="HTML"

        )

        logger.info(

            "Performance berhasil dikirim | "
            "channel=%s | signals=%s",

            PUBLIC_CHANNEL_ID,

            signal_count

        )

        date_text = (

            format_date_indonesia(
                performance_date
            )

            if performance_date

            else "Tidak diketahui"

        )

        await message.answer(

            f"""
✅ <b>PERFORMANCE TERKIRIM</b>

📅 Tanggal : <b>{date_text}</b>
📊 Signal : <b>{signal_count}</b>
📢 Channel : <code>{PUBLIC_CHANNEL_ID}</code>

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
# PERFORMANCE ADMIN
#
# Handler terpisah supaya tidak bentrok
# dengan data Broker/Gmail user.
# =========================================================

@dp.message(
    F.text
)
async def performance_to_channel(
    message: Message
):

    # =====================================================
    # COMMAND JANGAN DIPROSES
    # =====================================================

    if message.text.startswith("/"):

        return

    # =====================================================
    # PROFILE USER SEDANG MENUNGGU
    #
    # Handler receive_profile yang menangani.
    # =====================================================

    if user_profile_pending.get(
        message.from_user.id,
        False
    ):

        return

    # =====================================================
    # ADMIN SAJA
    # =====================================================

    if not is_admin(
        message.from_user.id
    ):

        return

    await process_performance_message(
        message
    )


# =========================================================
# MAIN
# =========================================================

async def main():

    logger.info(
        "=========================================="
    )

    logger.info(
        "🤖 XAU AI Assistant Bot Running..."
    )

    logger.info(
        "=========================================="
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
        "👥 Private Group ID: %s",
        PRIVATE_GROUP_ID
    )

    logger.info(
        "👨‍💼 Admin IDs: %s",
        ADMIN_IDS
    )

    logger.info(
        "🎯 TP1 = %s Pips | TP2 = %s Pips | SL = -%s Pips",
        TP1_PIPS,
        TP2_PIPS,
        SL_PIPS
    )

    logger.info(
        "🔐 Group Invite = 1 user + expired 24 jam"
    )

    logger.info(
        "📝 Broker/Gmail = ADMIN ONLY"
    )

    logger.info(
        "📊 Broker/Gmail = TIDAK disimpan ke Google Sheets"
    )

    logger.info(
        "⏳ Expired Monitor = aktif setiap 10 menit"
    )

    # =====================================================
    # START EXPIRED MONITOR
    # =====================================================

    asyncio.create_task(
        expired_monitor()
    )

    # =====================================================
    # START TELEGRAM BOT
    # =====================================================

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
