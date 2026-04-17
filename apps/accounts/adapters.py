from django.conf import settings
from django.shortcuts import redirect

from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class WhitelistSocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        email = sociallogin.account.extra_data.get("email", "")
        allowed = settings.ALLOWED_LOGIN_EMAILS

        if email not in allowed:
            raise ImmediateHttpResponse(redirect("forbidden"))

    def is_auto_signup_allowed(self, request, sociallogin):
        return True

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        if not user.username:
            email = data.get("email") or sociallogin.account.extra_data.get("email", "")
            user.username = email.split("@")[0] if email else f"user{user.pk or ''}"
        return user
