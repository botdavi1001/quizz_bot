# ============================================================
# BOT DE TELEGRAM - PROCESADOR DE CSV
# Lee, valida y convierte archivos CSV en preguntas
# ============================================================

import csv
import io
from typing import List, Dict, Tuple, Optional
from datetime import datetime

from src import config
from src.utils import (
    validar_opciones, 
    validar_tiempo, 
    parsear_opciones_csv,
    parsear_correctas_csv,
    log_info, 
    log_error
)
from src.database import db

# ============================================================
# VALIDACIÓN DE CSV
# ============================================================

def validar_fila_csv(fila: Dict[str, str], numero_fila: int) -> Tuple[bool, str, Dict]:
    """
    Valida una fila del CSV.
    Retorna: (es_valida, mensaje_error, datos_convertidos)
    """
    try:
        # Obtener campos
        pregunta = fila.get('pregunta', '').strip()
        tipo = fila.get('tipo', '').strip().lower()
        opciones_str = fila.get('opciones', '').strip()
        correctas_str = fila.get('correctas', '').strip()
        tiempo_str = fila.get('tiempo', '').strip()
        imagen_url = fila.get('imagen_url', '').strip()
        video_url = fila.get('video_url', '').strip()
        enlace_url = fila.get('enlace', '').strip()
        
        # Validar pregunta
        if not pregunta:
            return False, "La pregunta está vacía", {}
        
        # Validar tipo
        if tipo not in ['multiple', 'vf', 'abierta']:
            return False, f"Tipo '{tipo}' no válido. Usa: multiple, vf, abierta", {}
        
        # Validar opciones según tipo
        opciones = []
        if tipo == 'multiple':
            opciones = parsear_opciones_csv(opciones_str)
            if len(opciones) < 2:
                return False, f"La pregunta múltiple debe tener al menos 2 opciones. Tiene: {len(opciones)}", {}
            if len(opciones) > config.MAX_OPCIONES_POR_PREGUNTA:
                return False, f"La pregunta tiene más de {config.MAX_OPCIONES_POR_PREGUNTA} opciones", {}
        
        elif tipo == 'vf':
            opciones = ['Verdadero', 'Falso']
        
        elif tipo == 'abierta':
            opciones = []
            # Las abiertas no necesitan opciones
        
        # Validar correctas
        correctas = []
        if tipo == 'multiple':
            if correctas_str and correctas_str.strip() != '0':
                correctas = parsear_correctas_csv(correctas_str, len(opciones))
                if not correctas and correctas_str.strip():
                    return False, f"Índices de correctas inválidos: {correctas_str}", {}
        
        elif tipo == 'vf':
            if correctas_str.strip().lower() in ['v', 'verdadero']:
                correctas = [0]  # Verdadero es la opción 0 (índice base 0)
            elif correctas_str.strip().lower() in ['f', 'falso']:
                correctas = [1]  # Falso es la opción 1 (índice base 0)
            else:
                return False, f"Valor incorrecto para VF: {correctas_str}. Usa V o F", {}
        
        elif tipo == 'abierta':
            correctas = []
        
        # Validar tiempo
        tiempo = validar_tiempo(tiempo_str) if tiempo_str else config.TIEMPO_GLOBAL_DEFAULT
        
        # Construir datos
        datos = {
            'texto': pregunta,
            'tipo': tipo,
            'opciones': opciones,
            'respuestas_correctas': correctas,
            'tiempo_segundos': tiempo,
            'imagen_url': imagen_url if imagen_url else '',
            'video_url': video_url if video_url else '',
            'enlace_url': enlace_url if enlace_url else ''
        }
        
        # Validar URLs (si tienen)
        if imagen_url and not imagen_url.startswith('http'):
            return False, f"URL de imagen inválida: {imagen_url}", {}
        
        if video_url and not video_url.startswith('http'):
            return False, f"URL de video inválida: {video_url}", {}
        
        if enlace_url and not enlace_url.startswith('http'):
            return False, f"URL de enlace inválida: {enlace_url}", {}
        
        return True, "OK", datos
    
    except Exception as e:
        return False, f"Error procesando fila: {str(e)}", {}

# ============================================================
# PROCESADOR PRINCIPAL
# ============================================================

def procesar_csv(contenido: bytes, admin_id: str) -> Tuple[int, int, List[Tuple[int, str]]]:
    """
    Procesa un archivo CSV y guarda las preguntas válidas.
    
    Args:
        contenido: Contenido del archivo CSV en bytes
        admin_id: ID del admin en Supabase
    
    Returns:
        (exitosas, fallidas, errores_detallados)
        errores_detallados: Lista de (numero_fila, mensaje_error)
    """
    exitosas = 0
    fallidas = 0
    errores = []
    preguntas_guardar = []
    
    try:
        # Decodificar CSV
        texto = contenido.decode('utf-8')
        lines = texto.splitlines()
        
        if not lines:
            return 0, 0, [(1, "El archivo CSV está vacío")]
        
        # Usar DictReader para detectar encabezados
        csv_reader = csv.DictReader(lines)
        
        # Verificar que tenga los campos necesarios
        campos_requeridos = ['pregunta', 'tipo']
        campos_reader = set(csv_reader.fieldnames) if csv_reader.fieldnames else set()
        
        for campo in campos_requeridos:
            if campo not in campos_reader:
                return 0, 0, [(1, f"El CSV debe tener la columna '{campo}'")]
        
        # Procesar cada fila
        for num_fila, fila in enumerate(csv_reader, start=2):  # Empezar en 2 porque la fila 1 es encabezados
            es_valido, mensaje, datos = validar_fila_csv(fila, num_fila)
            
            if es_valido:
                # Añadir admin_id
                datos['admin_id'] = admin_id
                preguntas_guardar.append(datos)
                exitosas += 1
            else:
                fallidas += 1
                errores.append((num_fila, mensaje))
        
        # Guardar preguntas válidas
        if preguntas_guardar:
            # Guardar una por una para manejar errores individuales
            guardadas = 0
            for pregunta in preguntas_guardar:
                try:
                    # Crear la pregunta en Supabase
                    result = db.crear_pregunta(admin_id, pregunta)
                    if result:
                        guardadas += 1
                    else:
                        fallidas += 1
                        errores.append((len(preguntas_guardar), f"Error guardando en Supabase"))
                except Exception as e:
                    fallidas += 1
                    errores.append((len(preguntas_guardar), f"Error: {str(e)}"))
            
            exitosas = guardadas
        
        return exitosas, fallidas, errores
    
    except csv.Error as e:
        return 0, 1, [(1, f"Error de formato CSV: {str(e)}")]
    except Exception as e:
        return 0, 1, [(1, f"Error procesando archivo: {str(e)}")]

# ============================================================
# GENERADOR DE CSV DE EJEMPLO
# ============================================================

def generar_csv_ejemplo() -> bytes:
    """
    Genera un archivo CSV de ejemplo con preguntas de muestra.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Encabezados
    writer.writerow([
        'pregunta',
        'tipo',
        'opciones',
        'correctas',
        'tiempo',
        'imagen_url',
        'video_url',
        'enlace'
    ])
    
    # Datos de ejemplo
    ejemplos = [
        ['¿Cuál es la capital de Cuba?', 'multiple', 'La Habana;Santiago de Cuba;Camagüey;Holguín', '1', '30', 'https://ejemplo.com/la-habana.jpg', '', ''],
        ['¿El sol es una estrella?', 'vf', 'Verdadero;Falso', 'V', '15', '', '', ''],
        ['¿Qué es la fotosíntesis?', 'abierta', '', '', '60', '', '', 'https://es.wikipedia.org/wiki/Fotos%C3%ADntesis'],
        ['¿Cuántos continentes hay?', 'multiple', '5;6;7;8', '2', '20', '', '', ''],
        ['¿El agua hierve a 100°C?', 'vf', 'Verdadero;Falso', 'V', '10', '', '', ''],
        ['¿Quién escribió "Cien años de soledad"?', 'abierta', '', '', '45', '', '', ''],
    ]
    
    for ejemplo in ejemplos:
        writer.writerow(ejemplo)
    
    return output.getvalue().encode('utf-8')

# ============================================================
# FUNCIÓN DE VALIDACIÓN PARA MENSAJES
# ============================================================

def formatear_resultado_csv(exitosas: int, fallidas: int, errores: List[Tuple[int, str]]) -> str:
    """
    Formatea el resultado del procesamiento CSV para mostrarlo al admin.
    """
    mensaje = f"📊 **Resultado del procesamiento CSV**\n\n"
    mensaje += f"✅ Válidas: {exitosas}\n"
    mensaje += f"❌ Inválidas: {fallidas}\n\n"
    
    if errores:
        mensaje += "**Errores encontrados:**\n"
        for num_fila, error in errores[:10]:  # Mostrar máximo 10 errores
            mensaje += f"• Fila {num_fila}: {error}\n"
        
        if len(errores) > 10:
            mensaje += f"\n... y {len(errores) - 10} errores más"
    
    if exitosas > 0:
        mensaje += f"\n\n✅ Se guardaron {exitosas} preguntas correctamente."
    
    if fallidas > 0:
        mensaje += f"\n❌ {fallidas} preguntas tenían errores y no se guardaron."
    
    return mensaje

# ============================================================
# FIN DE csv_processor.py
# ============================================================