# Localization (i18n)

STRINGS = {
    'EN': {
        'WELCOME_MSG': (
            "*Hi {name}!*\n\n"
            "I am the *Eligible STEM Bot*.\n"
            "I can verify your membership status instantly.\n\n"
            "👇 *Use the menu below to begin.*"
        ),
        'BTN_BECOME_MEMBER': "Become Member",
        'REGISTRATION_MSG': (
            "🌟 *Why join STEM?*\n\n"
            "• Official STEM Membership ID\n"
            "• Access to exclusive workshops & events\n"
            "• Networking with industry professionals\n"
            "• STEM Merchandise & goodies\n"
            "• Certificates of participation\n\n"
            "👇 *Click the button below to register!*"
        ),
        'HELP_MSG': (
            "*About This Bot*\n\n"
            "This bot checks the STEM USAS membership database. It connects securely to the official records.\n\n"
            "Made by *zis3c* ☺️"
        ),
        'HOW_IT_WORKS_MSG': (
            "*How it works?*\n\n"
            "Tap *Check Membership*, enter your matric number and IC last 4 digits, and the bot will verify your details against the official STEM USAS record.\n\n" 
            "if both match, your latest membership information is shown instantly, and if not, verification will fail safely.\n\n"
            "If you face any problems, please contact @STEMUSAS.\n\n"    
            "*Video Tutorial:* [How to use STEM bot](https://youtu.be/PAk9x6VrDkE)"
        ),
        'PROMPT_MATRIC': "Step 1/2\n\nPlease type your *Matric Number*:\n(Example: `I24067510`)",
        'PROMPT_IC': "Matric: `{matric}`\n\nStep 2/2\nNow enter the *Last 4 Digits* of your IC:\n(Example: `********1807`)",
        'PROMPT_LOADING': "*Verifying...*",
        
        'VERIFICATION_SUCCESS': (
            "*MEMBERSHIP VERIFIED* 🎉\n"
            "Membership ID: `{membership_id}`\n\n"
            "Name: *{name}*\n"
            "Matric: *{matric}*\n"
            "Program: *{program}*\n"
            "\n"
            "Register date: *{register_date}*\n"
            "Expired date: *{expired_date}*"
        ),
        
        'ERR_INVALID_MATRIC': "*Invalid Matric Format!*\nPlease try again (e.g. `I24067510`)",
        'ERR_INVALID_IC': "*Invalid IC!*\nPlease enter exactly 4 digits.",
        'ERR_DB_CONNECTION': "System Error: Database unavailable. Please contact @STEMUSAS if this persists.",
        'ERR_NOT_FOUND': "*Not Found*\nMatric Number not in records.",
        'ERR_CANCEL': "Oh okay cancelled.",
        'ERR_ACCESS_DENIED': "*Access Denied*\nYou are not an admin.",
        'ERR_CONTACT_SUPPORT': "If you face any problems, please contact @STEMUSAS",
        
        'STATUS_PENDING': "*MEMBERSHIP PENDING* ⏳\nYour registration is under admin review.",
        'STATUS_REJECT': "*MEMBERSHIP REJECTED* 🚫",
        'STATUS_EXPIRED': (
            "*MEMBERSHIP EXPIRED* ⌛\n"
            "Membership ID: `{membership_id}`\n"
            "Expired date: *{expired_date}*\n\n"
            "Please contact *@STEMUSAS* to renew your membership."
        ),
        'NOTIFY_NEW_REG': "🚨 *New Registration*\n\nName: {name}\nMatric: {matric}\nResit: {resit}",
        'BTN_APPROVE': "Accept",
        'BTN_REJECT': "Reject",
        'BTN_VIEW_DETAILS': "View Details",
        'BTN_RENEW': "Renew +1 Year",
        'BTN_CONFIRM_ACTION': "Confirm",
        'BTN_CANCEL_ACTION': "Cancel",
        'MSG_APPROVED': "✅ Accepted {name}.",
        'MSG_REJECTED': "🚫 Rejected {name}.",
        
        # Buttons
        'BTN_CHECK': "Check Membership",
        'BTN_HELP': "Help",
        'BTN_SETTINGS': "Settings",
        'BTN_CANCEL': "Cancel",
        'BTN_TRY_AGAIN': "Try Again",
        'BTN_BACK': "Back",
        

        
        'BTN_LANGUAGES': "Languages",
        'BTN_LANG_EN': "🇬🇧 English",
        'BTN_LANG_MS': "🇲🇾 Bahasa Melayu",
        'MSG_LANG_CHANGED': "Language changed to English! 🇬🇧",
        'MSG_SELECT_LANG': "🌐 *Select Language*",
        
        # Admin - Keep English for Admins usually, but good to have structure
        'ADMIN_DASHBOARD': "*Admin Dashboard*\nSelect an action:",
        'ADMIN_STATS': (
            "*Statistics ({stats_month_year})*\n\n"
            "New Applications: *{total_last_30}*\n"
            "Approved: *{approved_last_30}*\n"
            "Rejected: *{rejected_last_30}*\n"
            "Pending Queue (Current): *{pending_current}*\n"
            "Approval Rate: *{approval_rate}%*\n\n"
            "*Membership Expiry (1 Year Policy)*\n"
            "Expiring in Next 30 Days: *{expiring_next_30}*\n"
            "Expired This Month: *{expired_this_month}*\n\n"
            "*Registered This Month (Approved):* *{registered_current_month_count}*"
        ),
        'ADMIN_STATS_DETAIL': (
            "*Statistics Details ({stats_month_year})*\n\n"
            "*Registered Members (Whole DB):* *{registered_current_month_count}*\n"
            "{registered_current_month_list}\n\n"
            "*Course Mix (% of Registered Members, n={demographic_total})*\n"
            "{course_breakdown}\n\n"
            "*Year of Birth Mix (% of Registered Members, n={demographic_total})*\n"
            "{birth_year_breakdown}"
        ),

        'ADMIN_DEL_START': "*Delete Member*\nEnter Matric Number to delete:",
        'ADMIN_DEL_SUCCESS': "*Deleted*\nRow {row} removed.",
        'ADMIN_DEL_NOT_FOUND': "Matric not found.",
        'ADMIN_SAVING': "Saving...",
        'ADMIN_SEARCHING': "Searching...",
        'ADMIN_EXIT': "Exiting Admin Mode.",
        'ADMIN_LIST_HEADER': "*Member List* (Top {limit}):\n\n{items}",
        'ADMIN_LIST_EMPTY': "No members found.",
        'ADMIN_SEARCH_PROMPT': "Enter *Name*, *Matric*, or *IC* to search:",
        'ADMIN_SEARCH_MODE_PROMPT': "Select Search View:",
        'BTN_SEARCH_SIMPLE': "Simple View",
        'BTN_SEARCH_DETAIL': "Detailed View",
        'ADMIN_SEARCH_RESULT': "*Search Results* ({mode}) for '{query}':\n\n{items}",
        'ADMIN_SEARCH_EMPTY': "No matches found for '{query}'.",
        'ADMIN_PENDING_HEADER': "*Pending Reviews* ({count})\nSelect a member below:",
        'ADMIN_PENDING_EMPTY': "No pending members right now.",
        'BROADCAST_TITLE': "📢 *Admin Announcement*\n\n{msg}",
        
        'BTN_ADMIN_MANAGE': "Manage Members",
        'BTN_ADMIN_STATUS': "Status Members",
        'BTN_STATUS_VERIFIED': "Verified",
        'BTN_STATUS_PENDING': "Pending",
        'BTN_STATUS_REJECTED': "Rejected",
        'BTN_STATUS_EXPIRED': "Expired",
        'BTN_ADMIN_DEL': "Delete Member",
        
        'BTN_SA_MAINTENANCE': "Maintenance Mode",
        'BTN_SA_ADMINS': "Manage Admins",
        'BTN_SA_HEALTH': "System Health",
        'BTN_SA_REFRESH': "Refresh Config",
        'BTN_SA_LOGS': "View Logs",
        'MSG_CONFIG_REFRESHED': "Configuration Refreshed!",

        'BTN_SA_ADD_ADMIN': "Add Admin",
        'BTN_SA_DEL_ADMIN': "Delete Admin",
        'BTN_SA_LIST_ADMIN': "List Admins",
        'BTN_SA_EXIT': "Exit SuperAdmin",
        
        'PROMPT_SA_ADD': "Please reply with the *Telegram ID* (User ID) to add as Admin:",
        'PROMPT_SA_DEL': "Please reply with the *Telegram ID* to remove:",
        'MSG_SA_ADDED': "✅ *Admin added successfully!*",
        'MSG_SA_DELETED': "✅ *Admin removed successfully!*",
        'ERR_SA_INVALID_ID': "⚠️ *Invalid ID format. Must be numeric.*",

        'ERR_SA_ALREADY_ADMIN': "⚠️ *User is already an Admin.*",
        'MSG_SA_PROMOTED': "🎉 *Congratulations! You have been promoted to Admin.*",
        
        'BTN_ADMIN_LIST': "List Members",
        'BTN_ADMIN_SEARCH': "Search Member",
        'BTN_ADMIN_CHECK_PENDING': "Pending Reviews",
        'BTN_ADMIN_BROADCAST': "Broadcast",
        'BTN_ADMIN_STATS': "Stats",
        'BTN_ADMIN_STATS_DETAIL': "Stats Details",
        'BTN_ADMIN_EXIT': "Exit Admin",
        
        'BTN_CONFIRM_YES': "Confirm Send",
        'BTN_CONFIRM_NO': "Cancel",
        
        'ADMIN_BROADCAST_PROMPT': "Enter message to broadcast to all users:",
        'ADMIN_BROADCAST_CONFIRM': "Preview:\n\n{msg}\n\n Send to *{count}* users?",
        'ADMIN_BROADCAST_START': "Sending...",
        'ADMIN_BROADCAST_DONE': "*Broadcast Complete* 📢\n\nSuccess: *{success}*\nBlocked/Failed: *{failed}*",
        
        # Programs
        'BTN_PROG_IT': "DIPLOMA TEKNOLOGI MAKLUMAT",
        'BTN_PROG_MM': "DIPLOMA MULTIMEDIA DENGAN DAKWAH",
        'BTN_PROG_CS': "IJAZAH SARJANA MUDA SAINS KOMPUTER",
        'BTN_PROG_MD': "IJAZAH SARJANA MUDA MULTIMEDIA KREATIF",
        'BTN_PROG_AG': "IJAZAH SARJANA MUDA PERTANIAN",
        'BTN_PROG_LA': "IJAZAH SARJANA MUDA SENI BINA LANDSKAP",
    },
    'MS': {
        'WELCOME_MSG': (
            "*Hai {name}!*\n\n"
            "Saya *Eligible STEM Bot*.\n"
            "Saya boleh semak status keahlian anda dengan pantas.\n\n"
            "👇 *Gunakan menu di bawah untuk mula.*"
        ),
        'BTN_BECOME_MEMBER': "Menjadi Ahli",
        'REGISTRATION_MSG': (
            "🌟 *Kenapa sertai STEM?*\n\n"
            "• ID Keahlian STEM Rasmi\n"
            "• Akses ke bengkel & acara eksklusif\n"
            "• Rangkaian dengan profesional industri\n"
            "• Barangan & cenderahati STEM\n"
            "• Sijil penyertaan\n\n"
            "👇 *Klik butang di bawah untuk mendaftar!*"
        ),
        'HELP_MSG': (
            "*Tentang Bot Ini*\n\n"
            "Perkhidmatan ini menyemak pangkalan data keahlian STEM USAS.\n"
            "Ia bersambung secara selamat ke rekod rasmi.\n\n"
            "Jika anda menghadapi sebarang masalah, sila hubungi @STEMUSAS\n\n"
            "Dev: zis3c ☺️"
        ),
        'PROMPT_MATRIC': "Langkah 1/2\n\nSila taip *Nombor Matrik* anda:\n(Contoh: `I24067510`)",
        'PROMPT_IC': "Matrik: `{matric}`\n\nLangkah 2/2\nSekarang masukkan *4 Digit Terakhir* IC anda:\n(Contoh: `********1807`)",
        'PROMPT_LOADING': "*Sedang Semak...*",
        
        'VERIFICATION_SUCCESS': (
            "*KEAHLIAN DISAHKAN* 🎉\n"
            "ID Keahlian: `{membership_id}`\n\n"
            "Nama: {name}\n"
            "Matrik: {matric}\n"
            "Program: {program}\n"
            "\n"
            "Tarikh Daftar: *{register_date}*\n"
            "Tarikh Tamat: *{expired_date}*"
        ),
        
        'ERR_INVALID_MATRIC': "*Format Matrik Tidak Sah!*\nSila cuba lagi (cth. `I24067510`)",
        'ERR_INVALID_IC': "*IC Tidak Sah!*\nSila masukkan tepat 4 digit.",
        'ERR_DB_CONNECTION': "Ralat Sistem: Pangkalan data tidak tersedia. Sila hubungi @STEMUSAS jika berterusan.",
        'ERR_NOT_FOUND': "*Tidak Dijumpai*\nNombor Matrik tiada dalam rekod.",
        'ERR_CANCEL': "Oh okay dibatalkan.",
        'ERR_ACCESS_DENIED': "*Akses Ditolak*\nAnda bukan admin.",
        'ERR_CONTACT_SUPPORT': "Jika anda menghadapi sebarang masalah, sila hubungi @STEMUSAS",
        
        'STATUS_PENDING': "*KEAHLIAN SEDANG DIPROSES* ⏳\nPermohonan anda sedang disemak oleh admin.",
        'STATUS_REJECT': "*KEAHLIAN DITOLAK* 🚫",
        'STATUS_EXPIRED': (
            "*KEAHLIAN SUDAH TAMAT* ⌛\n"
            "ID Keahlian: `{membership_id}`\n"
            "Tarikh Tamat: *{expired_date}*\n\n"
            "Untuk perbaharui, sila hubungi *@STEMUSAS*."
        ),
        'NOTIFY_NEW_REG': "🚨 *Pendaftaran Baru*\n\nNama: {name}\nMatrik: {matric}\nResit: {resit}",
        'BTN_APPROVE': "Terima",
        'BTN_REJECT': "Tolak",
        'BTN_VIEW_DETAILS': "Lihat Butiran",
        'BTN_RENEW': "Perbaharui +1 Tahun",
        'BTN_CONFIRM_ACTION': "Sahkan",
        'BTN_CANCEL_ACTION': "Batal",
        'MSG_APPROVED': "✅ Diterima {name}.",
        'MSG_REJECTED': "🚫 Ditolak {name}.",
        
        # Buttons
        'BTN_CHECK': "Semak Keahlian",
        'BTN_HELP': "Info",
        'BTN_SETTINGS': "Tetapan",
        'BTN_CANCEL': "Batal",
        'BTN_TRY_AGAIN': "Cuba Lagi",
        'BTN_BACK': "Kembali",
        

        
        'BTN_LANGUAGES': "Bahasa",
        'BTN_LANG_EN': "🇬🇧 English",
        'BTN_LANG_MS': "🇲🇾 Bahasa Melayu",
        'MSG_LANG_CHANGED': "Bahasa ditukar kepada Bahasa Melayu! 🇲🇾",
        'MSG_SELECT_LANG': "🌐 *Pilih Bahasa*",
        
        # Admin - Fallback to English often okay, but can translate
        'ADMIN_DASHBOARD': "*Admin Dashboard*\nPilih tindakan:",
        'ADMIN_STATS': (
            "*Statistik ({stats_month_year})*\n\n"
            "Permohonan Baharu: *{total_last_30}*\n"
            "Diluluskan: *{approved_last_30}*\n"
            "Ditolak: *{rejected_last_30}*\n"
            "Dalam Giliran (Semasa): *{pending_current}*\n"
            "Kadar Kelulusan: *{approval_rate}%*\n\n"
            "*Tamat Keahlian (Polisi 1 Tahun)*\n"
            "Akan Tamat Dalam 30 Hari: *{expiring_next_30}*\n"
            "Sudah Tamat Bulan Ini: *{expired_this_month}*\n\n"
            "*Berdaftar Bulan Ini (Lulus):* *{registered_current_month_count}*"
        ),
        'ADMIN_STATS_DETAIL': (
            "*Butiran Statistik ({stats_month_year})*\n\n"
            "*Jumlah Ahli Berdaftar (Keseluruhan DB):* *{registered_current_month_count}*\n"
            "{registered_current_month_list}\n\n"
            "*Peratus Kursus (Ahli Berdaftar, n={demographic_total})*\n"
            "{course_breakdown}\n\n"
            "*Peratus Tahun Lahir (Ahli Berdaftar, n={demographic_total})*\n"
            "{birth_year_breakdown}"
        ),

        'ADMIN_DEL_START': "*Padam Ahli*\nMasukkan Nombor Matrik untuk dibuang:",
        'ADMIN_DEL_SUCCESS': "*Dipadam*\nBaris {row} dikeluarkan.",
        'ADMIN_DEL_NOT_FOUND': "Matrik tidak dijumpai.",
        'ADMIN_SAVING': "Menyimpan...",
        'ADMIN_SEARCHING': "Mencari...",
        'ADMIN_EXIT': "Keluar Mod Admin.",
        'ADMIN_LIST_HEADER': "*Senarai Ahli* (Top {limit}):\n\n{items}",
        'ADMIN_LIST_EMPTY': "Tiada ahli dijumpai.",
        'ADMIN_SEARCH_PROMPT': "Masukkan *Nama*, *Matrik*, atau *IC* untuk carian:",
        'ADMIN_SEARCH_MODE_PROMPT': "Pilih Paparan Carian:",
        'BTN_SEARCH_SIMPLE': "Paparan Ringkas",
        'BTN_SEARCH_DETAIL': "Paparan Terperinci",
        'ADMIN_SEARCH_RESULT': "*Keputusan Carian* ({mode}) untuk '{query}':\n\n{items}",
        'ADMIN_SEARCH_EMPTY': "Tiada padanan untuk '{query}'.",
        'ADMIN_PENDING_HEADER': "*Semakan Tertunda* ({count})\nPilih ahli di bawah:",
        'ADMIN_PENDING_EMPTY': "Tiada ahli tertunda sekarang.",
        'BROADCAST_TITLE': "📢 *Pengumuman Admin*\n\n{msg}",
        
        'BTN_ADMIN_MANAGE': "Urus Ahli",
        'BTN_ADMIN_STATUS': "Status Ahli",
        'BTN_STATUS_VERIFIED': "Disahkan",
        'BTN_STATUS_PENDING': "Sedang Diproses",
        'BTN_STATUS_REJECTED': "Ditolak",
        'BTN_STATUS_EXPIRED': "Tamat",
        'BTN_ADMIN_ADD': "Tambah Ahli",
        'BTN_ADMIN_DEL': "Padam Ahli",
        'BTN_ADMIN_LIST': "Senarai Ahli",
        'BTN_ADMIN_SEARCH': "Cari Ahli",
        'BTN_ADMIN_CHECK_PENDING': "Semakan Tertunda",
        'BTN_ADMIN_BROADCAST': "Hebahan",
        'BTN_ADMIN_STATS': "Statistik",
        'BTN_ADMIN_STATS_DETAIL': "Butiran Statistik",
        'BTN_ADMIN_EXIT': "Keluar Admin",
        
        'BTN_SA_MAINTENANCE': "Mod Penyelenggaraan",
        'BTN_SA_ADMINS': "Urus Admin",
        'BTN_SA_HEALTH': "Kesihatan Sistem",
        'BTN_SA_REFRESH': "Muat Semula Konfigurasi",
        'BTN_SA_LOGS': "Lihat Log",
        'MSG_CONFIG_REFRESHED': "Konfigurasi Dikemaskini!",
        'BTN_SA_ADD_ADMIN': "Tambah Admin",
        'BTN_SA_DEL_ADMIN': "Padam Admin",
        'BTN_SA_LIST_ADMIN': "Senarai Admin",
        'BTN_SA_EXIT': "Keluar SuperAdmin",
        
        'PROMPT_SA_ADD': "Sila balas dengan *ID Telegram* untuk ditambah:",
        'PROMPT_SA_DEL': "Sila balas dengan *ID Telegram* untuk dipadam:",
        'MSG_SA_ADDED': "✅ Admin berjaya ditambah!",
        'MSG_SA_DELETED': "✅ Admin berjaya dipadam!",
        'ERR_SA_INVALID_ID': "⚠️ Format ID tidak sah.",
        
        'ERR_SA_ALREADY_ADMIN': "⚠️ Pengguna ini sudah menjadi Admin.",
        'MSG_SA_PROMOTED': "🎉 Tahniah! Anda telah dilantik sebagai Admin.",
        
        'BTN_CONFIRM_YES': "Sahkan Hantar",
        'BTN_CONFIRM_NO': "Batal",
        
        'ADMIN_BROADCAST_PROMPT': "Masukkan mesej untuk hebahan kepada semua:",
        'ADMIN_BROADCAST_CONFIRM': "Pratonton:\n\n{msg}\n\n*Hantar kepada {count} pengguna?*",
        'ADMIN_BROADCAST_START': "Sedang menghantar...",
        'ADMIN_BROADCAST_DONE': "*Hebahan Selesai* 📢\n\n✅ Berjaya: {success}\n❌ Gagal: {failed}",
        
        # Programs (Same for both languages usually, or translate if needed)
        'BTN_PROG_IT': "DIPLOMA TEKNOLOGI MAKLUMAT",
        'BTN_PROG_MM': "DIPLOMA MULTIMEDIA DENGAN DAKWAH",
        'BTN_PROG_CS': "IJAZAH SARJANA MUDA SAINS KOMPUTER",
        'BTN_PROG_MD': "IJAZAH SARJANA MUDA MULTIMEDIA KREATIF",
        'BTN_PROG_AG': "IJAZAH SARJANA MUDA PERTANIAN",
        'BTN_PROG_LA': "IJAZAH SARJANA MUDA SENI BINA LANDSKAP",
    }
}

DEFAULT_LANG = 'EN'


def format_program_short(program: str) -> str:
    """Return compact program code for UI display when recognized."""
    text = str(program or "").strip()
    key = " ".join(text.upper().split())
    if not key or key == "-":
        return "-"

    if "SAINS KOMPUTER" in key:
        return "BCS"
    if "MULTIMEDIA KREATIF" in key:
        return "BCM"
    if "PERTANIAN" in key:
        return "BAgr"
    if "SENI BINA LANDSKAP" in key:
        return "BLA"
    if "DIPLOMA TEKNOLOGI MAKLUMAT" in key:
        return "Dip. IT"
    if "DIPLOMA MULTIMEDIA DENGAN DAKWAH" in key:
        return "Dip.MD"

    return text

def get(key, lang='EN'):
    """Get string by key and language, fall back to Default if missing"""
    return STRINGS.get(lang, STRINGS[DEFAULT_LANG]).get(key, STRINGS[DEFAULT_LANG].get(key, key))

def get_all(key):
    """Get a list of values for a key across all languages (for Filters)"""
    return [STRINGS[l].get(key) for l in STRINGS if STRINGS[l].get(key)]
