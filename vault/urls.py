from django.urls import path
from . import views

app_name = 'vault'
urlpatterns = [
    path('reveal/<int:pk>/', views.reveal_password, name='reveal_password'),
    path('', views.dashboard, name='dashboard'),
    path('add/', views.add_password, name='add_password'),
    path('edit/<int:pk>/', views.edit_password, name='edit_password'),
    path('delete/<int:pk>/', views.delete_password, name='delete_password'),
    path('category/add/', views.add_category, name='add_category'),
    path('category/edit/<int:pk>/', views.edit_category, name='edit_category'),
    path('category/delete/<int:pk>/', views.delete_category, name='delete_category'),
    path('generate/', views.generate_password_view, name='generate_password'),
    path('check-strength/', views.check_strength, name='check_strength'),
]
