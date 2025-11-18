"""
URL configuration for webapps project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
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
from django.urls import path, include, reverse_lazy # <-- Import include & reverse_lazy
from django.views.generic.base import RedirectView # <-- Import RedirectView
from ohq import views
from ohq.views import CustomEmailView # <-- Import CustomEmailView

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # App URLs
    path('', views.queue_list_action, name = 'queue-list'), # list of all queues
    path('queue/create', views.queue_create_action, name='queue-create'), # <-- New URL
    path('queue/<int:id>', views.queue_action, name = 'queue'), # individual queue view
    path('settings/queue/<int:id>', views.queue_settings_action, name = 'queue-settings'), # settings for an individual queue

    # --- New Site Settings URLs ---
    path('settings/site', views.site_settings_action, name='site-settings'),
    path('api/site/search_users', views.site_search_api, name='api-site-search-users'),
    path('api/site/manage_admin', views.manage_site_admin_api, name='api-site-manage-admin'),
    # --- End New Site Settings URLs ---

    # --- New API URLs ---
    path('api/queue/<int:id>/search_users', views.user_search_api, name='api-search-users'),
    path('api/queue/<int:id>/manage_staff', views.manage_queue_staff_api, name='api-manage-staff'),
    # --- End New API URLs ---

    # This is the new, unified control panel.
    path('accounts/', views.user_control_panel, name='user-control-panel'),
    
    # This overrides the allauth email view to redirect back to our control panel.
    path('accounts/email/', CustomEmailView.as_view(), name='account_email'),

    # This redirects the old user settings URL to the new one.
    path('settings/user/<int:id>', RedirectView.as_view(url=reverse_lazy('user-control-panel'), permanent=True), name = 'user-settings'), # <-- Modified path
    
    # Auth URLs - Must come AFTER our custom /accounts/ and /accounts/email/
    path('accounts/', include('allauth.urls')), # <-- Added allauth URLs
    
    path('mockup', views.index),
]