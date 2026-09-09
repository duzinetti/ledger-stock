"""
Middleware customizado do app - roda em toda requisição, entre a
AuthenticationMiddleware do Django (que resolve request.user) e a view.
"""
from django.shortcuts import redirect
from django.urls import reverse


class ForcePasswordChangeMiddleware:
    """Redireciona qualquer usuário autenticado com
    membership.must_change_password=True pra tela de troca de senha,
    antes de deixar ele chegar em qualquer outra página.

    Precisa ficar registrado DEPOIS da AuthenticationMiddleware no
    settings.py (só existe request.user por causa dela). Usa
    request.path (a URL crua) em vez de request.resolver_match porque
    é simples e sempre disponível, sem depender de quando o Django
    resolve a URL no ciclo da requisição.
    """

    def __init__(self, get_response):
        # Django chama isso UMA VEZ, quando o servidor sobe - get_response
        # é a "próxima etapa" da cadeia de middlewares (pode ser o
        # próximo middleware, ou a view em si, se este for o último).
        self.get_response = get_response

    def __call__(self, request):
        # Isso aqui roda EM TODA requisição.
        user = request.user

        if user.is_authenticated and hasattr(user, 'membership') and user.membership.must_change_password:
            paginas_liberadas = {reverse('password_change'), reverse('logout')}
            if request.path not in paginas_liberadas:
                return redirect('password_change')

        # Deixa a requisição seguir pro próximo middleware/view normalmente.
        return self.get_response(request)
