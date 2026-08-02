# ============================================================
# BOT DE TELEGRAM - LÓGICA DE CUESTIONARIO
# Muestra preguntas, maneja tiempos, reinicios y estados
# ============================================================

import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from src import config
from src.database import db
from src.utils import (
    similitud_semantica, 
    normalizar_respuesta_abierta,
    log_info, 
    log_error
)
from src.backup_system import backup

# ============================================================
# CACHE DE PREGUNTAS
# ============================================================

preguntas_cache = {}
cache_timestamp = {}


def obtener_preguntas_cuestionario(cuestionario_id: str, admin_id: str) -> List[Dict]:
    """
    Obtiene las preguntas del cuestionario, usando caché si está disponible.
    """
    global preguntas_cache, cache_timestamp
    
    # Verificar caché (5 minutos de validez)
    if cuestionario_id in preguntas_cache:
        timestamp = cache_timestamp.get(cuestionario_id, 0)
        if (datetime.now().timestamp() - timestamp) < 300:  # 5 minutos
            return preguntas_cache[cuestionario_id]
    
    # Obtener cuestionario
    cuestionario = db.obtener_cuestionario(cuestionario_id)
    if not cuestionario:
        return []
    
    # Obtener IDs de preguntas
    preguntas_ids = cuestionario.get('preguntas_ids', [])
    if not preguntas_ids:
        return []
    
    # Obtener preguntas
    preguntas = db.obtener_preguntas_por_ids(preguntas_ids)
    
    # Guardar en caché
    preguntas_cache[cuestionario_id] = preguntas
    cache_timestamp[cuestionario_id] = datetime.now().timestamp()
    
    return preguntas


def limpiar_cache():
    """Limpia la caché de preguntas"""
    global preguntas_cache, cache_timestamp
    preguntas_cache = {}
    cache_timestamp = {}


# ============================================================
# SELECCIÓN DE PREGUNTAS
# ============================================================

def seleccionar_preguntas(preguntas: List[Dict], cantidad: int, tipo: str, 
                          admin_seleccion: Optional[str] = None) -> List[str]:
    """
    Selecciona preguntas según el tipo de selección.
    
    Args:
        preguntas: Lista de todas las preguntas disponibles
        cantidad: Número de preguntas a seleccionar
        tipo: 'fijas', 'azar', 'filtro'
        admin_seleccion: Para 'fijas', los IDs seleccionados por el admin
                         Para 'filtro', formato: "30:multiple,20:vf,50:abierta"
    
    Returns:
        Lista de IDs de preguntas seleccionadas
    """
    if not preguntas:
        return []
    
    # Limitar cantidad
    cantidad = min(cantidad, config.MAX_PREGUNTAS_MOSTRAR)
    cantidad = min(cantidad, len(preguntas))
    
    if tipo == 'fijas' and admin_seleccion:
        # El admin selecciona manualmente
        ids_seleccionados = []
        for p in preguntas:
            if p['id'] in admin_seleccion:
                ids_seleccionados.append(p['id'])
        return ids_seleccionados[:cantidad]
    
    elif tipo == 'filtro' and admin_seleccion:
        # Seleccionar por tipo (ej: "30:multiple,20:vf,50:abierta")
        try:
            filtros = {}
            for parte in admin_seleccion.split(','):
                if ':' in parte:
                    num, tipo_preg = parte.split(':')
                    filtros[tipo_preg.strip()] = int(num.strip())
            
            # Agrupar preguntas por tipo
            por_tipo = {}
            for p in preguntas:
                tipo_p = p.get('tipo', 'abierta')
                if tipo_p not in por_tipo:
                    por_tipo[tipo_p] = []
                por_tipo[tipo_p].append(p)
            
            seleccionados = []
            for tipo_p, cantidad_tipo in filtros.items():
                if tipo_p in por_tipo:
                    disponibles = por_tipo[tipo_p]
                    cantidad_tipo = min(cantidad_tipo, len(disponibles))
                    if cantidad_tipo > 0:
                        elegidos = random.sample(disponibles, cantidad_tipo)
                        seleccionados.extend([p['id'] for p in elegidos])
            
            # Si no hay suficientes, completar con aleatorias
            if len(seleccionados) < cantidad:
                restantes = [p['id'] for p in preguntas if p['id'] not in seleccionados]
                faltantes = cantidad - len(seleccionados)
                if restantes:
                    seleccionados.extend(random.sample(restantes, min(faltantes, len(restantes))))
            
            return seleccionados[:cantidad]
        except:
            # Si falla, usar azar
            return [p['id'] for p in random.sample(preguntas, min(cantidad, len(preguntas)))]
    
    else:  # 'azar' o default
        return [p['id'] for p in random.sample(preguntas, min(cantidad, len(preguntas)))]

# ============================================================
# MOSTRAR PREGUNTA
# ============================================================

async def mostrar_pregunta(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                           sesion: Dict, pregunta: Dict, pregunta_idx: int, 
                           total_preguntas: int, tiempo_global: int = None):
    """
    Muestra una pregunta al usuario con sus opciones y tiempo.
    """
    try:
        user_id = update.effective_user.id
        texto_pregunta = pregunta.get('texto', 'Pregunta sin texto')
        tipo = pregunta.get('tipo', 'abierta')
        tiempo = pregunta.get('tiempo_segundos', config.TIEMPO_GLOBAL_DEFAULT)
        
        # Usar tiempo global si está definido
        if tiempo_global is not None and tiempo_global > 0:
            tiempo = tiempo_global
        
        # Construir mensaje
        mensaje = f"**Pregunta {pregunta_idx + 1} de {total_preguntas}**\n\n"
        mensaje += f"{texto_pregunta}\n\n"
        
        if tiempo > 0:
            mensaje += f"⏱️ Tiempo: {tiempo} segundos\n"
        else:
            mensaje += f"⏱️ Sin límite de tiempo\n"
        
        # Construir botones según tipo
        if tipo == 'multiple':
            opciones = pregunta.get('opciones', [])
            if not opciones:
                await update.message.reply_text("❌ Error: La pregunta no tiene opciones")
                return
            
            keyboard = []
            for i, opcion in enumerate(opciones):
                keyboard.append([InlineKeyboardButton(opcion, callback_data=f"resp_{i}")])
            
            # Botón para cancelar
            keyboard.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancelar")])
            
            await update.message.reply_text(
                mensaje,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif tipo == 'vf':
            keyboard = [
                [
                    InlineKeyboardButton("✅ Verdadero", callback_data="resp_v"),
                    InlineKeyboardButton("❌ Falso", callback_data="resp_f")
                ],
                [InlineKeyboardButton("❌ Cancelar", callback_data="cancelar")]
            ]
            
            await update.message.reply_text(
                mensaje,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif tipo == 'abierta':
            keyboard = [
                [InlineKeyboardButton("📝 Escribir respuesta", callback_data="resp_abierta")],
                [InlineKeyboardButton("❌ Cancelar", callback_data="cancelar")]
            ]
            
            await update.message.reply_text(
                mensaje + "\n✏️ Escribe tu respuesta en el siguiente mensaje.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        # Guardar estado del tiempo en context
        if tiempo > 0:
            context.user_data['tiempo_restante'] = tiempo
            context.user_data['tiempo_inicio'] = datetime.now()
            context.user_data['pregunta_actual'] = pregunta_idx
            context.user_data['sesion_id'] = sesion.get('id')
            
            # Iniciar temporizador
            asyncio.create_task(manejar_tiempo(update, context, sesion['id'], tiempo, pregunta_idx))
    
    except Exception as e:
        log_error(f"Error mostrando pregunta: {str(e)}")
        await update.message.reply_text("❌ Error al mostrar la pregunta. Intenta de nuevo.")


async def manejar_tiempo(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                         sesion_id: str, tiempo: int, pregunta_idx: int):
    """
    Maneja el temporizador de una pregunta.
    """
    await asyncio.sleep(tiempo)
    
    # Verificar que la sesión siga activa
    sesion = db.obtener_sesion(sesion_id)
    if not sesion:
        return
    
    # Verificar que no haya sido completada o abandonada
    if sesion.get('completado') or sesion.get('abandonado'):
        return
    
    # Verificar que aún esté en la misma pregunta
    if sesion.get('pregunta_actual') != pregunta_idx:
        return
    
    # Marcar como tiempo agotado
    db.agotar_tiempo_sesion(sesion_id)
    
    # Notificar al usuario
    try:
        await update.message.reply_text(
            config.MENSAJE_TIEMPO_AGOTADO,
            parse_mode='Markdown'
        )
        
        # Guardar en historial
        pregunta = db.obtener_pregunta(sesion.get('preguntas_ids', [])[pregunta_idx] if pregunta_idx < len(sesion.get('preguntas_ids', [])) else None)
        if pregunta:
            db.guardar_respuesta_sesion(
                sesion_id,
                pregunta['id'],
                'TIEMPO_AGOTADO',
                False,
                tiempo
            )
        
        # Reiniciar desde 0
        await reiniciar_cuestionario(update, context, sesion_id)
        
    except Exception as e:
        log_error(f"Error en manejar_tiempo: {str(e)}")


async def reiniciar_cuestionario(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                 sesion_id: str):
    """
    Reinicia el cuestionario desde la pregunta 1.
    """
    try:
        # Obtener sesión
        sesion = db.obtener_sesion(sesion_id)
        if not sesion:
            return
        
        # Obtener cuestionario
        cuestionario = db.obtener_cuestionario(sesion.get('cuestionario_id'))
        if not cuestionario:
            return
        
        # Obtener preguntas
        preguntas = obtener_preguntas_cuestionario(cuestionario['id'], cuestionario['admin_id'])
        if not preguntas:
            return
        
        # Verificar reintentos
        intentos = sesion.get('intento_numero', 1)
        max_intentos = cuestionario.get('reintentos', config.REINTENTOS_DEFAULT)
        
        if intentos > max_intentos:
            await update.message.reply_text(
                config.MENSAJE_REINTENTOS_AGOTADOS,
                parse_mode='Markdown'
            )
            db.abandonar_sesion(sesion_id)
            return
        
        # Incrementar intento
        db.actualizar_sesion(sesion_id, {
            'pregunta_actual': 0,
            'intento_numero': intentos + 1,
            'respuestas': [],
            'tiempo_agotado': False
        })
        
        # Mostrar primera pregunta
        await mostrar_pregunta(
            update, 
            context, 
            sesion, 
            preguntas[0], 
            0, 
            len(preguntas)
        )
        
    except Exception as e:
        log_error(f"Error reiniciando cuestionario: {str(e)}")


async def continuar_cuestionario(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                 sesion_id: str, continuar: bool):
    """
    Continúa o reinicia un cuestionario según la decisión del usuario.
    """
    try:
        sesion = db.obtener_sesion(sesion_id)
        if not sesion:
            await update.message.reply_text("❌ Sesión no encontrada.")
            return
        
        if not continuar:
            # Abandonar sesión
            db.abandonar_sesion(sesion_id)
            await update.message.reply_text("✅ Sesión descartada. Puedes empezar uno nuevo.")
            return
        
        # Continuar desde donde estaba
        pregunta_actual = sesion.get('pregunta_actual', 0)
        
        # Obtener cuestionario
        cuestionario = db.obtener_cuestionario(sesion.get('cuestionario_id'))
        if not cuestionario:
            await update.message.reply_text("❌ Cuestionario no encontrado.")
            return
        
        # Obtener preguntas
        preguntas = obtener_preguntas_cuestionario(cuestionario['id'], cuestionario['admin_id'])
        if not preguntas:
            await update.message.reply_text("❌ No se encontraron preguntas.")
            return
        
        # Verificar si el cuestionario sigue activo
        if not cuestionario.get('activo', False):
            await update.message.reply_text(
                config.MENSAJE_CUESTIONARIO_INACTIVO,
                parse_mode='Markdown'
            )
            db.abandonar_sesion(sesion_id)
            return
        
        # Verificar que la pregunta exista
        if pregunta_actual >= len(preguntas):
            # Ya completó todas
            await completar_cuestionario(update, context, sesion_id)
            return
        
        # Mostrar pregunta
        await mostrar_pregunta(
            update,
            context,
            sesion,
            preguntas[pregunta_actual],
            pregunta_actual,
            len(preguntas)
        )
        
    except Exception as e:
        log_error(f"Error continuando cuestionario: {str(e)}")


async def completar_cuestionario(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                 sesion_id: str):
    """
    Completa un cuestionario y muestra los resultados.
    """
    try:
        # Marcar como completado
        db.completar_sesion(sesion_id)
        
        sesion = db.obtener_sesion(sesion_id)
        if not sesion:
            return
        
        # Obtener historial de respuestas
        historial = db.obtener_detalle_historial(sesion_id)
        
        # Contar aciertos
        correctas = sum(1 for h in historial if h.get('es_correcta') is True)
        total = len(historial)
        
        # Mensaje de resultado
        mensaje = "🎉 **¡Completaste el cuestionario!**\n\n"
        mensaje += f"📝 Respuestas: {total}\n"
        mensaje += f"✅ Correctas: {correctas}\n"
        mensaje += f"❌ Incorrectas: {total - correctas}\n"
        
        if total > 0:
            porcentaje = (correctas / total) * 100
            mensaje += f"📊 Porcentaje: {porcentaje:.1f}%\n\n"
        
        # Tiempo total
        if sesion.get('tiempo_inicio') and sesion.get('tiempo_fin'):
            try:
                inicio = datetime.fromisoformat(sesion['tiempo_inicio'].replace('Z', '+00:00'))
                fin = datetime.fromisoformat(sesion['tiempo_fin'].replace('Z', '+00:00'))
                tiempo_total = (fin - inicio).total_seconds()
                mensaje += f"⏱️ Tiempo total: {int(tiempo_total)} segundos\n"
            except:
                pass
        
        # Notificar al admin (si está configurado)
        admin_config = db.obtener_config_admin(sesion.get('admin_id'))
        if admin_config.get('notificar_admin', True):
            # Obtener admin
            admin = db.obtener_admin(sesion.get('admin_id'))
            if admin:
                try:
                    await update.get_bot().send_message(
                        chat_id=admin['telegram_id'],
                        text=f"📢 **Usuario completó cuestionario**\n\n"
                             f"👤 {sesion.get('first_name', 'Usuario')} (@{sesion.get('username', 'sin username')})\n"
                             f"✅ Aciertos: {correctas}/{total}\n"
                             f"📊 Porcentaje: {porcentaje:.1f}%\n"
                             f"⏱️ Tiempo: {int(tiempo_total)}s",
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    log_error(f"Error notificando admin: {str(e)}")
        
        # Verificar si mostrar correctas
        if admin_config.get('mostrar_correctas', True):
            keyboard = [
                [InlineKeyboardButton("📋 Ver respuestas correctas", callback_data="ver_correctas")]
            ]
            await update.message.reply_text(
                mensaje,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(mensaje, parse_mode='Markdown')
        
        # Limpiar datos del usuario
        context.user_data.clear()
        
    except Exception as e:
        log_error(f"Error completando cuestionario: {str(e)}")


async def mostrar_respuestas_correctas(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                      sesion_id: str):
    """
    Muestra las respuestas correctas de una sesión completada.
    """
    try:
        historial = db.obtener_detalle_historial(sesion_id)
        if not historial:
            await update.message.reply_text("❌ No se encontraron respuestas.")
            return
        
        mensaje = "📋 **Respuestas correctas**\n\n"
        
        for i, h in enumerate(historial, 1):
            texto = h.get('texto_pregunta', 'Pregunta sin texto')
            respuesta = h.get('respuesta_usuario', 'Sin respuesta')
            correcta = h.get('es_correcta')
            
            if correcta is True:
                icono = "✅"
            elif correcta is False:
                icono = "❌"
            else:
                icono = "⏳"  # Pendiente de calificación
            
            mensaje += f"**{i}. {texto}**\n"
            mensaje += f"Tu respuesta: {respuesta}\n"
            mensaje += f"Estado: {icono}\n\n"
        
        await update.message.reply_text(mensaje, parse_mode='Markdown')
        
    except Exception as e:
        log_error(f"Error mostrando respuestas correctas: {str(e)}")


# ============================================================
# FUNCIÓN PARA VERIFICAR RESPUESTA ABIERTA
# ============================================================

def verificar_respuesta_abierta(respuesta_usuario: str, pregunta: Dict, 
                                admin_config: Dict) -> Tuple[bool, bool]:
    """
    Verifica una respuesta abierta.
    Retorna: (es_correcta, es_manual)
    """
    es_manual = False
    
    # Si no tiene respuestas correctas definidas, es manual
    if not pregunta.get('respuestas_correctas'):
        es_manual = True
        return False, es_manual
    
    # Obtener respuesta esperada
    respuesta_esperada = pregunta.get('respuestas_correctas', [''])[0]
    if not respuesta_esperada:
        es_manual = True
        return False, es_manual
    
    # Obtener tolerancia
    tolerancia = admin_config.get('tolerancia_abiertas', config.TOLERANCIA_ABIERTAS)
    
    # Calcular similitud
    es_correcta, porcentaje = similitud_semantica(
        respuesta_usuario,
        respuesta_esperada,
        tolerancia
    )
    
    return es_correcta, False

# ============================================================
# FIN DE cuestionario.py
# ============================================================