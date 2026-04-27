from django.apps import AppConfig
import threading
import os


class PowerbiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'powerbi'  # ✅ correcto

    def ready(self):
        # 🔥 evita doble ejecución en runserver
        if os.environ.get('RUN_MAIN') != 'true':
            return

        from powerbi.scheduler import iniciar_scheduler

        hilo = threading.Thread(target=iniciar_scheduler, daemon=True)
        hilo.start()