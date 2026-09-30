from django.urls import path, include
from django.contrib.auth.views import LoginView
from inventory.admin import admin_site
from inventory.forms import StyledAuthenticationForm
from inventory.views import StyledPasswordChangeView, privacy_policy, robots_txt, service_worker
from rest_framework.routers import DefaultRouter
from inventory.api_views import ProductViewSet, StockMovementViewSet
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

router = DefaultRouter()
router.register('products', ProductViewSet, basename='product')
router.register('movements', StockMovementViewSet, basename='movement')


urlpatterns = [
    path('admin/', admin_site.urls),
    path('robots.txt', robots_txt, name='robots_txt'),
    path('service-worker.js', service_worker, name='service_worker'),
    path('privacidade/', privacy_policy, name='privacy_policy'),
    # router.urls já vem com todas as rotas de ProductViewSet prontas
    # (list/create/retrieve/update) - incluído sob api/ pra separar
    # claramente das rotas HTML normais.
    path('api/', include(router.urls)),
    # Login/refresh JWT - trocam usuário+senha (ou um refresh token)
    # por um access token, sem depender de cookie de sessão.
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    # SpectacularAPIView gera o schema (o "mapa" da API) a partir dos
    # serializers/views automaticamente; SpectacularSwaggerView só
    # mostra esse schema de forma navegável/testável no navegador -
    # por isso aponta pro nome do primeiro (url_name='schema').
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
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
