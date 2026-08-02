# ============================================================
# BOT DE TELEGRAM - COMPRESOR DE IMÁGENES
# Comprime imágenes, sube a Supabase Storage o ImgBB
# ============================================================

import os
import io
import asyncio
import base64
from datetime import datetime
from typing import Optional, Tuple, Dict, Any
from PIL import Image, ImageOps
import requests
from telegram import File

from src import config
from src.database import db
from src.utils import log_info, log_error

# ============================================================
# COMPRESIÓN DE IMÁGENES
# ============================================================

def comprimir_imagen(contenido: bytes, max_kb: int = config.IMG_COMPRESS_KB) -> bytes:
    """
    Comprime una imagen al tamaño máximo especificado en KB.
    Retorna los bytes de la imagen comprimida.
    """
    try:
        # Abrir imagen
        img = Image.open(io.BytesIO(contenido))
        
        # Convertir a RGB si es RGBA (para JPEG)
        if img.mode == 'RGBA':
            img = img.convert('RGB')
        
        # Redimensionar si es muy grande (máximo 1200px de ancho)
        if img.width > 1200 or img.height > 1200:
            img.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
        
        # Comprimir progresivamente
        calidad = 85
        bytes_io = io.BytesIO()
        img.save(bytes_io, format='JPEG', quality=calidad, optimize=True)
        
        # Verificar tamaño y reducir calidad si es necesario
        while len(bytes_io.getvalue()) > max_kb * 1024 and calidad > 20:
            calidad -= 5
            bytes_io = io.BytesIO()
            img.save(bytes_io, format='JPEG', quality=calidad, optimize=True)
        
        return bytes_io.getvalue()
    
    except Exception as e:
        log_error(f"Error comprimiendo imagen: {str(e)}")
        return contenido  # Retornar original si falla

# ============================================================
# SUBIDA A SUPABASE STORAGE
# ============================================================

def subir_a_supabase_storage(imagen_bytes: bytes, nombre_archivo: str) -> Optional[str]:
    """
    Sube una imagen a Supabase Storage.
    Retorna la URL pública o None si falla.
    """
    try:
        if not config.SUPABASE_STORAGE_URL:
            log_error("SUPABASE_STORAGE_URL no configurado")
            return None
        
        # Preparar el archivo
        archivo = io.BytesIO(imagen_bytes)
        archivo.seek(0)
        
        # Nombre único
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        nombre = f"imagenes/{timestamp}_{nombre_archivo}"
        
        # Subir a Supabase Storage
        # Nota: Supabase Python SDK no tiene soporte directo para storage
        # Usamos requests directamente
        headers = {
            'Authorization': f'Bearer {config.SUPABASE_KEY}',
            'Content-Type': 'image/jpeg'
        }
        
        url_subida = f"{config.SUPABASE_URL}/storage/v1/object/imagenes/{nombre}"
        
        response = requests.post(
            url_subida,
            headers=headers,
            data=archivo.getvalue()
        )
        
        if response.status_code == 200 or response.status_code == 201:
            # Construir URL pública
            url_publica = f"{config.SUPABASE_URL}/storage/v1/object/public/imagenes/{nombre}"
            log_info(f"✅ Imagen subida a Supabase Storage: {url_publica}")
            return url_publica
        
        else:
            log_error(f"Error subiendo a Supabase Storage: {response.status_code} - {response.text}")
            return None
    
    except Exception as e:
        log_error(f"Error en subida a Supabase Storage: {str(e)}")
        return None

# ============================================================
# FALLBACK: SUBIDA A IMGBB (GRATIS)
# ============================================================

def subir_a_imgbb(imagen_bytes: bytes) -> Optional[str]:
    """
    Sube una imagen a ImgBB (fallback cuando Supabase Storage falla).
    Retorna la URL pública o None si falla.
    """
    try:
        # Codificar imagen a base64
        imagen_base64 = base64.b64encode(imagen_bytes).decode('utf-8')
        
        # ImgBB API (sin API key se puede usar, pero limitado)
        url = "https://api.imgbb.com/1/upload"
        
        # Nota: ImgBB requiere API key. Como fallback, si no tenemos key,
        # intentamos con el servicio gratuito sin key (limitado)
        # Podrías obtener una key gratis en https://imgbb.com/
        api_key = os.getenv('IMGBB_API_KEY', '')
        
        if not api_key:
            log_error("IMGBB_API_KEY no configurado. Fallback no disponible.")
            return None
        
        data = {
            'key': api_key,
            'image': imagen_base64
        }
        
        response = requests.post(url, data=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                url_imagen = result['data']['url']
                log_info(f"✅ Imagen subida a ImgBB: {url_imagen}")
                return url_imagen
        
        log_error(f"Error subiendo a ImgBB: {response.status_code}")
        return None
    
    except Exception as e:
        log_error(f"Error en subida a ImgBB: {str(e)}")
        return None

# ============================================================
# FUNCIÓN PRINCIPAL PARA SUBIR IMÁGENES
# ============================================================

async def procesar_y_subir_imagen(archivo: File, nombre_base: str = "imagen") -> Tuple[bool, Optional[str], str]:
    """
    Procesa una imagen: descarga, comprime y sube.
    
    Args:
        archivo: Objeto File de Telegram
        nombre_base: Nombre base para el archivo
    
    Returns:
        (exito, url, mensaje)
    """
    try:
        # Descargar archivo
        contenido = await archivo.download_as_bytearray()
        
        if not contenido:
            return False, None, "❌ No se pudo descargar la imagen"
        
        # Verificar que sea una imagen
        try:
            img = Image.open(io.BytesIO(contenido))
            if img.format not in ['JPEG', 'PNG', 'GIF', 'WEBP']:
                return False, None, "❌ Formato de imagen no soportado. Usa JPG, PNG, GIF o WEBP"
        except:
            return False, None, "❌ El archivo no es una imagen válida"
        
        # Comprimir
        nombre_archivo = f"{nombre_base}.jpg"
        contenido_comprimido = comprimir_imagen(bytes(contenido), config.IMG_COMPRESS_KB)
        
        # Verificar si se comprimió correctamente
        if len(contenido_comprimido) > config.IMG_COMPRESS_KB * 1024 * 1.5:
            # Avisar que la imagen sigue siendo pesada
            tamaño_mb = len(contenido_comprimido) / (1024 * 1024)
            aviso = f"⚠️ La imagen pesa {tamaño_mb:.2f}MB (recomendado < {config.IMG_COMPRESS_KB}KB)"
        else:
            aviso = ""
        
        # Intentar subir a Supabase Storage primero
        url = subir_a_supabase_storage(contenido_comprimido, nombre_archivo)
        
        # Si falla, intentar con ImgBB (fallback)
        if not url:
            log_info("Supabase Storage falló, intentando ImgBB...")
            url = subir_a_imgbb(contenido_comprimido)
        
        if url:
            # Verificar almacenamiento usado
            usado_mb = db.contar_almacenamiento_usado()
            if usado_mb >= config.LIMITE_ALMACENAMIENTO_AVISO:
                aviso += f"\n⚠️ Almacenamiento al {int(usado_mb)}% - Considera limpiar imágenes antiguas"
            
            return True, url, aviso
        else:
            return False, None, "❌ No se pudo subir la imagen a ningún servicio"
    
    except Exception as e:
        log_error(f"Error procesando imagen: {str(e)}")
        return False, None, f"❌ Error procesando imagen: {str(e)}"

# ============================================================
# LIMPIEZA DE IMÁGENES ANTIGUAS
# ============================================================

def limpiar_imagenes_antiguas(dias_antiguedad: int = 30) -> int:
    """
    Elimina imágenes antiguas del storage.
    Retorna el número de imágenes eliminadas.
    """
    try:
        # Obtener preguntas con imágenes antiguas
        # Esto es complejo con Supabase Storage directamente
        # Implementaremos una versión simplificada:
        # 1. Obtener todas las preguntas del admin
        # 2. Verificar fecha de creación
        # 3. Si tienen imagen y son antiguas, eliminarlas
        
        # Por simplicidad, solo haremos un conteo y aviso
        # La eliminación real se hará desde el panel de Supabase
        log_info(f"Limpieza de imágenes antiguas (> {dias_antiguedad} días) - Manual en Supabase")
        return 0
    
    except Exception as e:
        log_error(f"Error limpiando imágenes: {str(e)}")
        return 0

# ============================================================
# CONTEO DE ALMACENAMIENTO
# ============================================================

def obtener_espacio_usado() -> float:
    """
    Obtiene el espacio usado en MB.
    """
    return db.contar_almacenamiento_usado()

# ============================================================
# FIN DE image_compressor.py
# ============================================================