# ============================================================
# BOT DE TELEGRAM - BASE DE DATOS
# Conexión y operaciones con Supabase
# ============================================================

import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple

from supabase import create_client, Client
from src import config

# ============================================================
# CONEXIÓN A SUPABASE
# ============================================================

class Database:
    """Clase única para manejar todas las operaciones con Supabase"""
    
    _instance: Optional['Database'] = None
    _client: Optional[Client] = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._client is None:
            self._client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
            print("✅ Conexión a Supabase establecida")
    
    @property
    def client(self) -> Client:
        return self._client
    
    # ============================================================
    # MÉTODOS DE UTILIDAD
    # ============================================================
    
    def _handle_error(self, error: Exception, context: str = ""):
        """Maneja errores de Supabase y los registra"""
        error_msg = f"❌ Error en {context}: {str(error)}"
        print(error_msg)
        return None
    
    # ============================================================
    # ADMINS
    # ============================================================
    
    def registrar_admin(self, telegram_id: int, username: str = None, first_name: str = None) -> bool:
        """Registra un nuevo admin en la base de datos"""
        try:
            # Verificar si ya existe
            existente = self.client.table('admins').select('*').eq('telegram_id', telegram_id).execute()
            if existente.data:
                # Actualizar datos si ya existe
                data = {'username': username, 'first_name': first_name}
                self.client.table('admins').update(data).eq('telegram_id', telegram_id).execute()
                return True
            
            # Crear nuevo admin
            data = {
                'telegram_id': telegram_id,
                'username': username,
                'first_name': first_name,
                'config': {
                    'notificar_admin': True,
                    'tiempo_global_default': 30,
                    'mostrar_correctas': True,
                    'reintentos_default': 3,
                    'formato_reporte': 'resumido',
                    'tolerancia_abiertas': 80
                }
            }
            self.client.table('admins').insert(data).execute()
            return True
        except Exception as e:
            self._handle_error(e, "registrar_admin")
            return False
    
    def obtener_admin(self, telegram_id: int) -> Optional[Dict]:
        """Obtiene los datos de un admin por su ID de Telegram"""
        try:
            result = self.client.table('admins').select('*').eq('telegram_id', telegram_id).execute()
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            self._handle_error(e, "obtener_admin")
            return None
    
    def obtener_config_admin(self, telegram_id: int) -> Dict:
        """Obtiene la configuración del admin"""
        admin = self.obtener_admin(telegram_id)
        if admin:
            return admin.get('config', {})
        return {}
    
    def actualizar_config_admin(self, telegram_id: int, config_data: Dict) -> bool:
        """Actualiza la configuración del admin"""
        try:
            self.client.table('admins').update({'config': config_data}).eq('telegram_id', telegram_id).execute()
            return True
        except Exception as e:
            self._handle_error(e, "actualizar_config_admin")
            return False
    
    # ============================================================
    # PREGUNTAS
    # ============================================================
    
    def crear_pregunta(self, admin_id: str, data: Dict) -> Optional[str]:
        """Crea una nueva pregunta"""
        try:
            # Asegurar que los campos opcionales tengan valores por defecto
            data['admin_id'] = admin_id
            data.setdefault('imagen_url', '')
            data.setdefault('video_url', '')
            data.setdefault('enlace_url', '')
            data.setdefault('tiempo_segundos', config.TIEMPO_GLOBAL_DEFAULT)
            
            result = self.client.table('preguntas').insert(data).execute()
            if result.data:
                return result.data[0]['id']
            return None
        except Exception as e:
            self._handle_error(e, "crear_pregunta")
            return None
    
    def crear_preguntas_masivas(self, admin_id: str, preguntas: List[Dict]) -> Tuple[int, List[str]]:
        """Crea múltiples preguntas de una vez. Retorna (cantidad_exitosas, ids)"""
        exitosas = 0
        ids = []
        
        for pregunta in preguntas:
            pregunta['admin_id'] = admin_id
            pregunta.setdefault('imagen_url', '')
            pregunta.setdefault('video_url', '')
            pregunta.setdefault('enlace_url', '')
            pregunta.setdefault('tiempo_segundos', config.TIEMPO_GLOBAL_DEFAULT)
            
            try:
                result = self.client.table('preguntas').insert(pregunta).execute()
                if result.data:
                    exitosas += 1
                    ids.append(result.data[0]['id'])
            except Exception as e:
                print(f"⚠️ Error al crear pregunta: {e}")
                continue
        
        return exitosas, ids
    
    def obtener_preguntas(self, admin_id: str, limit: int = None) -> List[Dict]:
        """Obtiene todas las preguntas de un admin"""
        try:
            query = self.client.table('preguntas').select('*').eq('admin_id', admin_id).order('fecha_creacion', desc=False)
            if limit:
                query = query.limit(limit)
            result = query.execute()
            return result.data if result.data else []
        except Exception as e:
            self._handle_error(e, "obtener_preguntas")
            return []
    
    def obtener_pregunta(self, pregunta_id: str) -> Optional[Dict]:
        """Obtiene una pregunta por su ID"""
        try:
            result = self.client.table('preguntas').select('*').eq('id', pregunta_id).execute()
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            self._handle_error(e, "obtener_pregunta")
            return None
    
    def obtener_preguntas_por_ids(self, ids: List[str]) -> List[Dict]:
        """Obtiene múltiples preguntas por sus IDs"""
        try:
            if not ids:
                return []
            result = self.client.table('preguntas').select('*').in_('id', ids).execute()
            return result.data if result.data else []
        except Exception as e:
            self._handle_error(e, "obtener_preguntas_por_ids")
            return []
    
    def actualizar_pregunta(self, pregunta_id: str, data: Dict) -> bool:
        """Actualiza una pregunta existente"""
        try:
            self.client.table('preguntas').update(data).eq('id', pregunta_id).execute()
            return True
        except Exception as e:
            self._handle_error(e, "actualizar_pregunta")
            return False
    
    def eliminar_pregunta(self, pregunta_id: str) -> bool:
        """Elimina una pregunta"""
        try:
            self.client.table('preguntas').delete().eq('id', pregunta_id).execute()
            return True
        except Exception as e:
            self._handle_error(e, "eliminar_pregunta")
            return False
    
    def contar_preguntas(self, admin_id: str) -> int:
        """Cuenta cuántas preguntas tiene un admin"""
        try:
            result = self.client.table('preguntas').select('id', count='exact').eq('admin_id', admin_id).execute()
            return result.count or 0
        except Exception as e:
            self._handle_error(e, "contar_preguntas")
            return 0
    
    # ============================================================
    # CUESTIONARIO
    # ============================================================
    
    def crear_cuestionario(self, admin_id: str, nombre: str, preguntas_ids: List[str], 
                       seleccion_tipo: str, reintentos: int) -> Optional[str]:
        """
        Crea un nuevo cuestionario y desactiva TODOS los cuestionarios activos
        (de cualquier admin), asegurando que solo haya uno activo.
        """
        try:
            # Desactivar TODOS los cuestionarios activos (sin importar el admin)
            self.client.table('cuestionario').update({'activo': False}).eq('activo', True).execute()
            
            # Crear nuevo cuestionario
            data = {
                'admin_id': admin_id,
                'nombre': nombre,
                'preguntas_ids': preguntas_ids,
                'seleccion_tipo': seleccion_tipo,
                'activo': True,
                'reintentos': reintentos
            }
            result = self.client.table('cuestionario').insert(data).execute()
            if result.data:
                return result.data[0]['id']
            return None
        except Exception as e:
            self._handle_error(e, "crear_cuestionario")
            return None
    
    def obtener_cuestionario_activo(self) -> Optional[Dict]:
        """
        Obtiene el cuestionario activo más reciente.
        Si hay varios, devuelve el último creado (por fecha).
        """
        try:
            result = self.client.table('cuestionario').select('*') \
                .eq('activo', True) \
                .order('creado_en', desc=True) \
                .limit(1) \
                .execute()
            
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            self._handle_error(e, "obtener_cuestionario_activo")
            return None
    
    def desactivar_cuestionario(self, cuestionario_id: str) -> bool:
        """Desactiva un cuestionario"""
        try:
            self.client.table('cuestionario').update({'activo': False}).eq('id', cuestionario_id).execute()
            return True
        except Exception as e:
            self._handle_error(e, "desactivar_cuestionario")
            return False
    
    def obtener_cuestionario(self, cuestionario_id: str) -> Optional[Dict]:
        """Obtiene un cuestionario por su ID"""
        try:
            result = self.client.table('cuestionario').select('*').eq('id', cuestionario_id).execute()
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            self._handle_error(e, "obtener_cuestionario")
            return None
    
    # ============================================================
    # SESIONES
    # ============================================================
    
    def crear_sesion(self, usuario_id: int, username: str, first_name: str, 
                     cuestionario_id: str, intento_numero: int = 1) -> Optional[str]:
        """Crea una nueva sesión para un usuario"""
        try:
            # Verificar si ya tiene una sesión activa
            sesion_activa = self.obtener_sesion_activa(usuario_id)
            if sesion_activa:
                return sesion_activa['id']
            
            data = {
                'usuario_id': usuario_id,
                'username': username,
                'first_name': first_name,
                'cuestionario_id': cuestionario_id,
                'pregunta_actual': 0,
                'respuestas': [],
                'intento_numero': intento_numero
            }
            result = self.client.table('sesiones').insert(data).execute()
            if result.data:
                return result.data[0]['id']
            return None
        except Exception as e:
            self._handle_error(e, "crear_sesion")
            return None
    
    def obtener_sesion_activa(self, usuario_id: int) -> Optional[Dict]:
        """Obtiene la sesión activa de un usuario (no completada ni abandonada)"""
        try:
            result = self.client.table('sesiones').select('*') \
                .eq('usuario_id', usuario_id) \
                .eq('completado', False) \
                .eq('abandonado', False) \
                .eq('tiempo_agotado', False) \
                .execute()
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            self._handle_error(e, "obtener_sesion_activa")
            return None
    
    def obtener_sesion(self, sesion_id: str) -> Optional[Dict]:
        """Obtiene una sesión por su ID"""
        try:
            result = self.client.table('sesiones').select('*').eq('id', sesion_id).execute()
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            self._handle_error(e, "obtener_sesion")
            return None
    
    def actualizar_sesion(self, sesion_id: str, data: Dict) -> bool:
        """Actualiza una sesión"""
        try:
            self.client.table('sesiones').update(data).eq('id', sesion_id).execute()
            return True
        except Exception as e:
            self._handle_error(e, "actualizar_sesion")
            return False
    
    def guardar_respuesta_sesion(self, sesion_id: str, pregunta_id: str, respuesta: str, 
                                  es_correcta: bool = None, tiempo_tardado: int = None) -> bool:
        """Guarda una respuesta en la sesión y en el historial"""
        try:
            # Obtener sesión
            sesion = self.obtener_sesion(sesion_id)
            if not sesion:
                return False
            
            # Obtener pregunta
            pregunta = self.obtener_pregunta(pregunta_id)
            if not pregunta:
                return False
            
            # Actualizar respuestas de la sesión
            respuestas = sesion.get('respuestas', [])
            respuestas.append({
                'pregunta_id': pregunta_id,
                'respuesta': respuesta
            })
            
            # Actualizar pregunta actual
            nueva_pregunta = sesion.get('pregunta_actual', 0) + 1
            
            self.client.table('sesiones').update({
                'respuestas': respuestas,
                'pregunta_actual': nueva_pregunta
            }).eq('id', sesion_id).execute()
            
            # Guardar en historial
            historial_data = {
                'sesion_id': sesion_id,
                'pregunta_id': pregunta_id,
                'texto_pregunta': pregunta.get('texto', ''),
                'tipo_pregunta': pregunta.get('tipo', ''),
                'opciones_mostradas': pregunta.get('opciones', []),
                'respuesta_usuario': respuesta,
                'es_correcta': es_correcta,
                'tiempo_tardado': tiempo_tardado,
                'intento_numero': sesion.get('intento_numero', 1)
            }
            
            # Si es abierta manual, guardar como pendiente de calificación
            if pregunta.get('tipo') == 'abierta' and es_correcta is None:
                # Primero insertar historial
                result = self.client.table('historial').insert(historial_data).execute()
                if result.data:
                    historial_id = result.data[0]['id']
                    # Crear registro pendiente
                    self.client.table('respuestas_abiertas_pendientes').insert({
                        'historial_id': historial_id,
                        'calificado': False
                    }).execute()
            else:
                self.client.table('historial').insert(historial_data).execute()
            
            return True
        except Exception as e:
            self._handle_error(e, "guardar_respuesta_sesion")
            return False
    
    def completar_sesion(self, sesion_id: str) -> bool:
        """Marca una sesión como completada"""
        try:
            self.client.table('sesiones').update({
                'completado': True,
                'tiempo_fin': datetime.now().isoformat()
            }).eq('id', sesion_id).execute()
            return True
        except Exception as e:
            self._handle_error(e, "completar_sesion")
            return False
    
    def abandonar_sesion(self, sesion_id: str, pregunta_en_abandono: int = None) -> bool:
        """Marca una sesión como abandonada"""
        try:
            data = {'abandonado': True}
            if pregunta_en_abandono is not None:
                data['pregunta_en_abandono'] = pregunta_en_abandono
            self.client.table('sesiones').update(data).eq('id', sesion_id).execute()
            return True
        except Exception as e:
            self._handle_error(e, "abandonar_sesion")
            return False
    
    def agotar_tiempo_sesion(self, sesion_id: str) -> bool:
        """Marca una sesión como tiempo agotado"""
        try:
            self.client.table('sesiones').update({
                'tiempo_agotado': True,
                'pregunta_actual': 0  # Reinicia desde 0
            }).eq('id', sesion_id).execute()
            return True
        except Exception as e:
            self._handle_error(e, "agotar_tiempo_sesion")
            return False
    
    def contar_intentos_usuario(self, usuario_id: int, cuestionario_id: str) -> int:
        """Cuenta cuántos intentos ha hecho un usuario en un cuestionario"""
        try:
            result = self.client.table('sesiones').select('id', count='exact') \
                .eq('usuario_id', usuario_id) \
                .eq('cuestionario_id', cuestionario_id) \
                .execute()
            return result.count or 0
        except Exception as e:
            self._handle_error(e, "contar_intentos_usuario")
            return 0
    
    # ============================================================
    # HISTORIAL
    # ============================================================
    
    def obtener_historial_usuario(self, usuario_id: int, limit: int = 20) -> List[Dict]:
        """Obtiene el historial de un usuario"""
        try:
            result = self.client.table('sesiones').select('*') \
                .eq('usuario_id', usuario_id) \
                .order('tiempo_inicio', desc=True) \
                .limit(limit) \
                .execute()
            return result.data if result.data else []
        except Exception as e:
            self._handle_error(e, "obtener_historial_usuario")
            return []
    
    def obtener_detalle_historial(self, sesion_id: str) -> List[Dict]:
        """Obtiene el detalle de respuestas de una sesión"""
        try:
            result = self.client.table('historial').select('*') \
                .eq('sesion_id', sesion_id) \
                .order('fecha', desc=False) \
                .execute()
            return result.data if result.data else []
        except Exception as e:
            self._handle_error(e, "obtener_detalle_historial")
            return []
    
    def obtener_historial_completo_admin(self, admin_id: str) -> List[Dict]:
        """Obtiene todo el historial del admin (todas las sesiones)"""
        try:
            # Obtener el cuestionario del admin
            cuestionario = self.client.table('cuestionario').select('id') \
                .eq('admin_id', admin_id) \
                .execute()
            
            if not cuestionario.data:
                return []
            
            cuestionario_ids = [c['id'] for c in cuestionario.data]
            
            result = self.client.table('sesiones').select('*') \
                .in_('cuestionario_id', cuestionario_ids) \
                .order('tiempo_inicio', desc=True) \
                .execute()
            return result.data if result.data else []
        except Exception as e:
            self._handle_error(e, "obtener_historial_completo_admin")
            return []
    
    def contar_historial_total(self) -> int:
        """Cuenta el total de registros en el historial"""
        try:
            result = self.client.rpc('contar_historial_total').execute()
            return result.data if result.data else 0
        except Exception as e:
            self._handle_error(e, "contar_historial_total")
            return 0
    
    def limpiar_historial_antiguo(self, dias: int) -> int:
        """Elimina historial más antiguo de X días. Retorna cantidad eliminados"""
        try:
            result = self.client.rpc('limpiar_historial_antiguo', {'dias': dias}).execute()
            return result.data if result.data else 0
        except Exception as e:
            self._handle_error(e, "limpiar_historial_antiguo")
            return 0
    
    # ============================================================
    # FALLOS DE CONEXIÓN (RESPALDOS)
    # ============================================================
    
    def guardar_fallo_conexion(self, error: str, datos: Dict) -> bool:
        """Guarda un fallo de conexión para procesarlo después"""
        try:
            data = {
                'error': error,
                'datos_afectados': datos,
                'resuelto': False
            }
            self.client.table('fallos_conexion').insert(data).execute()
            return True
        except Exception as e:
            print(f"⚠️ Error al guardar fallo de conexión: {e}")
            return False
    
    def obtener_fallos_pendientes(self) -> List[Dict]:
        """Obtiene todos los fallos de conexión no resueltos"""
        try:
            result = self.client.table('fallos_conexion').select('*') \
                .eq('resuelto', False) \
                .order('fecha', desc=False) \
                .execute()
            return result.data if result.data else []
        except Exception as e:
            self._handle_error(e, "obtener_fallos_pendientes")
            return []
    
    def marcar_fallo_resuelto(self, fallo_id: str) -> bool:
        """Marca un fallo como resuelto"""
        try:
            self.client.table('fallos_conexion').update({'resuelto': True}).eq('id', fallo_id).execute()
            return True
        except Exception as e:
            self._handle_error(e, "marcar_fallo_resuelto")
            return False
    
    # ============================================================
    # RESPUESTAS ABIERTAS PENDIENTES (CALIFICACIÓN MANUAL)
    # ============================================================
    
    def obtener_respuestas_abiertas_pendientes(self, admin_id: str) -> List[Dict]:
        """Obtiene todas las respuestas abiertas pendientes de calificar"""
        try:
            # Obtener IDs de preguntas abiertas del admin
            preguntas_result = self.client.table('preguntas').select('id') \
                .eq('admin_id', admin_id) \
                .eq('tipo', 'abierta') \
                .execute()
            
            if not preguntas_result.data:
                return []
            
            pregunta_ids = [p['id'] for p in preguntas_result.data]
            
            # Obtener historial de esas preguntas que están pendientes
            result = self.client.table('respuestas_abiertas_pendientes') \
                .select('*, historial(*)') \
                .eq('calificado', False) \
                .in_('historial.pregunta_id', pregunta_ids) \
                .execute()
            
            return result.data if result.data else []
        except Exception as e:
            self._handle_error(e, "obtener_respuestas_abiertas_pendientes")
            return []
    
    def calificar_respuesta_abierta(self, historial_id: str, calificacion: bool) -> bool:
        """Califica una respuesta abierta"""
        try:
            # Actualizar la tabla de pendientes
            self.client.table('respuestas_abiertas_pendientes') \
                .update({
                    'calificado': True,
                    'calificacion': calificacion,
                    'fecha_calificacion': datetime.now().isoformat()
                }) \
                .eq('historial_id', historial_id) \
                .execute()
            
            # Actualizar el historial con la calificación
            self.client.table('historial') \
                .update({'es_correcta': calificacion}) \
                .eq('id', historial_id) \
                .execute()
            
            return True
        except Exception as e:
            self._handle_error(e, "calificar_respuesta_abierta")
            return False
    
    # ============================================================
    # ESTADÍSTICAS PARA EL ADMIN
    # ============================================================
    
    def obtener_estadisticas_admin(self, admin_id: str) -> Dict:
        """Obtiene estadísticas generales para el admin"""
        try:
            # Total de preguntas
            total_preguntas = self.contar_preguntas(admin_id)
            
            # Total de sesiones
            cuestionario = self.client.table('cuestionario').select('id') \
                .eq('admin_id', admin_id) \
                .execute()
            
            total_sesiones = 0
            total_completados = 0
            total_abandonados = 0
            total_tiempo_agotado = 0
            promedio_aciertos = 0
            
            if cuestionario.data:
                cuestionario_ids = [c['id'] for c in cuestionario.data]
                sesiones_result = self.client.table('sesiones').select('*') \
                    .in_('cuestionario_id', cuestionario_ids) \
                    .execute()
                
                if sesiones_result.data:
                    sesiones = sesiones_result.data
                    total_sesiones = len(sesiones)
                    total_completados = sum(1 for s in sesiones if s.get('completado'))
                    total_abandonados = sum(1 for s in sesiones if s.get('abandonado'))
                    total_tiempo_agotado = sum(1 for s in sesiones if s.get('tiempo_agotado'))
            
            # Total en historial
            total_historial = self.contar_historial_total()
            
            return {
                'total_preguntas': total_preguntas,
                'total_sesiones': total_sesiones,
                'total_completados': total_completados,
                'total_abandonados': total_abandonados,
                'total_tiempo_agotado': total_tiempo_agotado,
                'total_historial': total_historial
            }
        except Exception as e:
            self._handle_error(e, "obtener_estadisticas_admin")
            return {}
    
    # ============================================================
    # CONTEO DE ALMACENAMIENTO (SUPABASE STORAGE)
    # ============================================================
    
    def contar_almacenamiento_usado(self) -> float:
        """Estima el almacenamiento usado en MB (solo para aviso)"""
        # Esta función es aproximada. Supabase no expone el tamaño fácilmente
        # Contamos imágenes en preguntas y estimamos
        try:
            result = self.client.table('preguntas').select('imagen_url') \
                .neq('imagen_url', '') \
                .execute()
            
            # Estimar 200KB por imagen con URL
            total_imagenes = len(result.data) if result.data else 0
            estimado_mb = (total_imagenes * 0.2)  # 200KB = 0.2MB
            
            return estimado_mb
        except Exception as e:
            self._handle_error(e, "contar_almacenamiento_usado")
            return 0.0

# ============================================================
# INSTANCIA ÚNICA
# ============================================================

db = Database()

# ============================================================
# FIN DE database.py
# ============================================================