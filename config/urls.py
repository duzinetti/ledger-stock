from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # Built-in login/logout/password-change views (names: login, logout,
    # password_change, ...). Needed because every inventory view now
    # requires authentication (PRD §6.4) and Django's LoginView is the
    # simplest correct implementation - no custom auth code to maintain.
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('inventory.urls')),
]
