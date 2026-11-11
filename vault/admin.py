from django.contrib import admin
from .models import Category, PasswordEntry

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'user']
    list_filter = ['user']
    search_fields = ['name']

@admin.register(PasswordEntry)
class PasswordEntryAdmin(admin.ModelAdmin):
    list_display = ['website', 'username', 'user', 'category', 'created_at']
    list_filter = ['user', 'category']
    search_fields = ['website', 'username']
