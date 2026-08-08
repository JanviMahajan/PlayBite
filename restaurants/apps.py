from django.apps import AppConfig


class RestaurantsConfig(AppConfig):
    name = 'restaurants'

    def ready(self):
        # import signal handlers
        try:
            from . import signals  # noqa: F401
        except Exception:
            pass
