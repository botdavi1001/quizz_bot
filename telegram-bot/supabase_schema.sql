-- ============================================================
-- BOT DE TELEGRAM - CUESTIONARIOS
-- Esquema completo para Supabase
-- ============================================================

-- 1. TABLA: admins
CREATE TABLE IF NOT EXISTS admins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_id BIGINT UNIQUE NOT NULL,
    username TEXT,
    first_name TEXT,
    config JSONB DEFAULT '{
        "notificar_admin": true,
        "tiempo_global_default": 30,
        "mostrar_correctas": true,
        "reintentos_default": 3,
        "formato_reporte": "resumido",
        "tolerancia_abiertas": 80
    }'::jsonb,
    registrado_en TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. TABLA: preguntas
CREATE TABLE IF NOT EXISTS preguntas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_id UUID REFERENCES admins(id) ON DELETE CASCADE,
    texto TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('multiple', 'vf', 'abierta')),
    opciones JSONB,
    respuestas_correctas JSONB,
    tiempo_segundos INTEGER DEFAULT 30,
    imagen_url TEXT DEFAULT '',
    video_url TEXT DEFAULT '',
    enlace_url TEXT DEFAULT '',
    fecha_creacion TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. TABLA: cuestionario (solo uno activo a la vez)
CREATE TABLE IF NOT EXISTS cuestionario (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_id UUID REFERENCES admins(id) ON DELETE CASCADE,
    nombre TEXT NOT NULL,
    preguntas_ids JSONB NOT NULL,
    seleccion_tipo TEXT NOT NULL CHECK (seleccion_tipo IN ('fijas', 'azar', 'filtro')),
    activo BOOLEAN DEFAULT TRUE,
    reintentos INTEGER DEFAULT 3,
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. TABLA: sesiones
CREATE TABLE IF NOT EXISTS sesiones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id BIGINT NOT NULL,
    username TEXT,
    first_name TEXT,
    cuestionario_id UUID REFERENCES cuestionario(id) ON DELETE CASCADE,
    pregunta_actual INTEGER DEFAULT 0,
    respuestas JSONB DEFAULT '[]'::jsonb,
    tiempo_inicio TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    tiempo_fin TIMESTAMP WITH TIME ZONE,
    completado BOOLEAN DEFAULT FALSE,
    abandonado BOOLEAN DEFAULT FALSE,
    tiempo_agotado BOOLEAN DEFAULT FALSE,
    intento_numero INTEGER DEFAULT 1,
    pregunta_en_abandono INTEGER DEFAULT 0
);

-- 5. TABLA: historial
CREATE TABLE IF NOT EXISTS historial (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sesion_id UUID REFERENCES sesiones(id) ON DELETE CASCADE,
    pregunta_id UUID REFERENCES preguntas(id) ON DELETE SET NULL,
    texto_pregunta TEXT,
    tipo_pregunta TEXT,
    opciones_mostradas JSONB,
    respuesta_usuario TEXT,
    es_correcta BOOLEAN,
    tiempo_tardado INTEGER,
    fecha TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    intento_numero INTEGER DEFAULT 1
);

-- 6. TABLA: fallos_conexion
CREATE TABLE IF NOT EXISTS fallos_conexion (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fecha TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    error TEXT,
    datos_afectados JSONB,
    resuelto BOOLEAN DEFAULT FALSE
);

-- 7. TABLA: respuestas_abiertas_pendientes (para calificación manual)
CREATE TABLE IF NOT EXISTS respuestas_abiertas_pendientes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    historial_id UUID REFERENCES historial(id) ON DELETE CASCADE,
    calificado BOOLEAN DEFAULT FALSE,
    calificacion BOOLEAN,  -- TRUE = correcta, FALSE = incorrecta
    fecha_calificacion TIMESTAMP WITH TIME ZONE
);

-- ============================================================
-- ÍNDICES PARA OPTIMIZAR CONSULTAS
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_historial_usuario ON sesiones (usuario_id);
CREATE INDEX IF NOT EXISTS idx_historial_fecha ON historial (fecha);
CREATE INDEX IF NOT EXISTS idx_sesiones_usuario ON sesiones (usuario_id);
CREATE INDEX IF NOT EXISTS idx_sesiones_cuestionario ON sesiones (cuestionario_id);
CREATE INDEX IF NOT EXISTS idx_preguntas_admin ON preguntas (admin_id);
CREATE INDEX IF NOT EXISTS idx_preguntas_fecha ON preguntas (fecha_creacion);
CREATE INDEX IF NOT EXISTS idx_fallos_resuelto ON fallos_conexion (resuelto);

-- ============================================================
-- FUNCIÓN: CONTAR REGISTROS DE HISTORIAL
-- ============================================================

CREATE OR REPLACE FUNCTION contar_historial_total()
RETURNS BIGINT AS $$
BEGIN
    RETURN (SELECT COUNT(*) FROM historial);
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- FUNCIÓN: LIMPIAR HISTORIAL ANTIGUO (más de X días)
-- ============================================================

CREATE OR REPLACE FUNCTION limpiar_historial_antiguo(dias INTEGER)
RETURNS INTEGER AS $$
DECLARE
    eliminados INTEGER;
BEGIN
    WITH eliminados_cte AS (
        DELETE FROM historial
        WHERE fecha < NOW() - (dias || ' days')::INTERVAL
        RETURNING id
    )
    SELECT COUNT(*) INTO eliminados FROM eliminados_cte;
    RETURN eliminados;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- DISPARADOR: ACTUALIZAR TIEMPO_FIN EN SESIONES AL COMPLETAR
-- ============================================================

CREATE OR REPLACE FUNCTION actualizar_tiempo_fin()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.completado = TRUE AND OLD.completado = FALSE THEN
        NEW.tiempo_fin = NOW();
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_actualizar_tiempo_fin
BEFORE UPDATE ON sesiones
FOR EACH ROW
EXECUTE FUNCTION actualizar_tiempo_fin();

-- ============================================================
-- CONFIGURACIÓN INICIAL (opcional, descomentar si quieres)
-- ============================================================

-- INSERT INTO admins (telegram_id, username, first_name)
-- VALUES (0, 'admin', 'Admin')
-- ON CONFLICT (telegram_id) DO NOTHING;

-- ============================================================
-- FIN DEL ESQUEMA
-- ============================================================