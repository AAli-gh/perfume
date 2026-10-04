"""مشخصات ساخت‌یافته رایحه: پایه مقایسه محصولات، «عطر مناسب من» و پیشنهادها."""

from django.db import models


class Gender(models.TextChoices):
    MEN = "men", "مردانه"
    WOMEN = "women", "زنانه"
    UNISEX = "unisex", "یونیسکس"


class Concentration(models.TextChoices):
    EXTRAIT = "extrait", "اکستریت (عصاره عطر)"
    EDP = "edp", "ادو پرفیوم"
    EDT = "edt", "ادو تویلت"
    EDC = "edc", "ادو کلن"


class Season(models.TextChoices):
    SPRING = "spring", "بهار"
    SUMMER = "summer", "تابستان"
    AUTUMN = "autumn", "پاییز"
    WINTER = "winter", "زمستان"


class Occasion(models.TextChoices):
    DAILY = "daily", "روزانه"
    OFFICE = "office", "محیط کار"
    EVENING = "evening", "شب و مهمانی"
    FORMAL = "formal", "مجلسی و رسمی"
    ROMANTIC = "romantic", "قرار عاشقانه"


LEVELS = {1: "خیلی کم", 2: "کم", 3: "متوسط", 4: "زیاد", 5: "خیلی زیاد"}
LONGEVITY_HOURS = {1: "کمتر از ۲ ساعت", 2: "۲ تا ۴ ساعت", 3: "۴ تا ۶ ساعت", 4: "۶ تا ۸ ساعت", 5: "بیش از ۸ ساعت"}


def labels(choices, values):
    mapping = dict(choices.choices)
    return [mapping[v] for v in values or [] if v in mapping]
