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
            admin_estado[update.effective_user.id]['formatos'] = {}
            admin_estado[update.effective_user.id]['tiempos'] = {}
            admin_estado[update.effective_user.id]['respuestas'] = {}
            
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
                estado['esperando_confirmacion'] = True
                await update.message.reply_text(
                    f"⚠️ Escribiste {len(preguntas)} preguntas, pero dijiste que serían {cantidad}.\n"
                    f"¿Quieres continuar con {len(preguntas)} preguntas? (responde 'si' o 'no')",
                    parse_mode='Markdown'
                )
                return ESPERANDO_PREGUNTAS_TEXTO
            
            estado['paso'] = 'formato'
            mensaje = f"✅ {len(preguntas)} preguntas guardadas.\n\n"
            mensaje += "Ahora asigna el formato para cada pregunta.\n"
            mensaje += "**1 = Múltiple**\n"
            mensaje += "**2 = Verdadero/Falso**\n"
            mensaje += "**3 = Abierta**\n\n"
            mensaje += "Ejemplos:\n"
            mensaje += "• `1-5: 1`\n"
            mensaje += "• `todos: 1`\n\n"
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
        """Paso 4: Recibir formato por lotes"""
        texto = update.message.text.strip()
        user_id = update.effective_user.id
        estado = admin_estado.get(user_id, {})
        total_preguntas = len(estado.get('preguntas', []))
        
        try:
            from src.utils import parsear_formato_lotes
            formatos = parsear_formato_lotes(texto, total_preguntas)
            
            if not formatos:
                await update.message.reply_text(
                    "❌ Formato inválido. Usa el formato correcto (ej: `1-5: 1` o `todos: 1`).\n"
                    "Intenta de nuevo:",
                    parse_mode='Markdown'
                )
                return ESPERANDO_FORMATO_LOTES
            
            # Guardar formatos
            estado['formatos'] = {}
            for num, fmt in formatos.items():
                if fmt in ['1', '2', '3']:
                    estado['formatos'][num] = int(fmt)
            
            await update.message.reply_text(
                f"✅ Formatos asignados para {len(estado['formatos'])} preguntas.\n\n"
                "Ahora asigna el tiempo para cada pregunta (en segundos).\n"
                "Ejemplos:\n"
                "• `1-10: 30`\n"
                "• `todos: 45`\n"
                "• `5,12: 0` (sin tiempo)\n\n"
                "Escribe las asignaciones:",
                parse_mode='Markdown'
            )
            return ESPERANDO_TIEMPO_LOTES
            
        except Exception as e:
            await update.message.reply_text(
                f"❌ Error: {str(e)}\nIntenta de nuevo:",
                parse_mode='Markdown'
            )
            return ESPERANDO_FORMATO_LOTES
    
    async def recibir_tiempo(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Paso 5: Recibir tiempo por lotes"""
        texto = update.message.text.strip()
        user_id = update.effective_user.id
        estado = admin_estado.get(user_id, {})
        total_preguntas = len(estado.get('preguntas', []))
        
        try:
            from src.utils import parsear_tiempo_lotes
            tiempos = parsear_tiempo_lotes(texto, total_preguntas)
            
            if not tiempos:
                await update.message.reply_text(
                    "❌ Tiempo inválido. Usa el formato correcto (ej: `1-10: 30` o `todos: 45`).\n"
                    "Intenta de nuevo:",
                    parse_mode='Markdown'
                )
                return ESPERANDO_TIEMPO_LOTES
            
            # Guardar tiempos
            estado['tiempos'] = tiempos
            
            await update.message.reply_text(
                f"✅ Tiempos asignados para {len(estado['tiempos'])} preguntas.\n\n"
                "**Ahora configura las respuestas**\n\n"
                "Para cada pregunta, te preguntaré:\n"
                "• Múltiple: opciones (separadas por ;) y correctas (números, 0=ninguna)\n"
                "• V/F: Verdadero o Falso\n"
                "• Abierta: respuesta esperada (o 'manual' para calificar después)\n\n"
                "Empezando con la pregunta 1:",
                parse_mode='Markdown'
            )
            
            # Iniciar configuración de respuestas
            estado['respuesta_actual'] = 0
            estado['respuestas'] = {}
            return await iniciar_configuracion_pregunta(update, context)
            
        except Exception as e:
            await update.message.reply_text(
                f"❌ Error: {str(e)}\nIntenta de nuevo:",
                parse_mode='Markdown'
            )
            return ESPERANDO_TIEMPO_LOTES
    
    async def iniciar_configuracion_pregunta(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Inicia la configuración de la pregunta actual"""
        user_id = update.effective_user.id
        estado = admin_estado.get(user_id, {})
        preguntas = estado.get('preguntas', [])
        idx = estado.get('respuesta_actual', 0)
        
        # Si ya terminó todas las preguntas, guardar
        if idx >= len(preguntas):
            return await guardar_preguntas_en_supabase(update, context)
        
        num_pregunta = idx + 1
        texto_pregunta = preguntas[idx]
        formato = estado.get('formatos', {}).get(num_pregunta, 1)
        
        tipo_nombre = {1: 'Múltiple', 2: 'Verdadero/Falso', 3: 'Abierta'}.get(formato, 'Múltiple')
        
        mensaje = f"**Pregunta {num_pregunta}**\n\n"
        mensaje += f"📝 {texto_pregunta}\n"
        mensaje += f"📌 Tipo: {tipo_nombre}\n\n"
        
        if formato == 1:  # Múltiple
            mensaje += "Escribe las opciones (separadas por ;):\n"
            mensaje += "Ejemplo: `Opción 1;Opción 2;Opción 3`"
            estado['esperando_respuesta_tipo'] = 'opciones'
        elif formato == 2:  # V/F
            mensaje += "¿Es Verdadero o Falso?\n"
            mensaje += "Escribe `V` o `F`:"
            estado['esperando_respuesta_tipo'] = 'vf'
        elif formato == 3:  # Abierta
            mensaje += "Escribe la respuesta esperada (o escribe 'manual' para calificar después):"
            estado['esperando_respuesta_tipo'] = 'abierta'
        
        await update.message.reply_text(mensaje, parse_mode='Markdown')
        return ESPERANDO_RESPUESTAS_PREGUNTA
    
    async def recibir_respuesta_pregunta(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Paso 6: Recibir respuesta de la pregunta actual"""
        texto = update.message.text.strip()
        user_id = update.effective_user.id
        estado = admin_estado.get(user_id, {})
        idx = estado.get('respuesta_actual', 0)
        num_pregunta = idx + 1
        formato = estado.get('formatos', {}).get(num_pregunta, 1)
        tipo_espera = estado.get('esperando_respuesta_tipo', '')
        
        # Si no hay tipo de espera, ir a la siguiente pregunta
        if not tipo_espera:
            estado['respuesta_actual'] = idx + 1
            return await iniciar_configuracion_pregunta(update, context)
        
        # Procesar según el tipo de espera
        if tipo_espera == 'opciones':
            opciones = [o.strip() for o in texto.split(';') if o.strip()]
            if len(opciones) < 2:
                await update.message.reply_text(
                    "❌ Debes escribir al menos 2 opciones separadas por ;\n"
                    "Intenta de nuevo:",
                    parse_mode='Markdown'
                )
                return ESPERANDO_RESPUESTAS_PREGUNTA
            
            estado['respuestas'][num_pregunta] = {'opciones': opciones}
            estado['esperando_respuesta_tipo'] = 'correctas'
            await update.message.reply_text(
                f"✅ Opciones guardadas: {len(opciones)}\n\n"
                "Ahora escribe los números de las opciones correctas (separados por coma, 0=ninguna):",
                parse_mode='Markdown'
            )
            return ESPERANDO_RESPUESTAS_PREGUNTA
        
        elif tipo_espera == 'correctas':
            try:
                indices = [int(i.strip()) for i in texto.split(',') if i.strip()]
                total_opciones = len(estado.get('respuestas', {}).get(num_pregunta, {}).get('opciones', []))
                indices_validos = [i for i in indices if 1 <= i <= total_opciones]
                estado['respuestas'][num_pregunta]['correctas'] = indices_validos
                estado['esperando_respuesta_tipo'] = ''
                estado['respuesta_actual'] = idx + 1
                return await iniciar_configuracion_pregunta(update, context)
            except:
                await update.message.reply_text(
                    "❌ Números inválidos. Escribe los números separados por coma (ej: 1,3):",
                    parse_mode='Markdown'
                )
                return ESPERANDO_RESPUESTAS_PREGUNTA
        
        elif tipo_espera == 'vf':
            if texto.lower() in ['v', 'verdadero']:
                estado['respuestas'][num_pregunta] = {'correctas': [0]}
                estado['esperando_respuesta_tipo'] = ''
                estado['respuesta_actual'] = idx + 1
                return await iniciar_configuracion_pregunta(update, context)
            elif texto.lower() in ['f', 'falso']:
                estado['respuestas'][num_pregunta] = {'correctas': [1]}
                estado['esperando_respuesta_tipo'] = ''
                estado['respuesta_actual'] = idx + 1
                return await iniciar_configuracion_pregunta(update, context)
            else:
                await update.message.reply_text(
                    "❌ Escribe 'V' para Verdadero o 'F' para Falso:",
                    parse_mode='Markdown'
                )
                return ESPERANDO_RESPUESTAS_PREGUNTA
        
        elif tipo_espera == 'abierta':
            if texto.lower() == 'manual':
                estado['respuestas'][num_pregunta] = {'manual': True}
            else:
                estado['respuestas'][num_pregunta] = {'respuesta_esperada': texto}
            estado['esperando_respuesta_tipo'] = ''
            estado['respuesta_actual'] = idx + 1
            return await iniciar_configuracion_pregunta(update, context)
        
        # Si llegamos aquí, algo salió mal
        estado['respuesta_actual'] = idx + 1
        return await iniciar_configuracion_pregunta(update, context)
    
    async def guardar_preguntas_en_supabase(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Guarda todas las preguntas en Supabase"""
        user_id = update.effective_user.id
        estado = admin_estado.get(user_id, {})
        
        admin = db.obtener_admin(user_id)
        if not admin:
            await update.message.reply_text("❌ No eres admin.", parse_mode='Markdown')
            return ConversationHandler.END
        
        preguntas = estado.get('preguntas', [])
        formatos = estado.get('formatos', {})
        tiempos = estado.get('tiempos', {})
        respuestas = estado.get('respuestas', {})
        
        if not preguntas:
            await update.message.reply_text("❌ No hay preguntas para guardar.", parse_mode='Markdown')
            return ConversationHandler.END
        
        # Preparar datos para guardar
        datos_guardar = []
        errores = 0
        
        for i, texto in enumerate(preguntas):
            num = i + 1
            formato = formatos.get(num, 1)
            tiempo = tiempos.get(num, config.TIEMPO_GLOBAL_DEFAULT)
            resp = respuestas.get(num, {})
            
            tipo_map = {1: 'multiple', 2: 'vf', 3: 'abierta'}
            tipo = tipo_map.get(formato, 'multiple')
            
            pregunta_data = {
                'texto': texto,
                'tipo': tipo,
                'tiempo_segundos': tiempo,
                'imagen_url': '',
                'video_url': '',
                'enlace_url': ''
            }
            
            if tipo == 'multiple':
                opciones = resp.get('opciones', [])
                correctas = resp.get('correctas', [])
                pregunta_data['opciones'] = opciones
                pregunta_data['respuestas_correctas'] = correctas
            
            elif tipo == 'vf':
                pregunta_data['opciones'] = ['Verdadero', 'Falso']
                correctas = resp.get('correctas', [0])
                pregunta_data['respuestas_correctas'] = correctas
            
            elif tipo == 'abierta':
                pregunta_data['opciones'] = []
                if resp.get('manual'):
                    pregunta_data['respuestas_correctas'] = []
                else:
                    pregunta_data['respuestas_correctas'] = [resp.get('respuesta_esperada', '')]
            
            datos_guardar.append(pregunta_data)
        
        # Guardar en Supabase
        exitosas, ids = db.crear_preguntas_masivas(admin['id'], datos_guardar)
        
        # Limpiar estado
        admin_estado.pop(user_id, None)
        context.user_data.clear()
        
        # Respuesta final
        if exitosas > 0:
            mensaje = f"✅ **¡{exitosas} preguntas guardadas en Supabase!**\n\n"
            mensaje += f"📝 Total de preguntas creadas: {exitosas}\n\n"
            mensaje += "Volviendo al menú principal..."
            await update.message.reply_text(mensaje, parse_mode='Markdown')
        else:
            await update.message.reply_text(
                "❌ Error al guardar las preguntas. Intenta de nuevo.",
                parse_mode='Markdown'
            )
        
        from src.bot import mostrar_panel_admin
        await mostrar_panel_admin(update, context)
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
            ESPERANDO_RESPUESTAS_PREGUNTA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_respuesta_pregunta)
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
        await update.message.reply_text(
            "📂 **Subir CSV**\n\n"
            "Esta función está en desarrollo.\n"
            "Por ahora, usa la creación manual.",
            parse_mode='Markdown'
        )
        return ConversationHandler.END
    
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

class AdminHandlers:
    def registrar_handlers(self, application):
        registrar_handlers(application)

admin_handlers = AdminHandlers()

# ============================================================
# FIN DE admin_handlers.py
# ============================================================