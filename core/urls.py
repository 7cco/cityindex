from django.urls import path
from . import views
from django.contrib.auth import views as auth_views


urlpatterns = [
    path('', views.home_view, name = 'home'),

    path('main/', views.main_view, name = 'main'),

    path('compare/', views.compare_cities, name = 'compare'),

    path('login/', auth_views.LoginView.as_view(
        template_name = 'core/login.html'
    ), name = 'login'),

    path('logout/', auth_views.LogoutView.as_view(
        next_page = 'home'
    ), name = 'logout'),
    
    path('register/', views.register, name = 'register'),

    path('export/csv/', views.export_cities_csv, name = 'export_csv'),
]