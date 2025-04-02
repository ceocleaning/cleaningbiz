from django.urls import path
from . import views

urlpatterns = [
    path('setup/', views.setup_retell_agent, name='setup_retell_agent'),
    path('create-llm/', views.create_retell_llm, name='create_retell_llm'),
    path('list-voices/', views.list_retell_voices, name='list_retell_voices'),
    path('agents/', views.list_retell_agents, name='list_retell_agents'),
    path('agents/update/<str:agent_id>/', views.update_retell_agent, name='update_retell_agent'),
    path('agents/delete/<str:agent_id>/', views.delete_retell_agent, name='delete_retell_agent'),
    path('agents/assign-number/', views.assign_phone_number, name='assign_phone_number'),
] 