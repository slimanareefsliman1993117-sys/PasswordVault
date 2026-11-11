from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from two_factor.views import SetupView
app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('register/', views.register, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('password_reset/', views.VaultPasswordResetView.as_view(
        template_name='accounts/password_reset.html',
        email_template_name='registration/password_reset_email.html',
        success_url='/accounts/password_reset/done/'
    ), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='accounts/password_reset_done.html'
    ), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='accounts/password_reset_confirm.html',
        success_url='/accounts/reset/done/'
    ), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='accounts/password_reset_complete.html'
    ), name='password_reset_complete'),
    path('recovery-login/', views.recovery_login, name='recovery_login'),
    path('manage-2fa/', views.manage_2fa, name='manage_2fa'),
    path('verify/<uidb64>/<token>/', views.verify_email, name='verify_email'),
    path('resend-verification/', views.resend_verification, name='resend_verification'),
    path('settings/', views.account_settings, name='account_settings'),
    path('two-factor-verify/', views.two_factor_verify, name='two_factor_verify'),
    path('two-factor/setup/', views.VaultSetupView.as_view(), name='two_factor_setup'),
]
