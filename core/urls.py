from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('main/', views.main_view, name='main'),
    path('compare/', views.compare_cities, name='compare'),
]