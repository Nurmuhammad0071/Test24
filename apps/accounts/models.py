import uuid
from datetime import timedelta

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, phone_number, password=None, **extra_fields):
        if not phone_number:
            raise ValueError("Users must have a phone number")
        phone_number = self.normalize_phone(phone_number)
        user = self.model(phone_number=phone_number, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(phone_number, password, **extra_fields)

    def create_superuser(self, phone_number, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(phone_number, password, **extra_fields)

    @staticmethod
    def normalize_phone(phone_number: str) -> str:
        return phone_number.strip()


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone_number = models.CharField(
        max_length=16,
        unique=True,
        validators=[
            RegexValidator(
                regex=r"^\+?\d{5,16}$",
                message="Phone number must be in international format (e.g. +998901234567)",
            )
        ],
    )
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "phone_number"
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ("date_joined",)

    def __str__(self):
        return self.phone_number


class OTPVerificationSession(models.Model):
    OTP_TTL = timedelta(minutes=5)
    RESEND_INTERVAL = timedelta(seconds=60)
    MAX_ATTEMPTS = 5

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    address = models.CharField(max_length=32, db_index=True)
    client_secret = models.CharField(max_length=255, blank=True, default="")
    otp_code = models.CharField(max_length=4)
    expires_at = models.DateTimeField()
    last_sent_at = models.DateTimeField(auto_now_add=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=MAX_ATTEMPTS)
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    session_data = models.JSONField(blank=True, default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.address} ({self.id})"

    # business helpers
    def seconds_until_retry(self) -> int:
        delta = timezone.now() - self.last_sent_at
        remaining = self.RESEND_INTERVAL.total_seconds() - delta.total_seconds()
        return max(0, int(remaining))

    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    def can_retry(self) -> bool:
        return self.seconds_until_retry() == 0

    def mark_sent(self, otp_code: str, client_secret: str = ""):
        self.otp_code = otp_code
        self.client_secret = client_secret or ""
        self.last_sent_at = timezone.now()
        self.expires_at = self.last_sent_at + self.OTP_TTL
        self.attempts = 0
        self.is_verified = False
        self.verified_at = None
        self.save(
            update_fields=[
                "otp_code",
                "client_secret",
                "last_sent_at",
                "expires_at",
                "attempts",
                "is_verified",
                "verified_at",
            ]
        )

    def register_attempt(self, success: bool):
        if success:
            self.is_verified = True
            self.verified_at = timezone.now()
            self.save(update_fields=["is_verified", "verified_at"])
        else:
            self.attempts = models.F("attempts") + 1
            self.save(update_fields=["attempts"])
            self.refresh_from_db(fields=["attempts"])

    def consume(self, session_payload: dict | None = None):
        self.consumed_at = timezone.now()
        if session_payload is not None:
            self.session_data = session_payload
        self.save(update_fields=["consumed_at", "session_data"])
