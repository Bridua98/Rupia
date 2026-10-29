from core.menus import main_menu


def menu(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    return {"menu": main_menu(request)}
