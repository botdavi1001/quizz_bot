# ============================================================
# BOT DE TELEGRAM - CONFIGURACIÓN PRINCIPAL
# Handlers, comandos, menús y detección de admin
# ============================================================

import asyncio
import json
from datetime import datetime
from typing import Dict, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    ConversationHandler
)

from src import config
from src.database import db
from src.utils import log_info, log_error
from src.estados import *

# Importar funciones directamente desde admin_handlers
from src.admin_handlers import (
    iniciar_crear,
    iniciar_csv,
    mostrar_historial,
    mostrar_config,
    iniciar_lanzar,
    mostrar_gestion,
    mostrar_respaldos,
    manejar_callback_historial
)

# ============================================================
# FUNCIÓN PARA VERIFICAR ADMIN
# ============================================================

def es_admin(update: Update) -> bool:
    """Verifica si el usuario es el admin registrado"""
    try:
        user_id = update.effective_user.id
        admin = db.obtener_admin(user_id)
        return admin is not None
    except Exception as e:
        log_error(f"Error verificando admin: {str(e)}")
        return False


def obtener_admin_id() -> Optional[int]:
    """Obtiene el ID del admin registrado"""
    try:
        result = db.client.table('admins').select('telegram_id').limit(1).execute()
        if result.data:
            return result.data[0]['telegram_id']
        return None
    except:
        return None


# ============================================================
# FUNCIONES PARA VERIFICAR CONVERSACIÓN ACTIVA
# ============================================================

def esta_en_conversacion(context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Verifica si el usuario está en medio de una conversación"""
    if context.user_data.get('conversation_state'):
        return True
    if context.user_data.get('in_conversation'):
        return True
    return False


# ============================================================
# MANEJADORES DE MENSAJES PRINCIPALES
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /start"""
    user = update.effective_user
    user_id = user.id
    
    if es_admin(update):
        await mostrar_panel_admin(update, context)
        return
    
    await mostrar_panel_usuario(update, context)


async def mostrar_panel_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el panel de administrador"""
    keyboard = [
        [config.BOTON_ADMIN['crear'], config.BOTON_ADMIN['csv']],
        [config.BOTON_ADMIN['historial'], config.BOTON_ADMIN['configurar']],
        [config.BOTON_ADMIN['lanzar'], config.BOTON_ADMIN['gestionar']],
        [config.BOTON_ADMIN['respaldos']]
    ]
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    mensaje = "👑 **Panel de Administrador**\n\n"
    
    admin = db.obtener_admin(update.effective_user.id)
    if admin:
        total_preguntas = db.contar_preguntas(admin['id'])
        mensaje += f"📝 Total de preguntas: {total_preguntas}\n"
        
        cuestionario = db.obtener_cuestionario_activo()
        if cuestionario:
            mensaje += f"🚀 Cuestionario activo: {cuestionario.get('nombre', 'Sin nombre')}\n"
        else:
            mensaje += "📭 No hay cuestionario activo\n"
        
        total_historial = db.contar_historial_total()
        if total_historial >= config.LIMITE_HISTORIAL_AVISO:
            mensaje += f"⚠️ Historial: {total_historial} registros (cerca del límite)\n"
    
    await update.message.reply_text(
        mensaje,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def mostrar_panel_usuario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el panel de usuario normal"""
    admin_id = obtener_admin_id()
    if not admin_id:
        await update.message.reply_text(
            config.MENSAJE_SIN_PREGUNTAS,
            parse_mode='Markdown'
        )
        return
    
    admin = db.obtener_admin(admin_id)
    if not admin:
        await update.message.reply_text(
            config.MENSAJE_SIN_PREGUNTAS,
            parse_mode='Markdown'
        )
        return
    
    total_preguntas = db.contar_preguntas(admin['id'])
    if total_preguntas == 0:
        await update.message.reply_text(
            config.MENSAJE_SIN_PREGUNTAS,
            parse_mode='Markdown'
        )
        return
    
    cuestionario = db.obtener_cuestionario_activo()
    if not cuestionario:
        await update.message.reply_text(
            config.MENSAJE_SIN_CUESTIONARIO,
            parse_mode='Markdown'
        )
        return
    
    sesion = db.obtener_sesion_activa(update.effective_user.id)
    
    keyboard = [
        [config.BOTON_USUARIO['responder']],
        [config.BOTON_USUARIO['mi_historial']]
    ]
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    mensaje = "📝 **Panel de Usuario**\n\n"
    mensaje += f"📌 Cuestionario activo: {cuestionario.get('nombre', 'Sin nombre')}\n"
    
    if sesion:
        mensaje += f"⏳ Tienes un cuestionario en progreso.\n"
        mensaje += f"📊 Pregunta {sesion.get('pregunta_actual', 0) + 1} de {len(cuestionario.get('preguntas_ids', []))}\n"
    
    await update.message.reply_text(
        mensaje,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


# ============================================================
# MANEJADOR DE ADMIN /admin_registro
# ============================================================

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /admin_registro CONTRASEÑA"""
    user = update.effective_user
    user_id = user.id
    
    text = update.message.text
    partes = text.split(' ', 1)
    
    if len(partes) < 2:
        await update.message.reply_text(
            "❌ Uso: `/admin_registro CONTRASEÑA`\n\n"
            "Reemplaza 'CONTRASEÑA' con la contraseña configurada.",
            parse_mode='Markdown'
        )
        return
    
    password = partes[1].strip()
    
    if password != config.ADMIN_PASSWORD:
        await update.message.reply_text("❌ Contraseña incorrecta.")
        return
    
    username = user.username
    first_name = user.first_name or "Admin"
    
    exito = db.registrar_admin(user_id, username, first_name)
    
    if exito:
        await update.message.reply_text(
            "✅ **Admin registrado correctamente.**\n\n"
            "Ya puedes usar el panel de administración.\n\n"
            "Recuerda: Usa el comando `/admin_registro CONTRASEÑA` si necesitas cambiar de dispositivo.",
            parse_mode='Markdown'
        )
        await mostrar_panel_admin(update, context)
    else:
        await update.message.reply_text(
            "❌ Error al registrar admin. Intenta de nuevo.",
            parse_mode='Markdown'
        )


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela cualquier conversación en curso"""
    context.user_data.clear()
    
    await update.message.reply_text(
        "✅ Operación cancelada.",
        parse_mode='Markdown'
    )
    
    if es_admin(update):
        await mostrar_panel_admin(update, context)
    else:
        await mostrar_panel_usuario(update, context)


# ============================================================
# HANDLER DEL MENÚ PRINCIPAL
# ============================================================

# ============================================================
# HANDLER DEL MENÚ PRINCIPAL
# ============================================================

async def manejar_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los mensajes de texto del menú principal - SOLO si NO hay conversación activa"""
    
    # VERIFICAR SI HAY UNA CONVERSACIÓN ACTIVA
    if context.user_data.get('conversation_state'):
        return  # Ignorar el mensaje, la conversación lo manejará
    
    text = update.message.text
    
    if es_admin(update):
        # Usar funciones importadas directamente
        if text == config.BOTON_ADMIN['crear']:
            await iniciar_crear(update, context)
        elif text == config.BOTON_ADMIN['csv']:
            await iniciar_csv(update, context)
        elif text == config.BOTON_ADMIN['historial']:
            await mostrar_historial(update, context)
        elif text == config.BOTON_ADMIN['configurar']:
            await mostrar_config(update, context)
        elif text == config.BOTON_ADMIN['lanzar']:
            await iniciar_lanzar(update, context)
        elif text == config.BOTON_ADMIN['gestionar']:
            await mostrar_gestion(update, context)
        elif text == config.BOTON_ADMIN['respaldos']:
            await mostrar_respaldos(update, context)
        else:
            await update.message.reply_text(
                "❌ Opción no reconocida. Usa los botones del menú.",
                parse_mode='Markdown'
            )
    else:
        from src.user_handlers import user_handlers
        
        if text == config.BOTON_USUARIO['responder']:
            await user_handlers.iniciar_responder(update, context)
        elif text == config.BOTON_USUARIO['mi_historial']:
            await user_handlers.mostrar_mi_historial(update, context)
        else:
            await update.message.reply_text(
                "❌ Opción no reconocida. Usa los botones del menú.",
                parse_mode='Markdown'
            )


# ============================================================
# CONFIGURACIÓN DE LA APLICACIÓN
# ============================================================

def configurar_bot() -> Application:
    """Configura y retorna la aplicación del bot"""
    
    application = Application.builder().token(config.TELEGRAM_TOKEN).build()
    
    # ============================================================
    # COMANDOS
    # ============================================================
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin_registro", admin_command))
    application.add_handler(CommandHandler("cancelar", cancelar))
    
    # ============================================================
    # HANDLER DE MENÚ - PRIORIDAD BAJA (group=2)
    # ============================================================

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            manejar_menu
        ),
        group=2  # Prioridad BAJA - se ejecuta DESPUÉS de los ConversationHandlers
    )
    
    # ============================================================
    # HANDLERS DE ADMIN (ConversationHandlers) - PRIORIDAD BAJA
    # ============================================================
    
    from src.admin_handlers import admin_handlers
    admin_handlers.registrar_handlers(application, group=1)
    
    # ============================================================
    # HANDLERS DE USUARIO (ConversationHandlers) - PRIORIDAD BAJA
    # ============================================================
    
    from src.user_handlers import user_handlers
    user_handlers.registrar_handlers(application, group=1)
    
    # ============================================================
    # HANDLER DE CALLBACK QUERY (botones inline)
    # ============================================================
    
    async def manejar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja todas las respuestas de botones inline"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        # Callbacks de admin
        if data.startswith('admin_'):
            if data.startswith('admin_hist_'):
                await manejar_callback_historial(update, context)
            else:
                # Si tienes manejar_callback_admin, impórtala y úsala
                pass
        
        # Callbacks de usuario
        elif data.startswith('user_'):
            from src.user_handlers import user_handlers
            await user_handlers.manejar_callback_usuario(update, context)
        
        # Respuestas
        elif data.startswith('resp_'):
            from src.user_handlers import user_handlers
            await user_handlers.manejar_respuesta(update, context)
        
        # Lanzar cuestionario (ya manejado en admin_handlers)
        elif data.startswith('lanzar_'):
            pass
        
        elif data == 'cancelar':
            await cancelar(update, context)
        
        elif data == 'ver_correctas':
            sesion = db.obtener_sesion_activa(update.effective_user.id)
            if sesion:
                from src.cuestionario import mostrar_respuestas_correctas
                await mostrar_respuestas_correctas(update, context, sesion['id'])
        else:
            await query.edit_message_text("❌ Opción no reconocida.")
    
    application.add_handler(CallbackQueryHandler(manejar_callback))
    
    # ============================================================
    # HANDLER DE ERRORES
    # ============================================================
    
    async def manejar_error(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja errores del bot - SOLO para errores críticos"""
        error = context.error
        
        # Ignorar errores de "Conflict" que son normales en polling
        if "Conflict" in str(error):
            log_info(f"ℹ️ Conflicto de polling normal: {str(error)}")
            return
        
        # Ignorar errores de "Timed out"
        if "Timed out" in str(error):
            log_info(f"ℹ️ Timeout normal: {str(error)}")
            return
        
        # Ignorar errores de "Network"
        if "Network" in str(error):
            log_info(f"ℹ️ Error de red normal: {str(error)}")
            return
        
        # Loggear el error real
        log_error(f"❌ Error crítico en el bot: {str(error)}")
        import traceback
        log_error(f"❌ Traceback: {traceback.format_exc()}")
        
        try:
            if update and update.effective_message:
                await update.effective_message.reply_text(
                    "❌ Ocurrió un error. Intenta de nuevo más tarde.",
                    parse_mode='Markdown'
                )
        except:
            pass
    
    application.add_error_handler(manejar_error)
    
    return application

# ============================================================
# FIN DE bot.py
# ============================================================