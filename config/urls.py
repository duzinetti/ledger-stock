from django.urls import path, include
from inventory.admin import admin_site

urlpatterns = [
    path('admin/', admin_site.urls),
    # Built-in login/logout/password-change views (names: login, logout,
    # password_change, ...). Needed because every inventory view now
    # requires authentication (PRD §6.4) and Django's LoginView is the
    # simplest correct implementation - no custom auth code to maintain.
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('inventory.urls')),
]
