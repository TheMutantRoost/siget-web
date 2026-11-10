export type Rol = "Administrador" | "Docente" | "Operador";

export interface UsuarioSesion {
  id: number;
  username: string;
  nombre_completo: string;
  rol: Rol;
  debe_cambiar_password: boolean;
  docente_id: number | null;
  ultimo_acceso: string | null;
}

export interface Pagina<T> {
  items: T[];
  total: number;
  pagina: number;
  tamano: number;
}

export interface Sede { id: number; nombre: string; direccion: string; estado: "Activo" | "Inactivo" }
export interface Ambiente { id: number; sede_id: number; codigo: string; nombre: string; capacidad: number | null; estado: "Activo" | "Inactivo"; sede: Sede }
export interface Area { id: number; nombre: string; activo: boolean }
export interface Facultad { id: number; codigo: string; nombre: string; activo: boolean }
export interface Carrera { id: number; facultad_id: number; codigo: string; nombre: string; activo: boolean; facultad: Facultad }
export interface Ciclo { id: number; nombre: string; fecha_inicio: string; fecha_fin: string; activo: boolean }
export interface TipoDocumento { id: number; codigo: string; nombre: string; longitud_min: number; longitud_max: number; solo_digitos: boolean; activo: boolean }

export type EstadoEstudiante = "Activo" | "Inactivo" | "Egresado";
export interface Estudiante {
  id: number;
  tipo_documento_id: number;
  numero_documento: string;
  codigo_universitario: string;
  nombres: string;
  apellido_paterno: string;
  apellido_materno: string | null;
  fecha_nacimiento: string | null;
  carrera_id: number;
  ciclo_actual: number | null;
  email: string | null;
  telefono: string | null;
  estado: EstadoEstudiante;
  tipo_documento: TipoDocumento;
  carrera: Carrera;
}

export interface Disponibilidad { id: number; dia_semana: number; hora_inicio: string; hora_fin: string; vigente_desde: string | null; vigente_hasta: string | null }
export interface Docente {
  id: number;
  usuario_id: number;
  tipo_documento_id: number;
  numero_documento: string;
  nombres: string;
  apellido_paterno: string;
  apellido_materno: string | null;
  nombre_completo: string;
  email: string;
  telefono: string | null;
  activo: boolean;
  areas: Area[];
  disponibilidad: Disponibilidad[];
}

export type EstadoTaller = "Activo" | "Suspendido" | "Finalizado";
export interface Bloque { id: number; dia_semana: number; hora_inicio: string; hora_fin: string; ambiente_id: number | null }
export interface Taller {
  id: number;
  codigo: string;
  nombre: string;
  descripcion: string | null;
  area: Area;
  ciclo: Ciclo;
  docente: { id: number; nombre_completo: string };
  sede: Sede;
  ambiente: Ambiente | null;
  cupo_maximo: number;
  horas_totales: number;
  umbral_aptitud: number;
  fecha_inicio: string;
  fecha_fin: string;
  estado: EstadoTaller;
  inscripciones_bloqueadas: boolean;
  motivo_bloqueo: string | null;
  horarios: Bloque[];
}
export interface TallerDetalle extends Taller {
  inscritos_activos: number;
  sesiones_realizadas: number;
  sesiones_programadas: number;
  inscripciones_cerradas: boolean;
  en_riesgo: boolean;
}

export type EstadoSesion = "Programada" | "Realizada" | "Cancelada" | "Reprogramada";
export interface Sesion { id: number; taller_id: number; numero_sesion: number; fecha: string; hora_inicio: string; hora_fin: string; ambiente_id: number | null; estado: EstadoSesion; motivo_estado: string | null }

export interface EstudianteBreve { id: number; codigo_universitario: string; numero_documento: string; nombres: string; apellido_paterno: string; apellido_materno: string | null }
export interface Inscripcion { id: number; taller_id: number; estado: "Activo" | "Retirado"; fecha_inscripcion: string; estudiante: EstudianteBreve }

export type EstadoAsistencia = "P" | "A" | "J";
export interface FilaHoja { inscripcion_id: number; estudiante: EstudianteBreve; estado: EstadoAsistencia | null; observacion: string | null }
export interface HojaAsistencia { sesion: Sesion; taller_id: number; taller: string; congelada: boolean; primer_registro: boolean; puede_editar: boolean; motivo_bloqueo: string | null; filas: FilaHoja[] }

export interface Resultado { sesiones_correspondientes: number; validas: number; faltas: number; porcentaje: string; calculable: boolean; en_riesgo: boolean | null; apto: boolean | null }
export interface FilaResumen { inscripcion_id: number; estudiante: EstudianteBreve; resultado: Resultado }
export interface Avance { taller_id: number; umbral_aptitud: number; puede_generar: boolean; definitivo: boolean; sesiones_programadas: number; sesiones_realizadas: number; motivo: string | null; filas: FilaResumen[] }

export interface Lista { id: number; taller_id: number; version: number; estado: "Vigente" | "Anulada"; umbral_aplicado: number; sesiones_realizadas: number; total_inscritos: number; total_aptos: number; total_excluidos: number; generada_en: string; motivo_anulacion: string | null; anulada_en: string | null }
export interface DetalleLista { estudiante_id: number; tipo_documento: string; numero_documento: string; codigo_universitario: string; nombres: string; apellido_paterno: string; apellido_materno: string | null; carrera: string; sesiones_correspondientes: number; sesiones_validas: number; porcentaje: string; es_apto: boolean; excluido_manual: boolean; motivo_exclusion: string | null }
export interface ListaDetalle extends Lista { detalle: DetalleLista[] }

export interface TallerIndicador { id: number; codigo: string; nombre: string; sede: string; fecha_fin: string; inscritos: number; en_riesgo: number; porcentaje_promedio: number | null }
export interface SesionVencida { sesion_id: number; taller_id: number; taller: string; numero: number; fecha: string; inicio: string; fin: string }
export interface Dashboard {
  estudiantes_activos: number;
  docentes_activos: number;
  talleres_activos: number;
  talleres_finalizados: number;
  inscripciones_activas: number;
  asistencia_general: number | null;
  aptos: number;
  no_aptos: number;
  estudiantes_en_riesgo: number;
  talleres_en_riesgo: TallerIndicador[];
  proximos_a_finalizar: TallerIndicador[];
  sesiones_vencidas: SesionVencida[];
}

export interface UsuarioAdmin { id: number; username: string; email: string; nombres: string; apellido_paterno: string; apellido_materno: string | null; activo: boolean; debe_cambiar_password: boolean; ultimo_acceso: string | null; intentos_fallidos: number; bloqueado_hasta: string | null; rol_nombre: Rol }
export interface RegistroAuditoria { id: number; usuario_id: number | null; ip: string | null; modulo: string; evento: string; accion: string; entidad: string | null; registro_id: string | null; datos_anteriores: Record<string, unknown> | null; datos_nuevos: Record<string, unknown> | null; created_at: string }
export interface Parametro { clave: string; valor: number; minimo: number; maximo: number; descripcion: string; updated_at: string }
