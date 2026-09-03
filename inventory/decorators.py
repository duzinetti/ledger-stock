from functools import wraps
from django.core.exceptions import PermissionDenied

def gestor_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.groups.filter(name='Gestor').exists():
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper