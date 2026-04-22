from django.conf import settings
from django.shortcuts import redirect

from allauth.account.adapter import DefaultAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class NoSignupAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return False


class WhitelistSocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        email = sociallogin.account.extra_data.get("email", "")
        allowed = settings.ALLOWED_LOGIN_EMAILS

        if email not in allowed:
            raise ImmediateHttpResponse(redirect("forbidden"))

    def is_open_for_signup(self, request, sociallogin):
        email = sociallogin.account.extra_data.get("email", "")
        return email in settings.ALLOWED_LOGIN_EMAILS

    def is_auto_signup_allowed(self, request, sociallogin):
        email = sociallogin.account.extra_data.get("email", "")
        return email in settings.ALLOWED_LOGIN_EMAILS

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        if not user.username:
            email = data.get("email") or sociallogin.account.extra_data.get("email", "")
            user.username = email.split("@")[0] if email else f"user{user.pk or ''}"
        return user
