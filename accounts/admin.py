from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class VaultUserAdmin(UserAdmin):
    list_display = ['email', 'first_name', 'last_name', 'email_verified', 'is_2fa_enabled', 'is_staff']
    ordering = ['email']
    search_fields = ['email', 'first_name', 'last_name']
    readonly_fields = ['is_2fa_enabled']
    fieldsets = UserAdmin.fieldsets + (('Vault', {'fields': ('email_verified', 'is_2fa_enabled')}),)
    add_fieldsets = UserAdmin.add_fieldsets + (('Vault', {'fields': ('email', 'email_verified')}),)
