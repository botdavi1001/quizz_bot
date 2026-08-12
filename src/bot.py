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
    manejar_callback_historial,
    admin_estado,
    recibir_eliminar_pregunta,
    confirmar_eliminar_pregunta
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
        [config.BOTON_ADMIN['modo_usuario']]
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
    
    if es_admin(update):
        keyboard.append([config.BOTON_ADMIN['modo_admin']])
    
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
    context.user_data.pop('conversation_state', None)
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
# MANEJADOR DE RESPUESTAS DE ELIMINAR PREGUNTA
# ============================================================

async def manejar_respuesta_eliminar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja las respuestas del proceso de eliminar preguntas"""
    user_id = update.effective_user.id
    estado = admin_estado.get(user_id, {})
    
    # Si no está en modo eliminar, ignorar
    if not estado.get('esperando_eliminar'):
        return
    
    # Si está esperando confirmación
    if estado.get('esperando_confirmacion'):
        await confirmar_eliminar_pregunta(update, context)
    else:
        await recibir_eliminar_pregunta(update, context)


# ============================================================
# HANDLER DEL MENÚ PRINCIPAL
# ============================================================

async def manejar_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los mensajes de texto del menú principal - SOLO si NO hay conversación activa"""
    text = update.message.text
    log_info(f"📩 Mensaje recibido en manejar_menu: {text}") 
    
    if context.user_data.get('conversation_state'):
        return
    
    text = update.message.text
    user_id = update.effective_user.id
    
    es_admin_real = es_admin(update)
    modo_usuario_activo = context.user_data.get('modo_usuario', False)
    
    if es_admin_real and modo_usuario_activo:
        from src.user_handlers import user_handlers
        
        if text == config.BOTON_USUARIO['responder']:
            await user_handlers.iniciar_responder(update, context)
        elif text == config.BOTON_USUARIO['mi_historial']:
            await user_handlers.mostrar_mi_historial(update, context)
        elif text == config.BOTON_ADMIN['modo_admin']:
            context.user_data['modo_usuario'] = False
            await mostrar_panel_admin(update, context)
        else:
            pass
        return
    
    if es_admin_real:
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
        elif text == config.BOTON_ADMIN['modo_usuario']:
            context.user_data['modo_usuario'] = True
            await mostrar_panel_usuario(update, context)
        return
    
    from src.user_handlers import user_handlers
    
    if text == config.BOTON_USUARIO['responder']:
        await user_handlers.iniciar_responder(update, context)
    elif text == config.BOTON_USUARIO['mi_historial']:
        await user_handlers.mostrar_mi_historial(update, context)


# ============================================================
# CONFIGURACIÓN DE LA APLICACIÓN
# ============================================================

def configurar_bot() -> Application:
    """Configura y retorna la aplicación del bot"""
    
    application = Application.builder().token(config.TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin_registro", admin_command))
    application.add_handler(CommandHandler("cancelar", cancelar))
    
    # ============================================================
    # HANDLER PARA ELIMINAR PREGUNTA (prioridad alta)
    # ============================================================
    
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            manejar_respuesta_eliminar
        ),
        group=1  # Prioridad alta
    )
    
    # ============================================================
    # HANDLER DE MENÚ (prioridad baja)
    # ============================================================

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            manejar_menu
        ),
        group=2
    )
    
    # ============================================================
    # HANDLERS DE ADMIN (ConversationHandlers) - PRIORIDAD BAJA
    # ============================================================
    
    from src.admin_handlers import admin_handlers
    admin_handlers.registrar_handlers(application, group=2)
    
    # ============================================================
    # HANDLERS DE USUARIO (ConversationHandlers) - PRIORIDAD BAJA
    # ============================================================
    
    from src.user_handlers import user_handlers
    user_handlers.registrar_handlers(application, group=2)
    
    # ============================================================
    # HANDLER DE CALLBACK QUERY (botones inline)
    # ============================================================
    
    async def manejar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        data = query.data
        
        if data.startswith('admin_hist_'):
            from src.admin_handlers import manejar_callback_historial
            await manejar_callback_historial(update, context)
            return
        
        if data.startswith('config_'):
            from src.admin_handlers import manejar_callback_config
            await manejar_callback_config(update, context)
            return
        
        if data.startswith('user_'):
            from src.user_handlers import user_handlers
            await user_handlers.manejar_callback_usuario(update, context)
            return
        
        if data.startswith('resp_'):
            from src.user_handlers import user_handlers
            await user_handlers.manejar_respuesta(update, context)
            return
        
        if data.startswith('lanzar_'):
            return
        
        if data == 'cancelar':
            from src.user_handlers import cancelar_respuesta
            await cancelar_respuesta(update, context)
            return
        
        if data == 'ver_correctas':
            sesion = db.obtener_sesion_activa(update.effective_user.id)
            if sesion:
                from src.cuestionario import mostrar_respuestas_correctas
                await mostrar_respuestas_correctas(update, context, sesion['id'])
            return
        
        return
    
    application.add_handler(CallbackQueryHandler(manejar_callback))
    
    # ============================================================
    # MANEJADOR DE ERRORES MEJORADO - IGNORA ERRORES NORMALES
    # ============================================================
    
    async def manejar_error(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja errores del bot - Ignora errores comunes y solo muestra mensajes críticos"""
        error = context.error
        error_str = str(error)
        
        # Lista de errores que se deben IGNORAR
        errores_ignorar = [
            "Conflict", "Timed out", "Network", "Message not modified",
            "Can't parse entities", "Message is not modified", "CallbackQuery",
            "Query is too old", "Message to edit not found", "Can't edit message",
            "Not enough rights", "Chat not found", "User not found",
            "Bad Request: message is not modified", "Bad Request: can't parse entities",
            "message to edit", "not modified"
        ]
        
        for patron in errores_ignorar:
            if patron.lower() in error_str.lower():
                log_info(f"ℹ️ Error ignorado (normal): {error_str[:150]}")
                return
        
        if "bad request" in error_str.lower() and "not modified" in error_str.lower():
            log_info(f"ℹ️ Error de mensaje no modificado (normal): {error_str[:150]}")
            return
        
        if "callback" in error_str.lower() and ("query" in error_str.lower() or "expired" in error_str.lower()):
            log_info(f"ℹ️ Callback expirado (normal): {error_str[:150]}")
            return
        
        log_error(f"❌ Error crítico en el bot: {str(error)}")
        import traceback
        log_error(f"❌ Traceback: {traceback.format_exc()}")
    
    application.add_error_handler(manejar_error)
    
    return application

# ============================================================
# FIN DE bot.py
# ============================================================