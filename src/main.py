# ============================================================
# BOT DE TELEGRAM - PUNTO DE ENTRADA PRINCIPAL (SIMPLIFICADO)
# ============================================================

import sys
import asyncio
from datetime import datetime
from flask import Flask

sys.path.append('.')
from src import config
from src.bot import configurar_bot
from src.database import db
from src.backup_system import backup
from src.utils import log_info, log_error

# ============================================================
# SERVIDOR WEB PARA /ping
# ============================================================

app = Flask(__name__)

@app.route('/ping', methods=['GET'])
def ping():
    return 'OK', 200

@app.route('/health', methods=['GET'])
def health():
    try:
        db.client.table('admins').select('count', count='exact').execute()
        return {'status': 'ok', 'timestamp': datetime.now().isoformat()}, 200
    except Exception as e:
        return {'status': 'error', 'error': str(e)}, 500

def iniciar_servidor():
    """Inicia Flask en un hilo separado"""
    app.run(host='0.0.0.0', port=config.PORT, debug=False, use_reloader=False)

# ============================================================
# FUNCIÓN PRINCIPAL
# ============================================================

async def ejecutar_bot():
    """Función asíncrona que ejecuta el bot"""
    
    # === ELIMINAR WEBHOOK PARA EVITAR CONFLICTOS ===
    try:
        from telegram import Bot
        bot = Bot(token=config.TELEGRAM_TOKEN)
        await bot.delete_webhook(drop_pending_updates=True)
        log_info("✅ Webhook eliminado correctamente")
        await asyncio.sleep(1)
    except Exception as e:
        log_error(f"⚠️ Error eliminando webhook: {str(e)}")
    
    # Verificar Supabase
    try:
        db.client.table('admins').select('count', count='exact').execute()
        log_info("✅ Conexión a Supabase verificada")
    except Exception as e:
        log_error(f"⚠️ Error conectando a Supabase: {str(e)}")
    
    # Sincronizar respaldos
    try:
        sincronizados = await backup.sincronizar()
        if sincronizados > 0:
            log_info(f"✅ {sincronizados} respaldos sincronizados")
    except Exception as e:
        log_error(f"Error sincronizando respaldos: {str(e)}")
    
    # Configurar y ejecutar el bot
    application = configurar_bot()
    log_info("✅ Bot configurado correctamente")
    log_info("🤖 Bot iniciado. Esperando mensajes...")
    
    try:
        # Usar run_polling directamente
        await application.run_polling(
            drop_pending_updates=True,
            allowed_updates=['message', 'callback_query'],
            stop_signals=None
        )
    except Exception as e:
        log_error(f"❌ Error ejecutando el bot: {str(e)}")
        raise

# ============================================================
# PUNTO DE ENTRADA
# ============================================================

if __name__ == '__main__':
    import threading
    
    # Iniciar Flask en hilo
    threading.Thread(target=iniciar_servidor, daemon=True).start()
    
    # Ejecutar el bot usando asyncio.run()
    try:
        asyncio.run(ejecutar_bot())
    except KeyboardInterrupt:
        log_info("🛑 Bot detenido por el usuario")
    except Exception as e:
        log_error(f"❌ Error fatal: {str(e)}")
        sys.exit(1)