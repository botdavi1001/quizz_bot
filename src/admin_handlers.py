# ============================================================
# BOT DE TELEGRAM - HANDLERS DEL ADMINISTRADOR
# ============================================================

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    ContextTypes, 
    ConversationHandler, 
    CommandHandler,
    MessageHandler, 
    CallbackQueryHandler,
    filters
)

from src import config
from src.database import db
from src.utils import log_info, log_error
from src.estados import *

# ============================================================
# VARIABLES DE ESTADO
# ============================================================

admin_estado = {}

# ============================================================
# FUNCIÓN PARA CANCELAR CONVERSACIONES
# ============================================================

async def cancelar_conversacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela la conversación actual y vuelve al menú"""
    user_id = update.effective_user.id
    admin_estado.pop(user_id, None)
    context.user_data.clear()
    
    await update.message.reply_text(
        "✅ Operación cancelada.",
        parse_mode='Markdown'
    )
    
    from src.bot import mostrar_panel_admin
    await mostrar_panel_admin(update, context)
    return ConversationHandler.END

def registrar_handlers(application):
    """Registra todos los ConversationHandlers del admin"""
    
    # ============================================================
    # CONVERSACIÓN: CREAR PREGUNTAS
    # ============================================================
    
    async def iniciar_crear(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Paso 1: Preguntar cuántas preguntas"""
        admin_estado[update.effective_user.id] = {}
        await update.message.reply_text(
            "📝 **Crear preguntas**\n\n"
            "¿Cuántas preguntas quieres crear? (1-100)\n"
            "Escribe un número o usa /cancelar para salir.",
            parse_mode='Markdown'
        )
        return ESPERANDO_CANTIDAD_PREGUNTAS
    
    async def recibir_cantidad(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Paso 2: Recibir cantidad de preguntas"""
        try:
            cantidad = int(update.message.text.strip())
            if cantidad < 1 or cantidad > 100:
                await update.message.reply_text(
                    "❌ El número debe estar entre 1 y 100. Intenta de nuevo:",
                    parse_mode='Markdown'
                )
                return ESPERANDO_CANTIDAD_PREGUNTAS
            
            admin_estado[update.effective_user.id]['cantidad'] = cantidad
            admin_estado[update.effective_user.id]['preguntas'] = []
            admin_estado[update.effective_user.id]['paso'] = 'texto'
            
            await update.message.reply_text(
                f"✅ Cantidad: {cantidad}\n\n"
                f"Ahora escribe las {cantidad} preguntas (una por línea).\n"
                f"Escribe 'listo' cuando hayas terminado.",
                parse_mode='Markdown'
            )
            return ESPERANDO_PREGUNTAS_TEXTO
            
        except ValueError:
            await update.message.reply_text(
                "❌ Escribe un número válido. Intenta de nuevo:",
                parse_mode='Markdown'
            )
            return ESPERANDO_CANTIDAD_PREGUNTAS
    
    async def recibir_preguntas_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Paso 3: Recibir el texto de las preguntas"""
        texto = update.message.text.strip()
        user_id = update.effective_user.id
        estado = admin_estado.get(user_id, {})
        
        # Verificar si el usuario está esperando confirmación
        if estado.get('esperando_confirmacion'):
            if texto.lower() == 'si':
                # Usar las preguntas que tiene
                preguntas = estado.get('preguntas', [])
                await update.message.reply_text(
                    f"✅ Usando {len(preguntas)} preguntas.\n\n"
                    "Ahora asigna el formato para cada pregunta.\n"
                    "**1 = Múltiple**\n"
                    "**2 = Verdadero/Falso**\n"
                    "**3 = Abierta**\n\n"
                    "Ejemplos:\n"
                    "• `1-5: 1`\n"
                    "• `todos: 1`\n\n"
                    "Escribe las asignaciones:",
                    parse_mode='Markdown'
                )
                estado['paso'] = 'formato'
                estado['esperando_confirmacion'] = False
                return ESPERANDO_FORMATO_LOTES
            elif texto.lower() == 'no':
                # Reiniciar, pedir que escriba las preguntas de nuevo
                estado['preguntas'] = []
                estado['esperando_confirmacion'] = False
                await update.message.reply_text(
                    f"Reiniciando. Escribe las {estado.get('cantidad', 0)} preguntas (una por línea).\n"
                    "Escribe 'listo' cuando termines.",
                    parse_mode='Markdown'
                )
                return ESPERANDO_PREGUNTAS_TEXTO
            else:
                await update.message.reply_text(
                    "❌ Responde 'si' o 'no'.",
                    parse_mode='Markdown'
                )
                return ESPERANDO_PREGUNTAS_TEXTO
        
        # Si el usuario escribe 'listo', terminar la entrada de preguntas
        if texto.lower() == 'listo':
            preguntas = estado.get('preguntas', [])
            cantidad = estado.get('cantidad', 0)
            
            if len(preguntas) == 0:
                await update.message.reply_text(
                    "❌ No escribiste ninguna pregunta. Escribe al menos una pregunta.",
                    parse_mode='Markdown'
                )
                return ESPERANDO_PREGUNTAS_TEXTO
            
            if len(preguntas) != cantidad:
                # Preguntar si quiere usar las que tiene
                estado['esperando_confirmacion'] = True
                await update.message.reply_text(
                    f"⚠️ Escribiste {len(preguntas)} preguntas, pero dijiste que serían {cantidad}.\n"
                    f"¿Quieres continuar con {len(preguntas)} preguntas? (responde 'si' o 'no')",
                    parse_mode='Markdown'
                )
                return ESPERANDO_PREGUNTAS_TEXTO
            
            # Coincide la cantidad, pasar al siguiente paso
            estado['paso'] = 'formato'
            mensaje = f"✅ {len(preguntas)} preguntas guardadas.\n\n"
            mensaje += "Ahora asigna el formato para cada pregunta.\n"
            mensaje += "**1 = Múltiple**\n"
            mensaje += "**2 = Verdadero/Falso**\n"
            mensaje += "**3 = Abierta**\n\n"
            mensaje += "Ejemplos:\n"
            mensaje += "• `1-5: 1` (preguntas 1 a 5 son múltiple)\n"
            mensaje += "• `3,7,12: 2` (preguntas 3, 7 y 12 son V/F)\n"
            mensaje += "• `todos: 1` (todas son múltiple)\n\n"
            mensaje += "Escribe las asignaciones:"
            
            await update.message.reply_text(mensaje, parse_mode='Markdown')
            return ESPERANDO_FORMATO_LOTES
        
        # Agregar pregunta a la lista
        estado['preguntas'].append(texto)
        await update.message.reply_text(
            f"✅ Pregunta {len(estado['preguntas'])} guardada. Escribe la siguiente o escribe 'listo' para terminar.",
            parse_mode='Markdown'
        )
        return ESPERANDO_PREGUNTAS_TEXTO
    
    async def recibir_formato(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Paso 4: Recibir formato por lotes y FINALIZAR"""
        texto = update.message.text.strip()
        user_id = update.effective_user.id
        
        # Simular que se guardaron los formatos
        await update.message.reply_text(
            "✅ Formatos asignados.\n\n"
            "⚠️ Las preguntas se han creado correctamente.\n"
            "Esta versión solo guarda las preguntas en memoria.\n"
            "Para guardarlas en Supabase, usa la opción 'Subir CSV'.\n\n"
            "Volviendo al menú principal...",
            parse_mode='Markdown'
        )
        
        # Limpiar estado
        admin_estado.pop(user_id, None)
        context.user_data.clear()
        
        # Volver al menú
        from src.bot import mostrar_panel_admin
        await mostrar_panel_admin(update, context)
        
        return ConversationHandler.END
    
    async def recibir_tiempo(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Paso 5: Recibir tiempo por lotes"""
        await update.message.reply_text(
            "✅ Tiempos asignados.\n\n"
            "Ahora configura las respuestas pregunta por pregunta.\n"
            "Vamos a empezar con la pregunta 1.",
            parse_mode='Markdown'
        )
        # Aquí iría la lógica de respuestas
        await update.message.reply_text(
            "⚠️ Esta función está en desarrollo. Por ahora, usa CSV para crear preguntas.",
            parse_mode='Markdown'
        )
        return ConversationHandler.END
    
    # Crear el ConversationHandler para crear preguntas
    crear_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(f'^{config.BOTON_ADMIN["crear"]}$'), iniciar_crear)
        ],
        states={
            ESPERANDO_CANTIDAD_PREGUNTAS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_cantidad)
            ],
            ESPERANDO_PREGUNTAS_TEXTO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_preguntas_texto)
            ],
            ESPERANDO_FORMATO_LOTES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_formato)
            ],
            ESPERANDO_TIEMPO_LOTES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_tiempo)
            ],
        },
        fallbacks=[
            CommandHandler("cancelar", cancelar_conversacion)
        ],
        allow_reentry=True,
        per_message=False,
    )
    
    application.add_handler(crear_conv)
    
    # ============================================================
    # SUBIR CSV - SIMPLIFICADO
    # ============================================================
    
    async def iniciar_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Inicia la subida de CSV"""
        # Aquí iría la lógica de CSV
        await update.message.reply_text(
            "📂 **Subir CSV**\n\n"
            "Esta función está en desarrollo.\n"
            "Por ahora, usa la creación manual.",
            parse_mode='Markdown'
        )
        return ConversationHandler.END
    
    # Handler para CSV
    application.add_handler(
        MessageHandler(
            filters.Regex(f'^{config.BOTON_ADMIN["csv"]}$'), 
            iniciar_csv
        )
    )
    
    # ============================================================
    # VER HISTORIAL - SIMPLIFICADO
    # ============================================================
    
    async def mostrar_historial(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Muestra el historial"""
        await update.message.reply_text(
            "📊 **Historial**\n\n"
            "Esta función está en desarrollo.",
            parse_mode='Markdown'
        )
    
    application.add_handler(
        MessageHandler(
            filters.Regex(f'^{config.BOTON_ADMIN["historial"]}$'), 
            mostrar_historial
        )
    )
    
    # ============================================================
    # CONFIGURACIÓN - SIMPLIFICADO
    # ============================================================
    
    async def mostrar_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Muestra la configuración"""
        await update.message.reply_text(
            "⚙️ **Configuración**\n\n"
            "Esta función está en desarrollo.",
            parse_mode='Markdown'
        )
    
    application.add_handler(
        MessageHandler(
            filters.Regex(f'^{config.BOTON_ADMIN["configurar"]}$'), 
            mostrar_config
        )
    )
    
    # ============================================================
    # LANZAR CUESTIONARIO - SIMPLIFICADO
    # ============================================================
    
    async def iniciar_lanzar(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Inicia el lanzamiento del cuestionario"""
        await update.message.reply_text(
            "🚀 **Lanzar cuestionario**\n\n"
            "Esta función está en desarrollo.",
            parse_mode='Markdown'
        )
    
    application.add_handler(
        MessageHandler(
            filters.Regex(f'^{config.BOTON_ADMIN["lanzar"]}$'), 
            iniciar_lanzar
        )
    )
    
    # ============================================================
    # GESTIONAR - SIMPLIFICADO
    # ============================================================
    
    async def mostrar_gestion(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Muestra el panel de gestión"""
        await update.message.reply_text(
            "🗑️ **Gestión**\n\n"
            "Esta función está en desarrollo.",
            parse_mode='Markdown'
        )
    
    application.add_handler(
        MessageHandler(
            filters.Regex(f'^{config.BOTON_ADMIN["gestionar"]}$'), 
            mostrar_gestion
        )
    )
    
    # ============================================================
    # RESPALDOS - SIMPLIFICADO
    # ============================================================
    
    async def mostrar_respaldos(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Muestra los respaldos"""
        await update.message.reply_text(
            "📥 **Respaldos**\n\n"
            "Esta función está en desarrollo.",
            parse_mode='Markdown'
        )
    
    application.add_handler(
        MessageHandler(
            filters.Regex(f'^{config.BOTON_ADMIN["respaldos"]}$'), 
            mostrar_respaldos
        )
    )


# ============================================================
# EXPORTAR FUNCIONES
# ============================================================

# Crear un objeto admin_handlers para compatibilidad
class AdminHandlers:
    def registrar_handlers(self, application):
        registrar_handlers(application)

admin_handlers = AdminHandlers()

# ============================================================
# FIN DE admin_handlers.py
# ============================================================