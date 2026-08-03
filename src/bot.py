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
from src.estados import *  # Importar todos los estados desde el archivo separado

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
# MANEJADORES DE MENSAJES PRINCIPALES
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /start"""
    user = update.effective_user
    user_id = user.id
    
    # Verificar si es admin
    if es_admin(update):
        await mostrar_panel_admin(update, context)
        return
    
    # Usuario normal
    await mostrar_panel_usuario(update, context)


async def mostrar_panel_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el panel de administrador"""
    # Importar admin_handlers AQUÍ para evitar import circular
    from src.admin_handlers import admin_handlers
    
    keyboard = [
        [config.BOTON_ADMIN['crear'], config.BOTON_ADMIN['csv']],
        [config.BOTON_ADMIN['historial'], config.BOTON_ADMIN['configurar']],
        [config.BOTON_ADMIN['lanzar'], config.BOTON_ADMIN['gestionar']],
        [config.BOTON_ADMIN['respaldos']]
    ]
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    # Verificar estadísticas y límites
    mensaje = "👑 **Panel de Administrador**\n\n"
    
    # Contar preguntas
    admin = db.obtener_admin(update.effective_user.id)
    if admin:
        total_preguntas = db.contar_preguntas(admin['id'])
        mensaje += f"📝 Total de preguntas: {total_preguntas}\n"
        
        # Verificar cuestionario activo
        cuestionario = db.obtener_cuestionario_activo()
        if cuestionario:
            mensaje += f"🚀 Cuestionario activo: {cuestionario.get('nombre', 'Sin nombre')}\n"
        else:
            mensaje += "📭 No hay cuestionario activo\n"
        
        # Verificar historial
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
    # Verificar si hay preguntas
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
    
    # Contar preguntas
    total_preguntas = db.contar_preguntas(admin['id'])
    if total_preguntas == 0:
        await update.message.reply_text(
            config.MENSAJE_SIN_PREGUNTAS,
            parse_mode='Markdown'
        )
        return
    
    # Verificar cuestionario activo
    cuestionario = db.obtener_cuestionario_activo()
    if not cuestionario:
        await update.message.reply_text(
            config.MENSAJE_SIN_CUESTIONARIO,
            parse_mode='Markdown'
        )
        return
    
    # Verificar si tiene una sesión activa
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
# MANEJADOR DE ADMIN /admin*
# ============================================================

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /admin* CONTRASEÑA"""
    user = update.effective_user
    user_id = user.id
    
    # Obtener el texto del comando
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
    
    # Verificar contraseña
    if password != config.ADMIN_PASSWORD:
        await update.message.reply_text("❌ Contraseña incorrecta.")
        return
    
    # Registrar admin
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
    if 'conversation_state' in context.user_data:
        context.user_data.clear()
    
    await update.message.reply_text(
        "✅ Operación cancelada.",
        parse_mode='Markdown'
    )
    
    # Volver al panel correspondiente
    if es_admin(update):
        await mostrar_panel_admin(update, context)
    else:
        await mostrar_panel_usuario(update, context)

# ============================================================
# CONFIGURACIÓN DE LA APLICACIÓN
# ============================================================

def configurar_bot() -> Application:
    """Configura y retorna la aplicación del bot"""
    
    # Crear aplicación
    application = Application.builder().token(config.TELEGRAM_TOKEN).build()
    
    # ============================================================
    # COMANDOS
    # ============================================================
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin_registro", admin_command))
    application.add_handler(CommandHandler("cancelar", cancelar))
    
    # ============================================================
    # HANDLERS DE ADMIN (desde admin_handlers.py)
    # ============================================================
    
    # Registrar todos los handlers del admin
    # Importamos AQUÍ para evitar import circular
    from src.admin_handlers import admin_handlers
    admin_handlers.registrar_handlers(application)
    
    # ============================================================
    # HANDLERS DE USUARIO (desde user_handlers.py)
    # ============================================================
    
    # Registrar todos los handlers del usuario
    from src.user_handlers import user_handlers
    user_handlers.registrar_handlers(application)
    
    # ============================================================
    # HANDLER DE MENSAJES DE TEXTO (para botones de menú)
    # ============================================================
    
    async def manejar_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja los mensajes de texto del menú principal"""
        text = update.message.text
        
        # Verificar si es admin
        if es_admin(update):
            # Importar AQUÍ para evitar import circular
            from src.admin_handlers import admin_handlers
            
            # Botones del admin
            if text == config.BOTON_ADMIN['crear']:
                await admin_handlers.iniciar_crear_preguntas(update, context)
            elif text == config.BOTON_ADMIN['csv']:
                await admin_handlers.iniciar_subir_csv(update, context)
            elif text == config.BOTON_ADMIN['historial']:
                await admin_handlers.mostrar_historial(update, context)
            elif text == config.BOTON_ADMIN['configurar']:
                await admin_handlers.mostrar_configuracion(update, context)
            elif text == config.BOTON_ADMIN['lanzar']:
                await admin_handlers.iniciar_lanzar_cuestionario(update, context)
            elif text == config.BOTON_ADMIN['gestionar']:
                await admin_handlers.mostrar_gestion(update, context)
            elif text == config.BOTON_ADMIN['respaldos']:
                await admin_handlers.mostrar_respaldos(update, context)
            else:
                await update.message.reply_text(
                    "❌ Opción no reconocida. Usa los botones del menú.",
                    parse_mode='Markdown'
                )
        else:
            # Botones del usuario
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
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, manejar_menu))
    
    # ============================================================
    # HANDLER DE CALLBACK QUERY (botones inline)
    # ============================================================
    
    async def manejar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja todas las respuestas de botones inline"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        # Delegar según el tipo de callback
        if data.startswith('admin_'):
            from src.admin_handlers import admin_handlers
            await admin_handlers.manejar_callback_admin(update, context)
        elif data.startswith('user_'):
            from src.user_handlers import user_handlers
            await user_handlers.manejar_callback_usuario(update, context)
        elif data.startswith('resp_'):
            from src.user_handlers import user_handlers
            await user_handlers.manejar_respuesta(update, context)
        elif data == 'cancelar':
            await cancelar(update, context)
        elif data == 'ver_correctas':
            # Obtener sesión activa
            sesion = db.obtener_sesion_activa(update.effective_user.id)
            if sesion:
                from src.cuestionario import mostrar_respuestas_correctas
                await mostrar_respuestas_correctas(update, context, sesion['id'])
        else:
            await update.message.reply_text("❌ Opción no reconocida.")
    
    application.add_handler(CallbackQueryHandler(manejar_callback))
    
    # ============================================================
    # HANDLER DE ERRORES
    # ============================================================
    
    async def manejar_error(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja errores del bot"""
        error = context.error
        log_error(f"Error en el bot: {str(error)}")
        
        try:
            if update and update.effective_message:
                await update.effective_message.reply_text(
                    "❌ Ocurrió un error. Intenta de nuevo más tarde.\n"
                    "Si el problema persiste, contacta al administrador.",
                    parse_mode='Markdown'
                )
        except:
            pass
    
    application.add_error_handler(manejar_error)
    
    return application

# ============================================================
# FIN DE bot.py
# ============================================================