from django.urls import path, include
from django.contrib.auth.views import LoginView
from inventory.admin import admin_site
from inventory.forms import StyledAuthenticationForm
from inventory.views import StyledPasswordChangeView

urlpatterns = [
    path('admin/', admin_site.urls),
    # Overrides just login/password-change (matched before the include
    # below) to use styled forms/views - Bootstrap classes, and (for
    # password_change) clearing must_change_password on success. logout
    # etc. still come from the include, unchanged.
    path('accounts/login/', LoginView.as_view(authentication_form=StyledAuthenticationForm), name='login'),
    path('accounts/password_change/', StyledPasswordChangeView.as_view(), name='password_change'),
    # Built-in login/logout/password-change views (names: login, logout,
    # password_change, ...). Needed because every inventory view now
    # requires authentication (PRD §6.4) and Django's LoginView is the
    # simplest correct implementation - no custom auth code to maintain.
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('inventory.urls')),
]
