# ============================================================
# BOT DE TELEGRAM - HANDLERS DEL ADMINISTRADOR
# Crear preguntas, CSV, historial, configuración, lanzar, gestionar
# ============================================================

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, filters, MessageHandler, CallbackQueryHandler

import config
from src.database import db
from src.utils import (
    log_info, log_error,
    parsear_preguntas_texto,
    parsear_formato_lotes,
    parsear_tiempo_lotes,
    validar_opciones,
    validar_indices_correctos,
    validar_tiempo,
    validar_tolerancia,
    formatear_resumen_admin
)
from src.csv_processor import procesar_csv, generar_csv_ejemplo, formatear_resultado_csv
from src.historial_manager import (
    obtener_historial_para_reporte,
    verificar_limite_historial,
    verificar_almacenamiento,
    limpiar_historial_por_dias,
    limpiar_historial_por_usuario
)
from src.cuestionario import (
    obtener_preguntas_cuestionario,
    seleccionar_preguntas,
    limpiar_cache
)
from src.backup_system import backup
from src.image_compressor import procesar_y_subir_imagen, obtener_espacio_usado
from src.estados import *  # Importar todos los estados

# ============================================================
# VARIABLES DE ESTADO PARA EL ADMIN
# ============================================================

admin_estado = {}

# ============================================================
# REGISTRAR HANDLERS
# ============================================================

class AdminHandlers:
    """Clase para manejar todos los handlers del admin"""
    
    def registrar_handlers(self, application):
        """Registra todos los handlers del admin"""
        # Aquí se registrarán los handlers
        pass

admin_handlers = AdminHandlers()

# ============================================================
# FUNCIONES DE INICIO
# ============================================================

async def iniciar_crear_preguntas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia el proceso de crear preguntas"""
    admin_estado[update.effective_user.id] = {}
    await update.message.reply_text(
        "📝 **Crear preguntas**\n\n"
        "¿Cuántas preguntas quieres crear? (1-100)\n"
        "Escribe un número o 'cancelar' para salir.",
        parse_mode='Markdown'
    )
    return ESPERANDO_CANTIDAD_PREGUNTAS


async def iniciar_subir_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia el proceso de subir CSV"""
    # Generar y enviar archivo de ejemplo
    ejemplo = generar_csv_ejemplo()
    await update.message.reply_document(
        document=ejemplo,
        filename="ejemplo.csv",
        caption="📂 **Subir CSV**\n\n"
                "Descarga este archivo de ejemplo, edítalo y súbelo.\n\n"
                "**Columnas:**\n"
                "• pregunta: El texto de la pregunta\n"
                "• tipo: multiple, vf, abierta\n"
                "• opciones: Separadas por ; (ej: La Habana;Santiago)\n"
                "• correctas: Números separados por coma (0=ninguna), o V/F para VF\n"
                "• tiempo: Segundos (0=sin límite)\n"
                "• imagen_url: URL de imagen (opcional)\n"
                "• video_url: URL de video (opcional)\n"
                "• enlace: URL adicional (opcional)\n\n"
                "Sube el archivo CSV cuando esté listo.",
        parse_mode='Markdown'
    )
    return ESPERANDO_CSV


async def iniciar_lanzar_cuestionario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia el proceso de lanzar cuestionario"""
    # Verificar que haya preguntas
    admin = db.obtener_admin(update.effective_user.id)
    if not admin:
        await update.message.reply_text("❌ No eres admin.")
        return ConversationHandler.END
    
    total_preguntas = db.contar_preguntas(admin['id'])
    if total_preguntas == 0:
        await update.message.reply_text(
            "❌ No hay preguntas disponibles.\n"
            "Crea preguntas primero.",
            parse_mode='Markdown'
        )
        return ConversationHandler.END
    
    admin_estado[update.effective_user.id] = {
        'admin_id': admin['id']
    }
    
    await update.message.reply_text(
        "🚀 **Lanzar cuestionario**\n\n"
        "Escribe el nombre del cuestionario:",
        parse_mode='Markdown'
    )
    return ESPERANDO_LANZAR_NOMBRE


async def mostrar_historial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el menú de historial"""
    keyboard = [
        [InlineKeyboardButton("📈 Resumen general", callback_data="hist_resumido")],
        [InlineKeyboardButton("📋 Detallado", callback_data="hist_detallado")],
        [InlineKeyboardButton("👤 Por usuario", callback_data="hist_usuario")],
        [InlineKeyboardButton("📅 Por fecha", callback_data="hist_fecha")],
        [InlineKeyboardButton("🏆 Estadísticas", callback_data="hist_estadisticas")],
        [InlineKeyboardButton("🗑️ Limpiar historial", callback_data="hist_limpiar")],
        [InlineKeyboardButton("❌ Cerrar", callback_data="hist_cerrar")]
    ]
    
    # Verificar límites
    supera, total, mensaje = verificar_limite_historial()
    
    await update.message.reply_text(
        f"📊 **Historial**\n\n"
        f"{mensaje}\n\n"
        "Selecciona el tipo de reporte:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def mostrar_configuracion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el panel de configuración"""
    admin = db.obtener_admin(update.effective_user.id)
    if not admin:
        await update.message.reply_text("❌ No eres admin.")
        return
    
    config_actual = admin.get('config', {})
    
    keyboard = [
        [InlineKeyboardButton(f"🔔 Notificar admin: {'✅' if config_actual.get('notificar_admin', True) else '❌'}", 
                             callback_data="config_notificar")],
        [InlineKeyboardButton(f"⏱️ Tiempo global: {config_actual.get('tiempo_global_default', 30)}s", 
                             callback_data="config_tiempo")],
        [InlineKeyboardButton(f"🎯 Mostrar correctas: {'✅' if config_actual.get('mostrar_correctas', True) else '❌'}", 
                             callback_data="config_mostrar")],
        [InlineKeyboardButton(f"🔄 Reintentos: {config_actual.get('reintentos_default', 3)}", 
                             callback_data="config_reintentos")],
        [InlineKeyboardButton(f"📊 Formato reporte: {config_actual.get('formato_reporte', 'resumido')}", 
                             callback_data="config_formato")],
        [InlineKeyboardButton(f"📏 Tolerancia abiertas: {config_actual.get('tolerancia_abiertas', 80)}%", 
                             callback_data="config_tolerancia")],
        [InlineKeyboardButton("❌ Cerrar", callback_data="config_cerrar")]
    ]
    
    await update.message.reply_text(
        "⚙️ **Configuración**\n\n"
        "Selecciona una opción para cambiarla:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def mostrar_gestion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el panel de gestión"""
    keyboard = [
        [InlineKeyboardButton("📝 Editar pregunta", callback_data="gestion_editar")],
        [InlineKeyboardButton("❌ Eliminar pregunta", callback_data="gestion_eliminar")],
        [InlineKeyboardButton("🗑️ Eliminar todas las preguntas", callback_data="gestion_eliminar_todas")],
        [InlineKeyboardButton("🧹 Limpiar historial", callback_data="gestion_limpiar")],
        [InlineKeyboardButton("🗑️ Limpiar imágenes antiguas", callback_data="gestion_limpiar_imagenes")],
        [InlineKeyboardButton("❌ Cerrar", callback_data="gestion_cerrar")]
    ]
    
    await update.message.reply_text(
        "🗑️ **Gestión**\n\n"
        "Selecciona una opción:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def mostrar_respaldos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra los respaldos pendientes"""
    pendientes = backup.obtener_pendientes()
    estadisticas = backup.obtener_estadisticas()
    
    if not pendientes:
        await update.message.reply_text(
            "✅ **No hay respaldos pendientes.**\n\n"
            f"📊 Última sincronización: {estadisticas.get('ultima_sincronizacion', 'Nunca')}\n"
            f"📦 Respaldos completados: {estadisticas.get('completados', 0)}",
            parse_mode='Markdown'
        )
        return
    
    mensaje = f"📥 **Respaldos pendientes: {len(pendientes)}**\n\n"
    
    for i, respaldo in enumerate(pendientes[:10], 1):
        mensaje += f"{i}. {respaldo.get('tipo', 'desconocido')} - {respaldo.get('fecha', '')}\n"
        mensaje += f"   Intentos: {respaldo.get('intentos', 0)}/{config.SUPABASE_RETRIES}\n"
    
    if len(pendientes) > 10:
        mensaje += f"\n... y {len(pendientes) - 10} más."
    
    keyboard = [
        [InlineKeyboardButton("🔄 Sincronizar ahora", callback_data="respaldos_sincronizar")],
        [InlineKeyboardButton("🗑️ Limpiar respaldos", callback_data="respaldos_limpiar")],
        [InlineKeyboardButton("❌ Cerrar", callback_data="respaldos_cerrar")]
    ]
    
    await update.message.reply_text(
        mensaje,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


# ============================================================
# MANEJADORES DE CALLBACK DEL ADMIN
# ============================================================

async def manejar_callback_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja callbacks del admin"""
    query = update.callback_query
    data = query.data
    
    # Historial
    if data.startswith('hist_'):
        await manejar_callback_historial(update, context)
    
    # Configuración
    elif data.startswith('config_'):
        await manejar_callback_configuracion(update, context)
    
    # Gestión
    elif data.startswith('gestion_'):
        await manejar_callback_gestion(update, context)
    
    # Respaldos
    elif data.startswith('respaldos_'):
        await manejar_callback_respaldos(update, context)
    
    await query.answer()


async def manejar_callback_historial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja callbacks del historial"""
    query = update.callback_query
    data = query.data
    
    admin = db.obtener_admin(update.effective_user.id)
    if not admin:
        await query.edit_message_text("❌ No eres admin.")
        return
    
    if data == 'hist_resumido':
        _, mensaje = obtener_historial_para_reporte(admin['id'], 'resumido')
        await query.edit_message_text(mensaje, parse_mode='Markdown')
    
    elif data == 'hist_detallado':
        _, mensaje = obtener_historial_para_reporte(admin['id'], 'detallado')
        await query.edit_message_text(mensaje, parse_mode='Markdown')
    
    elif data == 'hist_usuario':
        _, mensaje = obtener_historial_para_reporte(admin['id'], 'usuario')
        await query.edit_message_text(mensaje, parse_mode='Markdown')
    
    elif data == 'hist_fecha':
        _, mensaje = obtener_historial_para_reporte(admin['id'], 'fecha')
        await query.edit_message_text(mensaje, parse_mode='Markdown')
    
    elif data == 'hist_estadisticas':
        _, mensaje = obtener_historial_para_reporte(admin['id'], 'estadisticas')
        await query.edit_message_text(mensaje, parse_mode='Markdown')
    
    elif data == 'hist_limpiar':
        await query.edit_message_text(
            "🗑️ **Limpiar historial**\n\n"
            "Escribe el número de días a mantener (ej: 30 para mantener 30 días):\n"
            "O escribe 'todo' para eliminar todo.",
            parse_mode='Markdown'
        )
        return ESPERANDO_LIMPIAR_HISTORIAL
    
    elif data == 'hist_cerrar':
        await query.edit_message_text("✅ Historial cerrado.")
        from src.bot import mostrar_panel_admin
        await mostrar_panel_admin(update, context)


async def manejar_callback_configuracion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja callbacks de configuración"""
    query = update.callback_query
    data = query.data
    
    admin = db.obtener_admin(update.effective_user.id)
    if not admin:
        await query.edit_message_text("❌ No eres admin.")
        return
    
    config_actual = admin.get('config', {})
    
    if data == 'config_notificar':
        nuevo_valor = not config_actual.get('notificar_admin', True)
        config_actual['notificar_admin'] = nuevo_valor
        db.actualizar_config_admin(update.effective_user.id, config_actual)
        await query.edit_message_text(f"✅ Notificaciones: {'Activadas' if nuevo_valor else 'Desactivadas'}")
        await mostrar_configuracion(update, context)
    
    elif data == 'config_tiempo':
        await query.edit_message_text(
            "⏱️ **Configurar tiempo global**\n\n"
            "Escribe el tiempo en segundos (ej: 30):",
            parse_mode='Markdown'
        )
        return ESPERANDO_CONFIGURACION
    
    elif data == 'config_mostrar':
        nuevo_valor = not config_actual.get('mostrar_correctas', True)
        config_actual['mostrar_correctas'] = nuevo_valor
        db.actualizar_config_admin(update.effective_user.id, config_actual)
        await query.edit_message_text(f"✅ Mostrar correctas: {'Activado' if nuevo_valor else 'Desactivado'}")
        await mostrar_configuracion(update, context)
    
    elif data == 'config_reintentos':
        await query.edit_message_text(
            "🔄 **Configurar reintentos**\n\n"
            "Escribe el número de reintentos permitidos (0 = sin límite):",
            parse_mode='Markdown'
        )
        return ESPERANDO_CONFIGURACION
    
    elif data == 'config_formato':
        nuevo_formato = 'detallado' if config_actual.get('formato_reporte', 'resumido') == 'resumido' else 'resumido'
        config_actual['formato_reporte'] = nuevo_formato
        db.actualizar_config_admin(update.effective_user.id, config_actual)
        await query.edit_message_text(f"✅ Formato de reporte: {nuevo_formato}")
        await mostrar_configuracion(update, context)
    
    elif data == 'config_tolerancia':
        await query.edit_message_text(
            "📏 **Configurar tolerancia para abiertas**\n\n"
            "Escribe la tolerancia (0-100):\n"
            "Ej: 80 significa que el texto debe coincidir al menos en un 80%",
            parse_mode='Markdown'
        )
        return ESPERANDO_CONFIGURACION
    
    elif data == 'config_cerrar':
        await query.edit_message_text("✅ Configuración cerrada.")
        from src.bot import mostrar_panel_admin
        await mostrar_panel_admin(update, context)


async def manejar_callback_gestion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja callbacks de gestión"""
    query = update.callback_query
    data = query.data
    
    admin = db.obtener_admin(update.effective_user.id)
    if not admin:
        await query.edit_message_text("❌ No eres admin.")
        return
    
    if data == 'gestion_editar':
        # Mostrar lista de preguntas para editar
        preguntas = db.obtener_preguntas(admin['id'])
        if not preguntas:
            await query.edit_message_text("❌ No hay preguntas para editar.")
            return
        
        mensaje = "📝 **Editar pregunta**\n\n"
        mensaje += "Selecciona el número de la pregunta a editar:\n\n"
        
        for i, p in enumerate(preguntas[:20], 1):
            texto = p.get('texto', '')[:50]
            mensaje += f"{i}. {texto}...\n"
        
        if len(preguntas) > 20:
            mensaje += f"\n... y {len(preguntas) - 20} más."
        
        mensaje += "\n\nEscribe el número de la pregunta:"
        
        admin_estado[update.effective_user.id] = {
            'preguntas': preguntas,
            'modo': 'editar'
        }
        
        await query.edit_message_text(mensaje, parse_mode='Markdown')
        return ESPERANDO_EDITAR_PREGUNTA
    
    elif data == 'gestion_eliminar':
        # Mostrar lista de preguntas para eliminar
        preguntas = db.obtener_preguntas(admin['id'])
        if not preguntas:
            await query.edit_message_text("❌ No hay preguntas para eliminar.")
            return
        
        mensaje = "❌ **Eliminar pregunta**\n\n"
        mensaje += "Selecciona el número de la pregunta a eliminar:\n\n"
        
        for i, p in enumerate(preguntas[:20], 1):
            texto = p.get('texto', '')[:50]
            mensaje += f"{i}. {texto}...\n"
        
        if len(preguntas) > 20:
            mensaje += f"\n... y {len(preguntas) - 20} más."
        
        mensaje += "\n\nEscribe el número de la pregunta (o 'todos' para eliminar todas):"
        
        admin_estado[update.effective_user.id] = {
            'preguntas': preguntas,
            'modo': 'eliminar'
        }
        
        await query.edit_message_text(mensaje, parse_mode='Markdown')
        return ESPERANDO_ELIMINAR_PREGUNTA
    
    elif data == 'gestion_eliminar_todas':
        await query.edit_message_text(
            "⚠️ **¿Eliminar todas las preguntas?**\n\n"
            "Esta acción no se puede deshacer.\n"
            "¿Estás seguro? (escribe 'SI' para confirmar)",
            parse_mode='Markdown'
        )
        return ESPERANDO_ELIMINAR_PREGUNTA
    
    elif data == 'gestion_limpiar':
        await query.edit_message_text(
            "🗑️ **Limpiar historial**\n\n"
            "Escribe el número de días a mantener (ej: 30 para mantener 30 días):\n"
            "O escribe 'todo' para eliminar todo.",
            parse_mode='Markdown'
        )
        return ESPERANDO_LIMPIAR_HISTORIAL
    
    elif data == 'gestion_limpiar_imagenes':
        await query.edit_message_text(
            "🗑️ **Limpiar imágenes antiguas**\n\n"
            "Escribe el número de días de antigüedad (ej: 30):",
            parse_mode='Markdown'
        )
        return ESPERANDO_LIMPIAR_HISTORIAL
    
    elif data == 'gestion_cerrar':
        await query.edit_message_text("✅ Gestión cerrada.")
        from src.bot import mostrar_panel_admin
        await mostrar_panel_admin(update, context)


async def manejar_callback_respaldos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja callbacks de respaldos"""
    query = update.callback_query
    data = query.data
    
    if data == 'respaldos_sincronizar':
        await query.edit_message_text("🔄 Sincronizando respaldos...")
        sincronizados = await backup.sincronizar()
        await query.edit_message_text(f"✅ Sincronización completada: {sincronizados} respaldos.")
        await mostrar_respaldos(update, context)
    
    elif data == 'respaldos_limpiar':
        backup.limpiar_historial_respaldos()
        await query.edit_message_text("✅ Historial de respaldos limpiado.")
        await mostrar_respaldos(update, context)
    
    elif data == 'respaldos_cerrar':
        await query.edit_message_text("✅ Respaldos cerrados.")
        from src.bot import mostrar_panel_admin
        await mostrar_panel_admin(update, context)


# ============================================================
# FUNCIÓN AUXILIAR PARA MOSTRAR PANEL ADMIN
# ============================================================

async def mostrar_panel_admin_local(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el panel de admin (wrapper para evitar importación circular)"""
    from src.bot import mostrar_panel_admin
    await mostrar_panel_admin(update, context)

# ============================================================
# EXPORTAR FUNCIONES
# ============================================================

# Asignar funciones a admin_handlers
admin_handlers.iniciar_crear_preguntas = iniciar_crear_preguntas
admin_handlers.iniciar_subir_csv = iniciar_subir_csv
admin_handlers.iniciar_lanzar_cuestionario = iniciar_lanzar_cuestionario
admin_handlers.mostrar_historial = mostrar_historial
admin_handlers.mostrar_configuracion = mostrar_configuracion
admin_handlers.mostrar_gestion = mostrar_gestion
admin_handlers.mostrar_respaldos = mostrar_respaldos
admin_handlers.manejar_callback_admin = manejar_callback_admin

# ============================================================
# FIN DE admin_handlers.py
# ============================================================