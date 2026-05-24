from django.apps import AppConfig


class ErpAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'erp_app'
    verbose_name = 'Auralith ERP'

    def ready(self):
        import erp_app.signals
