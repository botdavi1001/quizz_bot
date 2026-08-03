# ============================================================
# BOT DE TELEGRAM - SISTEMA DE RESPALDOS
# Guarda datos localmente si falla Supabase y sincroniza después
# ============================================================

import os
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional
from threading import Lock

from src import config
from src.utils import log_info, log_error
from src.database import db
from src.estados import *

# ============================================================
# GESTOR DE RESPALDOS
# ============================================================

class BackupSystem:
    """Sistema de respaldo local para cuando Supabase falla"""
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BackupSystem, cls).__new__(cls)
            cls._instance._inicializado = False
        return cls._instance
    
    def __init__(self):
        if not self._inicializado:
            self.archivo = config.BACKUP_FILE
            self._inicializado = True
            self._crear_directorio()
            self._cargar_datos()
    
    def _crear_directorio(self):
        """Crea el directorio para el archivo de respaldo si no existe"""
        directorio = os.path.dirname(self.archivo)
        if directorio and not os.path.exists(directorio):
            try:
                os.makedirs(directorio, exist_ok=True)
                log_info(f"📁 Directorio de respaldos creado: {directorio}")
            except Exception as e:
                log_error(f"Error creando directorio de respaldos: {str(e)}")
    
    def _cargar_datos(self):
        """Carga los datos del archivo de respaldo"""
        try:
            if os.path.exists(self.archivo):
                with open(self.archivo, 'r', encoding='utf-8') as f:
                    self.datos = json.load(f)
                log_info(f"📥 Respaldos cargados: {len(self.datos.get('pendientes', []))} pendientes")
            else:
                self.datos = {
                    'pendientes': [],      # Datos pendientes de sincronizar
                    'completados': [],     # Historial de respaldos completados
                    'ultima_sincronizacion': None
                }
                self._guardar()
        except Exception as e:
            log_error(f"Error cargando respaldos: {str(e)}")
            self.datos = {
                'pendientes': [],
                'completados': [],
                'ultima_sincronizacion': None
            }
    
    def _guardar(self):
        """Guarda los datos en el archivo de respaldo"""
        try:
            with self._lock:
                with open(self.archivo, 'w', encoding='utf-8') as f:
                    json.dump(self.datos, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log_error(f"Error guardando respaldos: {str(e)}")
    
    def guardar_respaldo(self, tipo: str, datos: Dict) -> bool:
        """
        Guarda un respaldo local.
        
        Args:
            tipo: 'sesion', 'historial', 'respuesta', etc.
            datos: Los datos a guardar
        """
        try:
            respaldo = {
                'id': f"{datetime.now().timestamp()}_{tipo}",
                'tipo': tipo,
                'datos': datos,
                'fecha': datetime.now().isoformat(),
                'intentos': 0
            }
            
            self.datos['pendientes'].append(respaldo)
            self._guardar()
            
            log_info(f"💾 Respaldo guardado: {tipo}")
            return True
        
        except Exception as e:
            log_error(f"Error guardando respaldo: {str(e)}")
            return False
    
    async def sincronizar(self) -> int:
        """
        Intenta sincronizar todos los respaldos pendientes con Supabase.
        Retorna el número de respaldos sincronizados.
        """
        sincronizados = 0
        
        if not self.datos['pendientes']:
            return 0
        
        log_info(f"🔄 Sincronizando {len(self.datos['pendientes'])} respaldos...")
        
        # Hacer una copia de la lista para iterar
        pendientes = self.datos['pendientes'][:]
        
        for respaldo in pendientes:
            try:
                exito = await self._procesar_respaldo(respaldo)
                
                if exito:
                    # Eliminar de pendientes
                    self.datos['pendientes'].remove(respaldo)
                    self.datos['completados'].append({
                        'id': respaldo['id'],
                        'fecha_sincronizacion': datetime.now().isoformat()
                    })
                    sincronizados += 1
                    log_info(f"✅ Respaldo sincronizado: {respaldo['id']}")
                else:
                    # Incrementar intentos
                    respaldo['intentos'] += 1
                    if respaldo['intentos'] >= config.SUPABASE_RETRIES:
                        log_error(f"❌ Respaldo falló después de {config.SUPABASE_RETRIES} intentos: {respaldo['id']}")
                        # Mover a fallidos permanentemente
                        self.datos['pendientes'].remove(respaldo)
                        self.datos['completados'].append({
                            'id': respaldo['id'],
                            'fecha_sincronizacion': None,
                            'fallo_permanente': True
                        })
            
            except Exception as e:
                log_error(f"Error sincronizando respaldo {respaldo.get('id', 'unknown')}: {str(e)}")
            
            # Pequeña pausa entre sincronizaciones
            await asyncio.sleep(0.5)
        
        # Guardar cambios
        self._guardar()
        
        # Actualizar última sincronización
        self.datos['ultima_sincronizacion'] = datetime.now().isoformat()
        self._guardar()
        
        log_info(f"✅ Sincronización completada: {sincronizados} respaldos")
        return sincronizados
    
    async def _procesar_respaldo(self, respaldo: Dict) -> bool:
        """
        Procesa un respaldo individual.
        Retorna True si se sincronizó correctamente.
        """
        tipo = respaldo.get('tipo')
        datos = respaldo.get('datos', {})
        
        try:
            if tipo == 'crear_pregunta':
                # Intentar crear la pregunta en Supabase
                resultado = db.crear_pregunta(
                    datos.get('admin_id'),
                    datos.get('pregunta')
                )
                return resultado is not None
            
            elif tipo == 'guardar_respuesta':
                # Intentar guardar la respuesta
                resultado = db.guardar_respuesta_sesion(
                    datos.get('sesion_id'),
                    datos.get('pregunta_id'),
                    datos.get('respuesta'),
                    datos.get('es_correcta'),
                    datos.get('tiempo_tardado')
                )
                return resultado
            
            elif tipo == 'completar_sesion':
                return db.completar_sesion(datos.get('sesion_id'))
            
            elif tipo == 'abandonar_sesion':
                return db.abandonar_sesion(
                    datos.get('sesion_id'),
                    datos.get('pregunta_en_abandono')
                )
            
            elif tipo == 'agotar_tiempo':
                return db.agotar_tiempo_sesion(datos.get('sesion_id'))
            
            elif tipo == 'actualizar_sesion':
                return db.actualizar_sesion(
                    datos.get('sesion_id'),
                    datos.get('data', {})
                )
            
            elif tipo == 'crear_cuestionario':
                return db.crear_cuestionario(
                    datos.get('admin_id'),
                    datos.get('nombre'),
                    datos.get('preguntas_ids'),
                    datos.get('seleccion_tipo'),
                    datos.get('reintentos')
                ) is not None
            
            else:
                log_error(f"Tipo de respaldo desconocido: {tipo}")
                return False
        
        except Exception as e:
            log_error(f"Error procesando respaldo {tipo}: {str(e)}")
            return False
    
    def obtener_pendientes(self) -> List[Dict]:
        """Obtiene la lista de respaldos pendientes"""
        return self.datos.get('pendientes', [])
    
    def obtener_estadisticas(self) -> Dict:
        """Obtiene estadísticas del sistema de respaldos"""
        return {
            'pendientes': len(self.datos.get('pendientes', [])),
            'completados': len(self.datos.get('completados', [])),
            'ultima_sincronizacion': self.datos.get('ultima_sincronizacion')
        }
    
    def limpiar_historial_respaldos(self, dias: int = 30):
        """Limpia el historial de respaldos completados de más de X días"""
        try:
            ahora = datetime.now()
            nuevos_completados = []
            
            for item in self.datos.get('completados', []):
                fecha_str = item.get('fecha_sincronizacion')
                if fecha_str:
                    try:
                        fecha = datetime.fromisoformat(fecha_str)
                        if (ahora - fecha).days < dias:
                            nuevos_completados.append(item)
                    except:
                        nuevos_completados.append(item)
            
            self.datos['completados'] = nuevos_completados
            self._guardar()
            
            log_info(f"🧹 Historial de respaldos limpiado (manteniendo {dias} días)")
        
        except Exception as e:
            log_error(f"Error limpiando historial de respaldos: {str(e)}")

# ============================================================
# INSTANCIA ÚNICA
# ============================================================

backup = BackupSystem()

# ============================================================
# FUNCIONES DE ALTO NIVEL (para usar desde otros módulos)
# ============================================================

async def guardar_con_respaldo(tipo: str, datos: Dict, funcion_db) -> Any:
    """
    Intenta guardar en Supabase, si falla guarda en respaldo.
    
    Args:
        tipo: Tipo de operación
        datos: Datos a guardar
        funcion_db: Función de Supabase a llamar
    
    Returns:
        El resultado de la función o None si falló
    """
    try:
        # Intentar guardar en Supabase
        resultado = funcion_db(**datos)
        
        if resultado is not None:
            return resultado
        else:
            # Si falló, guardar en respaldo
            backup.guardar_respaldo(tipo, datos)
            log_info(f"💾 Datos guardados en respaldo: {tipo}")
            return None
    
    except Exception as e:
        # Si hay excepción, guardar en respaldo
        log_error(f"Error guardando en Supabase: {str(e)}")
        backup.guardar_respaldo(tipo, datos)
        log_info(f"💾 Datos guardados en respaldo por error: {tipo}")
        return None

# ============================================================
# FIN DE backup_system.py
# ============================================================