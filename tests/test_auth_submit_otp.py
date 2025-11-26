import uuid

from datetime import timedelta

from django.utils import timezone
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import OTPVerificationSession


class SubmitOtpAPITests(APITestCase):
    def setUp(self):
        self.url = reverse('auth-submit-otp')

    def _create_session(self, **kwargs) -> OTPVerificationSession:
        data = {
            "address": "+998901234567",
            "otp_code": "1234",
            "expires_at": timezone.now() + OTPVerificationSession.OTP_TTL,
        }
        data.update(kwargs)
        return OTPVerificationSession.objects.create(**data)

    def test_submit_otp_success_marks_session_verified(self):
        session = self._create_session()
        response = self.client.post(
            self.url,
            {"session": str(session.id), "otp": "1234"},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        session.refresh_from_db()
        self.assertTrue(session.is_verified)

    def test_submit_otp_rejects_wrong_code(self):
        session = self._create_session()
        response = self.client.post(
            self.url,
            {"session": str(session.id), "otp": "9999"},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        session.refresh_from_db()
        self.assertEqual(session.attempts, 1)
        self.assertFalse(session.is_verified)

    def test_submit_otp_rejects_expired_session(self):
        session = self._create_session()
        session.expires_at = timezone.now() - timedelta(minutes=1)
        session.save(update_fields=["expires_at"])

        response = self.client.post(self.url, {"session": str(session.id), "otp": "1234"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("session", response.data)

    def test_submit_otp_respects_max_attempts(self):
        session = self._create_session(attempts=OTPVerificationSession.MAX_ATTEMPTS)
        response = self.client.post(self.url, {"session": str(session.id), "otp": "1234"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("otp", response.data)

    def test_submit_otp_requires_existing_session(self):
        response = self.client.post(
            self.url,
            {"session": str(uuid.uuid4()), "otp": "1234"},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_submit_otp_validates_client_secret(self):
        session = self._create_session(client_secret="abc")
        response = self.client.post(
            self.url,
            {"session": str(session.id), "otp": "1234", "client_secret": "wrong"},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("client_secret", response.data)

