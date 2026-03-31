from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
import strings

def get_main_menu(lang='EN'):
    return ReplyKeyboardMarkup(
        [
            [strings.get('BTN_CHECK', lang)],
            [strings.get('BTN_BECOME_MEMBER', lang)],
            [strings.get('BTN_HELP', lang), strings.get('BTN_SETTINGS', lang)]
        ], 
        resize_keyboard=True
    )

def get_become_member_keyboard(lang='EN'):
    url = "https://docs.google.com/forms/d/e/1FAIpQLSchZH3A3wvlq2RQE47KorzGNLqDgX48zc4PP46kapENjnBiBA/viewform?fbzx=7657887268860346255"
    keyboard = [
        [InlineKeyboardButton(strings.get('BTN_BECOME_MEMBER', lang), url=url)]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_settings_menu(lang='EN'):
    return ReplyKeyboardMarkup(
        [
            [strings.get('BTN_LANGUAGES', lang)],
            [strings.get('BTN_BACK', lang)]
        ],
        resize_keyboard=True
    )

def get_language_menu(lang='EN'):
    return ReplyKeyboardMarkup(
        [
            [strings.get('BTN_LANG_EN'), strings.get('BTN_LANG_MS')],
            [strings.get('BTN_BACK', lang)]
        ],
        resize_keyboard=True
    )

def get_cancel_menu(lang='EN'):
    return ReplyKeyboardMarkup(
        [[strings.get('BTN_CANCEL', lang)]], 
        resize_keyboard=True, 
        one_time_keyboard=True
    )

def get_retry_menu(lang='EN'):
    return ReplyKeyboardMarkup(
        [[strings.get('BTN_TRY_AGAIN', lang), strings.get('BTN_CANCEL', lang)]], 
        resize_keyboard=True, 
        one_time_keyboard=True
    )


def get_help_inline_keyboard(lang='EN'):
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("How it works?", callback_data="how_it_works")]]
    )

def get_help_back_inline_keyboard(lang='EN'):
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(strings.get('BTN_BACK', lang), callback_data="help_back")]]
    )
def get_admin_menu(lang='EN'):
    return ReplyKeyboardMarkup([
        [strings.get('BTN_ADMIN_MANAGE', lang)],
        [strings.get('BTN_ADMIN_BROADCAST', lang), strings.get('BTN_ADMIN_STATS', lang)],
        [strings.get('BTN_ADMIN_EXIT', lang)]
    ], resize_keyboard=True, one_time_keyboard=False)

def get_admin_manage_menu(lang='EN'):
    return ReplyKeyboardMarkup(
        [
            [strings.get('BTN_ADMIN_DEL', lang)],
            [strings.get('BTN_ADMIN_LIST', lang), strings.get('BTN_ADMIN_SEARCH', lang)],
            [strings.get('BTN_BACK', lang)]
        ],
        resize_keyboard=True
    )


def get_search_mode_menu(lang='EN'):
    return ReplyKeyboardMarkup(
        [
            [strings.get('BTN_SEARCH_SIMPLE', lang)],
            [strings.get('BTN_SEARCH_DETAIL', lang)],
            [strings.get('BTN_CANCEL', lang)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_confirm_menu(lang='EN'):
    return ReplyKeyboardMarkup(
        [
            [strings.get('BTN_CONFIRM_YES', lang), strings.get('BTN_CONFIRM_NO', lang)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_program_menu(lang='EN'):
    return ReplyKeyboardMarkup(
        [
            [strings.get('BTN_PROG_IT', lang)],
            [strings.get('BTN_PROG_MM', lang)],
            [strings.get('BTN_PROG_CS', lang)],
            [strings.get('BTN_PROG_MD', lang)],
            [strings.get('BTN_PROG_AG', lang)],
            [strings.get('BTN_PROG_LA', lang)],
            [strings.get('BTN_CANCEL', lang)]
        ],
        resize_keyboard=True
    )

