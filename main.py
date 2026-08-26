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
            int(x) for x in ADMIN_IDS
        ]

    except Exception:
        return False


# =========================================================
# SAFE EDIT REPLY MARKUP
# =========================================================

async def remove_keyboard(message: Message):
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
async def start(message: Message):

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

📈 <b>Analisa XAUUSD Premium</b>
🧠 <b>Smart Money Concept</b>
⚡ <b>Market Intelligence</b>
🤖 <b>AI Assistant Telegram</b>

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

    try:

        await callback.answer(
            "Silakan pilih paket membership"
        )

    except Exception:
        pass


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

        await callback.answer(
            "Paket tidak ditemukan.",
            show_alert=True
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

📸 Screenshot bukti pembayaran
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

    try:

        await callback.answer(
            "Paket berhasil dipilih"
        )

    except Exception:
        pass


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

    try:

        await callback.answer(
            "Silakan upload bukti pembayaran"
        )

    except Exception:
        pass


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

Status:

🟡 Menunggu verifikasi Admin

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

        await callback.answer(

            "⚠️ Data belum lengkap",

            show_alert=True

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

    try:

        await callback.answer(
            "Dikirim ke Admin"
        )

    except Exception:
        pass


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

        await callback.answer(
            "Anda bukan admin.",
            show_alert=True
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

        await callback.answer(

            "Data paket tidak ditemukan",

            show_alert=True

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

        await callback.answer(
            "Gagal mengambil data user.",
            show_alert=True
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

    try:

        await callback.answer(
            "Member aktif"
        )

    except Exception:
        pass


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

        await callback.answer(
            "Anda bukan admin.",
            show_alert=True
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

    try:

        await callback.answer(
            "Payment rejected"
        )

    except Exception:
        pass


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
# PERFORMANCE PARSER
# =========================================================

def parse_performance(text: str):
    """
    Membaca format:

    🕐 07:00 → ✅ TP
    🕐 08:00 → ❌ SL

    Menghasilkan list:
    [
        ("07:00", "TP"),
        ("08:00", "SL")
    ]
    """

    results = []

    pattern = re.compile(

        r"(\d{1,2}:\d{2})"
        r"\s*(?:→|->|➜|—|-)"
        r"\s*"
        r"(?:.*?)(TP|SL)\b",

        re.IGNORECASE

    )

    for match in pattern.finditer(text):

        hour = match.group(1)

        result = match.group(2).upper()

        results.append(
            (
                hour,
                result
            )
        )

    return results


# =========================================================
# CALCULATE PNL
# =========================================================

def calculate_pnl(
    wins: int,
    losses: int
):
    """
    Default:
    TP = +1R
    SL = -1R
    """

    return wins - losses


# =========================================================
# PERFORMANCE MESSAGE
# =========================================================

def build_performance_message(
    performance
):

    total = len(
        performance
    )

    wins = sum(
        1
        for _, result
        in performance
        if result == "TP"
    )

    losses = sum(
        1
        for _, result
        in performance
        if result == "SL"
    )

    if total:

        winrate = (
            wins / total
        ) * 100

    else:

        winrate = 0

    pnl = calculate_pnl(
        wins,
        losses
    )

    today = datetime.now()

    date_text = today.strftime(
        "%d %B %Y"
    )

    # Bahasa Indonesia bulan
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

    for en, idn in months.items():

        date_text = date_text.replace(
            en,
            idn
        )

    lines = []

    for hour, result in performance:

        if result == "TP":

            icon = "✅"

        else:

            icon = "❌"

        lines.append(
            f"🕐 {hour} → {icon} {result}"
        )

    performance_lines = "\n".join(
        lines
    )

    if pnl > 0:

        pnl_text = f"+{pnl}R"

    elif pnl < 0:

        pnl_text = f"{pnl}R"

    else:

        pnl_text = "0R"

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
🎯 Winrate      : <b>{winrate:.0f}%</b>

💰 PNL          : <b>{pnl_text}</b>

━━━━━━━━━━━━━━━━━━

🤖 <b>AKTIFKAN AI ASSISTANT GOLD</b>

Dapatkan akses AI Assistant Gold
untuk membantu membaca market
XAUUSD secara lebih terstruktur.

👉 Hubungi <b>@Intradayxauusd_bot</b>
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
    # seperti /start dan /sent
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

    # Tidak ada data TP / SL
    if not performance:

        return

    logger.info(
        "Performance diterima | admin=%s | signal=%s",
        message.from_user.id,
        len(performance)
    )

    # =====================================================
    # KIRIM KE PUBLIC CHANNEL
    # =====================================================

    try:

        final_message = build_performance_message(
            performance
        )

        await bot.send_message(

            chat_id=PUBLIC_CHANNEL_ID,

            text=final_message,

            parse_mode="HTML"

        )

        logger.info(
            "Performance berhasil dikirim ke Public Channel | "
            "signals=%s | channel=%s",
            len(performance),
            PUBLIC_CHANNEL_ID
        )

        # Konfirmasi ke admin
        await message.answer(

            f"""
✅ <b>PERFORMANCE TERKIRIM</b>

📊 Signal : <b>{len(performance)}</b>
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
