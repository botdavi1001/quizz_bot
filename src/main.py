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

@app.route('/ping-db', methods=['GET'])
def ping_db():
    """Endpoint para mantener vivo Supabase (usado por cron-job.org)"""
    try:
        result = db.client.table('admins').select('id', count='exact').limit(1).execute()
        return 'OK', 200  # <--- Respuesta simple
    except Exception as e:
        log_error(f"❌ Error en ping-db: {str(e)}")
        return 'ERROR', 500

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

async def mantener_supabase_vivo():
    """Tarea programada para mantener Supabase activo (ejecución interna)"""
    while True:
        try:
            # Realiza una consulta mínima y rápida a la base de datos
            result = db.client.table('admins').select('id', count='exact').limit(1).execute()
            log_info("✅ [Tarea Interna] Ping a Supabase exitoso. Proyecto activo.")
        except Exception as e:
            log_error(f"❌ [Tarea Interna] Error en ping a Supabase: {str(e)}")
        
        # Espera 1 día (86,400 segundos) antes de la próxima verificación.
        # Es un intervalo seguro que evita pausas.
        await asyncio.sleep(86400) 
    

async def main():
    log_info("=" * 50)
    log_info("📱 BOT DE TELEGRAM - CUESTIONARIOS")
    log_info("=" * 50)
    log_info(f"🕐 Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Verificar Supabase
    try:
        db.client.table('admins').select('count', count='exact').execute()
        log_info("✅ Conexión a Supabase verificada")
    except Exception as e:
        log_error(f"⚠️ Error conectando a Supabase: {str(e)}")

    asyncio.create_task(mantener_supabase_vivo())
    
    # Sincronizar respaldos
    try:
        sincronizados = await backup.sincronizar()
        if sincronizados > 0:
            log_info(f"✅ {sincronizados} respaldos sincronizados")
    except Exception as e:
        log_error(f"Error sincronizando respaldos: {str(e)}")
    
    # Iniciar el bot
    try:
        application = configurar_bot()
        log_info("✅ Bot configurado correctamente")
        
        # Iniciar polling
        await application.initialize()
        await application.start()
        await application.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=['message', 'callback_query']
        )
        log_info("🤖 Bot iniciado. Esperando mensajes...")
        
        # Mantener vivo
        while True:
            await asyncio.sleep(3600)
        
    except Exception as e:
        log_error(f"❌ Error: {str(e)}")
        raise
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()

# ============================================================
# PUNTO DE ENTRADA
# ============================================================

if __name__ == '__main__':
    import threading
    
    # Iniciar Flask en hilo
    threading.Thread(target=iniciar_servidor, daemon=True).start()
    
    # Ejecutar bot
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log_info("🛑 Bot detenido")
    except Exception as e:
        log_error(f"❌ Error fatal: {str(e)}")
        sys.exit(1)