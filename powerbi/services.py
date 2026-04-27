import requests
import urllib.parse
import time
import os, re
import json
from datetime import datetime, timedelta
from django.conf import settings
from django.core.mail import EmailMessage


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def obtener_log_path():
    fecha = datetime.now().strftime("%d_%m_%Y")
    nombre = f"Refresh_{fecha}.log"
    return os.path.join(settings.BASE_DIR, "backend", nombre)

with open(os.path.join(BASE_DIR, "backend", "config.json")) as f:
    CONFIG = json.load(f)

CLIENT_ID = settings.PBI_CLIENT_ID
CLIENT_SECRET = settings.PBI_CLIENT_SECRET
TENANT_ID = settings.PBI_TENANT_ID

#  MODO ACTUAL
WORKSPACE_ACTIVO = "Admin" 

# "Admin" habilita selector
# "CENTENARIO"



# =========================
# CACHE / ESTADOS
# =========================

ESTADOS_REFRESH = {}
ULTIMA_CONSULTA = {}
CACHE_ESTADO = {}

# =========================
# CONSTANTES
# =========================

MICROSOFT_OAUTH2_API_ENDPOINT = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
POWER_BI_RESOURCE_ENDPOINT = "https://analysis.windows.net/powerbi/api"

TOKEN_CACHE = None
TOKEN_EXPIRA = 0

# =========================
# AUTH
# =========================

def obtener_token():
    global TOKEN_CACHE, TOKEN_EXPIRA

    if TOKEN_CACHE and time.time() < TOKEN_EXPIRA:
        return TOKEN_CACHE

    token_url = MICROSOFT_OAUTH2_API_ENDPOINT.format(tenant_id=TENANT_ID)

    payload = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": POWER_BI_RESOURCE_ENDPOINT + "/.default",
    }).encode("utf-8")
    
    response = requests.post(
        token_url,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    response.raise_for_status()

    token = response.json()["access_token"]

    TOKEN_CACHE = token
    TOKEN_EXPIRA = time.time() + (30 * 60)

    return token

# =========================
# WORKSPACES
# =========================

def es_admin():
    return WORKSPACE_ACTIVO == "Admin"

def obtener_workspace(request=None):
    if es_admin():
        ws = None

        if request:
            ws = request.GET.get("workspace") or request.data.get("workspace")

        #  fallback: primer workspace del config
        if not ws:
            workspaces = [k for k in CONFIG.keys() if k != "AUTO_REFRESH"]
            return sorted(workspaces, key=lambda x: x.lower())[0]

        return ws

    return WORKSPACE_ACTIVO

def obtener_entorno(workspace):
    entorno = CONFIG.get(workspace)

    if not entorno:
        raise ValueError(f"No existe el workspace: {workspace}")

    return entorno

def obtener_workspaces():
    return list(CONFIG.keys())

# =========================
# DATASETS
# =========================

def obtener_datasets(workspace):

    entorno = obtener_entorno(workspace)

    resultado = {}

    for key, value in entorno.items():
        if isinstance(value, dict) and "PBI_DATASET_ID" in value:
            resultado[key] = {
                "IFRAME": value.get("IFRAME")
            }
        
    resultado["REPORT_LINK"] = entorno.get("Report")
    resultado["REPORT_LINK_HISTORICO"] = entorno.get("ReportHistorico")

    return resultado


def obtener_dataset(nombre_dataset, workspace):

    entorno = obtener_entorno(workspace)

    group_id = entorno.get("PBI_GROUP_ID")

    dataset = entorno.get(nombre_dataset)

    if not dataset:
        raise ValueError(f"No existe el dataset: {nombre_dataset}")

    dataset_id = dataset.get("PBI_DATASET_ID")
    iframe = dataset.get("IFRAME")

    return group_id, dataset_id, iframe

# =========================
# NORMALIZAR FECHA
# =========================
def normalizar_fechas_inclusivas(fecha_inicial, fecha_final):
    fi = datetime.strptime(fecha_inicial, "%Y-%m-%d")
    ff = datetime.strptime(fecha_final, "%Y-%m-%d")

    # 🔥 convierte rango inclusivo → exclusivo
    ff = ff + timedelta(days=1)

    return fi.strftime("%Y-%m-%d"), ff.strftime("%Y-%m-%d")
# =========================
# VALIDACIONES
# =========================



def validar_fechas(fecha_inicial, fecha_final):

    try:
        fi = datetime.strptime(fecha_inicial, "%Y-%m-%d")
        ff = datetime.strptime(fecha_final, "%Y-%m-%d")
    except:
        raise ValueError("Formato de fecha inválido. Debe ser YYYY-MM-DD")

    hoy = datetime.today()

    if fi > ff:
        raise ValueError("La fecha inicial no puede ser mayor que la final")

    if (ff - fi).days > 7:
        raise ValueError("El rango de fechas no puede superar 7 días")

    if (hoy - fi).days > 365:
        raise ValueError("La fecha inicial no puede tener más de 1 año de antigüedad")
    
def validar_guid(valor, nombre):
    regex = r"^[0-9a-fA-F\-]{36}$"
    if not valor or not re.match(regex, valor):
        raise ValueError(f"{nombre} tiene un formato inválido o está vacío")


def validar_config(nuevo_config):

    if not isinstance(nuevo_config, dict):
        raise ValueError("El config debe ser un objeto JSON")

    reservados = ["AUTO_REFRESH", "REPORT_LINK", "REPORT_LINK_HISTORICO"]

    workspaces = [
        k for k in nuevo_config.keys()
        if k not in reservados
    ]

    lower = [w.lower() for w in workspaces]
    if len(lower) != len(set(lower)):
        raise ValueError("Hay nombres de workspaces duplicados")

    for ws in workspaces:

        data = nuevo_config[ws]

        if not isinstance(data, dict):
            raise ValueError(f"Workspace '{ws}' inválido")

        group_id = data.get("PBI_GROUP_ID")
        validar_guid(group_id, f"PBI_GROUP_ID en {ws}")

        #  VALIDACIÓN DATASETS (LO QUE PEDISTE)
        datasets = [
            k for k in data.keys()
            if k not in ["PBI_GROUP_ID", "Report", "ReportHistorico"]
        ]

        if len(datasets) == 0:
            raise ValueError(f"El workspace '{ws}' no tiene datasets")

        for key in datasets:

            val = data[key]

            if not isinstance(val, dict):
                raise ValueError(f"Dataset '{key}' inválido en {ws}")

            dataset_id = val.get("PBI_DATASET_ID")
            validar_guid(dataset_id, f"PBI_DATASET_ID en {ws} -> {key}")


# =========================
# POWER BI
# =========================

def actualizar_parametros(token, fecha_inicial, fecha_final, GROUP_ID, DATASET_ID):

    url = f"https://api.powerbi.com/v1.0/myorg/groups/{GROUP_ID}/datasets/{DATASET_ID}/Default.UpdateParameters"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "updateDetails": [
            {"name": "Fecha inicial", "newValue": fecha_inicial},
            {"name": "Fecha Final", "newValue": fecha_final},
        ]
    }

    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()


def ejecutar_refresh(token, GROUP_ID, DATASET_ID):

    url = f"https://api.powerbi.com/v1.0/myorg/groups/{GROUP_ID}/datasets/{DATASET_ID}/refreshes"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {"notifyOption": "NoNotification"}
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()

def takeover_dataset(token, GROUP_ID, DATASET_ID):

    url = (
        f"https://api.powerbi.com/v1.0/myorg/groups/{GROUP_ID}"
        f"/datasets/{DATASET_ID}/Default.TakeOver"
    )

    headers = {
        "Authorization": f"Bearer {token}"
    }
    print(f"[POWER BI CALL] STATUS CHECK | Dataset: {DATASET_ID} | {datetime.now()}")
    response = requests.post(url, headers=headers)

    if response.status_code not in (200, 202):
        if "already" not in response.text.lower():
            response.raise_for_status()

    return True


def verificar_owner_y_takeover(token, GROUP_ID, DATASET_ID):

    url = f"https://api.powerbi.com/v1.0/myorg/groups/{GROUP_ID}/datasets/{DATASET_ID}"

    headers = {
        "Authorization": f"Bearer {token}"
    }
    print(f"[POWER BI CALL] Dataset: {DATASET_ID} | Hora: {datetime.now()}")
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    data = response.json()

    owner = data.get("configuredBy", "").lower()

    if "api_bi" in owner:
        return False

    takeover_dataset(token, GROUP_ID, DATASET_ID)

    return True


# =========================
# PROCESO PRINCIPAL
# =========================

def proceso_completo(fecha_inicial, fecha_final, nombre_dataset, workspace):

    validar_fechas(fecha_inicial, fecha_final)

    fecha_inicial, fecha_final = normalizar_fechas_inclusivas(
    fecha_inicial, fecha_final
)

    token = obtener_token()

    GROUP_ID, DATASET_ID, iframe = obtener_dataset(nombre_dataset, workspace)

    verificar_owner_y_takeover(token, GROUP_ID, DATASET_ID)

    actualizar_parametros(token, fecha_inicial, fecha_final, GROUP_ID, DATASET_ID)

    ejecutar_refresh(token, GROUP_ID, DATASET_ID)

    ESTADOS_REFRESH[nombre_dataset] = {
        "finalizado": False,
        "estado": None
    }

    return iframe

# =========================
# ESTADO REFRESH
# =========================

def obtener_estado_refresh(nombre_dataset, workspace):

    ahora = time.time()

    if nombre_dataset in ESTADOS_REFRESH:
        if ESTADOS_REFRESH[nombre_dataset]["finalizado"]:
            return ESTADOS_REFRESH[nombre_dataset]

    if nombre_dataset in CACHE_ESTADO:
        if (ahora - ULTIMA_CONSULTA.get(nombre_dataset, 0)) < 30:
            return CACHE_ESTADO[nombre_dataset]

    token = obtener_token()

    GROUP_ID, DATASET_ID, _ = obtener_dataset(nombre_dataset, workspace)

    url = f"https://api.powerbi.com/v1.0/myorg/groups/{GROUP_ID}/datasets/{DATASET_ID}/refreshes?$top=1"

    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    data = response.json()

    if not data.get("value"):
        return {"status": "Aguarde...", "finalizado": False}

    status = data["value"][0]["status"]

    finalizado = False

    if status == "Completed":
        status = "Actualización finalizada ✔"
        finalizado = True

    elif status == "Failed":
        status = "Falló ❌"
        finalizado = True

    elif status == "InProgress":
        status = "En progreso..."

    elif status == "Unknown":
        status = "Iniciando..."  # 🔥 clave

    else:
        status = f"Estado desconocido: {status}"

    resultado = {
        "status": status,
        "finalizado": finalizado
    }

    if finalizado:
        ESTADOS_REFRESH[nombre_dataset] = resultado

    CACHE_ESTADO[nombre_dataset] = resultado
    ULTIMA_CONSULTA[nombre_dataset] = ahora

    return resultado

# =========================
# CONFIG (ADMIN)
# =========================

def obtener_config_completo():
    return CONFIG




# =========================
# Guardar configuracion (ADMIN)
# =========================

def guardar_config_completo(nuevo_config):

    path = os.path.join(settings.BASE_DIR, "backend", "config.json")

    validar_config(nuevo_config)

    #  carpeta backups
    backup_dir = os.path.join(settings.BASE_DIR, "backend", "backups")
    os.makedirs(backup_dir, exist_ok=True)

    #  nombre con timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_path = os.path.join(backup_dir, f"config_{timestamp}.json")

    #  guardar backup
    with open(path, "r", encoding="utf-8") as f:
        config_actual = json.load(f)

    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(config_actual, f, indent=2)

    #  escritura segura (temp + replace)
    temp_path = path + ".tmp"

    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(nuevo_config, f, indent=2)

    os.replace(temp_path, path)

    #  actualizar config en memoria
    global CONFIG
    CONFIG = nuevo_config

# =========================
# AUTO REFRESH
# =========================

MAP_DIAS = {
    "Lunes": 0,
    "Martes": 1,
    "Miércoles": 2,
    "Jueves": 3,
    "Viernes": 4,
    "Sábado": 5,
    "Domingo": 6
}

ULTIMA_EJECUCION_AUTO = None
EJECUTANDO_AUTO = False


def calcular_fechas_auto():
    ahora = datetime.now()

    fin = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    inicio = fin - timedelta(days=7)                                ############CANTIDAD DE DIAS A ACTUALIZAR############

    return inicio.strftime("%Y-%m-%d"), fin.strftime("%Y-%m-%d")


def ya_se_ejecuto_hoy():
    global ULTIMA_EJECUCION_AUTO

    hoy = datetime.now().date()

    if ULTIMA_EJECUCION_AUTO == hoy:
        return True

    ULTIMA_EJECUCION_AUTO = hoy
    return False


def esperar_refresh(dataset, workspace, timeout=1800):

    inicio = time.time()

    while True:
        estado = obtener_estado_refresh(dataset, workspace)

        if estado["finalizado"]:
            return estado

        if time.time() - inicio > timeout:
            raise Exception("Timeout esperando refresh")

        time.sleep(45)


def ejecutar_auto_refresh(forzar=False):

    global EJECUTANDO_AUTO

    if EJECUTANDO_AUTO:
        return

    config = obtener_config_completo()
    auto = config.get("AUTO_REFRESH", {})

    if not auto.get("enabled"):
        return

    ahora = datetime.now()

    if not forzar:
        if not auto.get("enabled"):
            return

        # validar día
        if ahora.weekday() != MAP_DIAS.get(auto.get("day")):
            return

        # validar hora (con ventana de 5 min)
        if ahora.hour != auto.get("hour") or ahora.minute > 5:
            return

        # evitar duplicados
        if ya_se_ejecuto_hoy():
            return
    EJECUTANDO_AUTO = True

    errores = []  #  acumulador de errores

    try:
        fecha_inicial, fecha_final = calcular_fechas_auto()

        workspaces = [
            k for k in config.keys()
            if k not in ["AUTO_REFRESH", "ADMIN_REPORT_LINK","REPORT_LINK_HISTORICO"]
        ]

        for ws in workspaces:

            datasets = obtener_datasets(ws)

            datasets_lanzados = []

            # 🔹 FASE 1: disparar todos los datasets del workspace
            for nombre, data in datasets.items():

                if not isinstance(data, dict):
                    continue

                if nombre in ["REPORT_LINK", "REPORT_LINK_HISTORICO"]:
                    continue

                try:
                    print(f"[AUTO] Lanzando {ws} - {nombre}")
                    proceso_completo(fecha_inicial, fecha_final, nombre, ws)
                    datasets_lanzados.append(nombre)

                except Exception as e:
                    print(f"Error lanzando {ws} - {nombre}: {e}")
                    errores.append((f"{ws} - {nombre}", e))

            # 🔹 FASE 2: esperar todos los datasets del workspace
            for nombre in datasets_lanzados:

                try:
                    print(f"[AUTO] Esperando {ws} - {nombre}")
                    esperar_refresh(nombre, ws)

                except Exception as e:
                    print(f"Error esperando {ws} - {nombre}: {e}")
                    errores.append((f"{ws} - {nombre}", e))      
    finally:
        escribir_log_errores(errores)

        # envío de mail
        try:
            enviar_mail_resultado(errores)
        except Exception as e:
            print("Error enviando mail:", e)

        EJECUTANDO_AUTO = False

LOG_PATH = os.path.join(settings.BASE_DIR, "backend", "auto_refresh.log")

def escribir_log_errores(errores):
    """
    Solo escribe si hay errores.
    Pisa el archivo completo.
    """

    if not errores:
        return  # 🔥 clave: no hacer nada si no hay errores

    log_path = obtener_log_path()

    with open(log_path, "w", encoding="utf-8") as f:
        for dataset, error in errores:
            linea = f"{datetime.now().isoformat()}, {dataset}, {str(error)}\n"
            f.write(linea)

def enviar_mail_resultado(errores):

    print("👉 Entró a enviar_mail_resultado")

    config = obtener_config_completo()
    auto = config.get("AUTO_REFRESH", {})

    # validar toggle
    if not auto.get("email_enabled"):
        print("❌ email_enabled = False")
        return

    # obtener destinatarios
    destinatario = auto.get("email")
    print("👉 destinatario raw:", destinatario)

    if not destinatario:
        print("❌ Email vacío")
        return

    destinatarios = [e.strip() for e in destinatario.split(",") if e.strip()]
    print("👉 destinatarios procesados:", destinatarios)

    if not destinatarios:
        print("❌ Lista vacía")
        return

    # definir asunto y cuerpo
    if errores:
        asunto = "Actualizacion de Reportes BI ---> FALLO"
        cuerpo = "Se produjeron errores en la actualización automática. Ver log adjunto."
    else:
        asunto = "Actualizacion de Reportes BI ---> OK"
        cuerpo = "La actualización automática se ejecutó correctamente sin errores."

    print("✅ Va a enviar mail")

    email = EmailMessage(
        subject=asunto,
        body=cuerpo,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=destinatarios,
    )

    # adjuntar log si hay errores
    log_path = obtener_log_path()

    if errores and os.path.exists(log_path):
        email.attach_file(log_path)

    email.send(fail_silently=True)


