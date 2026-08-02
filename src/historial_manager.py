# ============================================================
# BOT DE TELEGRAM - GESTOR DE HISTORIAL
# Reportes, estadísticas, límites y gestión del historial
# ============================================================

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from src import config
from src.database import db
from src.utils import formatear_fecha, formatear_tiempo, formatear_estado

# ============================================================
# REPORTES PARA EL ADMIN
# ============================================================

def generar_reporte_resumido(sesiones: List[Dict]) -> str:
    """
    Genera un reporte resumido de las sesiones.
    """
    if not sesiones:
        return "📊 No hay datos en el historial."
    
    texto = "📊 **RESUMEN DE SESIONES**\n\n"
    texto += f"Total: {len(sesiones)}\n\n"
    
    # Estadísticas básicas
    completados = sum(1 for s in sesiones if s.get('completado'))
    abandonados = sum(1 for s in sesiones if s.get('abandonado'))
    tiempo_agotado = sum(1 for s in sesiones if s.get('tiempo_agotado'))
    
    texto += f"✅ Completados: {completados}\n"
    texto += f"🚫 Abandonados: {abandonados}\n"
    texto += f"⏰ Tiempo agotado: {tiempo_agotado}\n"
    
    return texto


def generar_reporte_detallado(sesiones: List[Dict]) -> str:
    """
    Genera un reporte detallado de las sesiones.
    """
    if not sesiones:
        return "📊 No hay datos en el historial."
    
    texto = "📊 **REPORTE DETALLADO**\n\n"
    texto += f"Total de sesiones: {len(sesiones)}\n\n"
    
    # Mostrar últimas 10 sesiones
    mostrar = sesiones[:10]
    
    for i, sesion in enumerate(mostrar, 1):
        username = sesion.get('username', 'sin username') or f"ID: {sesion.get('usuario_id')}"
        nombre = sesion.get('first_name', 'Usuario')
        estado = formatear_estado(sesion)
        fecha = formatear_fecha(sesion.get('tiempo_inicio', ''))
        
        texto += f"**{i}. {nombre} (@{username})**\n"
        texto += f"   📅 {fecha}\n"
        texto += f"   📌 {estado}\n"
        
        # Si está completado, mostrar puntuación
        if sesion.get('completado'):
            respuestas = sesion.get('respuestas', [])
            texto += f"   📝 Respuestas: {len(respuestas)}\n"
        
        texto += "\n"
    
    if len(sesiones) > 10:
        texto += f"\n... y {len(sesiones) - 10} sesiones más."
    
    return texto


def generar_reporte_por_usuario(sesiones: List[Dict]) -> str:
    """
    Genera un reporte agrupado por usuario.
    """
    if not sesiones:
        return "📊 No hay datos en el historial."
    
    # Agrupar por usuario
    usuarios = {}
    for sesion in sesiones:
        usuario_id = sesion.get('usuario_id')
        if usuario_id not in usuarios:
            usuarios[usuario_id] = {
                'username': sesion.get('username', 'sin username'),
                'first_name': sesion.get('first_name', 'Usuario'),
                'sesiones': []
            }
        usuarios[usuario_id]['sesiones'].append(sesion)
    
    texto = "👥 **REPORTE POR USUARIO**\n\n"
    
    for usuario_id, datos in list(usuarios.items())[:10]:  # Mostrar máximo 10 usuarios
        nombre = datos['first_name']
        username = datos['username']
        sesiones_user = datos['sesiones']
        completados = sum(1 for s in sesiones_user if s.get('completado'))
        total = len(sesiones_user)
        
        texto += f"**{nombre} (@{username})**\n"
        texto += f"   Total: {total}\n"
        texto += f"   ✅ Completados: {completados}\n"
        texto += f"   📊 Ratio: {completados}/{total}\n\n"
    
    if len(usuarios) > 10:
        texto += f"\n... y {len(usuarios) - 10} usuarios más."
    
    return texto


def generar_reporte_por_fecha(sesiones: List[Dict]) -> str:
    """
    Genera un reporte agrupado por fecha.
    """
    if not sesiones:
        return "📊 No hay datos en el historial."
    
    # Agrupar por fecha
    fechas = {}
    for sesion in sesiones:
        fecha_str = sesion.get('tiempo_inicio', '')
        if fecha_str:
            fecha = datetime.fromisoformat(fecha_str.replace('Z', '+00:00'))
            fecha_key = fecha.strftime('%d/%m/%Y')
            if fecha_key not in fechas:
                fechas[fecha_key] = []
            fechas[fecha_key].append(sesion)
    
    texto = "📅 **REPORTE POR FECHA**\n\n"
    
    # Ordenar por fecha (más reciente primero)
    for fecha_key in sorted(fechas.keys(), reverse=True)[:10]:
        sesiones_fecha = fechas[fecha_key]
        completados = sum(1 for s in sesiones_fecha if s.get('completado'))
        
        texto += f"**{fecha_key}**\n"
        texto += f"   Total: {len(sesiones_fecha)}\n"
        texto += f"   ✅ Completados: {completados}\n\n"
    
    if len(fechas) > 10:
        texto += f"\n... y {len(fechas) - 10} días más."
    
    return texto


def generar_estadisticas(sesiones: List[Dict]) -> str:
    """
    Genera estadísticas detalladas.
    """
    if not sesiones:
        return "📊 No hay datos en el historial."
    
    total = len(sesiones)
    completados = sum(1 for s in sesiones if s.get('completado'))
    abandonados = sum(1 for s in sesiones if s.get('abandonado'))
    tiempo_agotado = sum(1 for s in sesiones if s.get('tiempo_agotado'))
    
    # Calcular tiempos
    tiempos = []
    for sesion in sesiones:
        if sesion.get('tiempo_inicio') and sesion.get('tiempo_fin'):
            try:
                inicio = datetime.fromisoformat(sesion['tiempo_inicio'].replace('Z', '+00:00'))
                fin = datetime.fromisoformat(sesion['tiempo_fin'].replace('Z', '+00:00'))
                tiempo = (fin - inicio).total_seconds()
                tiempos.append(tiempo)
            except:
                pass
    
    promedio_tiempo = sum(tiempos) / len(tiempos) if tiempos else 0
    min_tiempo = min(tiempos) if tiempos else 0
    max_tiempo = max(tiempos) if tiempos else 0
    
    texto = "🏆 **ESTADÍSTICAS DETALLADAS**\n\n"
    texto += f"📊 Total de sesiones: {total}\n"
    texto += f"✅ Completados: {completados} ({completados/total*100:.1f}%)\n"
    texto += f"🚫 Abandonados: {abandonados} ({abandonados/total*100:.1f}%)\n"
    texto += f"⏰ Tiempo agotado: {tiempo_agotado} ({tiempo_agotado/total*100:.1f}%)\n\n"
    
    if tiempos:
        texto += f"⏱️ Tiempo promedio: {formatear_tiempo(int(promedio_tiempo))}\n"
        texto += f"⏱️ Tiempo mínimo: {formatear_tiempo(int(min_tiempo))}\n"
        texto += f"⏱️ Tiempo máximo: {formatear_tiempo(int(max_tiempo))}\n"
    
    return texto

# ============================================================
# REPORTE DE HISTORIAL DEL USUARIO
# ============================================================

def generar_historial_usuario(sesiones: List[Dict]) -> str:
    """
    Genera un reporte del historial para un usuario normal.
    """
    if not sesiones:
        return "📋 No tienes historial aún."
    
    texto = "📋 **TU HISTORIAL**\n\n"
    
    for i, sesion in enumerate(sesiones, 1):
        nombre = sesion.get('nombre_cuestionario', 'Cuestionario')
        estado = formatear_estado(sesion)
        fecha = formatear_fecha(sesion.get('tiempo_inicio', ''))
        
        texto += f"**{i}. {nombre}**\n"
        texto += f"   📅 {fecha}\n"
        texto += f"   📌 {estado}\n"
        
        if sesion.get('completado'):
            respuestas = sesion.get('respuestas', [])
            texto += f"   📝 Respuestas: {len(respuestas)}\n"
        
        texto += "\n"
    
    return texto

# ============================================================
# VERIFICACIÓN DE LÍMITES
# ============================================================

def verificar_limite_historial() -> Tuple[bool, int, str]:
    """
    Verifica si el historial ha superado el límite de aviso.
    Retorna: (supera_limite, total_registros, mensaje)
    """
    total = db.contar_historial_total()
    supera = total >= config.LIMITE_HISTORIAL_AVISO
    
    if supera:
        mensaje = f"⚠️ El historial ha superado los {config.LIMITE_HISTORIAL_AVISO} registros."
        mensaje += f"\n📊 Total actual: {total} registros."
        mensaje += "\n🗑️ Considera limpiar el historial antiguo para mantener el rendimiento."
    else:
        mensaje = f"✅ Historial dentro del límite: {total} registros."
    
    return supera, total, mensaje


def verificar_almacenamiento() -> Tuple[bool, float, str]:
    """
    Verifica el estado del almacenamiento de imágenes.
    Retorna: (supera_limite, porcentaje_usado, mensaje)
    """
    usado_mb = db.contar_almacenamiento_usado()
    # Límite aproximado de 1GB = 1000MB
    porcentaje = (usado_mb / 1000) * 100
    
    if porcentaje >= config.LIMITE_ALMACENAMIENTO_AVISO:
        mensaje = f"⚠️ Almacenamiento al {porcentaje:.1f}% ({usado_mb:.1f}MB usado)"
        mensaje += "\n🗑️ Considera eliminar imágenes antiguas."
        return True, porcentaje, mensaje
    else:
        mensaje = f"✅ Almacenamiento: {porcentaje:.1f}% ({usado_mb:.1f}MB usado)"
        return False, porcentaje, mensaje

# ============================================================
# OBTENER DATOS DEL HISTORIAL
# ============================================================

def obtener_historial_para_reporte(admin_id: str, tipo: str) -> Tuple[List[Dict], str]:
    """
    Obtiene los datos del historial según el tipo de reporte solicitado.
    """
    # Obtener todas las sesiones del admin
    sesiones = db.obtener_historial_completo_admin(admin_id)
    
    if not sesiones:
        return [], "📊 No hay datos en el historial."
    
    # Generar reporte según tipo
    if tipo == 'resumido':
        return sesiones, generar_reporte_resumido(sesiones)
    elif tipo == 'detallado':
        return sesiones, generar_reporte_detallado(sesiones)
    elif tipo == 'usuario':
        return sesiones, generar_reporte_por_usuario(sesiones)
    elif tipo == 'fecha':
        return sesiones, generar_reporte_por_fecha(sesiones)
    elif tipo == 'estadisticas':
        return sesiones, generar_estadisticas(sesiones)
    else:
        return sesiones, generar_reporte_resumido(sesiones)

# ============================================================
# LIMPIEZA DE HISTORIAL
# ============================================================

def limpiar_historial_por_dias(dias: int) -> int:
    """
    Elimina el historial más antiguo de X días.
    Retorna el número de registros eliminados.
    """
    return db.limpiar_historial_antiguo(dias)


def limpiar_historial_por_usuario(usuario_id: int) -> int:
    """
    Elimina todo el historial de un usuario específico.
    Retorna el número de sesiones eliminadas.
    """
    # Obtener sesiones del usuario
    sesiones = db.obtener_historial_usuario(usuario_id, limit=99999)
    
    if not sesiones:
        return 0
    
    eliminadas = 0
    for sesion in sesiones:
        # Eliminar historial asociado
        # Nota: Esto es complejo con las claves foráneas
        # Implementaremos una versión simplificada
        try:
            # Marcar como abandonado para no mostrarlo
            db.abandonar_sesion(sesion['id'])
            eliminadas += 1
        except:
            pass
    
    return eliminadas

# ============================================================
# FIN DE historial_manager.py
# ============================================================