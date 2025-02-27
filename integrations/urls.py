from django.urls import path
from . import views

urlpatterns = [
    path('', views.integration_list, name='integration_list'),
    path('add/', views.add_integration, name='add_integration'),
    path('<int:platform_id>/mapping/', views.integration_mapping, name='integration_mapping'),
    path('<int:platform_id>/preview/', views.preview_mapping, name='preview_mapping'),
    path('<int:platform_id>/edit/', views.edit_integration, name='edit_integration'),
    path('<int:platform_id>/delete/', views.delete_integration, name='delete_integration'),
]