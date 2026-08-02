# ============================================================
# BOT DE TELEGRAM - UTILIDADES
# Funciones auxiliares, validación y similitud semántica
# ============================================================

import re
import unicodedata
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import Levenshtein

# ============================================================
# NORMALIZACIÓN DE TEXTO
# ============================================================

def normalizar_texto(texto: str) -> str:
    """
    Normaliza un texto para comparación:
    - Elimina acentos
    - Convierte a minúsculas
    - Elimina espacios extra
    - Elimina signos de puntuación
    """
    if not texto:
        return ""
    
    # Convertir a minúsculas
    texto = texto.lower()
    
    # Eliminar acentos
    texto = unicodedata.normalize('NFKD', texto)
    texto = ''.join([c for c in texto if not unicodedata.combining(c)])
    
    # Eliminar signos de puntuación (excepto espacios)
    texto = re.sub(r'[^\w\s]', '', texto)
    
    # Eliminar espacios extra
    texto = re.sub(r'\s+', ' ', texto).strip()
    
    return texto


def similitud_semantica(texto1: str, texto2: str, tolerancia: int = 80) -> Tuple[bool, float]:
    """
    Calcula la similitud entre dos textos usando Levenshtein.
    Retorna: (es_correcto, porcentaje_similitud)
    
    Args:
        texto1: Texto del usuario
        texto2: Texto esperado
        tolerancia: Porcentaje mínimo para considerar correcto (0-100)
    """
    if not texto1 or not texto2:
        return False, 0.0
    
    # Normalizar ambos textos
    t1 = normalizar_texto(texto1)
    t2 = normalizar_texto(texto2)
    
    if not t1 or not t2:
        return False, 0.0
    
    # Calcular distancia de Levenshtein
    distancia = Levenshtein.distance(t1, t2)
    max_len = max(len(t1), len(t2))
    
    if max_len == 0:
        return True, 100.0
    
    # Calcular porcentaje de similitud
    similitud = ((max_len - distancia) / max_len) * 100
    
    # Determinar si es correcto
    es_correcto = similitud >= tolerancia
    
    return es_correcto, similitud


def normalizar_respuesta_abierta(respuesta: str) -> str:
    """Normaliza una respuesta abierta para guardarla"""
    if not respuesta:
        return ""
    
    # Eliminar espacios extra
    respuesta = re.sub(r'\s+', ' ', respuesta).strip()
    
    # Capitalizar primera letra
    if respuesta:
        respuesta = respuesta[0].upper() + respuesta[1:] if len(respuesta) > 1 else respuesta.upper()
    
    return respuesta

# ============================================================
# VALIDACIONES
# ============================================================

def validar_opciones(opciones: List[str]) -> bool:
    """
    Valida que las opciones sean válidas:
    - No vacías
    - Máximo 10 opciones
    - No repetidas
    """
    if not opciones:
        return False
    
    if len(opciones) > 10:
        return False
    
    # Eliminar opciones vacías
    opciones_validas = [o.strip() for o in opciones if o.strip()]
    
    if len(opciones_validas) < 2:
        return False
    
    # Verificar duplicados
    if len(opciones_validas) != len(set(opciones_validas)):
        return False
    
    return True


def validar_indices_correctos(indices: str, total_opciones: int) -> List[int]:
    """
    Valida y convierte índices de respuestas correctas.
    Retorna lista de índices válidos (base 1 a base 0).
    """
    if not indices or indices.strip() == '0':
        return []
    
    try:
        # Separar por comas y limpiar
        partes = [p.strip() for p in indices.split(',') if p.strip()]
        numeros = []
        
        for p in partes:
            # Verificar rangos (ej: "1-3")
            if '-' in p:
                inicio, fin = p.split('-')
                inicio = int(inicio.strip())
                fin = int(fin.strip())
                for i in range(inicio, fin + 1):
                    if 1 <= i <= total_opciones:
                        numeros.append(i - 1)  # Convertir a base 0
            else:
                num = int(p)
                if 1 <= num <= total_opciones:
                    numeros.append(num - 1)  # Convertir a base 0
        
        # Eliminar duplicados y ordenar
        numeros = sorted(list(set(numeros)))
        
        return numeros
    except:
        return []


def validar_tiempo(tiempo: str) -> int:
    """Valida que el tiempo sea un número entero no negativo"""
    try:
        t = int(tiempo)
        if t < 0:
            return 0
        return t
    except:
        return 30  # Default


def validar_tolerancia(tolerancia: str) -> int:
    """Valida que la tolerancia esté entre 0 y 100"""
    try:
        t = int(tolerancia)
        if t < 0:
            return 0
        if t > 100:
            return 100
        return t
    except:
        return 80  # Default

# ============================================================
# FORMATEO
# ============================================================

def formatear_fecha(fecha_str: str) -> str:
    """Formatea una fecha para mostrar"""
    try:
        fecha = datetime.fromisoformat(fecha_str.replace('Z', '+00:00'))
        return fecha.strftime('%d/%m/%Y %H:%M')
    except:
        return fecha_str


def formatear_tiempo(segundos: int) -> str:
    """Formatea segundos en formato legible"""
    if segundos is None or segundos < 0:
        return "0s"
    
    if segundos < 60:
        return f"{segundos}s"
    
    minutos = segundos // 60
    segs = segundos % 60
    
    if minutos < 60:
        return f"{minutos}m {segs}s"
    
    horas = minutos // 60
    minutos = minutos % 60
    
    return f"{horas}h {minutos}m {segs}s"


def formatear_estado(estado: Dict) -> str:
    """Formatea el estado de una sesión para mostrar"""
    if estado.get('completado'):
        return "✅ Completado"
    elif estado.get('tiempo_agotado'):
        return "⏰ Tiempo agotado"
    elif estado.get('abandonado'):
        return "🚫 Abandonado"
    else:
        return "⏳ En progreso"


def formatear_resumen_admin(estadisticas: Dict) -> str:
    """Formatea las estadísticas para el admin"""
    texto = "📊 **RESUMEN GENERAL**\n\n"
    texto += f"📝 Total de preguntas: {estadisticas.get('total_preguntas', 0)}\n"
    texto += f"👥 Total de sesiones: {estadisticas.get('total_sesiones', 0)}\n"
    texto += f"✅ Completados: {estadisticas.get('total_completados', 0)}\n"
    texto += f"🚫 Abandonados: {estadisticas.get('total_abandonados', 0)}\n"
    texto += f"⏰ Tiempo agotado: {estadisticas.get('total_tiempo_agotado', 0)}\n"
    texto += f"📋 Registros en historial: {estadisticas.get('total_historial', 0)}\n"
    return texto

# ============================================================
# PROCESAMIENTO DE PREGUNTAS
# ============================================================

def parsear_preguntas_texto(texto: str) -> List[str]:
    """
    Parsea un texto con múltiples preguntas (una por línea).
    Ignora líneas vacías.
    """
    if not texto:
        return []
    
    lineas = texto.strip().split('\n')
    preguntas = []
    
    for linea in lineas:
        linea = linea.strip()
        if linea and linea.lower() != 'listo':
            preguntas.append(linea)
    
    return preguntas


def parsear_formato_lotes(texto: str, total_preguntas: int) -> Dict[int, str]:
    """
    Parsea asignaciones de formato por lotes.
    Ejemplo: "1-10:1, 11-20:2, 21-30:3"
    Retorna: {numero_pregunta: formato}
    """
    if not texto:
        return {}
    
    resultado = {}
    texto = texto.replace(' ', '')
    
    # Separar por comas
    partes = texto.split(',')
    
    for parte in partes:
        if not parte.strip():
            continue
        
        if ':' not in parte:
            continue
        
        rango, formato = parte.split(':')
        formato = formato.strip()
        
        # Verificar si es "todos"
        if rango.lower() == 'todos':
            for i in range(1, total_preguntas + 1):
                resultado[i] = formato
            continue
        
        # Procesar rangos
        if '-' in rango:
            inicio, fin = rango.split('-')
            inicio = int(inicio.strip())
            fin = int(fin.strip())
            
            for i in range(inicio, fin + 1):
                if 1 <= i <= total_preguntas:
                    resultado[i] = formato
        else:
            # Número individual
            num = int(rango.strip())
            if 1 <= num <= total_preguntas:
                resultado[num] = formato
    
    return resultado


def parsear_tiempo_lotes(texto: str, total_preguntas: int) -> Dict[int, int]:
    """
    Parsea asignaciones de tiempo por lotes.
    Ejemplo: "1-10:30, todos:45, 5,12:0"
    Retorna: {numero_pregunta: tiempo}
    """
    if not texto:
        return {}
    
    resultado = {}
    texto = texto.replace(' ', '')
    
    partes = texto.split(',')
    
    for parte in partes:
        if not parte.strip():
            continue
        
        if ':' not in parte:
            continue
        
        rango, tiempo = parte.split(':')
        tiempo = validar_tiempo(tiempo.strip())
        
        if rango.lower() == 'todos':
            for i in range(1, total_preguntas + 1):
                resultado[i] = tiempo
            continue
        
        if '-' in rango:
            inicio, fin = rango.split('-')
            inicio = int(inicio.strip())
            fin = int(fin.strip())
            
            for i in range(inicio, fin + 1):
                if 1 <= i <= total_preguntas:
                    resultado[i] = tiempo
        else:
            num = int(rango.strip())
            if 1 <= num <= total_preguntas:
                resultado[num] = tiempo
    
    return resultado

# ============================================================
# PROCESAMIENTO DE CSV
# ============================================================

def parsear_opciones_csv(opciones_str: str) -> List[str]:
    """Parsea opciones desde CSV (separadas por ;)"""
    if not opciones_str:
        return []
    
    opciones = [o.strip() for o in opciones_str.split(';') if o.strip()]
    return opciones


def parsear_correctas_csv(correctas_str: str, total_opciones: int) -> List[int]:
    """Parsea índices correctos desde CSV"""
    if not correctas_str or correctas_str.strip() == '0':
        return []
    
    try:
        indices = [int(i.strip()) for i in correctas_str.split(',') if i.strip()]
        # Convertir a base 0
        return [i - 1 for i in indices if 1 <= i <= total_opciones]
    except:
        return []

# ============================================================
# GENERACIÓN DE IDS
# ============================================================

def generar_id_unico() -> str:
    """Genera un ID único simple para preguntas temporales"""
    import uuid
    return str(uuid.uuid4())

# ============================================================
# LOGGING
# ============================================================

def log_error(error: str, contexto: str = ""):
    """Registra un error en la consola"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] ❌ {contexto}: {error}")


def log_info(mensaje: str):
    """Registra información en la consola"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] ℹ️ {mensaje}")

# ============================================================
# FIN DE utils.py
# ============================================================