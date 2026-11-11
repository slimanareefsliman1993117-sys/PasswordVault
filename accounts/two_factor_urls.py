from django.urls import path
from two_factor.views import QRGeneratorView
from . import views

app_name = 'two_factor'
urlpatterns = [
    path('account/login/', views.login_view, name='login'),
    path('account/two_factor/setup/', views.VaultSetupView.as_view(), name='setup'),
    path('account/two_factor/qrcode/', QRGeneratorView.as_view(), name='qr'),
    path('account/two_factor/setup/complete/', views.account_settings, name='setup_complete'),
    path('account/two_factor/', views.account_settings, name='profile'),
    path('account/two_factor/disable/', views.account_settings, name='disable'),
    path('account/two_factor/backup/tokens/', views.account_settings, name='backup_tokens'),
]
