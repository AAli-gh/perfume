from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

from apps.core.validators import iran_mobile_validator, postal_code_validator


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("ایمیل الزامی است.")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra["is_staff"] = True
        extra["is_superuser"] = True
        return self._create_user(email, password, **extra)


class User(AbstractUser):
    """کاربر با ورود از طریق ایمیل."""

    username = None
    email = models.EmailField("ایمیل", unique=True)
    phone = models.CharField("موبایل", max_length=11, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = "کاربر"
        verbose_name_plural = "کاربران"

    def __str__(self):
        return self.get_full_name() or self.email

    @property
    def display_name(self):
        return self.first_name or self.email.split("@")[0]


class Address(models.Model):
    """آدرس ذخیره‌شده مشتری؛ در تسویه‌حساب پیش‌فرض قرار می‌گیرد.

    سفارش‌ها کپی آدرس را نگه می‌دارند (snapshot)، پس تغییر یا حذف آدرس روی سفارش‌های قبلی اثری ندارد.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="addresses", verbose_name="کاربر")
    title = models.CharField("عنوان", max_length=50, blank=True, help_text="مثلاً: خانه، محل کار")
    first_name = models.CharField("نام", max_length=80)
    last_name = models.CharField("نام خانوادگی", max_length=80)
    phone = models.CharField("موبایل", max_length=11, validators=[iran_mobile_validator])
    province = models.CharField("استان", max_length=50)
    city = models.CharField("شهر", max_length=80)
    address = models.CharField("نشانی", max_length=300)
    postal_code = models.CharField("کد پستی", max_length=10, validators=[postal_code_validator])
    is_default = models.BooleanField("آدرس پیش‌فرض", default=False)
    created_at = models.DateTimeField("تاریخ ثبت", auto_now_add=True)

    FIELDS = ("first_name", "last_name", "phone", "province", "city", "address", "postal_code")

    class Meta:
        ordering = ["-is_default", "-created_at"]
        verbose_name = "آدرس"
        verbose_name_plural = "آدرس‌ها"
        constraints = [
            models.UniqueConstraint(
                fields=["user"], condition=models.Q(is_default=True), name="accounts_single_default_address"
            ),
        ]

    def __str__(self):
        return f"{self.title or self.city} — {self.address}"
