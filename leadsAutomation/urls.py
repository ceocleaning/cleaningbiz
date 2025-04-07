"""
URL configuration for leadsAutomation project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from leadsAutomation.error_handlers import handler400, handler403, handler404, handler500

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('automation.urls')),
    path('account/', include('accounts.urls')),
    path('booking/', include('bookings.urls')),
    path('invoice/', include('invoice.urls')),
    path('integration/', include('integrations.urls')),
    path('analytics/', include('analytics.urls')),
    path('ai_agent/', include('ai_agent.urls')),
    path('usage_analytics/', include('usage_analytics.urls')),
    path('subscription/', include('subscription.urls')),
    path('voice_agent/', include('retell_agent.urls')),
    path('admin-dashboard/', include('admin_dashbaord.urls')),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

handler400 = 'leadsAutomation.error_handlers.handler400'
handler403 = 'leadsAutomation.error_handlers.handler403'
handler404 = 'leadsAutomation.error_handlers.handler404'
handler500 = 'leadsAutomation.error_handlers.handler500'