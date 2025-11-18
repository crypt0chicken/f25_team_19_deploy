# In ohq/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # Maps the base path ('') of the included app to the 'index' view
    path('', views.index, name=''),
]