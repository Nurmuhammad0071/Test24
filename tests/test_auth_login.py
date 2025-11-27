from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import OTPVerificationSession, User


class LoginAPITests(APITestCase):
    def setUp(self):
        self.url = reverse('auth-login')
        self.phone = "+998901234567"

    def _create_verified_session(self, **kwargs) -> OTPVerificationSession:
        session = OTPVerificationSession.objects.create(
            address=self.phone,
            otp_code="1234",
            expires_at=timezone.now() + OTPVerificationSession.OTP_TTL,
            is_verified=True,
            verified_at=timezone.now(),
        )
        for field, value in kwargs.items():
            setattr(session, field, value)
        session.save()
        return session

    def _login_payload(self, session_id, client_secret=""):
        return {
            "verification_data": {
                "session": str(session_id),
                "client_secret": client_secret,
            },
            "session_data": {
                "platform": "ANDROID",
                "device_os": "14",
                "device_model": "Pixel",
            },
        }

    def test_login_success_returns_tokens_and_user(self):
        session = self._create_verified_session()
        response = self.client.post(self.url, self._login_payload(session.id), format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        user = User.objects.get(phone_number=self.phone)
        session.refresh_from_db()
        self.assertIsNotNone(session.consumed_at)
        self.assertEqual(response.data["user_id"], str(user.id))

    def test_login_rejects_unverified_session(self):
        session = OTPVerificationSession.objects.create(
            address=self.phone,
            otp_code="1234",
            expires_at=timezone.now() + OTPVerificationSession.OTP_TTL,
        )
        response = self.client.post(self.url, self._login_payload(session.id), format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("session", response.data)

    def test_login_rejects_consumed_session(self):
        session = self._create_verified_session(consumed_at=timezone.now())
        response = self.client.post(self.url, self._login_payload(session.id), format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("session", response.data)

    def test_login_validates_client_secret(self):
        session = self._create_verified_session(client_secret="secret")
        response = self.client.post(self.url, self._login_payload(session.id, client_secret="wrong"), format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("client_secret", response.data)

    def test_full_flow_with_test_number(self):
        request_url = reverse('auth-request-otp')
        submit_url = reverse('auth-submit-otp')
        phone = "+998999990000"

        request_resp = self.client.post(request_url, {"address": phone}, format='json')
        self.assertEqual(request_resp.status_code, status.HTTP_200_OK)
        session_id = request_resp.data["session"]

        submit_resp = self.client.post(
            submit_url,
            {"session": session_id, "otp": "0571"},
            format='json',
        )
        self.assertEqual(submit_resp.status_code, status.HTTP_200_OK)

        login_resp = self.client.post(
            self.url,
            {
                "verification_data": {"session": session_id},
                "session_data": {"platform": "ANDROID"},
            },
            format='json',
        )
        self.assertEqual(login_resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", login_resp.data)



