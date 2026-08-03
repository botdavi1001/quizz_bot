# ============================================================
# BOT DE TELEGRAM - HANDLERS DE USUARIOS
# Responder cuestionarios, historial personal, manejo de respuestas
# ============================================================

import asyncio
from datetime import datetime
from typing import Dict, List, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, filters, MessageHandler, CallbackQueryHandler, CommandHandler

from src import config
from src.database import db
from src.utils import (
    log_info, log_error,
    normalizar_respuesta_abierta,
    formatear_fecha,
    formatear_estado
)
from src.cuestionario import (
    obtener_preguntas_cuestionario,
    mostrar_pregunta,
    continuar_cuestionario,
    completar_cuestionario,
    verificar_respuesta_abierta,
    limpiar_cache
)
from src.backup_system import backup
from src.estados import *

# ============================================================
# VARIABLES DE ESTADO
# ============================================================

user_estado = {}

# ============================================================
# REGISTRAR HANDLERS
# ============================================================

class UserHandlers:
    """Clase para manejar todos los handlers de usuario"""
    
    def registrar_handlers(self, application, group=1):
        """Registra todos los handlers de usuario con prioridad group"""
        
        # ============================================================
        # CONVERSACIÓN: RESPUESTA ABIERTA
        # ============================================================
        
        respuesta_abierta_conv = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(manejar_callback_usuario, pattern="^resp_abierta$")
            ],
            states={
                ESPERANDO_RESPUESTA_ABIERTA_TEXTO: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_respuesta_abierta)
                ]
            },
            fallbacks=[
                CommandHandler("cancelar", cancelar_respuesta)
            ],
            allow_reentry=True,
            per_message=False,
        )
        
        application.add_handler(respuesta_abierta_conv, group=group)

user_handlers = UserHandlers()

# ============================================================
# FUNCIONES DE INICIO
# ============================================================

async def iniciar_responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia el proceso de responder un cuestionario"""
    user = update.effective_user
    user_id = user.id
    
    # Verificar si hay cuestionario activo
    cuestionario = db.obtener_cuestionario_activo()
    if not cuestionario:
        await update.message.reply_text(
            config.MENSAJE_SIN_CUESTIONARIO,
            parse_mode='Markdown'
        )
        return
    
    # Verificar si ya tiene una sesión activa
    sesion = db.obtener_sesion_activa(user_id)
    
    if sesion:
        # Preguntar si quiere continuar
        keyboard = [
            [InlineKeyboardButton("✅ Continuar", callback_data="user_continuar")],
            [InlineKeyboardButton("🔄 Reiniciar", callback_data="user_reiniciar")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="user_cancelar")]
        ]
        
        await update.message.reply_text(
            "⏳ **Tienes un cuestionario en progreso.**\n\n"
            f"📊 Pregunta {sesion.get('pregunta_actual', 0) + 1} de {len(cuestionario.get('preguntas_ids', []))}\n\n"
            "¿Quieres continuar o reiniciar?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return
    
    # Iniciar nuevo cuestionario
    await iniciar_nuevo_cuestionario(update, context, cuestionario)


async def iniciar_nuevo_cuestionario(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                     cuestionario: Dict):
    """Inicia un nuevo cuestionario para el usuario"""
    user = update.effective_user
    
    # Verificar reintentos
    intentos = db.contar_intentos_usuario(user.id, cuestionario['id'])
    max_intentos = cuestionario.get('reintentos', config.REINTENTOS_DEFAULT)
    
    if max_intentos > 0 and intentos >= max_intentos:
        await update.message.reply_text(
            config.MENSAJE_REINTENTOS_AGOTADOS,
            parse_mode='Markdown'
        )
        return
    
    # Obtener preguntas
    preguntas = obtener_preguntas_cuestionario(cuestionario['id'], cuestionario['admin_id'])
    if not preguntas:
        await update.message.reply_text(
            "❌ No se encontraron preguntas para este cuestionario.",
            parse_mode='Markdown'
        )
        return
    
    # Crear sesión
    username = user.username or ""
    first_name = user.first_name or "Usuario"
    
    sesion_id = db.crear_sesion(
        user.id,
        username,
        first_name,
        cuestionario['id'],
        intentos + 1
    )
    
    if not sesion_id:
        await update.message.reply_text(
            "❌ Error al crear la sesión. Intenta de nuevo.",
            parse_mode='Markdown'
        )
        return
    
    # Guardar en contexto
    context.user_data['sesion_id'] = sesion_id
    context.user_data['pregunta_actual'] = 0
    
    # Mostrar primera pregunta
    await mostrar_pregunta(
        update,
        context,
        {'id': sesion_id},
        preguntas[0],
        0,
        len(preguntas)
    )


async def mostrar_mi_historial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el historial del usuario"""
    user_id = update.effective_user.id
    
    sesiones = db.obtener_historial_usuario(user_id, limit=20)
    
    if not sesiones:
        await update.message.reply_text(
            "📋 No tienes historial aún.",
            parse_mode='Markdown'
        )
        return
    
    mensaje = "📋 **Tu historial**\n\n"
    
    for i, sesion in enumerate(sesiones, 1):
        # Obtener nombre del cuestionario
        cuestionario = db.obtener_cuestionario(sesion.get('cuestionario_id'))
        nombre = cuestionario.get('nombre', 'Sin nombre') if cuestionario else 'Cuestionario'
        
        estado = formatear_estado(sesion)
        fecha = formatear_fecha(sesion.get('tiempo_inicio', ''))
        
        mensaje += f"**{i}. {nombre}**\n"
        mensaje += f"   📅 {fecha}\n"
        mensaje += f"   📌 {estado}\n"
        mensaje += f"   📝 Respuestas: {len(sesion.get('respuestas', []))}\n\n"
    
    await update.message.reply_text(mensaje, parse_mode='Markdown')

# ============================================================
# MANEJADORES DE CALLBACK DEL USUARIO
# ============================================================

async def manejar_callback_usuario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja callbacks de usuario"""
    query = update.callback_query
    data = query.data
    
    user_id = update.effective_user.id
    
    if data == 'user_continuar':
        # Continuar cuestionario
        sesion = db.obtener_sesion_activa(user_id)
        if not sesion:
            await query.edit_message_text("❌ No tienes una sesión activa.")
            return
        
        await continuar_cuestionario(update, context, sesion['id'], True)
    
    elif data == 'user_reiniciar':
        # Reiniciar cuestionario
        sesion = db.obtener_sesion_activa(user_id)
        if not sesion:
            await query.edit_message_text("❌ No tienes una sesión activa.")
            return
        
        db.abandonar_sesion(sesion['id'])
        
        # Iniciar nuevo
        cuestionario = db.obtener_cuestionario_activo()
        if cuestionario:
            await iniciar_nuevo_cuestionario(update, context, cuestionario)
        else:
            await query.edit_message_text("❌ No hay cuestionario activo.")
    
    elif data == 'user_cancelar':
        # Cancelar
        sesion = db.obtener_sesion_activa(user_id)
        if sesion:
            db.abandonar_sesion(sesion['id'])
        
        await query.edit_message_text("✅ Cuestionario cancelado.")
        from src.bot import mostrar_panel_usuario
        await mostrar_panel_usuario(update, context)
    
    elif data == 'resp_abierta':
        # El usuario quiere escribir una respuesta abierta
        await query.edit_message_text(
            "✏️ Escribe tu respuesta en el siguiente mensaje.\n"
            "Escribe 'cancelar' para salir.",
            parse_mode='Markdown'
        )
        return ESPERANDO_RESPUESTA_ABIERTA_TEXTO

# ============================================================
# MANEJADORES DE RESPUESTAS
# ============================================================

async def manejar_respuesta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja las respuestas de los botones inline (opciones múltiple, V/F)"""
    query = update.callback_query
    await query.answer()
    data = query.data
    
    user_id = update.effective_user.id
    
    # Obtener sesión activa
    sesion = db.obtener_sesion_activa(user_id)
    if not sesion:
        await query.edit_message_text("❌ No tienes una sesión activa.")
        return
    
    # Obtener cuestionario
    cuestionario = db.obtener_cuestionario(sesion.get('cuestionario_id'))
    if not cuestionario:
        await query.edit_message_text("❌ Cuestionario no encontrado.")
        return
    
    # Verificar si el cuestionario sigue activo
    if not cuestionario.get('activo', False):
        await query.edit_message_text(
            config.MENSAJE_CUESTIONARIO_INACTIVO,
            parse_mode='Markdown'
        )
        db.abandonar_sesion(sesion['id'])
        return
    
    # Obtener preguntas
    preguntas = obtener_preguntas_cuestionario(cuestionario['id'], cuestionario['admin_id'])
    if not preguntas:
        await query.edit_message_text("❌ No se encontraron preguntas.")
        return
    
    # Obtener pregunta actual
    pregunta_idx = sesion.get('pregunta_actual', 0)
    if pregunta_idx >= len(preguntas):
        # Ya completó todas
        await completar_cuestionario(update, context, sesion['id'])
        return
    
    pregunta = preguntas[pregunta_idx]
    
    # Procesar respuesta según tipo
    if data.startswith('resp_'):
        # Respuesta a opción múltiple o V/F
        if data == 'resp_v':
            respuesta = 'Verdadero'
            opcion_seleccionada = 0
        elif data == 'resp_f':
            respuesta = 'Falso'
            opcion_seleccionada = 1
        else:
            # Respuesta a múltiple (resp_0, resp_1, etc.)
            opcion_idx = int(data.split('_')[1])
            opciones = pregunta.get('opciones', [])
            if opcion_idx < len(opciones):
                respuesta = opciones[opcion_idx]
                opcion_seleccionada = opcion_idx
            else:
                await query.edit_message_text("❌ Opción inválida.")
                return
        
        # Verificar si es correcta
        correctas = pregunta.get('respuestas_correctas', [])
        es_correcta = opcion_seleccionada in correctas if correctas else False
        
        # Calcular tiempo tardado
        tiempo_tardado = 0
        if 'tiempo_inicio' in context.user_data:
            inicio = context.user_data['tiempo_inicio']
            tiempo_tardado = int((datetime.now() - inicio).total_seconds())
        
        # Guardar respuesta
        exito = db.guardar_respuesta_sesion(
            sesion['id'],
            pregunta['id'],
            respuesta,
            es_correcta,
            tiempo_tardado
        )
        
        if not exito:
            # Guardar en respaldo
            backup.guardar_respaldo('guardar_respuesta', {
                'sesion_id': sesion['id'],
                'pregunta_id': pregunta['id'],
                'respuesta': respuesta,
                'es_correcta': es_correcta,
                'tiempo_tardado': tiempo_tardado
            })
        
        # Limpiar tiempo de contexto
        context.user_data.pop('tiempo_inicio', None)
        
        # Mostrar feedback
        if es_correcta:
            feedback = "✅ ¡Correcto!"
        else:
            feedback = "❌ Incorrecto."
        
        await query.edit_message_text(
            f"{feedback}\n\n⏳ Siguiente pregunta...",
            parse_mode='Markdown'
        )
        
        # Pasar a la siguiente pregunta
        await asyncio.sleep(1)
        
        siguiente_idx = pregunta_idx + 1
        
        if siguiente_idx >= len(preguntas):
            # Completar cuestionario
            await completar_cuestionario(update, context, sesion['id'])
        else:
            # Mostrar siguiente pregunta
            await mostrar_pregunta(
                update,
                context,
                sesion,
                preguntas[siguiente_idx],
                siguiente_idx,
                len(preguntas)
            )


async def recibir_respuesta_abierta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe y procesa una respuesta abierta"""
    user_id = update.effective_user.id
    texto = update.message.text.strip()
    
    if texto.lower() == 'cancelar':
        await update.message.reply_text("✅ Respuesta cancelada.")
        return ConversationHandler.END
    
    # Obtener sesión activa
    sesion = db.obtener_sesion_activa(user_id)
    if not sesion:
        await update.message.reply_text("❌ No tienes una sesión activa.")
        return ConversationHandler.END
    
    # Obtener cuestionario
    cuestionario = db.obtener_cuestionario(sesion.get('cuestionario_id'))
    if not cuestionario:
        await update.message.reply_text("❌ Cuestionario no encontrado.")
        return ConversationHandler.END
    
    # Verificar si el cuestionario sigue activo
    if not cuestionario.get('activo', False):
        await update.message.reply_text(
            config.MENSAJE_CUESTIONARIO_INACTIVO,
            parse_mode='Markdown'
        )
        db.abandonar_sesion(sesion['id'])
        return ConversationHandler.END
    
    # Obtener preguntas
    preguntas = obtener_preguntas_cuestionario(cuestionario['id'], cuestionario['admin_id'])
    if not preguntas:
        await update.message.reply_text("❌ No se encontraron preguntas.")
        return ConversationHandler.END
    
    # Obtener pregunta actual
    pregunta_idx = sesion.get('pregunta_actual', 0)
    if pregunta_idx >= len(preguntas):
        await completar_cuestionario(update, context, sesion['id'])
        return ConversationHandler.END
    
    pregunta = preguntas[pregunta_idx]
    
    # Normalizar respuesta
    respuesta_normalizada = normalizar_respuesta_abierta(texto)
    
    # Verificar si es correcta (si es automática)
    admin = db.obtener_admin(cuestionario['admin_id'])
    admin_config = admin.get('config', {}) if admin else {}
    
    es_correcta = None
    es_manual = True
    
    # Verificar si es manual o automática
    if pregunta.get('respuestas_correctas'):
        es_correcta, es_manual = verificar_respuesta_abierta(
            respuesta_normalizada,
            pregunta,
            admin_config
        )
    
    # Guardar respuesta
    tiempo_tardado = 0
    if 'tiempo_inicio' in context.user_data:
        inicio = context.user_data['tiempo_inicio']
        tiempo_tardado = int((datetime.now() - inicio).total_seconds())
    
    exito = db.guardar_respuesta_sesion(
        sesion['id'],
        pregunta['id'],
        respuesta_normalizada,
        es_correcta,
        tiempo_tardado
    )
    
    if not exito:
        backup.guardar_respaldo('guardar_respuesta', {
            'sesion_id': sesion['id'],
            'pregunta_id': pregunta['id'],
            'respuesta': respuesta_normalizada,
            'es_correcta': es_correcta,
            'tiempo_tardado': tiempo_tardado
        })
    
    # Limpiar tiempo de contexto
    context.user_data.pop('tiempo_inicio', None)
    
    # Mostrar feedback
    if es_manual:
        feedback = "⏳ Respuesta guardada. Pendiente de calificación."
    elif es_correcta:
        feedback = "✅ ¡Correcto!"
    else:
        feedback = "❌ Incorrecto."
    
    await update.message.reply_text(
        f"{feedback}\n\n⏳ Siguiente pregunta...",
        parse_mode='Markdown'
    )
    
    # Pasar a la siguiente pregunta
    await asyncio.sleep(1)
    
    siguiente_idx = pregunta_idx + 1
    
    if siguiente_idx >= len(preguntas):
        await completar_cuestionario(update, context, sesion['id'])
    else:
        await mostrar_pregunta(
            update,
            context,
            sesion,
            preguntas[siguiente_idx],
            siguiente_idx,
            len(preguntas)
        )
    
    return ConversationHandler.END


async def cancelar_respuesta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela la respuesta abierta y vuelve al menú"""
    user_id = update.effective_user.id
    
    # Abandonar sesión si existe
    sesion = db.obtener_sesion_activa(user_id)
    if sesion:
        db.abandonar_sesion(sesion['id'])
    
    context.user_data.clear()
    
    await update.message.reply_text(
        "✅ Respuesta cancelada. Volviendo al menú...",
        parse_mode='Markdown'
    )
    
    from src.bot import mostrar_panel_usuario
    await mostrar_panel_usuario(update, context)
    return ConversationHandler.END


# ============================================================
# FUNCIÓN AUXILIAR PARA MOSTRAR PANEL DE USUARIO
# ============================================================

async def mostrar_panel_usuario_local(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el panel de usuario (wrapper para evitar importación circular)"""
    from src.bot import mostrar_panel_usuario
    await mostrar_panel_usuario(update, context)


# ============================================================
# EXPORTAR FUNCIONES
# ============================================================

# Asignar funciones a user_handlers
user_handlers.iniciar_responder = iniciar_responder
user_handlers.mostrar_mi_historial = mostrar_mi_historial
user_handlers.manejar_callback_usuario = manejar_callback_usuario
user_handlers.manejar_respuesta = manejar_respuesta
user_handlers.recibir_respuesta_abierta = recibir_respuesta_abierta

# ============================================================
# FIN DE user_handlers.py
# ============================================================