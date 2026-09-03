def gestor_flag(request):
    """Exposes `is_gestor` to every template (registered in settings.py),
    so base.html can hide/show the employee-management link without
    every view having to pass this flag manually.
    """
    is_gestor = (
        request.user.is_authenticated
        and request.user.groups.filter(name='Gestor').exists()
    )
    return {'is_gestor': is_gestor}
