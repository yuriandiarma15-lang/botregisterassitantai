import asyncio
import re
import logging

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

TP_PIPS = 70
SL_PIPS = 50


# =========================================================
# TEMP STORAGE
# =========================================================

user_packages = {}

user_proofs = {}


# =========================================================
# SAFE REMOVE KEYBOARD
# =========================================================

async def safe_remove_keyboard(
    message: Message
):

    try:

        await message.edit_reply_markup(
            reply_markup=None
        )

    except TelegramBadRequest as e:

        error_text = str(e).lower()

        if (
            "message is not modified"
            in error_text
        ):
            return

        raise

    except Exception:

        logger.exception(
            "Gagal menghapus keyboard."
        )


# =========================================================
# CALLBACK ANSWER SAFE
# =========================================================

async def safe_callback_answer(
    callback: CallbackQuery,
    text=""
):

    try:

        await callback.answer(
            text
        )

    except TelegramBadRequest:

        # Callback sudah expired /
        # sudah dijawab Telegram.
        pass

    except Exception:

        logger.exception(
            "Gagal menjawab callback."
        )


# =========================================================
# PERFORMANCE PARSER
# =========================================================

def parse_performance(
    text: str
):

    """
    Format:

    07 TP
    08 SL
    09 TP

    atau:

    07:00 TP
    08:00 SL

    atau:

    🕐 07:00 → ✅ TP
    """

    lines = text.strip().splitlines()

    results = []

    for line in lines:

        line = line.strip()

        if not line:
            continue

        # -------------------------------------------------
        # NORMALIZE
        # -------------------------------------------------

        clean = line.upper()

        clean = clean.replace(
            "🕐",
            ""
        )

        clean = clean.replace(
            "→",
            " "
        )

        clean = clean.replace(
            "✅",
            ""
        )

        clean = clean.replace(
            "❌",
            ""
        )

        clean = clean.strip()

        # -------------------------------------------------
        # MATCH JAM
        # -------------------------------------------------

        match = re.search(
            r"\b(\d{1,2})(?::00)?\s+(TP|SL)\b",
            clean
        )

        if not match:
            continue

        hour = int(
            match.group(1)
        )

        result = match.group(2)

        if hour < 0 or hour > 23:
            continue

        results.append(
            {
                "hour": hour,
                "result": result
            }
        )

    # -----------------------------------------------------
    # SORT BERDASARKAN URUTAN INPUT
    # -----------------------------------------------------

    return results


# =========================================================
# BUILD PERFORMANCE
# =========================================================

def build_performance_message(
    results
):

    total = len(results)

    wins = sum(
        1
        for item in results
        if item["result"] == "TP"
    )

    losses = sum(
        1
        for item in results
        if item["result"] == "SL"
    )

    # -----------------------------------------------------
    # WINRATE
    # -----------------------------------------------------

    if total > 0:

        winrate = (
            wins
            / total
            * 100
        )

    else:

        winrate = 0

    # -----------------------------------------------------
    # P/L
    # -----------------------------------------------------

    profit_pips = (
        wins
        * TP_PIPS
    )

    loss_pips = (
        losses
        * SL_PIPS
    )

    net_pips = (
        profit_pips
        - loss_pips
    )

    # -----------------------------------------------------
    # TANGGAL
    # -----------------------------------------------------

    now = datetime.now()

    day_name = [
        "Senin",
        "Selasa",
        "Rabu",
        "Kamis",
        "Jumat",
        "Sabtu",
        "Minggu"
    ][now.weekday()]

    date_text = now.strftime(
        "%d %B %Y"
    )

    # -----------------------------------------------------
    # BULAN INDONESIA
    # -----------------------------------------------------

    months = {
        "January": "Januari",
        "February": "Februari",
        "March": "Maret",
        "April": "April",
        "May": "Mei",
        "June": "Juni",
        "July": "Juli",
        "August": "Agustus",
        "September": "September",
        "October": "Oktober",
        "November": "November",
        "December": "Desember"
    }

    for english, indonesia in months.items():

        date_text = date_text.replace(
            english,
            indonesia
        )

    # -----------------------------------------------------
    # SIGNAL ROWS
    # -----------------------------------------------------

    rows = []

    for item in results:

        hour = item["hour"]

        result = item["result"]

        time_text = (
            f"{hour:02d}:00"
        )

        if result == "TP":

            icon = "✅"

        else:

            icon = "❌"

        rows.append(
            f"🕐 {time_text} → {icon} {result}"
        )

    signal_text = "\n".join(
        rows
    )

    # -----------------------------------------------------
    # NET FORMAT
    # -----------------------------------------------------

    if net_pips >= 0:

        net_text = (
            f"+{net_pips} Pips"
        )

        net_icon = "🟢"

    else:

        net_text = (
            f"{net_pips} Pips"
        )

        net_icon = "🔴"

    # -----------------------------------------------------
    # FINAL MESSAGE
    # -----------------------------------------------------

    message = f"""
📊 <b>XAU AI ASSISTANT</b>
━━━━━━━━━━━━━━━━━━
📅 <b>PERFORMANCE — {day_name}, {date_text}</b>

<b>{total} SIGNAL PERFORMANCE</b>

{signal_text}

━━━━━━━━━━━━━━━━━━
📈 <b>PERFORMANCE</b>

✅ WIN  : {wins}
❌ LOSS : {losses}
🎯 WINRATE : <b>{winrate:.0f}%</b>

💰 <b>P/L</b>
🟢 TP : +{profit_pips} Pips
🔴 SL : -{loss_pips} Pips
{net_icon} NET : <b>{net_text}</b>

━━━━━━━━━━━━━━━━━━
🤖 <b>AKTIFKAN AI ASSISTANT GOLD</b>

Dapatkan analisa Gold langsung
dari AI Assistant.

👉 <b>Hubungi @Intradayxauusd_bot</b>

━━━━━━━━━━━━━━━━━━
"""

    return message


# =========================================================
# PERFORMANCE ADMIN HANDLER
# =========================================================

@dp.message(
    F.text
)
async def performance_handler(
    message: Message
):

    # =====================================================
    # HANYA ADMIN
    # =====================================================

    if message.from_user.id not in ADMIN_IDS:

        return

    text = (
        message.text
        or ""
    ).strip()

    # =====================================================
    # JANGAN PROSES COMMAND
    # =====================================================

    if text.startswith("/"):

        return

    # =====================================================
    # PARSE
    # =====================================================

    results = parse_performance(
        text
    )

    # =====================================================
    # BUKAN PERFORMANCE
    # =====================================================

    if not results:

        return

    # =====================================================
    # BATASI 20 SIGNAL
    # =====================================================

    if len(results) != 20:

        await message.answer(
            f"""
⚠️ <b>PERFORMANCE BELUM VALID</b>

Bot menemukan:

<b>{len(results)} signal</b>

Format performance harus berisi
tepat <b>20 signal</b> dari:

🕐 07:00
sampai
🕐 02:00

Contoh:

<code>07 TP
08 SL
09 TP
10 TP</code>

Silakan kirim ulang.
""",
            parse_mode="HTML"
        )

        return

    # =====================================================
    # BUILD
    # =====================================================

    performance_text = build_performance_message(
        results
    )

    # =====================================================
    # SEND TO PUBLIC CHANNEL
    # =====================================================

    try:

        await bot.send_message(

            chat_id=PUBLIC_CHANNEL_ID,

            text=performance_text,

            parse_mode="HTML"
        )

    except Exception as e:

        logger.exception(
            "Gagal mengirim performance ke Channel."
        )

        await message.answer(

            f"""
❌ <b>GAGAL MENGIRIM PERFORMANCE</b>

Pastikan:

✅ Bot sudah menjadi Admin Channel
✅ Bot memiliki izin mengirim pesan
✅ PUBLIC_CHANNEL_ID benar

Error:

<code>{e}</code>
""",

            parse_mode="HTML"
        )

        return

    # =====================================================
    # SUCCESS
    # =====================================================

    await message.answer(
        """
✅ <b>PERFORMANCE BERHASIL DIKIRIM</b>

Performance 20 signal sudah
diterbitkan ke Channel Umum.

📊 Winrate dan P/L dihitung otomatis.
""",
        parse_mode="HTML"
    )


# =========================================================
# START WELCOME
# =========================================================

@dp.message(
    CommandStart()
)
async def start(
    message: Message
):

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
🤖 <b>XAU AI ASSISTANT PREMIUM</b>

👋 Halo <b>{message.from_user.first_name}</b>

Selamat datang di layanan
<b>XAU AI Assistant Premium</b>.

<blockquote>"Partner AI pribadi untuk membantu Anda membaca market Gold lebih cepat, lebih terstruktur, dan tanpa noise."</blockquote>

━━━━━━━━━━━━━━━━━━

🚀 <b>FITUR PREMIUM</b>

📈 Analisa XAUUSD Premium
🧠 Smart Money Concept Analysis
⚡ Update Market Gold Terbaru
🤖 AI Assistant Telegram Pribadi

━━━━━━━━━━━━━━━━━━

💎 <b>KENAPA BERBEDA?</b>

Anda tidak perlu lagi:

❌ Membaca ratusan chat signal
❌ Mencari informasi penting
❌ Takut kehilangan momentum
❌ Pamer Profit yang membuat ada FOMO

Semua informasi akan dirangkum
langsung oleh AI Assistant Anda.

━━━━━━━━━━━━━━━━━━

🔐 <b>AKTIFKAN AKSES SEKARANG</b>

Dapatkan akses premium untuk membantu
analisa Gold secara lebih cepat
dan profesional.

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

    await safe_remove_keyboard(
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
                    text="👑 LIFETIME ACCESS | Rp1.500.000",
                    callback_data="pkg_permanent"
                )
            ]

        ]
    )

    text = """
💎 <b>PILIH MEMBERSHIP PLAN</b>

<blockquote>"Pilih paket akses yang sesuai kebutuhan trading Anda."</blockquote>

━━━━━━━━━━━━━━━━━━

🥇 <b>STARTER PLAN</b>
📅 1 Bulan
💰 Rp250.000

━━━━━━━━━━━━━━━━━━

🥈 <b>PRO PLAN</b>
📅 6 Bulan
💰 Rp500.000

━━━━━━━━━━━━━━━━━━

🥉 <b>ELITE PLAN</b>
📅 12 Bulan
💰 Rp850.000

━━━━━━━━━━━━━━━━━━

👑 <b>LIFETIME ACCESS</b>
♾️ Permanent
💰 Rp1.500.000

━━━━━━━━━━━━━━━━━━

✨ Semua paket mendapatkan:

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

    await safe_remove_keyboard(
        callback.message
    )

    package_key = callback.data.replace(
        "pkg_",
        ""
    )

    user_packages[
        callback.from_user.id
    ] = package_key

    data = PACKAGE_MAP[
        package_key
    ]

    payment_text = f"""
💳 <b>AKTIVASI MEMBERSHIP</b>

<blockquote>"Selangkah lagi menuju akses AI Assistant Premium Anda."</blockquote>

━━━━━━━━━━━━━━━━━━

📦 <b>Paket Dipilih</b>
{data['label']}

💰 <b>Total Pembayaran</b>
Rp {data['price']:,}

━━━━━━━━━━━━━━━━━━

📌 <b>INSTRUKSI PEMBAYARAN</b>

1️⃣ Scan QRIS di atas
2️⃣ Lakukan pembayaran
3️⃣ Kirim bukti pembayaran

📸 Screenshot bukti pembayaran
ke chat ini.

━━━━━━━━━━━━━━━━━━

⏳ Admin akan melakukan verifikasi
dan mengaktifkan akses Anda.

Terima kasih telah bergabung
bersama <b>XAU AI Assistant</b>.
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
# MINTA UPLOAD BUKTI
# =========================================================

@dp.callback_query(
    F.data == "upload"
)
async def upload_request(
    callback: CallbackQuery
):

    await callback.message.answer(

        """
📸 <b>UPLOAD BUKTI PEMBAYARAN</b>

<blockquote>"Pastikan bukti pembayaran terlihat jelas agar proses aktivasi dapat berjalan cepat."</blockquote>

━━━━━━━━━━━━━━━━━━

Silakan kirim:

✅ Screenshot pembayaran
atau
✅ Foto bukti transfer QRIS

Admin akan melakukan pengecekan
setelah bukti diterima.
""",

        parse_mode="HTML"
    )

    await safe_callback_answer(
        callback,
        "Silakan upload bukti pembayaran ke sini"
    )


# =========================================================
# TERIMA BUKTI PEMBAYARAN
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

    await message.answer(

        """
✅ <b>BUKTI PEMBAYARAN DITERIMA</b>

<blockquote>"Data pembayaran Anda sudah siap untuk dikirim ke Admin."</blockquote>

━━━━━━━━━━━━━━━━━━

Status:

🟡 Menunggu verifikasi Admin

Klik tombol berikut untuk mengirim
permintaan pengecekan.
""",

        reply_markup=keyboard,

        parse_mode="HTML"
    )


# =========================================================
# KIRIM VERIFIKASI ADMIN
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
            "⚠️ Data belum lengkap"
        )

        return

    await safe_remove_keyboard(
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

<blockquote>"Member baru menunggu pengecekan aktivasi membership."</blockquote>

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
⏳ <b>VERIFIKASI BERHASIL DIKIRIM</b>

<blockquote>"Admin sedang melakukan pengecekan pembayaran Anda."</blockquote>

━━━━━━━━━━━━━━━━━━

Status:

🟡 Menunggu approval

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

    await safe_remove_keyboard(
        callback.message
    )

    user_id = int(
        callback.data.split("_")[1]
    )

    user = await bot.get_chat(
        user_id
    )

    package_key = user_packages.get(
        user_id
    )

    if not package_key:

        await safe_callback_answer(
            callback,
            "Data paket tidak ditemukan"
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

        "telegram_id": user_id,

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

<blockquote>"Selamat! Anda sekarang resmi menjadi bagian dari XAU AI Assistant Premium."</blockquote>

━━━━━━━━━━━━━━━━━━

📦 <b>Paket Anda</b>
{data['label']}

⏳ <b>Masa Aktif</b>
{expired}

━━━━━━━━━━━━━━━━━━

🚀 <b>Akses Premium Anda:</b>

✅ AI Assistant Telegram
✅ Analisa XAUUSD
✅ Smart Money Concept
✅ Market Intelligence Update

━━━━━━━━━━━━━━━━━━

Klik tombol di bawah untuk mulai
menggunakan AI Assistant.

Selamat trading bersama
<b>XAU AI Assistant</b> 🤖
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

    await safe_remove_keyboard(
        callback.message
    )

    user_id = int(
        callback.data.split("_")[1]
    )

    reject_text = """
❌ <b>PEMBAYARAN BELUM DIVERIFIKASI</b>

<blockquote>"Terjadi kendala saat melakukan pengecekan pembayaran Anda."</blockquote>

━━━━━━━━━━━━━━━━━━

Mohon:

📌 Periksa kembali bukti pembayaran
📌 Pastikan nominal sesuai
📌 Hubungi Admin untuk bantuan

Admin siap membantu proses
aktivasi Anda.
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
# RUN BOT
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

    await dp.start_polling(
        bot
    )


# =========================================================
# START
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
