from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import OTPVerificationSession


class RequestOtpAPITests(APITestCase):
    def setUp(self):
        self.url = reverse('auth-request-otp')
        self.phone_number = "+998901234567"

    def test_request_otp_success(self):
        response = self.client.post(self.url, {"address": self.phone_number}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["retry_after"], 0)
        self.assertTrue(OTPVerificationSession.objects.filter(id=response.data["session"]).exists())

    def test_request_otp_respects_retry_after(self):
        first = self.client.post(self.url, {"address": self.phone_number}, format='json')
        self.assertEqual(first.status_code, status.HTTP_200_OK)

        second = self.client.post(self.url, {"address": self.phone_number}, format='json')
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertGreater(second.data["retry_after"], 0)
        self.assertEqual(first.data["session"], second.data["session"])

    def test_request_otp_validates_phone_number(self):
        response = self.client.post(self.url, {"address": "12345"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("address", response.data)

    def test_request_otp_uses_test_number_and_code(self):
        test_number = "+998999990000"
        response = self.client.post(self.url, {"address": test_number}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        session = OTPVerificationSession.objects.get(id=response.data["session"])
        self.assertEqual(session.otp_code, "0571")


