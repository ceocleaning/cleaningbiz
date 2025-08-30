from django.urls import path
from .views import dashboard
from .auth_views import customer_signup, customer_login, customer_logout, profile, change_password



app_name = 'customer'

urlpatterns = [
    path('dashboard/', dashboard, name='dashboard'),
    path('signup/', customer_signup, name='signup'),
    path('login/', customer_login, name='login'),
    path('logout/', customer_logout, name='logout'),
    path('profile/', profile, name='profile'),
    path('change-password/', change_password, name='change_password'),
]
