# ============================================================
# BOT DE TELEGRAM - PUNTO DE ENTRADA PRINCIPAL
# Inicia el servidor web para /ping y ejecuta el bot
# ============================================================

import os
import sys
import asyncio
import threading
from datetime import datetime
from flask import Flask, request

from src import config
from src.bot import configurar_bot
from src.database import db
from src.backup_system import backup
from src.utils import log_info, log_error

# ============================================================
# SERVIDOR WEB PARA RENDER (ENDPOINT /ping)
# ============================================================

app = Flask(__name__)

@app.route('/ping', methods=['GET'])
def ping():
    """Endpoint para cron-job.org - Mantiene el bot vivo en Render"""
    return 'OK', 200

@app.route('/health', methods=['GET'])
def health():
    """Endpoint para verificar el estado del bot"""
    try:
        # Verificar conexión a Supabase
        db.client.table('admins').select('count', count='exact').execute()
        return {'status': 'ok', 'timestamp': datetime.now().isoformat()}, 200
    except Exception as e:
        return {'status': 'error', 'error': str(e)}, 500

def iniciar_servidor():
    """Inicia el servidor Flask en un hilo separado"""
    port = config.PORT
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ============================================================
# FUNCIÓN PRINCIPAL
# ============================================================

async def iniciar_bot():
    """Inicia el bot de Telegram"""
    
    log_info("🚀 Iniciando bot de Telegram...")
    log_info(f"📋 Configuración cargada:")
    log_info(f"   - Supabase URL: {config.SUPABASE_URL}")
    log_info(f"   - Admin password: {'✅ configurada' if config.ADMIN_PASSWORD else '❌ no configurada'}")
    log_info(f"   - Tiempo global: {config.TIEMPO_GLOBAL_DEFAULT}s")
    log_info(f"   - Reintentos: {config.REINTENTOS_DEFAULT}")
    log_info(f"   - Notificar admin: {config.NOTIFICAR_ADMIN}")
    
    # Verificar conexión a Supabase
    try:
        db.client.table('admins').select('count', count='exact').execute()
        log_info("✅ Conexión a Supabase verificada")
    except Exception as e:
        log_error(f"❌ Error conectando a Supabase: {str(e)}")
        log_error("   El bot continuará pero las operaciones pueden fallar")
    
    # Verificar que haya un admin registrado
    try:
        admin = db.client.table('admins').select('telegram_id').limit(1).execute()
        if admin.data:
            log_info(f"✅ Admin registrado: {admin.data[0]['telegram_id']}")
        else:
            log_info("⚠️ No hay admin registrado. Usa /admin* CONTRASEÑA para registrar")
    except Exception as e:
        log_error(f"Error verificando admin: {str(e)}")
    
    # Sincronizar respaldos pendientes al inicio
    try:
        sincronizados = await backup.sincronizar()
        if sincronizados > 0:
            log_info(f"✅ {sincronizados} respaldos sincronizados al iniciar")
    except Exception as e:
        log_error(f"Error sincronizando respaldos: {str(e)}")
    
    # Configurar y ejecutar el bot
    try:
        application = configurar_bot()
        log_info("✅ Bot configurado correctamente")
        
        # Iniciar el bot (long polling)
        log_info("🤖 Bot iniciado. Esperando mensajes...")
        await application.run_polling(
            drop_pending_updates=True,
            allowed_updates=['message', 'callback_query']
        )
        
    except Exception as e:
        log_error(f"❌ Error ejecutando el bot: {str(e)}")
        sys.exit(1)

# ============================================================
# PUNTO DE ENTRADA
# ============================================================

if __name__ == '__main__':
    log_info("=" * 50)
    log_info("📱 BOT DE TELEGRAM - CUESTIONARIOS")
    log_info("=" * 50)
    log_info(f"🕐 Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Iniciar servidor Flask en un hilo separado
    log_info(f"🌐 Iniciando servidor web en puerto {config.PORT}...")
    servidor_thread = threading.Thread(target=iniciar_servidor, daemon=True)
    servidor_thread.start()
    log_info("✅ Servidor web iniciado")
    
    # Ejecutar el bot
    try:
        asyncio.run(iniciar_bot())
    except KeyboardInterrupt:
        log_info("🛑 Bot detenido por el usuario")
    except Exception as e:
        log_error(f"❌ Error fatal: {str(e)}")
        sys.exit(1)

# ============================================================
# FIN DE main.py
# ============================================================