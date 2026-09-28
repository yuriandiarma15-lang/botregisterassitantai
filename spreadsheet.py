import os
import json

import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime


# =========================================================
# GOOGLE SHEETS CONFIG
# =========================================================

SPREADSHEET_ID = "1J3_Go0MdiNaDxVl6EuA00hJMsamB35Gjq0eHEg96ZMw"

SHEET_NAME = "Members"


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]


# =========================================================
# GOOGLE AUTHENTICATION
# =========================================================

service_account_info = json.loads(
    os.environ["GOOGLE_SERVICE_ACCOUNT"]
)


creds = Credentials.from_service_account_info(
    service_account_info,
    scopes=SCOPES
)


client = gspread.authorize(
    creds
)


spreadsheet = client.open_by_key(
    SPREADSHEET_ID
)


sheet = spreadsheet.worksheet(
    SHEET_NAME
)


# =========================================================
# SAVE MEMBER
# =========================================================

def save_member(data):

    try:

        print("=== DATA KE GOOGLE SHEET ===")
        print(data)

        sheet.append_row([

            data.get(
                "telegram_id",
                ""
            ),

            data.get(
                "username",
                ""
            ),

            data.get(
                "nama",
                ""
            ),

            data.get(
                "paket",
                ""
            ),

            data.get(
                "harga",
                ""
            ),

            data.get(
                "register",
                ""
            ),

            data.get(
                "expired",
                ""
            ),

            data.get(
                "status",
                ""
            )

        ])

        print("STATUS:")
        print("SUCCESS")

        print("RESPON GOOGLE SHEET:")
        print("Member berhasil disimpan")

        return True

    except Exception as e:

        print(
            "Google Sheet Error:"
        )

        print(e)

        return False


# =========================================================
# GET EXPIRED GROUP MEMBERS
# =========================================================

def get_expired_group_members():

    try:

        print(
            "[EXPIRED] "
            "Membaca data member dari Google Sheets..."
        )

        records = sheet.get_all_records()

        expired_members = []

        today = datetime.now().date()

        for row in records:

            # =================================================
            # STATUS
            # =================================================

            status = str(
                row.get(
                    "status",
                    ""
                )
            ).strip().upper()

            # Hanya member ACTIVE
            if status != "ACTIVE":

                continue


            # =================================================
            # PACKAGE
            # =================================================

            paket = str(
                row.get(
                    "paket",
                    ""
                )
            ).strip().lower()


            # Hanya paket yang punya akses grup
            #
            # 1 Bulan TIDAK DIPROSES
            #
            group_package = (
                "6 bulan" in paket
                or
                "12 bulan" in paket
                or
                "3 tahun" in paket
            )


            if not group_package:

                continue


            # =================================================
            # EXPIRED
            # =================================================

            expired_text = str(
                row.get(
                    "expired",
                    ""
                )
            ).strip()


            if not expired_text:

                continue


            # =================================================
            # PERMANENT
            # =================================================

            if (
                "permanent" in
                expired_text.lower()
            ):

                continue


            # =================================================
            # PARSE DATE
            # =================================================

            expired_date = None

            date_formats = [

                "%d-%m-%Y",

                "%d/%m/%Y",

                "%Y-%m-%d",

                "%d-%m-%Y %H:%M:%S",

                "%d/%m/%Y %H:%M:%S",

                "%Y-%m-%d %H:%M:%S"

            ]


            for date_format in date_formats:

                try:

                    expired_date = (
                        datetime.strptime(
                            expired_text,
                            date_format
                        )
                        .date()
                    )

                    break

                except ValueError:

                    continue


            if expired_date is None:

                print(
                    "[EXPIRED] "
                    f"Tanggal tidak dikenali: "
                    f"{expired_text}"
                )

                continue


            # =================================================
            # CHECK EXPIRED
            # =================================================

            if expired_date <= today:

                telegram_id = row.get(
                    "telegram_id"
                )


                if not telegram_id:

                    print(
                        "[EXPIRED] "
                        "Telegram ID kosong."
                    )

                    continue


                expired_members.append({

                    "telegram_id":
                        telegram_id,

                    "username":
                        row.get(
                            "username",
                            ""
                        ),

                    "nama":
                        row.get(
                            "nama",
                            ""
                        ),

                    "paket":
                        row.get(
                            "paket",
                            ""
                        ),

                    "expired":
                        expired_text,

                    "status":
                        status

                })


        print(
            "[EXPIRED] "
            f"Ditemukan "
            f"{len(expired_members)} "
            f"member expired."
        )


        return expired_members


    except Exception as e:

        print(
            "[EXPIRED] "
            "Gagal membaca Google Sheets:"
        )

        print(e)

        raise


# =========================================================
# UPDATE MEMBER STATUS
# =========================================================

def update_member_status(
    telegram_id,
    new_status
):

    try:

        print(
            "[SHEET] "
            f"Mencari Telegram ID "
            f"{telegram_id}"
        )


        records = sheet.get_all_records()


        for index, row in enumerate(
            records,
            start=2
        ):

            row_telegram_id = str(
                row.get(
                    "telegram_id",
                    ""
                )
            ).strip()


            if (
                row_telegram_id
                !=
                str(
                    telegram_id
                ).strip()
            ):

                continue


            # =============================================
            # CARI KOLOM STATUS
            # =============================================

            headers = sheet.row_values(
                1
            )


            if "status" not in headers:

                raise Exception(
                    "Kolom 'status' "
                    "tidak ditemukan."
                )


            status_column = (
                headers.index(
                    "status"
                )
                + 1
            )


            # =============================================
            # UPDATE
            # =============================================

            sheet.update_cell(

                index,

                status_column,

                new_status

            )


            print(
                "[SHEET] "
                f"Telegram ID {telegram_id} "
                f"-> {new_status}"
            )


            return True


        print(
            "[SHEET] "
            f"Telegram ID {telegram_id} "
            f"tidak ditemukan."
        )


        return False


    except Exception as e:

        print(
            "[SHEET] "
            "Gagal update status:"
        )

        print(e)

        raise
