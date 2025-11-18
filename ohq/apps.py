from django.apps import AppConfig


class OhqConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ohq'

    def ready(self):
        # Import signals here to ensure they are registered
        import ohq.signals