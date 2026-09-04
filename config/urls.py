from django.urls import path, include
from django.contrib.auth.views import LoginView
from inventory.admin import admin_site
from inventory.forms import StyledAuthenticationForm

urlpatterns = [
    path('admin/', admin_site.urls),
    # Overrides just the login view (matched before the include below)
    # to use StyledAuthenticationForm - Bootstrap classes on its
    # widgets. logout/password-change etc. still come from the include,
    # unchanged.
    path('accounts/login/', LoginView.as_view(authentication_form=StyledAuthenticationForm), name='login'),
    # Built-in login/logout/password-change views (names: login, logout,
    # password_change, ...). Needed because every inventory view now
    # requires authentication (PRD §6.4) and Django's LoginView is the
    # simplest correct implementation - no custom auth code to maintain.
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('inventory.urls')),
]
