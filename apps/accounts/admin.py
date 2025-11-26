from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import OTPVerificationSession, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("date_joined",)
    list_display = ("phone_number", "is_staff", "is_superuser", "date_joined")
    search_fields = ("phone_number", "first_name", "last_name")
    fieldsets = (
        (None, {"fields": ("phone_number", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name")}),
        (_("Permissions"), {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("phone_number", "password1", "password2", "is_staff", "is_superuser"),
            },
        ),
    )
    readonly_fields = ("date_joined", "last_login")


@admin.register(OTPVerificationSession)
class OTPVerificationSessionAdmin(admin.ModelAdmin):
    list_display = ("address", "id", "is_verified", "attempts", "expires_at", "consumed_at")
    search_fields = ("address", "id")
    list_filter = ("is_verified", "consumed_at")
