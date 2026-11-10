import { Plus } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router";

import { api, mensajeDeError } from "../api/cliente";
import type { Ambiente, Area, Ciclo, Docente, Pagina, Sede, Taller } from "../api/tipos";
import { Alerta, AreaTexto, Boton, Campo, Cargando, Celda, Encabezado, Insignia, Modal, Paginacion, Selector, Tabla, Tarjeta } from "../components/ui";
import { useAuth } from "../contexts/Auth";
import { useApi } from "../hooks/useApi";
import { DIAS_CORTOS, fecha, hora } from "../utils/formato";

export function colorEstado(estado: string): "verde" | "ambar" | "gris" {
  return estado === "Activo" ? "verde" : estado === "Suspendido" ? "ambar" : "gris";
}

interface DatosTaller {
  codigo: string; nombre: string; descripcion: string; area_id: string; ciclo_academico_id: string; docente_id: string;
  sede_id: string; ambiente_id: string; cupo_maximo: string; horas_totales: string; umbral_aptitud: string;
  fecha_inicio: string; fecha_fin: string; justificacion_area: string;
}

export function FormularioTaller({ taller, alGuardar, alCancelar }: { taller?: Taller; alGuardar: (t: Taller) => void; alCancelar: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const areas = useApi<Area[]>("/catalogos/areas");
  const ciclos = useApi<Ciclo[]>("/catalogos/ciclos");
  const sedes = useApi<Sede[]>("/catalogos/sedes");
  const { register, handleSubmit, watch, formState: { isSubmitting } } = useForm<DatosTaller>({
    defaultValues: taller
      ? { nombre: taller.nombre, descripcion: taller.descripcion ?? "", docente_id: String(taller.docente.id), ambiente_id: taller.ambiente ? String(taller.ambiente.id) : "",
          cupo_maximo: String(taller.cupo_maximo), horas_totales: String(taller.horas_totales), umbral_aptitud: String(taller.umbral_aptitud), fecha_fin: taller.fecha_fin,
          area_id: String(taller.area.id), sede_id: String(taller.sede.id), justificacion_area: "" }
      : { umbral_aptitud: "80", justificacion_area: "" },
  });
  const areaId = watch("area_id");
  const sedeId = watch("sede_id");
  const [verTodos, setVerTodos] = useState(false);
  const docentes = useApi<Docente[]>("/docentes", { area_id: verTodos ? "" : areaId, solo_activos: true });
  const ambientes = useApi<Ambiente[]>(sedeId ? "/catalogos/ambientes" : null, { sede_id: sedeId });
  const docenteSel = (docentes.datos ?? []).find((d) => String(d.id) === watch("docente_id"));
  const requiereExcepcion = !!docenteSel && !docenteSel.areas.some((a) => String(a.id) === areaId);

  const enviar = async (d: DatosTaller) => {
    setError(null);
    const numero = (v: string) => (v === "" ? null : Number(v));
    try {
      const r = taller
        ? await api.patch<Taller>(`/talleres/${taller.id}`, { nombre: d.nombre, descripcion: d.descripcion || null, docente_id: Number(d.docente_id), ambiente_id: numero(d.ambiente_id),
            cupo_maximo: Number(d.cupo_maximo), horas_totales: Number(d.horas_totales), umbral_aptitud: Number(d.umbral_aptitud), fecha_fin: d.fecha_fin, justificacion_area: d.justificacion_area || null })
        : await api.post<Taller>("/talleres", { ...d, descripcion: d.descripcion || null, area_id: Number(d.area_id), ciclo_academico_id: Number(d.ciclo_academico_id), docente_id: Number(d.docente_id),
            sede_id: Number(d.sede_id), ambiente_id: numero(d.ambiente_id), cupo_maximo: Number(d.cupo_maximo), horas_totales: Number(d.horas_totales), umbral_aptitud: Number(d.umbral_aptitud),
            justificacion_area: d.justificacion_area || null });
      alGuardar(r.data);
    } catch (e) {
      setError(mensajeDeError(e));
    }
  };

  return (
    <form onSubmit={handleSubmit(enviar)} className="space-y-4" noValidate>
      {error && <Alerta tipo="error">{error}</Alerta>}
      <fieldset className="grid gap-3 sm:grid-cols-3">
        <legend className="mb-2 text-sm font-semibold text-slate-700">Datos generales</legend>
        {!taller && <Campo etiqueta="Código" obligatorio {...register("codigo")} />}
        <div className={taller ? "sm:col-span-3" : "sm:col-span-2"}><Campo etiqueta="Nombre" obligatorio {...register("nombre")} /></div>
        <div className="sm:col-span-3"><AreaTexto etiqueta="Descripción" {...register("descripcion")} /></div>
        {!taller && <Selector etiqueta="Área" obligatorio vacio="Seleccione…" opciones={(areas.datos ?? []).filter((a) => a.activo).map((a) => ({ valor: a.id, texto: a.nombre }))} {...register("area_id")} />}
        {!taller && <Selector etiqueta="Ciclo académico" obligatorio vacio="Seleccione…" opciones={(ciclos.datos ?? []).map((c) => ({ valor: c.id, texto: `${c.nombre}${c.activo ? " (activo)" : ""}` }))} {...register("ciclo_academico_id")} />}
      </fieldset>
      <fieldset className="grid gap-3 sm:grid-cols-3">
        <legend className="mb-2 text-sm font-semibold text-slate-700">Docente y lugar</legend>
        <div className="sm:col-span-1">
          <Selector etiqueta="Docente responsable" obligatorio vacio={areaId ? "Seleccione…" : "Elija primero el área"} opciones={(docentes.datos ?? []).map((d) => ({ valor: d.id, texto: d.nombre_completo }))} {...register("docente_id")} />
          <label className="mt-1 flex items-center gap-2 text-xs text-slate-600"><input type="checkbox" checked={verTodos} onChange={(e) => setVerTodos(e.target.checked)} /> Mostrar docentes de otras áreas (excepción)</label>
        </div>
        {!taller && <Selector etiqueta="Sede" obligatorio vacio="Seleccione…" opciones={(sedes.datos ?? []).filter((s) => s.estado === "Activo").map((s) => ({ valor: s.id, texto: s.nombre }))} {...register("sede_id")} />}
        <Selector etiqueta="Ambiente por defecto" vacio="Sin ambiente" opciones={(ambientes.datos ?? []).filter((a) => a.estado === "Activo").map((a) => ({ valor: a.id, texto: `${a.codigo} · ${a.nombre}${a.capacidad ? ` (${a.capacidad})` : ""}` }))} {...register("ambiente_id")} />
        {requiereExcepcion && (
          <div className="sm:col-span-3">
            <AreaTexto etiqueta="Justificación de la excepción de área" obligatorio ayuda="El docente no está autorizado para esta área. Quedará registrado en la auditoría." {...register("justificacion_area")} />
          </div>
        )}
      </fieldset>
      <fieldset className="grid gap-3 sm:grid-cols-3">
        <legend className="mb-2 text-sm font-semibold text-slate-700">Cupo, horas y fechas</legend>
        <Campo etiqueta="Cupo máximo" type="number" min={1} obligatorio {...register("cupo_maximo")} />
        <Campo etiqueta="Horas totales" type="number" min={1} obligatorio {...register("horas_totales")} />
        <Campo etiqueta="Umbral de aptitud (%)" type="number" min={50} max={100} obligatorio ayuda="Entre 50 y 100" {...register("umbral_aptitud")} />
        {!taller && <Campo etiqueta="Fecha de inicio" type="date" obligatorio {...register("fecha_inicio")} />}
        <Campo etiqueta="Fecha de fin" type="date" obligatorio {...register("fecha_fin")} />
      </fieldset>
      <div className="flex justify-end gap-2">
        <Boton variante="secundario" onClick={alCancelar}>Cancelar</Boton>
        <Boton type="submit" cargando={isSubmitting}>{taller ? "Guardar cambios" : "Crear taller"}</Boton>
      </div>
    </form>
  );
}

export function Talleres() {
  const { usuario } = useAuth();
  const navegar = useNavigate();
  const esAdmin = usuario?.rol === "Administrador";
  const [pagina, setPagina] = useState(1);
  const [filtros, setFiltros] = useState({ sede_id: "", estado: "", texto: "" });
  const sedes = useApi<Sede[]>("/catalogos/sedes");
  const { datos, cargando, error } = useApi<Pagina<Taller>>("/talleres", { pagina, tamano: 20, ...filtros });
  const [nuevo, setNuevo] = useState(false);

  return (
    <>
      <Encabezado titulo={esAdmin ? "Talleres" : "Mis talleres"} descripcion="Horarios, sesiones, inscritos, asistencia y aptos" acciones={esAdmin && <Boton icono={<Plus className="h-4 w-4" />} onClick={() => setNuevo(true)}>Nuevo taller</Boton>} />
      <Tarjeta>
        <div className="mb-3 grid gap-3 sm:grid-cols-3">
          <Campo etiqueta="Buscar" placeholder="Código o nombre" value={filtros.texto} onChange={(e) => { setFiltros((f) => ({ ...f, texto: e.target.value })); setPagina(1); }} />
          <Selector etiqueta="Sede" value={filtros.sede_id} onChange={(e) => { setFiltros((f) => ({ ...f, sede_id: e.target.value })); setPagina(1); }} vacio="Todas" opciones={(sedes.datos ?? []).map((s) => ({ valor: s.id, texto: s.nombre }))} />
          <Selector etiqueta="Estado" value={filtros.estado} onChange={(e) => { setFiltros((f) => ({ ...f, estado: e.target.value })); setPagina(1); }} vacio="Todos" opciones={["Activo", "Suspendido", "Finalizado"].map((x) => ({ valor: x, texto: x }))} />
        </div>
        {error && <Alerta tipo="error">{error}</Alerta>}
        {cargando || !datos ? <Cargando /> : (
          <>
            <Tabla encabezados={["Taller", "Área", "Docente", "Sede", "Horario", "Fechas", "Estado"]} vacio={!datos.items.length}>
              {datos.items.map((t) => (
                <tr key={t.id} className="hover:bg-slate-50">
                  <Celda><Link to={`/talleres/${t.id}`} className="font-medium text-marca-700 hover:underline">{t.codigo} · {t.nombre}</Link></Celda>
                  <Celda>{t.area.nombre}</Celda>
                  <Celda>{t.docente.nombre_completo}</Celda>
                  <Celda>{t.sede.nombre}</Celda>
                  <Celda className="text-xs">{t.horarios.map((b) => `${DIAS_CORTOS[b.dia_semana]} ${hora(b.hora_inicio)}–${hora(b.hora_fin)}`).join(" · ") || <Insignia color="ambar">Sin horario</Insignia>}</Celda>
                  <Celda>{fecha(t.fecha_inicio)} – {fecha(t.fecha_fin)}</Celda>
                  <Celda><Insignia color={colorEstado(t.estado)}>{t.estado}</Insignia></Celda>
                </tr>
              ))}
            </Tabla>
            <Paginacion pagina={pagina} tamano={20} total={datos.total} alCambiar={setPagina} />
          </>
        )}
      </Tarjeta>
      <Modal abierto={nuevo} titulo="Nuevo taller" alCerrar={() => setNuevo(false)} ancho="max-w-3xl">
        {nuevo && <FormularioTaller alCancelar={() => setNuevo(false)} alGuardar={(t) => navegar(`/talleres/${t.id}?pestana=horario`)} />}
      </Modal>
    </>
  );
}
