from django.conf import settings
from django.shortcuts import redirect

from allauth.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class WhitelistSocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        email = sociallogin.account.extra_data.get("email", "")
        allowed = settings.ALLOWED_LOGIN_EMAILS

        if email not in allowed:
            raise ImmediateHttpResponse(redirect("forbidden"))
