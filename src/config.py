# ============================================================
# BOT DE TELEGRAM - CONFIGURACIÓN
# Carga variables de entorno y las convierte en constantes
# ============================================================

import os
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

# --- BOT DE TELEGRAM ---
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')

if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN no está definido en .env")

# --- SUPABASE ---
SUPABASE_URL = os.getenv('SUPABASE_URL', '')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', '')
SUPABASE_STORAGE_URL = os.getenv('SUPABASE_STORAGE_URL', '')

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("❌ SUPABASE_URL y SUPABASE_KEY son obligatorios")

# --- ADMIN ---
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')

# --- CONFIGURACIÓN POR DEFECTO ---
TIEMPO_GLOBAL_DEFAULT = int(os.getenv('TIEMPO_GLOBAL_DEFAULT', '30'))
NOTIFICAR_ADMIN = os.getenv('NOTIFICAR_ADMIN', 'True').lower() == 'true'
REINTENTOS_DEFAULT = int(os.getenv('REINTENTOS_DEFAULT', '3'))
TOLERANCIA_ABIERTAS = int(os.getenv('TOLERANCIA_ABIERTAS', '80'))
IMG_COMPRESS_KB = int(os.getenv('IMG_COMPRESS_KB', '200'))

# --- SISTEMA ---
BACKUP_FILE = os.getenv('BACKUP_FILE', 'data/respaldos.json')

# --- RENDER ---
PORT = int(os.getenv('PORT', '10000'))

# --- TIMEOUTS ---
SUPABASE_TIMEOUT = 10  # segundos
SUPABASE_RETRIES = 3
TELEGRAM_TIMEOUT = 30  # segundos

# --- LÍMITES ---
MAX_PREGUNTAS_POR_LOTE = 20
MAX_OPCIONES_POR_PREGUNTA = 10
MAX_PREGUNTAS_MOSTRAR = 100
LIMITE_HISTORIAL_AVISO = 10000  # 10,000 registros
LIMITE_ALMACENAMIENTO_AVISO = 90  # 90%

# --- MENSAJES ---
MENSAJE_SIN_PREGUNTAS = "📭 El bot no tiene preguntas disponibles aún. Vuelve más tarde."
MENSAJE_SIN_CUESTIONARIO = "📭 No hay cuestionario activo en este momento. Vuelve más tarde."
MENSAJE_TIEMPO_AGOTADO = "⏰ Tiempo agotado. Reiniciando desde la pregunta 1."
MENSAJE_REINTENTOS_AGOTADOS = "❌ Has agotado todos tus reintentos. No puedes continuar."
MENSAJE_CUESTIONARIO_INACTIVO = "📭 El cuestionario ya no está disponible. Puedes ver tu historial."

# --- TEXTOS PARA BOTONES ---
BOTON_ADMIN = {
    'crear': '📝 Crear pregunta',
    'csv': '📂 Subir CSV',
    'historial': '📊 Ver historial',
    'configurar': '⚙️ Configurar',
    'lanzar': '🚀 Lanzar cuestionario',
    'gestionar': '🗑️ Eliminar pregunta',
    'respaldos': '📥 Respaldos pendientes'
}

BOTON_USUARIO = {
    'responder': '📝 Responder cuestionario',
    'mi_historial': '📋 Mi historial'
}

# --- TIPOS DE PREGUNTA ---
TIPOS = {
    'multiple': 'Múltiple',
    'vf': 'Verdadero/Falso',
    'abierta': 'Abierta'
}

# ============================================================
# FIN DE CONFIGURACIÓN
# ============================================================