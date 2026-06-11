from nepali_datetime import date as NepaliDate
from datetime import date as EnglishDate


BS_SEPARATOR = '-'


def ad_to_bs(ad_date):
    if not ad_date:
        return ''
    if isinstance(ad_date, str):
        ad_date = EnglishDate.fromisoformat(ad_date)
    nepali_date = NepaliDate.from_datetime_date(ad_date)
    return nepali_date.strftime(f'%Y{BS_SEPARATOR}%m{BS_SEPARATOR}%d')


def bs_to_ad(bs_date_str):
    if not bs_date_str:
        return None
    parts = bs_date_str.strip().split(BS_SEPARATOR)
    if len(parts) != 3:
        return None
    year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
    nepali_date = NepaliDate(year, month, day)
    return nepali_date.to_datetime_date()


def today_bs():
    return ad_to_bs(EnglishDate.today())


def validate_bs_date(bs_date_str):
    try:
        parts = bs_date_str.strip().split(BS_SEPARATOR)
        if len(parts) != 3:
            return False
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
        NepaliDate(year, month, day)
        return True
    except (ValueError, TypeError):
        return False
