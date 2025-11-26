import logging
import random
from typing import Tuple

from django.db import transaction
from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import OTPVerificationSession, User

from .serializers import (
    LoginResponseSerializer,
    LoginSerializer,
    RequestOtpResponseSerializer,
    RequestOtpSerializer,
    SubmitOtpResponseSerializer,
    SubmitOtpSerializer,
)

logger = logging.getLogger(__name__)


class MockSMSService:
    """Simple SMS client used for local development and tests."""

    def send_otp(self, phone_number: str, otp_code: str) -> None:
        logger.info("Mock SMS → %s: %s", phone_number, otp_code)


class OTPWorkflowService:
    TEST_PHONE = "+998999990000"
    TEST_OTP = "0571"
    OTP_DIGITS = 4

    def __init__(self, sms_client: MockSMSService | None = None):
        self.sms_client = sms_client or MockSMSService()

    def _generate_otp(self, address: str) -> str:
        if address == self.TEST_PHONE:
            return self.TEST_OTP
        return f"{random.randint(0, 10 ** self.OTP_DIGITS - 1):0{self.OTP_DIGITS}d}"

    def _get_active_session(self, address: str) -> OTPVerificationSession | None:
        return (
            OTPVerificationSession.objects.filter(address=address, consumed_at__isnull=True)
            .order_by("-created_at")
            .first()
        )

    def issue_code(self, address: str, client_secret: str = "") -> Tuple[OTPVerificationSession, bool, int]:
        session = self._get_active_session(address)
        if session and not session.can_retry():
            return session, True, session.seconds_until_retry()

        otp_code = self._generate_otp(address)
        if session and not session.is_verified:
            session.mark_sent(otp_code, client_secret)
        else:
            session = OTPVerificationSession.objects.create(
                address=address,
                client_secret=client_secret or "",
                otp_code=otp_code,
                expires_at=timezone.now() + OTPVerificationSession.OTP_TTL,
            )
        self.sms_client.send_otp(address, otp_code)
        return session, False, 0


otp_service = OTPWorkflowService()


def _get_session_or_404(session_id) -> OTPVerificationSession:
    try:
        return OTPVerificationSession.objects.get(id=session_id)
    except OTPVerificationSession.DoesNotExist as exc:
        raise NotFound(detail="Session not found.") from exc


def _validate_client_secret(session: OTPVerificationSession, provided_secret: str | None) -> None:
    if session.client_secret and session.client_secret != (provided_secret or ""):
        raise ValidationError({"client_secret": "Client secret mismatch."})


def _ensure_session_is_active(session: OTPVerificationSession) -> None:
    if session.is_expired():
        raise ValidationError({"session": "Session expired. Please request a new OTP."})
    if session.consumed_at:
        raise ValidationError({"session": "Session already used for login."})


class RequestOTPView(APIView):
    permission_classes = [AllowAny]
    serializer_class = RequestOtpSerializer

    @swagger_auto_schema(
        operation_id="AuthRequestOTP",
        operation_description="Creates or reuses an OTP session and sends a 4-digit code to the given phone number.",
        request_body=RequestOtpSerializer,
        responses={200: RequestOtpResponseSerializer},
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        session, throttled, retry_after = otp_service.issue_code(
            serializer.validated_data["address"],
            serializer.validated_data.get("client_secret", ""),
        )

        if throttled:
            return Response({"session": str(session.id), "retry_after": retry_after}, status=status.HTTP_200_OK)

        return Response({"session": str(session.id), "retry_after": 0}, status=status.HTTP_200_OK)


class SubmitOTPView(APIView):
    permission_classes = [AllowAny]
    serializer_class = SubmitOtpSerializer

    @swagger_auto_schema(
        operation_id="AuthSubmitOTP",
        operation_description="Validates the submitted OTP for the provided session.",
        request_body=SubmitOtpSerializer,
        responses={200: SubmitOtpResponseSerializer},
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = _get_session_or_404(serializer.validated_data["session"])
        _ensure_session_is_active(session)
        _validate_client_secret(session, serializer.validated_data.get("client_secret"))

        if session.attempts >= session.max_attempts:
            raise ValidationError({"otp": "Maximum attempts exceeded. Please request a new OTP."})

        if serializer.validated_data["otp"] != session.otp_code:
            session.register_attempt(False)
            raise ValidationError({"otp": "OTP is incorrect."})

        session.register_attempt(True)
        return Response({"session": str(session.id)}, status=status.HTTP_200_OK)


class LoginView(APIView):
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    @swagger_auto_schema(
        operation_id="AuthLogin",
        operation_description="Exchanges a verified OTP session for JWT access and refresh tokens.",
        request_body=LoginSerializer,
        responses={200: LoginResponseSerializer},
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        verification_payload = serializer.validated_data["verification_data"]
        session = _get_session_or_404(verification_payload["session"])
        _validate_client_secret(session, verification_payload.get("client_secret"))

        if not session.is_verified:
            raise ValidationError({"session": "OTP not verified yet."})
        _ensure_session_is_active(session)

        with transaction.atomic():
            user, _ = User.objects.get_or_create(phone_number=session.address)
            metadata = {
                "session_data": serializer.validated_data.get("session_data") or {},
                "referral_code": serializer.validated_data.get("referral_code"),
            }
            session.consume(metadata)

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user_id": str(user.id),
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_200_OK,
        )

