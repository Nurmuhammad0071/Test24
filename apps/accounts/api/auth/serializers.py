import re

from rest_framework import serializers

PHONE_REGEX = re.compile(r"^\+998\d{9}$")


class RequestOtpSerializer(serializers.Serializer):
    address = serializers.CharField(max_length=16)
    client_secret = serializers.CharField(required=False, allow_blank=True)

    def validate_address(self, value: str) -> str:
        if not PHONE_REGEX.match(value):
            raise serializers.ValidationError("Address must be a valid Uzbekistan phone number (e.g. +998901234567).")
        return value


class SubmitOtpSerializer(serializers.Serializer):
    session = serializers.UUIDField()
    otp = serializers.CharField(min_length=4, max_length=4)
    client_secret = serializers.CharField(required=False, allow_blank=True)

    def validate_otp(self, value: str) -> str:
        if not value.isdigit():
            raise serializers.ValidationError("OTP must contain digits only.")
        return value


class SessionDataSerializer(serializers.Serializer):
    PLATFORM_CHOICES = ("ANDROID", "IOS", "WEB", "HarmonyOS")

    platform = serializers.ChoiceField(choices=PLATFORM_CHOICES, required=False)
    device_os = serializers.CharField(required=False, allow_blank=True)
    device_model = serializers.CharField(required=False, allow_blank=True)
    mac_address = serializers.CharField(required=False, allow_blank=True)
    lang = serializers.CharField(required=False, allow_blank=True)
    app_version = serializers.CharField(required=False, allow_blank=True)
    theme = serializers.CharField(required=False, allow_blank=True)


class VerificationDataSerializer(serializers.Serializer):
    session = serializers.UUIDField()
    client_secret = serializers.CharField(required=False, allow_blank=True)


class LoginSerializer(serializers.Serializer):
    session_data = SessionDataSerializer(required=False)
    verification_data = VerificationDataSerializer()
    referral_code = serializers.CharField(required=False, allow_blank=True)


class RequestOtpResponseSerializer(serializers.Serializer):
    session = serializers.UUIDField()
    retry_after = serializers.IntegerField(min_value=0)


class SubmitOtpResponseSerializer(serializers.Serializer):
    session = serializers.UUIDField()


class LoginResponseSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()
    access = serializers.CharField()
    refresh = serializers.CharField()

