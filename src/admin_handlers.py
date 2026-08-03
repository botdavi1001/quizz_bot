# ============================================================
# BOT DE TELEGRAM - HANDLERS DEL ADMINISTRADOR
# ============================================================

import asyncio
import json
import random
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
    context.user_data.pop('conversation_state', None)  # <--- AGREGADO
    context.user_data.clear()
    
    await update.message.reply_text(
        "✅ Operación cancelada.",
        parse_mode='Markdown'
    )
    
    await enviar_panel_admin(update, context)
    return ConversationHandler.END


# ============================================================
# FUNCIONES DE CREACIÓN DE PREGUNTAS
# ============================================================

async def iniciar_crear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Paso 1: Preguntar cuántas preguntas"""
    context.user_data['conversation_state'] = True  # <--- AGREGADO
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
    
    if idx >= len(preguntas):
        return await guardar_preguntas_en_supabase(update, context)
    
    num_pregunta = idx + 1
    texto_pregunta = preguntas[idx]
    formato = estado.get('formatos', {}).get(num_pregunta, 1)
    
    tipo_nombre = {1: 'Múltiple', 2: 'Verdadero/Falso', 3: 'Abierta'}.get(formato, 'Múltiple')
    
    mensaje = f"**Pregunta {num_pregunta}**\n\n"
    mensaje += f"📝 {texto_pregunta}\n"
    mensaje += f"📌 Tipo: {tipo_nombre}\n\n"
    
    if formato == 1:
        mensaje += "Escribe las opciones (separadas por ;):\n"
        mensaje += "Ejemplo: `Opción 1;Opción 2;Opción 3`"
        estado['esperando_respuesta_tipo'] = 'opciones'
    elif formato == 2:
        mensaje += "¿Es Verdadero o Falso?\n"
        mensaje += "Escribe `V` o `F`:"
        estado['esperando_respuesta_tipo'] = 'vf'
    elif formato == 3:
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
    
    if not tipo_espera:
        estado['respuesta_actual'] = idx + 1
        return await iniciar_configuracion_pregunta(update, context)
    
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
    
    exitosas, ids = db.crear_preguntas_masivas(admin['id'], datos_guardar)
    
    admin_estado.pop(user_id, None)
    context.user_data.pop('conversation_state', None)
    context.user_data.clear()
    
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
    
    # Usar enviar_panel_admin en lugar de mostrar_panel_admin
    await enviar_panel_admin(update, context)
    return ConversationHandler.END

# ============================================================
# FUNCIONES DE HISTORIAL Y OTROS
# ============================================================

# ============================================================
# SUBIR CSV - COMPLETO
# ============================================================

async def iniciar_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia el proceso de subir un archivo CSV"""
    context.user_data['conversation_state'] = True  # <--- AGREGADO
    user_id = update.effective_user.id
    admin = db.obtener_admin(user_id)
    
    if not admin:
        await update.message.reply_text("❌ No eres admin.", parse_mode='Markdown')
        return ConversationHandler.END
    
    # Guardar el admin_id en el estado
    admin_estado[user_id] = {'admin_id': admin['id']}
    
    # Generar y enviar archivo de ejemplo
    from src.csv_processor import generar_csv_ejemplo
    
    ejemplo = generar_csv_ejemplo()
    
    await update.message.reply_document(
        document=ejemplo,
        filename="ejemplo.csv",
        caption="📂 **Subir CSV**\n\n"
                "Descarga este archivo de ejemplo, edítalo y súbelo.\n\n"
                "**Columnas:**\n"
                "• `pregunta`: El texto de la pregunta (obligatorio)\n"
                "• `tipo`: `multiple`, `vf` o `abierta` (obligatorio)\n"
                "• `opciones`: Separadas por `;` (ej: `La Habana;Santiago;Camagüey`)\n"
                "• `correctas`: Números separados por coma (ej: `1` o `1,3`), o `V`/`F` para VF\n"
                "• `tiempo`: Segundos (0 = sin límite)\n"
                "• `imagen_url`: URL de imagen (opcional)\n"
                "• `video_url`: URL de video (opcional)\n"
                "• `enlace`: URL adicional (opcional)\n\n"
                "Sube el archivo CSV cuando esté listo.",
        parse_mode='Markdown'
    )
    
    # Cambiar el estado para esperar el archivo
    admin_estado[user_id]['esperando_csv'] = True
    return ESPERANDO_CSV


async def recibir_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe y procesa el archivo CSV"""
    user_id = update.effective_user.id
    estado = admin_estado.get(user_id, {})
    
    if not estado.get('esperando_csv'):
        return
    
    # Verificar que sea un documento
    if not update.message.document:
        await update.message.reply_text(
            "❌ Por favor, sube un archivo CSV (no un mensaje de texto).",
            parse_mode='Markdown'
        )
        return ESPERANDO_CSV
    
    # Verificar que sea un archivo CSV
    documento = update.message.document
    nombre_archivo = documento.file_name or ""
    
    if not nombre_archivo.lower().endswith('.csv'):
        await update.message.reply_text(
            "❌ El archivo debe tener extensión `.csv`.\n"
            "Por favor, sube un archivo CSV válido.",
            parse_mode='Markdown'
        )
        return ESPERANDO_CSV
    
    # Descargar el archivo
    try:
        archivo = await documento.get_file()
        contenido = await archivo.download_as_bytearray()
        
        # Procesar el CSV
        from src.csv_processor import procesar_csv, formatear_resultado_csv
        
        admin_id = estado.get('admin_id')
        exitosas, fallidas, errores = procesar_csv(bytes(contenido), admin_id)
        
        # Mostrar resultado
        mensaje = formatear_resultado_csv(exitosas, fallidas, errores)
        await update.message.reply_text(mensaje, parse_mode='Markdown')
        
        # Limpiar estado
        admin_estado.pop(user_id, None)
        
        # Volver al menú
        await enviar_panel_admin(update, context)
        return ConversationHandler.END
        
    except Exception as e:
        log_error(f"Error procesando CSV: {str(e)}")
        await update.message.reply_text(
            f"❌ Error al procesar el archivo: {str(e)[:200]}\n\n"
            "Verifica que el archivo tenga el formato correcto.",
            parse_mode='Markdown'
        )
        return ESPERANDO_CSV

# ============================================================
# HISTORIAL
# ============================================================

async def mostrar_historial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el menú de historial para el admin"""
    user_id = update.effective_user.id
    
    try:
        log_info(f"📊 Historial: Iniciando para usuario {user_id}")
        
        admin = db.obtener_admin(user_id)
        
        if not admin:
            await update.message.reply_text("❌ No eres admin.", parse_mode='Markdown')
            return
        
        log_info(f"📊 Historial: Admin encontrado: {admin.get('id')}")
        
        from src.historial_manager import (
            verificar_limite_historial,
            verificar_almacenamiento
        )
        
        supera, total, mensaje_limite = verificar_limite_historial()
        _, porcentaje, mensaje_almacenamiento = verificar_almacenamiento()
        
        log_info(f"📊 Historial: Límites verificados - Total: {total}")
        
        keyboard = [
            [InlineKeyboardButton("📈 Resumen general", callback_data="admin_hist_resumido")],
            [InlineKeyboardButton("📋 Detallado", callback_data="admin_hist_detallado")],
            [InlineKeyboardButton("👤 Por usuario", callback_data="admin_hist_usuario")],
            [InlineKeyboardButton("📅 Por fecha", callback_data="admin_hist_fecha")],
            [InlineKeyboardButton("🏆 Estadísticas", callback_data="admin_hist_estadisticas")],
            [InlineKeyboardButton("🗑️ Limpiar historial", callback_data="admin_hist_limpiar")],
            [InlineKeyboardButton("❌ Cerrar", callback_data="admin_hist_cerrar")]
        ]
        
        mensaje = f"📊 **Historial**\n\n"
        mensaje += f"{mensaje_limite}\n"
        mensaje += f"{mensaje_almacenamiento}\n\n"
        mensaje += "Selecciona el tipo de reporte:"
        
        await update.message.reply_text(
            mensaje,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        log_info(f"📊 Historial: Menú mostrado correctamente")
        
    except Exception as e:
        log_error(f"❌ Error en mostrar_historial: {str(e)}")
        import traceback
        log_error(f"❌ Traceback: {traceback.format_exc()}")
        
        await update.message.reply_text(
            f"❌ Error al cargar historial: {str(e)[:100]}\n\n"
            "Revisa los logs de Render para más detalles.",
            parse_mode='Markdown'
        )


async def manejar_callback_historial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los callbacks del historial"""
    query = update.callback_query
    await query.answer()
    data = query.data
    
    user_id = update.effective_user.id
    
    try:
        log_info(f"📊 Callback historial: {data} - Usuario {user_id}")
        
        admin = db.obtener_admin(user_id)
        
        if not admin:
            await query.edit_message_text("❌ No eres admin.", parse_mode='Markdown')
            return
        
        from src.historial_manager import obtener_historial_para_reporte
        
        tipo = data.replace('admin_hist_', '')
        log_info(f"📊 Generando reporte tipo: {tipo}")
        
        if tipo == 'cerrar':
            await query.edit_message_text("✅ Historial cerrado.")
            await enviar_panel_admin(update, context)
            return
        
        if tipo == 'limpiar':
            await query.edit_message_text(
                "🗑️ **Limpiar historial**\n\n"
                "Escribe el número de días a mantener (ej: 30 para mantener 30 días):\n"
                "O escribe 'todo' para eliminar todo.",
                parse_mode='Markdown'
            )
            admin_estado[user_id] = {'modo': 'limpiar_historial'}
            return
        
        log_info(f"📊 Llamando a obtener_historial_para_reporte con admin_id: {admin['id']}, tipo: {tipo}")
        _, mensaje = obtener_historial_para_reporte(admin['id'], tipo)
        log_info(f"📊 Reporte generado, longitud: {len(mensaje)}")
        
        if not mensaje or mensaje == "📊 No hay datos en el historial.":
            await query.edit_message_text(
                "📊 **Sin datos**\n\n"
                "No hay sesiones registradas en el historial.",
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text(mensaje, parse_mode='Markdown')
        
    except Exception as e:
        log_error(f"❌ Error en manejar_callback_historial: {str(e)}")
        import traceback
        log_error(f"❌ Traceback: {traceback.format_exc()}")
        
        await query.edit_message_text(
            f"❌ Error al generar reporte: {str(e)[:100]}\n\n"
            "Revisa los logs de Render para más detalles.",
            parse_mode='Markdown'
        )


async def recibir_limpieza_historial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe la confirmación para limpiar historial"""
    texto = update.message.text.strip()
    user_id = update.effective_user.id
    estado = admin_estado.get(user_id, {})
    
    if estado.get('modo') != 'limpiar_historial':
        return
    
    from src.historial_manager import limpiar_historial_por_dias
    
    if texto.lower() == 'todo':
        eliminados = limpiar_historial_por_dias(30)
        await update.message.reply_text(
            f"🗑️ Se eliminaron {eliminados} registros antiguos (más de 30 días).",
            parse_mode='Markdown'
        )
    else:
        try:
            dias = int(texto)
            if dias < 1:
                await update.message.reply_text(
                    "❌ El número de días debe ser mayor a 0.",
                    parse_mode='Markdown'
                )
                return
            eliminados = limpiar_historial_por_dias(dias)
            await update.message.reply_text(
                f"🗑️ Se eliminaron {eliminados} registros con más de {dias} días de antigüedad.",
                parse_mode='Markdown'
            )
        except ValueError:
            await update.message.reply_text(
                "❌ Escribe un número válido o 'todo'.",
                parse_mode='Markdown'
            )
            return
    
    admin_estado.pop(user_id, None)
    await mostrar_historial(update, context)


# ============================================================
# CONFIGURACIÓN - EN DESARROLLO
# ============================================================

async def mostrar_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra la configuración"""
    await update.message.reply_text(
        "⚙️ **Configuración**\n\n"
        "Esta función está en desarrollo.",
        parse_mode='Markdown'
    )


# ============================================================
# LANZAR CUESTIONARIO
# ============================================================

async def iniciar_lanzar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Paso 1: Iniciar lanzamiento del cuestionario"""
    context.user_data['conversation_state'] = True  # <--- AGREGADO
    user_id = update.effective_user.id
    
    admin = db.obtener_admin(user_id)
    if not admin:
        await update.message.reply_text("❌ No eres admin.", parse_mode='Markdown')
        return ConversationHandler.END
    
    total_preguntas = db.contar_preguntas(admin['id'])
    if total_preguntas == 0:
        await update.message.reply_text(
            "❌ No hay preguntas disponibles.\n"
            "Crea preguntas primero.",
            parse_mode='Markdown'
        )
        return ConversationHandler.END
    
    admin_estado[user_id] = {
        'admin_id': admin['id'],
        'total_preguntas': total_preguntas
    }
    
    await update.message.reply_text(
        "🚀 **Lanzar cuestionario**\n\n"
        f"📝 Tienes {total_preguntas} preguntas disponibles.\n\n"
        "Escribe el **nombre del cuestionario**:",
        parse_mode='Markdown'
    )
    return ESPERANDO_LANZAR_NOMBRE


async def recibir_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Paso 2: Recibir nombre del cuestionario"""
    nombre = update.message.text.strip()
    if not nombre:
        await update.message.reply_text(
            "❌ El nombre no puede estar vacío.\n"
            "Escribe el nombre del cuestionario:",
            parse_mode='Markdown'
        )
        return ESPERANDO_LANZAR_NOMBRE
    
    user_id = update.effective_user.id
    admin_estado[user_id]['nombre'] = nombre
    
    total_preguntas = admin_estado[user_id].get('total_preguntas', 0)
    max_preguntas = min(total_preguntas, config.MAX_PREGUNTAS_MOSTRAR)
    
    await update.message.reply_text(
        f"✅ Nombre: **{nombre}**\n\n"
        f"📊 ¿Cuántas preguntas quieres mostrar? (máximo {max_preguntas})",
        parse_mode='Markdown'
    )
    return ESPERANDO_LANZAR_CANTIDAD


async def recibir_cantidad_lanzar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Paso 3: Recibir cantidad de preguntas"""
    try:
        cantidad = int(update.message.text.strip())
        total_preguntas = admin_estado[update.effective_user.id].get('total_preguntas', 0)
        max_preguntas = min(total_preguntas, config.MAX_PREGUNTAS_MOSTRAR)
        
        if cantidad < 1:
            await update.message.reply_text(
                "❌ Debes mostrar al menos 1 pregunta.\n"
                f"Escribe un número entre 1 y {max_preguntas}:",
                parse_mode='Markdown'
            )
            return ESPERANDO_LANZAR_CANTIDAD
        
        if cantidad > max_preguntas:
            await update.message.reply_text(
                f"❌ Solo tienes {total_preguntas} preguntas disponibles.\n"
                f"Escribe un número entre 1 y {max_preguntas}:",
                parse_mode='Markdown'
            )
            return ESPERANDO_LANZAR_CANTIDAD
        
        user_id = update.effective_user.id
        admin_estado[user_id]['cantidad'] = cantidad
        
        keyboard = [
            [InlineKeyboardButton("📌 Fijas", callback_data="lanzar_fijas")],
            [InlineKeyboardButton("🎲 Al azar", callback_data="lanzar_azar")],
            [InlineKeyboardButton("🔍 Filtrar por tipo", callback_data="lanzar_filtro")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="lanzar_cancelar")]
        ]
        
        await update.message.reply_text(
            f"✅ Cantidad: {cantidad} preguntas\n\n"
            "**¿Cómo quieres seleccionar las preguntas?**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return ESPERANDO_LANZAR_SELECCION
        
    except ValueError:
        await update.message.reply_text(
            "❌ Escribe un número válido.",
            parse_mode='Markdown'
        )
        return ESPERANDO_LANZAR_CANTIDAD


async def manejar_seleccion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Paso 4: Manejar la selección de preguntas"""
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    
    if data == 'lanzar_cancelar':
        admin_estado.pop(user_id, None)
        await query.edit_message_text("✅ Lanzamiento cancelado.")
        await enviar_panel_admin(update, context)
        return ConversationHandler.END
    
    admin_estado[user_id]['seleccion_tipo'] = data.replace('lanzar_', '')
    
    if data == 'lanzar_fijas':
        admin = db.obtener_admin(user_id)
        preguntas = db.obtener_preguntas(admin['id'])
        admin_estado[user_id]['preguntas_lista'] = preguntas
        
        mensaje = "📌 **Seleccionar preguntas fijas**\n\n"
        mensaje += "Escribe los números de las preguntas que quieres incluir.\n\n"
        mensaje += "**Ejemplos:**\n"
        mensaje += "• `1,3,5,7` (preguntas individuales)\n"
        mensaje += "• `1-10` (rango)\n"
        mensaje += "• `1-5,10,15-20` (combinación)\n\n"
        mensaje += "**Lista de preguntas disponibles:**\n"
        
        for i, p in enumerate(preguntas[:20], 1):
            texto = p.get('texto', '')[:50]
            mensaje += f"{i}. {texto}...\n"
        
        if len(preguntas) > 20:
            mensaje += f"\n... y {len(preguntas) - 20} más."
        
        await query.edit_message_text(mensaje, parse_mode='Markdown')
        return ESPERANDO_LANZAR_FIJAS
    
    elif data == 'lanzar_azar':
        admin_estado[user_id]['seleccion_detalle'] = 'azar'
        await query.edit_message_text(
            "✅ Selección al azar.\n\n"
            "Ahora configura el **tiempo global** para cada pregunta (en segundos).\n"
            "Escribe `0` para usar el tiempo individual de cada pregunta.",
            parse_mode='Markdown'
        )
        return ESPERANDO_LANZAR_TIEMPO
    
    elif data == 'lanzar_filtro':
        await query.edit_message_text(
            "🔍 **Filtrar por tipo**\n\n"
            "Escribe la cantidad por tipo en este formato:\n"
            "`30:multiple, 20:vf, 50:abierta`\n\n"
            "Ejemplo: `10:multiple, 5:vf, 5:abierta`\n"
            "(total = cantidad de preguntas a mostrar)",
            parse_mode='Markdown'
        )
        return ESPERANDO_LANZAR_FILTRO


async def recibir_fijas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Paso 5a: Recibir selección de preguntas fijas"""
    texto = update.message.text.strip()
    user_id = update.effective_user.id
    estado = admin_estado.get(user_id, {})
    preguntas_lista = estado.get('preguntas_lista', [])
    cantidad = estado.get('cantidad', 0)
    
    try:
        seleccionados = set()
        partes = texto.split(',')
        
        for parte in partes:
            parte = parte.strip()
            if '-' in parte:
                inicio, fin = parte.split('-')
                for i in range(int(inicio), int(fin) + 1):
                    if 1 <= i <= len(preguntas_lista):
                        seleccionados.add(i - 1)
            else:
                num = int(parte)
                if 1 <= num <= len(preguntas_lista):
                    seleccionados.add(num - 1)
        
        if len(seleccionados) == 0:
            await update.message.reply_text(
                "❌ No seleccionaste ninguna pregunta válida.\n"
                "Intenta de nuevo:",
                parse_mode='Markdown'
            )
            return ESPERANDO_LANZAR_FIJAS
        
        if len(seleccionados) != cantidad:
            await update.message.reply_text(
                f"⚠️ Seleccionaste {len(seleccionados)} preguntas, pero dijiste que serían {cantidad}.\n"
                f"¿Quieres continuar con {len(seleccionados)} preguntas? (responde 'si' o 'no')",
                parse_mode='Markdown'
            )
            estado['seleccion_temp'] = list(seleccionados)
            estado['esperando_confirmacion_seleccion'] = True
            return ESPERANDO_LANZAR_FIJAS
        
        ids_seleccionados = [preguntas_lista[i]['id'] for i in seleccionados]
        estado['preguntas_ids'] = ids_seleccionados
        estado['seleccion_detalle'] = 'fijas'
        
        await update.message.reply_text(
            f"✅ {len(ids_seleccionados)} preguntas seleccionadas.\n\n"
            "Ahora configura el **tiempo global** para cada pregunta (en segundos).\n"
            "Escribe `0` para usar el tiempo individual de cada pregunta.",
            parse_mode='Markdown'
        )
        return ESPERANDO_LANZAR_TIEMPO
        
    except Exception as e:
        await update.message.reply_text(
            f"❌ Error: {str(e)}\nIntenta de nuevo:",
            parse_mode='Markdown'
        )
        return ESPERANDO_LANZAR_FIJAS


async def recibir_filtro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Paso 5b: Recibir filtro por tipo"""
    texto = update.message.text.strip()
    user_id = update.effective_user.id
    estado = admin_estado.get(user_id, {})
    cantidad = estado.get('cantidad', 0)
    
    try:
        filtros = {}
        total_filtro = 0
        partes = texto.split(',')
        
        for parte in partes:
            parte = parte.strip()
            if ':' in parte:
                num, tipo = parte.split(':')
                num = int(num.strip())
                tipo = tipo.strip().lower()
                if tipo in ['multiple', 'vf', 'abierta']:
                    filtros[tipo] = num
                    total_filtro += num
        
        if not filtros:
            await update.message.reply_text(
                "❌ Formato inválido. Usa el formato: `30:multiple, 20:vf, 50:abierta`\n"
                "Intenta de nuevo:",
                parse_mode='Markdown'
            )
            return ESPERANDO_LANZAR_FILTRO
        
        if total_filtro != cantidad:
            await update.message.reply_text(
                f"⚠️ La suma de los filtros es {total_filtro}, pero dijiste que serían {cantidad}.\n"
                f"¿Quieres continuar con {total_filtro} preguntas? (responde 'si' o 'no')",
                parse_mode='Markdown'
            )
            estado['filtro_temp'] = filtros
            estado['esperando_confirmacion_filtro'] = True
            return ESPERANDO_LANZAR_FILTRO
        
        estado['filtros'] = filtros
        estado['seleccion_detalle'] = filtros
        
        await update.message.reply_text(
            f"✅ Filtros guardados:\n"
            f"• Múltiple: {filtros.get('multiple', 0)}\n"
            f"• V/F: {filtros.get('vf', 0)}\n"
            f"• Abierta: {filtros.get('abierta', 0)}\n\n"
            "Ahora configura el **tiempo global** para cada pregunta (en segundos).\n"
            "Escribe `0` para usar el tiempo individual de cada pregunta.",
            parse_mode='Markdown'
        )
        return ESPERANDO_LANZAR_TIEMPO
        
    except Exception as e:
        await update.message.reply_text(
            f"❌ Error: {str(e)}\nIntenta de nuevo:",
            parse_mode='Markdown'
        )
        return ESPERANDO_LANZAR_FILTRO


async def recibir_tiempo_lanzar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Paso 6: Recibir tiempo global"""
    try:
        tiempo = int(update.message.text.strip())
        if tiempo < 0:
            await update.message.reply_text(
                "❌ El tiempo no puede ser negativo.\n"
                "Escribe `0` para usar tiempos individuales o un número positivo:",
                parse_mode='Markdown'
            )
            return ESPERANDO_LANZAR_TIEMPO
        
        user_id = update.effective_user.id
        admin_estado[user_id]['tiempo_global'] = tiempo
        
        await update.message.reply_text(
            f"✅ Tiempo global: {'Sin límite' if tiempo == 0 else f'{tiempo} segundos'}\n\n"
            "**Último paso:**\n"
            "¿Cuántos **reintentos** quieres permitir por usuario?\n"
            "Escribe un número (0 = sin límite):",
            parse_mode='Markdown'
        )
        return ESPERANDO_LANZAR_REINTENTOS
        
    except ValueError:
        await update.message.reply_text(
            "❌ Escribe un número válido.",
            parse_mode='Markdown'
        )
        return ESPERANDO_LANZAR_TIEMPO


async def recibir_reintentos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Paso 7: Recibir reintentos"""
    try:
        reintentos = int(update.message.text.strip())
        if reintentos < 0:
            await update.message.reply_text(
                "❌ El número de reintentos no puede ser negativo.\n"
                "Escribe un número (0 = sin límite):",
                parse_mode='Markdown'
            )
            return ESPERANDO_LANZAR_REINTENTOS
        
        user_id = update.effective_user.id
        estado = admin_estado[user_id]
        estado['reintentos'] = reintentos
        
        mensaje = "📋 **Resumen del cuestionario**\n\n"
        mensaje += f"📌 Nombre: {estado.get('nombre', 'Sin nombre')}\n"
        mensaje += f"📊 Preguntas: {estado.get('cantidad', 0)}\n"
        mensaje += f"🎲 Selección: {estado.get('seleccion_tipo', 'N/A')}\n"
        mensaje += f"⏱️ Tiempo global: {'Sin límite' if estado.get('tiempo_global', 0) == 0 else f'{estado.get('tiempo_global', 0)}s'}\n"
        mensaje += f"🔄 Reintentos: {'Sin límite' if reintentos == 0 else reintentos}\n\n"
        mensaje += "¿Guardar y lanzar el cuestionario?"
        
        keyboard = [
            [InlineKeyboardButton("✅ Sí, lanzar", callback_data="lanzar_confirmar")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="lanzar_cancelar_final")]
        ]
        
        await update.message.reply_text(
            mensaje,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return ESPERANDO_LANZAR_CONFIRMAR
        
    except ValueError:
        await update.message.reply_text(
            "❌ Escribe un número válido.",
            parse_mode='Markdown'
        )
        return ESPERANDO_LANZAR_REINTENTOS


async def confirmar_lanzar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Paso 8: Confirmar y guardar el cuestionario"""
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    if data == 'lanzar_cancelar_final':
        admin_estado.pop(user_id, None)
        context.user_data.pop('conversation_state', None)
        await query.edit_message_text("✅ Lanzamiento cancelado.")
        # Enviar panel manualmente
        await enviar_panel_admin(update, context)
        return ConversationHandler.END

    if data == 'lanzar_confirmar':
        try:
            estado = admin_estado.get(user_id, {})
            admin = db.obtener_admin(user_id)

            if not admin:
                await query.edit_message_text("❌ No eres admin.")
                return ConversationHandler.END

            preguntas_ids = estado.get('preguntas_ids', [])
            seleccion_tipo = estado.get('seleccion_tipo', 'azar')

            if not preguntas_ids:
                todas_preguntas = db.obtener_preguntas(admin['id'])
                cantidad = estado.get('cantidad', 0)

                if seleccion_tipo == 'azar':
                    seleccionadas = random.sample(todas_preguntas, min(cantidad, len(todas_preguntas)))
                    preguntas_ids = [p['id'] for p in seleccionadas]

                elif seleccion_tipo == 'filtro':
                    filtros = estado.get('filtros', {})
                    seleccionadas = []

                    for tipo, cantidad_tipo in filtros.items():
                        disponibles = [p for p in todas_preguntas if p.get('tipo') == tipo]
                        if disponibles:
                            elegidas = random.sample(disponibles, min(cantidad_tipo, len(disponibles)))
                            seleccionadas.extend(elegidas)

                    if len(seleccionadas) < cantidad:
                        restantes = [p for p in todas_preguntas if p not in seleccionadas]
                        faltantes = cantidad - len(seleccionadas)
                        if restantes:
                            seleccionadas.extend(random.sample(restantes, min(faltantes, len(restantes))))

                    preguntas_ids = [p['id'] for p in seleccionadas]

            cuestionario_id = db.crear_cuestionario(
                admin_id=admin['id'],
                nombre=estado.get('nombre', 'Sin nombre'),
                preguntas_ids=preguntas_ids,
                seleccion_tipo=seleccion_tipo,
                reintentos=estado.get('reintentos', config.REINTENTOS_DEFAULT)
            )

            # Limpiar estado
            admin_estado.pop(user_id, None)
            context.user_data.pop('conversation_state', None)

            if cuestionario_id:
                mensaje = f"✅ **¡Cuestionario lanzado exitosamente!**\n\n"
                mensaje += f"📌 Nombre: {estado.get('nombre')}\n"
                mensaje += f"📊 Preguntas: {len(preguntas_ids)}\n"
                mensaje += f"🔄 Reintentos: {estado.get('reintentos', 0)}\n\n"
                mensaje += "Los usuarios ya pueden responder desde el panel de usuario."

                await query.edit_message_text(mensaje, parse_mode='Markdown')

                # Enviar panel manualmente (sin llamar a mostrar_panel_admin)
                await enviar_panel_admin(update, context)

            else:
                await query.edit_message_text(
                    "❌ Error al guardar el cuestionario. Intenta de nuevo.",
                    parse_mode='Markdown'
                )
                await enviar_panel_admin(update, context)

        except Exception as e:
            log_error(f"❌ Error en confirmar_lanzar: {str(e)}")
            import traceback
            log_error(traceback.format_exc())
            await query.edit_message_text(
                f"❌ Error al lanzar el cuestionario: {str(e)[:100]}",
                parse_mode='Markdown'
            )
            admin_estado.pop(user_id, None)
            context.user_data.pop('conversation_state', None)
            await enviar_panel_admin(update, context)

        return ConversationHandler.END

# Nueva función auxiliar para enviar el panel de admin sin usar mostrar_panel_admin
async def enviar_panel_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envía el panel de administrador manualmente"""
    user_id = update.effective_user.id
    admin = db.obtener_admin(user_id)
    total_preguntas = db.contar_preguntas(admin['id']) if admin else 0
    cuestionario = db.obtener_cuestionario_activo()
    cuestionario_nombre = cuestionario.get('nombre', 'Sin nombre') if cuestionario else 'Ninguno activo'

    keyboard = [
        [config.BOTON_ADMIN['crear'], config.BOTON_ADMIN['csv']],
        [config.BOTON_ADMIN['historial'], config.BOTON_ADMIN['configurar']],
        [config.BOTON_ADMIN['lanzar'], config.BOTON_ADMIN['gestionar']],
        [config.BOTON_ADMIN['respaldos']]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    mensaje = f"👑 **Panel de Administrador**\n\n"
    mensaje += f"📝 Total de preguntas: {total_preguntas}\n"
    mensaje += f"🚀 Cuestionario activo: {cuestionario_nombre}\n"

    # Usar query.message para enviar si existe, o update.message
    if update.callback_query:
        await update.callback_query.message.reply_text(mensaje, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(mensaje, reply_markup=reply_markup, parse_mode='Markdown')
# ============================================================
# GESTIONAR - EN DESARROLLO
# ============================================================

async def mostrar_gestion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el panel de gestión"""
    await update.message.reply_text(
        "🗑️ **Gestión**\n\n"
        "Esta función está en desarrollo.",
        parse_mode='Markdown'
    )


# ============================================================
# RESPALDOS - EN DESARROLLO
# ============================================================

async def mostrar_respaldos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra los respaldos"""
    await update.message.reply_text(
        "📥 **Respaldos**\n\n"
        "Esta función está en desarrollo.",
        parse_mode='Markdown'
    )


# ============================================================
# REGISTRAR HANDLERS
# ============================================================

def registrar_handlers(application, group=1):
    """Registra todos los ConversationHandlers del admin con prioridad group"""
    
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
    
    # Crear el ConversationHandler para lanzar cuestionario
    lanzar_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(f'^{config.BOTON_ADMIN["lanzar"]}$'), iniciar_lanzar)
        ],
        states={
            ESPERANDO_LANZAR_NOMBRE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_nombre)
            ],
            ESPERANDO_LANZAR_CANTIDAD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_cantidad_lanzar)
            ],
            ESPERANDO_LANZAR_SELECCION: [
                CallbackQueryHandler(manejar_seleccion, pattern="^lanzar_")
            ],
            ESPERANDO_LANZAR_FIJAS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_fijas)
            ],
            ESPERANDO_LANZAR_FILTRO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_filtro)
            ],
            ESPERANDO_LANZAR_TIEMPO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_tiempo_lanzar)
            ],
            ESPERANDO_LANZAR_REINTENTOS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_reintentos)
            ],
            ESPERANDO_LANZAR_CONFIRMAR: [
                CallbackQueryHandler(confirmar_lanzar, pattern="^lanzar_confirmar$"),
                CallbackQueryHandler(confirmar_lanzar, pattern="^lanzar_cancelar_final$")
            ],
        },
        fallbacks=[
            CommandHandler("cancelar", cancelar_conversacion)
        ],
        allow_reentry=True,
        per_message=False,
    )
    
    # Agregar los ConversationHandlers
    application.add_handler(crear_conv, group=group)
    application.add_handler(lanzar_conv, group=group)
    
    # ============================================================
    # HANDLERS SIMPLES (sin conversación)
    # ============================================================
    
    # Subir CSV
    application.add_handler(
        MessageHandler(
            filters.Regex(f'^{config.BOTON_ADMIN["csv"]}$'), 
            iniciar_csv
        )
    )
    
    # Handler para recibir archivos CSV
    application.add_handler(
        MessageHandler(
            filters.Document.ALL, 
            recibir_csv
        )
    )
    
    # Historial
    application.add_handler(
        MessageHandler(
            filters.Regex(f'^{config.BOTON_ADMIN["historial"]}$'), 
            mostrar_historial
        )
    )
    
    # Configurar
    application.add_handler(
        MessageHandler(
            filters.Regex(f'^{config.BOTON_ADMIN["configurar"]}$'), 
            mostrar_config
        )
    )
    
    # Gestionar
    application.add_handler(
        MessageHandler(
            filters.Regex(f'^{config.BOTON_ADMIN["gestionar"]}$'), 
            mostrar_gestion
        )
    )
    
    # Respaldos
    application.add_handler(
        MessageHandler(
            filters.Regex(f'^{config.BOTON_ADMIN["respaldos"]}$'), 
            mostrar_respaldos
        )
    )
    
    # Handler para limpiar historial (recibir número de días)
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            recibir_limpieza_historial
        )
    )


# ============================================================
# EXPORTAR FUNCIONES (Clase AdminHandlers)
# ============================================================

class AdminHandlers:
    def registrar_handlers(self, application, group=1):
        registrar_handlers(application, group=group)

admin_handlers = AdminHandlers()

# ============================================================
# FIN DE admin_handlers.py
# ============================================================