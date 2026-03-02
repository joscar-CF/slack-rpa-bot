import requests
import json
import os
from datetime import datetime, timedelta, timezone
import time

# --- CONFIGURACIÓN ---
SLACK_TOKEN = os.getenv("SLACK_TOKEN")
ID_SMOKE_CHANNEL = os.getenv("ID_SMOKE_CHANNEL")
ID_QA_CHANNEL = os.getenv("ID_QA_CHANNEL")
SEARCH_TEXT = "Smoke aprobado, que la fuerza y :gabo: nos acompañe"
QAS_LIST = ["Daniela", "Yanys", "Juan", "Joscar", "Neal"]
DATA_FILE = "rpa_state.json"


# --- FUNCIONES DE PERSISTENCIA ---
def load_state():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {
        "current_index": 0,
        "last_rotation_date": None  # Formato YYYY-MM-DD
    }


def save_state(state):
    with open(DATA_FILE, 'w') as f:
        json.dump(state, f)


# --- LÓGICA PRINCIPAL ---
def run_automation():
    # Configurar zona horaria local
    tz_local = timezone(timedelta(hours=-4))
    now_local = datetime.now(tz_local)

    # BLOQUEO DE FIN DE SEMANA (Sábado = 5, Domingo = 6)
    # Esto asegura que si GitHub lo despierta un Sábado a las 10 AM, el script se cierre solo.
    if now_local.weekday() >= 5:
        print(f"😴 Fin de semana detectado ({now_local.strftime('%A')}). RPA en pausa.")
        return

    print(f"\n🚀 Ejecutando RPA - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    state = load_state()

    #1. Calcular fechas usando objetos conscientes de la zona horaria (UTC-4)
    # Creamos un objeto de zona horaria para UTC-4
    tz_local = timezone(timedelta(hours=-4))

    # Obtenemos la hora actual en esa zona horaria específicamente
    now_local = datetime.now(tz_local)
    today_str = now_local.strftime('%Y-%m-%d')

    # Para el timestamp de Slack (medianoche de hoy en tu zona)
    start_of_day = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    oldest_timestamp = start_of_day.timestamp()

    # 2. Consultar Historial de Slack (Request 01)
    headers = {"Authorization": f"Bearer {SLACK_TOKEN}"}
    url_history = f"https://slack.com/api/conversations.history?channel={ID_SMOKE_CHANNEL}&oldest={oldest_timestamp}"

    try:
        response = requests.get(url_history, headers=headers)
        data = response.json()

        if not data.get("ok"):
            print(f"❌ Error API Slack: {data.get('error')}")
            return

        messages = data.get("messages", [])
        found = False

        print(f"DEBUG: Analizando {len(messages)} mensajes recibidos hoy...")

        for msg in messages:
            # Extraemos texto de todas las fuentes posibles dentro del mensaje
            texto_principal = msg.get("text", "")

            textos_adjuntos = []
            for att in msg.get("attachments", []):
                textos_adjuntos.append(att.get("title", ""))
                textos_adjuntos.append(att.get("text", ""))
                textos_adjuntos.append(att.get("fallback", ""))

            # Unificamos el contenido del mensaje
            contenido_total = (texto_principal + " " + " ".join(textos_adjuntos)).strip()

            # Verificamos si nuestro texto clave está dentro del contenido
            if SEARCH_TEXT in contenido_total:
                found = True
                print(f"🎯 ¡MATCH ENCONTRADO! -> Contenido: {contenido_total[:60]}...")
                break

        # Definir encargado actual para uso en logs
        current_responsible = QAS_LIST[state["current_index"]]

        # 3. Validar Rotación
        if found:
            if state["last_rotation_date"] != today_str:
                old_index = state["current_index"]

                # Lógica de ciclo: si el índice actual es el último, vuelve a 0
                # De lo contrario, suma 1.
                if old_index >= len(QAS_LIST) - 1:
                    new_index = 0
                    print(f"🔄 ¡FIN DE CICLO! Reiniciando lista. De {QAS_LIST[old_index]} a {QAS_LIST[new_index]}")
                else:
                    new_index = old_index + 1
                    print(f"🔄 CAMBIO DE TURNO. De {QAS_LIST[old_index]} a {QAS_LIST[new_index]}")

                # Guardar el nuevo estado
                state["current_index"] = new_index
                state["last_rotation_date"] = today_str
                save_state(state)
            else:
                print(f"ℹ️ El mensaje de hoy ya fue procesado. El encargado sigue siendo: {current_responsible}")
        else:
            print(f"😴 No se encontró el mensaje de aprobación. El encargado actual sigue siendo: {current_responsible}")

        # 4. Notificar si estamos en la ventana horaria (Request 02 y 03)
        target_hour = 7
        current_responsible = QAS_LIST[state["current_index"]]

        if target_hour  <= now_local.hour <= target_hour :
            print(f"📢 Dentro de ventana horaria. Notificando a {current_responsible}...")
            send_slack_notification(current_responsible)
        else:
            print(f"🕒 Fuera de ventana horaria para notificaciones (Hora actual: {now_local.hour}:00).")

    except Exception as e:
        print(f"💥 Error crítico: {str(e)}")


def send_slack_notification(name):
    url_post = "https://slack.com/api/chat.postMessage"
    headers = {"Authorization": f"Bearer {SLACK_TOKEN}", "Content-Type": "application/json"}

    payload = {
        "text": f"📢 *Recordatorio de Smoke Test*\n\nEl encargado para el día de hoy es: *{name}* 👨‍💻👩‍💻\n\n_Por favor, estar atentos a la notificación de ambiente encendido._"
    }

    # Enviar a ambos canales
    for channel in [ID_QA_CHANNEL, ID_SMOKE_CHANNEL]:
        payload["channel"] = channel
        requests.post(url_post, headers=headers, json=payload)


# --- PROGRAMADOR ---
if __name__ == "__main__":
    # Ejecutar inmediatamente al iniciar
    run_automation()

    # # Programar cada hora
    # import schedule
    #
    # # schedule.every().hour.at(":00").do(run_automation)
    # schedule.every(1).minutes.do(run_automation)
    # print("🤖 RPA Iniciado y programado cada hora...")
    # while True:
    #     schedule.run_pending()
    #     # time.sleep(60)
    #     time.sleep(1)