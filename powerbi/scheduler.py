import time
from powerbi.services import ejecutar_auto_refresh

def iniciar_scheduler():
    print("🟢 Scheduler iniciado")

    while True:
        try:
            ejecutar_auto_refresh()
        except Exception as e:
            print("Error scheduler:", e)

        time.sleep(300)  # cada 5 minutos