from django.urls import path

from .views import LoginView, RequestOTPView, SubmitOTPView

urlpatterns = [
    path('request-otp/', RequestOTPView.as_view(), name='auth-request-otp'),
    path('submit-otp/', SubmitOTPView.as_view(), name='auth-submit-otp'),
    path('login/', LoginView.as_view(), name='auth-login'),
]


