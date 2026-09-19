"""Storefront / customer endpoints, mounted at /api/v1/."""
from django.urls import include, path
from rest_framework.routers import SimpleRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

app_name = "accounts"

router = SimpleRouter()
router.register("account/addresses", views.AddressViewSet, basename="address")

urlpatterns = [
    path("auth/register/", views.RegisterView.as_view(), name="register"),
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("auth/password/change/", views.ChangePasswordView.as_view(), name="password-change"),
    path("auth/password/forgot/", views.ForgotPasswordView.as_view(), name="password-forgot"),
    path("auth/password/reset/", views.ResetPasswordView.as_view(), name="password-reset"),
    path("account/profile/", views.ProfileView.as_view(), name="profile"),
    path("", include(router.urls)),
]
