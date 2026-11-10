import { AlertTriangle, ArrowLeft, Ban, ClipboardCheck, Download, FileCheck2, Lock, Pencil, Plus, Trash2, Unlock, UserMinus } from "lucide-react";
import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router";

import { api, descargar, detallesDeConflicto, mensajeDeError } from "../api/cliente";
import type { Ambiente, Avance, Estudiante, Inscripcion, Lista, ListaDetalle, Pagina, Sesion, Taller, TallerDetalle as Detalle } from "../api/tipos";
import { Alerta, AreaTexto, Boton, Campo, Cargando, Celda, Encabezado, Insignia, Modal, Pestanas, Selector, Tabla, Tarjeta, Vacio } from "../components/ui";
import { useAuth } from "../contexts/Auth";
import { useNotificar } from "../contexts/Notificaciones";
import { useApi } from "../hooks/useApi";
import { DIAS, DIAS_CORTOS, diaDeFecha, fecha, fechaHora, hora, nombreEstudiante } from "../utils/formato";
import { colorEstado, FormularioTaller } from "./Talleres";

type Pestana = "resumen" | "horario" | "sesiones" | "inscritos" | "asistencia" | "aptos";

function ConflictoDetalle({ error }: { error: unknown }) {
  const detalles = detallesDeConflicto(error);
  if (!detalles.length || !("taller_actual" in (detalles[0] ?? {}))) return null;
  return (
    <ul className="mt-2 list-disc pl-5 text-xs">
      {detalles.slice(0, 5).map((d, i) => (
        <li key={i}>{d.dia} {fecha(d.fecha)}: {d.taller_actual} ({d.inicio_actual}–{d.fin_actual}, {d.sede_actual}) frente a {d.taller_nuevo} ({d.inicio}–{d.fin}, {d.sede}) — {d.motivo}</li>
      ))}
    </ul>
  );
}

function PedirMotivo({ titulo, abierto, alCerrar, alConfirmar, peligro = false, texto }: { titulo: string; abierto: boolean; alCerrar: () => void; alConfirmar: (motivo: string) => Promise<void>; peligro?: boolean; texto?: string }) {
  const [motivo, setMotivo] = useState("");
  const [cargando, setCargando] = useState(false);
  return (
    <Modal abierto={abierto} titulo={titulo} alCerrar={alCerrar} pie={
      <>
        <Boton variante="secundario" onClick={alCerrar}>Cancelar</Boton>
        <Boton variante={peligro ? "peligro" : "primario"} disabled={motivo.trim().length < 3} cargando={cargando}
          onClick={async () => { setCargando(true); try { await alConfirmar(motivo.trim()); setMotivo(""); } finally { setCargando(false); } }}>Confirmar</Boton>
      </>
    }>
      {texto && <p className="mb-3 text-sm text-slate-600">{texto}</p>}
      <AreaTexto etiqueta="Motivo" obligatorio value={motivo} onChange={(e) => setMotivo(e.target.value)} ayuda="Queda registrado en la auditoría." />
    </Modal>
  );
}

// ---------- Resumen ----------
function Resumen({ taller, esAdmin, recargar }: { taller: Detalle; esAdmin: boolean; recargar: () => void }) {
  const notificar = useNotificar();
  const [accion, setAccion] = useState<null | "Suspendido" | "Finalizado" | "Activo" | "bloquear">(null);
  const [editando, setEditando] = useState(false);
  const ejecutar = async (motivo: string) => {
    try {
      if (accion === "bloquear") await api.post(`/talleres/${taller.id}/bloqueo-inscripciones`, { bloquear: true, motivo });
      else await api.post(`/talleres/${taller.id}/estado`, { estado: accion, motivo });
      notificar.exito("Cambio registrado.");
      setAccion(null);
      recargar();
    } catch (e) {
      notificar.error(mensajeDeError(e));
    }
  };
  const desbloquear = async () => {
    try {
      await api.post(`/talleres/${taller.id}/bloqueo-inscripciones`, { bloquear: false });
      notificar.exito("Inscripciones desbloqueadas.");
      recargar();
    } catch (e) {
      notificar.error(mensajeDeError(e));
    }
  };
  const dato = (titulo: string, valor: React.ReactNode) => (
    <div><dt className="text-xs text-slate-500">{titulo}</dt><dd className="text-sm font-medium">{valor}</dd></div>
  );
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {taller.en_riesgo && <Insignia color="ambar">Con estudiantes en riesgo</Insignia>}
        {taller.inscripciones_cerradas && <Insignia color="gris">Inscripciones cerradas</Insignia>}
        {taller.inscripciones_bloqueadas && <Insignia color="rojo">Inscripciones bloqueadas: {taller.motivo_bloqueo}</Insignia>}
      </div>
      <dl className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {dato("Área", taller.area.nombre)}
        {dato("Ciclo", taller.ciclo.nombre)}
        {dato("Docente", taller.docente.nombre_completo)}
        {dato("Sede", taller.sede.nombre)}
        {dato("Ambiente", taller.ambiente ? `${taller.ambiente.codigo} · ${taller.ambiente.nombre}` : "—")}
        {dato("Fechas", `${fecha(taller.fecha_inicio)} – ${fecha(taller.fecha_fin)}`)}
        {dato("Cupo", `${taller.inscritos_activos} / ${taller.cupo_maximo}`)}
        {dato("Umbral de aptitud", `${taller.umbral_aptitud} %`)}
        {dato("Horas totales", taller.horas_totales)}
        {dato("Sesiones realizadas", taller.sesiones_realizadas)}
        {dato("Sesiones programadas", taller.sesiones_programadas)}
      </dl>
      {taller.descripcion && <p className="text-sm text-slate-600">{taller.descripcion}</p>}
      {esAdmin && taller.estado !== "Finalizado" && (
        <div className="flex flex-wrap gap-2 border-t border-slate-200 pt-4">
          <Boton variante="secundario" icono={<Pencil className="h-4 w-4" />} onClick={() => setEditando(true)}>Editar</Boton>
          {taller.inscripciones_bloqueadas
            ? <Boton variante="secundario" icono={<Unlock className="h-4 w-4" />} onClick={desbloquear}>Desbloquear inscripciones</Boton>
            : <Boton variante="secundario" icono={<Lock className="h-4 w-4" />} onClick={() => setAccion("bloquear")}>Bloquear inscripciones</Boton>}
          {taller.estado === "Activo" && <Boton variante="secundario" onClick={() => setAccion("Suspendido")}>Suspender</Boton>}
          {taller.estado === "Suspendido" && <Boton variante="secundario" onClick={() => setAccion("Activo")}>Reactivar</Boton>}
          <Boton variante="peligro" onClick={() => setAccion("Finalizado")}>Finalizar taller</Boton>
        </div>
      )}
      <PedirMotivo abierto={!!accion} alCerrar={() => setAccion(null)} alConfirmar={ejecutar} peligro={accion === "Finalizado"}
        titulo={accion === "bloquear" ? "Bloquear inscripciones" : `Cambiar estado a ${accion}`}
        texto={accion === "Finalizado" ? "Un taller finalizado ya no se puede modificar." : undefined} />
      <Modal abierto={editando} titulo="Editar taller" alCerrar={() => setEditando(false)} ancho="max-w-3xl">
        {editando && <FormularioTaller taller={taller as Taller} alCancelar={() => setEditando(false)} alGuardar={() => { setEditando(false); notificar.exito("Taller actualizado."); recargar(); }} />}
      </Modal>
    </div>
  );
}

// ---------- Horario ----------
interface BloqueEd { dia_semana: number; hora_inicio: string; hora_fin: string; ambiente_id: string }
function Horario({ taller, esAdmin, recargar }: { taller: Detalle; esAdmin: boolean; recargar: () => void }) {
  const notificar = useNotificar();
  const ambientes = useApi<Ambiente[]>("/catalogos/ambientes", { sede_id: taller.sede.id });
  const [editando, setEditando] = useState(!taller.horarios.length && esAdmin);
  const [bloques, setBloques] = useState<BloqueEd[]>(taller.horarios.map((b) => ({ dia_semana: b.dia_semana, hora_inicio: hora(b.hora_inicio), hora_fin: hora(b.hora_fin), ambiente_id: b.ambiente_id ? String(b.ambiente_id) : "" })));
  const [motivo, setMotivo] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [guardando, setGuardando] = useState(false);
  const cambiar = (i: number, campo: keyof BloqueEd, valor: string) => setBloques((b) => b.map((x, j) => (j === i ? { ...x, [campo]: campo === "dia_semana" ? Number(valor) : valor } : x)));
  const guardar = async () => {
    setError(null);
    const invalido = bloques.find((b) => b.hora_fin <= b.hora_inicio);
    if (invalido) { setError({ mensaje: "En cada bloque la hora final debe ser posterior a la inicial." }); return; }
    setGuardando(true);
    try {
      await api.put(`/talleres/${taller.id}/horarios`, { motivo: motivo || null, bloques: bloques.map((b) => ({ ...b, ambiente_id: b.ambiente_id ? Number(b.ambiente_id) : null })) });
      notificar.exito("Horario guardado y sesiones generadas.");
      setEditando(false);
      recargar();
    } catch (e) {
      setError(e);
    } finally {
      setGuardando(false);
    }
  };
  const nombreAmbiente = (id: number | null) => {
    const a = (ambientes.datos ?? []).find((x) => x.id === id) ?? taller.ambiente;
    return a ? a.codigo : "Sin ambiente";
  };
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-7" aria-label="Calendario semanal">
        {[1, 2, 3, 4, 5, 6, 7].map((d) => (
          <div key={d} className="rounded-md border border-slate-200 bg-slate-50 p-2">
            <p className="mb-2 text-xs font-semibold text-slate-600">{DIAS[d]}</p>
            {taller.horarios.filter((b) => b.dia_semana === d).map((b) => (
              <div key={b.id} className="mb-1 rounded bg-marca-700 px-2 py-1 text-xs text-white">
                {hora(b.hora_inicio)}–{hora(b.hora_fin)}<br /><span className="text-marca-100">{nombreAmbiente(b.ambiente_id)}</span>
              </div>
            ))}
          </div>
        ))}
      </div>
      {esAdmin && !editando && taller.estado === "Activo" && <Boton variante="secundario" icono={<Pencil className="h-4 w-4" />} onClick={() => setEditando(true)}>Modificar horario</Boton>}
      {editando && (
        <Tarjeta titulo="Bloques horarios">
          <div className="space-y-3">
            <Alerta>Al guardar se regeneran solo las sesiones futuras sin asistencia. Las sesiones realizadas no cambian y la numeración continúa.</Alerta>
            {!!error && <Alerta tipo="error">{mensajeDeError(error)}<ConflictoDetalle error={error} /></Alerta>}
            {bloques.map((b, i) => (
              <div key={i} className="grid grid-cols-2 items-end gap-2 sm:grid-cols-[1fr_1fr_1fr_1.4fr_auto]">
                <Selector etiqueta="Día" value={b.dia_semana} onChange={(e) => cambiar(i, "dia_semana", e.target.value)} opciones={[1, 2, 3, 4, 5, 6, 7].map((d) => ({ valor: d, texto: DIAS[d]! }))} />
                <Campo etiqueta="Inicio" type="time" value={b.hora_inicio} onChange={(e) => cambiar(i, "hora_inicio", e.target.value)} />
                <Campo etiqueta="Fin" type="time" value={b.hora_fin} onChange={(e) => cambiar(i, "hora_fin", e.target.value)} />
                <Selector etiqueta="Ambiente" value={b.ambiente_id} onChange={(e) => cambiar(i, "ambiente_id", e.target.value)} vacio={`Por defecto${taller.ambiente ? ` (${taller.ambiente.codigo})` : ""}`} opciones={(ambientes.datos ?? []).filter((a) => a.estado === "Activo").map((a) => ({ valor: a.id, texto: `${a.codigo} · ${a.nombre}` }))} />
                <Boton variante="fantasma" aria-label="Quitar bloque" icono={<Trash2 className="h-4 w-4" />} onClick={() => setBloques((x) => x.filter((_, j) => j !== i))} />
              </div>
            ))}
            <Boton variante="secundario" icono={<Plus className="h-4 w-4" />} onClick={() => setBloques((b) => [...b, { dia_semana: 1, hora_inicio: "08:00", hora_fin: "10:00", ambiente_id: "" }])}>Agregar bloque</Boton>
            {taller.horarios.length > 0 && <Campo etiqueta="Motivo del cambio" value={motivo} onChange={(e) => setMotivo(e.target.value)} />}
            <div className="flex justify-end gap-2">
              {taller.horarios.length > 0 && <Boton variante="secundario" onClick={() => setEditando(false)}>Cancelar</Boton>}
              <Boton onClick={guardar} cargando={guardando} disabled={!bloques.length}>Guardar y generar sesiones</Boton>
            </div>
          </div>
        </Tarjeta>
      )}
    </div>
  );
}

// ---------- Sesiones ----------
function Sesiones({ taller, esAdmin, recargarTaller }: { taller: Detalle; esAdmin: boolean; recargarTaller: () => void }) {
  const notificar = useNotificar();
  const { datos, cargando, recargar } = useApi<Sesion[]>(`/talleres/${taller.id}/sesiones`);
  const [cancelar, setCancelar] = useState<Sesion | null>(null);
  const [autorizar, setAutorizar] = useState<Sesion | null>(null);
  const hoy = new Date().toLocaleDateString("en-CA", { timeZone: "America/Lima" });
  if (cargando || !datos) return <Cargando />;
  const color = { Programada: "azul", Realizada: "verde", Cancelada: "gris", Reprogramada: "ambar" } as const;
  return (
    <>
      <Tabla encabezados={["N.°", "Fecha", "Horario", "Estado", ""]} vacio={!datos.length}>
        {datos.map((s) => {
          const vencida = s.estado === "Programada" && s.fecha < hoy;
          return (
            <tr key={s.id} className={vencida ? "bg-amber-50" : ""}>
              <Celda>{s.numero_sesion}</Celda>
              <Celda>{diaDeFecha(s.fecha)} {fecha(s.fecha)}</Celda>
              <Celda>{hora(s.hora_inicio)}–{hora(s.hora_fin)}</Celda>
              <Celda>
                <Insignia color={color[s.estado]}>{s.estado}</Insignia>
                {vencida && <span className="ml-2 text-xs text-amber-800">Vencida sin registro</span>}
                {s.motivo_estado && <p className="text-xs text-slate-500">{s.motivo_estado}</p>}
              </Celda>
              <Celda className="text-right">
                {(s.estado === "Programada" || s.estado === "Realizada") && s.fecha <= hoy && (
                  <Link to={`/sesiones/${s.id}/asistencia`} className="mr-2 inline-flex items-center gap-1 text-sm text-marca-700 hover:underline"><ClipboardCheck className="h-4 w-4" aria-hidden /> Asistencia</Link>
                )}
                {esAdmin && s.estado === "Realizada" && s.fecha < hoy && <Boton variante="fantasma" onClick={() => setAutorizar(s)}>Autorizar edición</Boton>}
                {s.estado === "Programada" && taller.estado === "Activo" && <Boton variante="fantasma" icono={<Ban className="h-4 w-4" />} onClick={() => setCancelar(s)}>Cancelar</Boton>}
              </Celda>
            </tr>
          );
        })}
      </Tabla>
      <PedirMotivo abierto={!!cancelar} titulo={cancelar ? `Cancelar sesión N.° ${cancelar.numero_sesion}` : ""} alCerrar={() => setCancelar(null)} peligro
        texto="La sesión cancelada no cuenta para el porcentaje de asistencia ni bloquea la lista de aptos."
        alConfirmar={async (motivo) => {
          try { await api.post(`/sesiones/${cancelar!.id}/cancelar`, { motivo }); notificar.exito("Sesión cancelada."); setCancelar(null); void recargar(); recargarTaller(); }
          catch (e) { notificar.error(mensajeDeError(e)); }
        }} />
      <PedirMotivo abierto={!!autorizar} titulo="Autorizar edición al docente" alCerrar={() => setAutorizar(null)}
        texto="El docente podrá editar esta sesión una sola vez dentro de las próximas 72 horas."
        alConfirmar={async (motivo) => {
          try { await api.post(`/sesiones/${autorizar!.id}/autorizar-edicion`, { motivo }); notificar.exito("Autorización otorgada."); setAutorizar(null); }
          catch (e) { notificar.error(mensajeDeError(e)); }
        }} />
    </>
  );
}

// ---------- Inscritos ----------
function Inscritos({ taller, esAdmin, recargarTaller }: { taller: Detalle; esAdmin: boolean; recargarTaller: () => void }) {
  const notificar = useNotificar();
  const { datos, cargando, recargar } = useApi<Inscripcion[]>(`/talleres/${taller.id}/inscripciones`);
  const [buscar, setBuscar] = useState("");
  const candidatos = useApi<Pagina<Estudiante>>(esAdmin && buscar.length >= 2 ? "/estudiantes" : null, { texto: buscar, tamano: 8, estado: "Activo" });
  const [error, setError] = useState<unknown>(null);
  const [retirar, setRetirar] = useState<Inscripcion | null>(null);
  const [cambio, setCambio] = useState<Inscripcion | null>(null);
  const [destino, setDestino] = useState("");
  const otros = useApi<Pagina<Taller>>(cambio ? "/talleres" : null, { estado: "Activo", tamano: 100 });

  const inscribir = async (e: Estudiante) => {
    setError(null);
    try {
      await api.post(`/talleres/${taller.id}/inscripciones`, { estudiante_id: e.id });
      notificar.exito(`${nombreEstudiante(e)} inscrito.`);
      setBuscar("");
      void recargar();
      recargarTaller();
    } catch (err) {
      setError(err);
    }
  };
  if (cargando || !datos) return <Cargando />;
  const activos = datos.filter((i) => i.estado === "Activo");
  const bloqueado = taller.inscripciones_cerradas || taller.inscripciones_bloqueadas || taller.estado !== "Activo";
  return (
    <div className="space-y-4">
      {esAdmin && (
        bloqueado
          ? <Alerta tipo="advertencia">{taller.inscripciones_bloqueadas ? `Inscripciones bloqueadas: ${taller.motivo_bloqueo}` : taller.inscripciones_cerradas ? "Inscripciones cerradas: el taller ya tiene 3 o más sesiones realizadas." : "El taller no está activo."}</Alerta>
          : (
            <div className="relative max-w-xl">
              <Campo etiqueta={`Inscribir estudiante (${activos.length} de ${taller.cupo_maximo})`} placeholder="Escriba documento, código o apellido" value={buscar} onChange={(e) => setBuscar(e.target.value)} />
              {buscar.length >= 2 && candidatos.datos && (
                <ul className="absolute z-10 mt-1 w-full rounded-md border border-slate-200 bg-white shadow-lg">
                  {candidatos.datos.items.length === 0 && <li className="px-3 py-2 text-sm text-slate-500">Sin resultados.</li>}
                  {candidatos.datos.items.map((e) => (
                    <li key={e.id}><button type="button" className="w-full px-3 py-2 text-left text-sm hover:bg-marca-50" onClick={() => inscribir(e)}>{nombreEstudiante(e)} <span className="text-slate-500">· {e.codigo_universitario}</span></button></li>
                  ))}
                </ul>
              )}
            </div>
          )
      )}
      {!!error && <Alerta tipo="error">{mensajeDeError(error)}<ConflictoDetalle error={error} /></Alerta>}
      <Tabla encabezados={["Estudiante", "Código", "Inscripción", "Estado", ""]} vacio={!datos.length}>
        {datos.map((i) => (
          <tr key={i.id}>
            <Celda className="font-medium">{nombreEstudiante(i.estudiante)}</Celda>
            <Celda>{i.estudiante.codigo_universitario}</Celda>
            <Celda>{fecha(i.fecha_inscripcion)}</Celda>
            <Celda><Insignia color={i.estado === "Activo" ? "verde" : "gris"}>{i.estado}</Insignia></Celda>
            <Celda className="text-right">
              {esAdmin && i.estado === "Activo" && (
                <>
                  <Boton variante="fantasma" onClick={() => setCambio(i)}>Cambiar de taller</Boton>
                  <Boton variante="fantasma" icono={<UserMinus className="h-4 w-4" />} onClick={() => setRetirar(i)}>Retirar</Boton>
                </>
              )}
            </Celda>
          </tr>
        ))}
      </Tabla>
      <PedirMotivo abierto={!!retirar} titulo="Retirar estudiante" alCerrar={() => setRetirar(null)} peligro texto="Se conserva su historial y su asistencia en este taller."
        alConfirmar={async (motivo) => {
          try { await api.post(`/inscripciones/${retirar!.id}/retirar`, { motivo }); notificar.exito("Estudiante retirado."); setRetirar(null); void recargar(); recargarTaller(); }
          catch (e) { notificar.error(mensajeDeError(e)); }
        }} />
      <Modal abierto={!!cambio} titulo="Cambiar de taller" alCerrar={() => setCambio(null)}>
        {cambio && (
          <CambioTaller inscripcion={cambio} talleres={(otros.datos?.items ?? []).filter((t) => t.id !== taller.id)} destino={destino} setDestino={setDestino}
            alListo={() => { setCambio(null); notificar.exito("Cambio de taller registrado."); void recargar(); recargarTaller(); }} />
        )}
      </Modal>
    </div>
  );
}

function CambioTaller({ inscripcion, talleres, destino, setDestino, alListo }: { inscripcion: Inscripcion; talleres: Taller[]; destino: string; setDestino: (v: string) => void; alListo: () => void }) {
  const [motivo, setMotivo] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [cargando, setCargando] = useState(false);
  return (
    <div className="space-y-3">
      <p className="text-sm">{nombreEstudiante(inscripcion.estudiante)}: se retira de este taller (conserva su asistencia) y se inscribe en el destino con todas las validaciones.</p>
      {!!error && <Alerta tipo="error">{mensajeDeError(error)}<ConflictoDetalle error={error} /></Alerta>}
      <Selector etiqueta="Taller destino" obligatorio value={destino} onChange={(e) => setDestino(e.target.value)} vacio="Seleccione…" opciones={talleres.map((t) => ({ valor: t.id, texto: `${t.codigo} · ${t.nombre} (${t.horarios.map((b) => `${DIAS_CORTOS[b.dia_semana]} ${hora(b.hora_inicio)}`).join(", ")})` }))} />
      <AreaTexto etiqueta="Motivo" obligatorio value={motivo} onChange={(e) => setMotivo(e.target.value)} />
      <div className="flex justify-end">
        <Boton cargando={cargando} disabled={!destino || motivo.trim().length < 3} onClick={async () => {
          setError(null); setCargando(true);
          try { await api.post(`/inscripciones/${inscripcion.id}/cambiar-taller`, { taller_destino_id: Number(destino), motivo }); alListo(); }
          catch (e) { setError(e); } finally { setCargando(false); }
        }}>Confirmar cambio</Boton>
      </div>
    </div>
  );
}

// ---------- Asistencia y riesgo ----------
function ResumenAsistencia({ avance }: { avance: Avance }) {
  return (
    <div className="space-y-3">
      <Alerta>Porcentaje = (P + J) ÷ sesiones realizadas que le corresponden × 100. En riesgo: 10 % o más de faltas. Umbral de aptitud del taller: {avance.umbral_aptitud} %.</Alerta>
      <Tabla encabezados={["Estudiante", "Sesiones", "Válidas (P+J)", "Faltas", "%", "Situación"]} vacio={!avance.filas.length}>
        {avance.filas.map((f) => (
          <tr key={f.inscripcion_id} className={f.resultado.en_riesgo ? "bg-amber-50" : ""}>
            <Celda className="font-medium">{nombreEstudiante(f.estudiante)}</Celda>
            <Celda>{f.resultado.sesiones_correspondientes}</Celda>
            <Celda>{f.resultado.validas}</Celda>
            <Celda>{f.resultado.faltas}</Celda>
            <Celda>{f.resultado.calculable ? `${f.resultado.porcentaje} %` : "—"}</Celda>
            <Celda>
              {!f.resultado.calculable ? <Insignia>Sin sesiones aún</Insignia> : (
                <div className="flex gap-1">
                  {f.resultado.en_riesgo && <Insignia color="ambar"><AlertTriangle className="mr-1 h-3 w-3" aria-hidden />En riesgo</Insignia>}
                  <Insignia color={f.resultado.apto ? "verde" : "rojo"}>{f.resultado.apto ? "Apto" : "No apto"}</Insignia>
                </div>
              )}
            </Celda>
          </tr>
        ))}
      </Tabla>
    </div>
  );
}

// ---------- Aptos ----------
function Aptos({ taller, avance, esAdmin, recargarAvance }: { taller: Detalle; avance: Avance; esAdmin: boolean; recargarAvance: () => void }) {
  const notificar = useNotificar();
  const listas = useApi<Lista[]>(esAdmin ? `/talleres/${taller.id}/aptos` : null);
  const [exclusiones, setExclusiones] = useState<Record<number, string>>({});
  const [ver, setVer] = useState<number | null>(null);
  const [anular, setAnular] = useState<Lista | null>(null);
  const [generando, setGenerando] = useState(false);
  const detalle = useApi<ListaDetalle>(ver ? `/aptos/${ver}` : null);
  const vigente = listas.datos?.find((l) => l.estado === "Vigente");

  const generar = async () => {
    const faltan = Object.entries(exclusiones).filter(([, m]) => m.trim().length < 3);
    if (faltan.length) { notificar.error("Cada exclusión necesita un motivo (mínimo 3 caracteres)."); return; }
    if (!confirm("La lista generada es definitiva e inmutable. ¿Generar ahora?")) return;
    setGenerando(true);
    try {
      const r = await api.post<ListaDetalle>(`/talleres/${taller.id}/aptos`, { exclusiones: Object.entries(exclusiones).map(([id, motivo]) => ({ estudiante_id: Number(id), motivo })) });
      notificar.exito(`Lista v${r.data.version} generada: ${r.data.total_aptos} aptos.`);
      setExclusiones({});
      void listas.recargar();
      recargarAvance();
    } catch (e) {
      notificar.error(mensajeDeError(e));
    } finally {
      setGenerando(false);
    }
  };

  return (
    <div className="space-y-4">
      <Alerta tipo={avance.puede_generar ? "exito" : "advertencia"}>
        {avance.puede_generar ? "Todas las sesiones están cerradas: la lista ya se puede generar." : <>Avance informativo, <strong>no definitivo</strong>. {avance.motivo}</>}
      </Alerta>
      <p className="text-sm text-slate-600">El sistema no emite certificados: esta relación sirve para que los estudiantes soliciten su constancia ante la Dirección de Servicios Académicos.</p>
      <Tabla encabezados={["Estudiante", "%", "Condición", ...(esAdmin && avance.puede_generar && !vigente ? ["Excluir (motivo)"] : [])]} vacio={!avance.filas.length}>
        {avance.filas.map((f) => (
          <tr key={f.inscripcion_id}>
            <Celda className="font-medium">{nombreEstudiante(f.estudiante)}</Celda>
            <Celda>{f.resultado.calculable ? `${f.resultado.porcentaje} %` : "—"}</Celda>
            <Celda>{f.resultado.calculable ? <Insignia color={f.resultado.apto ? "verde" : "rojo"}>{f.resultado.apto ? "Apto" : "No apto"}</Insignia> : "—"}</Celda>
            {esAdmin && avance.puede_generar && !vigente && (
              <Celda>
                <div className="flex items-center gap-2">
                  <input type="checkbox" aria-label="Excluir" checked={f.estudiante.id in exclusiones} onChange={(e) => setExclusiones((x) => { const c = { ...x }; if (e.target.checked) c[f.estudiante.id] = ""; else delete c[f.estudiante.id]; return c; })} />
                  {f.estudiante.id in exclusiones && <input aria-label="Motivo de exclusión" className="w-56 rounded-md border border-slate-300 px-2 py-1 text-sm" placeholder="Motivo" value={exclusiones[f.estudiante.id]} onChange={(e) => setExclusiones((x) => ({ ...x, [f.estudiante.id]: e.target.value }))} />}
                </div>
              </Celda>
            )}
          </tr>
        ))}
      </Tabla>
      {esAdmin && (
        <>
          {avance.puede_generar && !vigente && <Boton icono={<FileCheck2 className="h-4 w-4" />} onClick={generar} cargando={generando}>Generar lista definitiva</Boton>}
          <Tarjeta titulo="Listas generadas">
            {!listas.datos?.length ? <Vacio titulo="Aún no se generó ninguna lista." /> : (
              <Tabla encabezados={["Versión", "Generada", "Umbral", "Aptos", "Excluidos", "Estado", ""]}>
                {listas.datos.map((l) => (
                  <tr key={l.id}>
                    <Celda>v{l.version}</Celda>
                    <Celda>{fechaHora(l.generada_en)}</Celda>
                    <Celda>{l.umbral_aplicado} %</Celda>
                    <Celda>{l.total_aptos} / {l.total_inscritos}</Celda>
                    <Celda>{l.total_excluidos}</Celda>
                    <Celda><Insignia color={l.estado === "Vigente" ? "verde" : "gris"}>{l.estado}</Insignia>{l.motivo_anulacion && <p className="text-xs text-slate-500">{l.motivo_anulacion}</p>}</Celda>
                    <Celda className="text-right">
                      <Boton variante="fantasma" onClick={() => setVer(l.id)}>Ver</Boton>
                      <Boton variante="fantasma" icono={<Download className="h-4 w-4" />} onClick={() => descargar(`/aptos/${l.id}/excel`, `aptos_${taller.codigo}_v${l.version}.xlsx`).catch((e) => notificar.error(mensajeDeError(e)))}>Excel</Boton>
                      {l.estado === "Vigente" && <Boton variante="fantasma" onClick={() => setAnular(l)}>Anular</Boton>}
                    </Celda>
                  </tr>
                ))}
              </Tabla>
            )}
          </Tarjeta>
        </>
      )}
      <Modal abierto={!!ver} titulo={detalle.datos ? `Lista v${detalle.datos.version} (${detalle.datos.estado})` : "Lista"} alCerrar={() => setVer(null)} ancho="max-w-4xl">
        {detalle.cargando || !detalle.datos ? <Cargando /> : (
          <Tabla encabezados={["Documento", "Código", "Estudiante", "Carrera", "Sesiones", "%", "Condición"]}>
            {detalle.datos.detalle.map((d) => (
              <tr key={d.estudiante_id}>
                <Celda>{d.tipo_documento} {d.numero_documento}</Celda>
                <Celda>{d.codigo_universitario}</Celda>
                <Celda>{nombreEstudiante(d)}</Celda>
                <Celda>{d.carrera}</Celda>
                <Celda>{d.sesiones_validas}/{d.sesiones_correspondientes}</Celda>
                <Celda>{d.porcentaje} %</Celda>
                <Celda>{d.excluido_manual ? <span title={d.motivo_exclusion ?? ""}><Insignia color="ambar">Excluido</Insignia></span> : <Insignia color={d.es_apto ? "verde" : "rojo"}>{d.es_apto ? "Apto" : "No apto"}</Insignia>}</Celda>
              </tr>
            ))}
          </Tabla>
        )}
      </Modal>
      <PedirMotivo abierto={!!anular} titulo="Anular lista" alCerrar={() => setAnular(null)} peligro texto="La lista anulada se conserva; luego podrá generar una nueva versión."
        alConfirmar={async (motivo) => {
          try { await api.post(`/aptos/${anular!.id}/anular`, { motivo }); notificar.exito("Lista anulada."); setAnular(null); void listas.recargar(); }
          catch (e) { notificar.error(mensajeDeError(e)); }
        }} />
    </div>
  );
}

export function TallerDetalle() {
  const { id } = useParams();
  const { usuario } = useAuth();
  const esAdmin = usuario?.rol === "Administrador";
  const [params, setParams] = useSearchParams();
  const pestana = (params.get("pestana") as Pestana) ?? "resumen";
  const { datos: taller, cargando, error, recargar } = useApi<Detalle>(`/talleres/${id}`);
  const avance = useApi<Avance>(`/talleres/${id}/aptos/avance`);
  const recargarTodo = () => { void recargar(); void avance.recargar(); };

  if (error) return <Alerta tipo="error">{error}</Alerta>;
  if (cargando || !taller) return <Cargando />;
  return (
    <>
      <Link to="/talleres" className="mb-2 inline-flex items-center gap-1 text-sm text-marca-700 hover:underline"><ArrowLeft className="h-4 w-4" aria-hidden /> Talleres</Link>
      <Encabezado titulo={`${taller.codigo} · ${taller.nombre}`} descripcion={`${taller.area.nombre} · ${taller.sede.nombre} · ${taller.docente.nombre_completo}`}
        acciones={<Insignia color={colorEstado(taller.estado)}>{taller.estado}</Insignia>} />
      <Tarjeta>
        <Pestanas valor={pestana} alCambiar={(v) => setParams({ pestana: v })} opciones={[
          { valor: "resumen", texto: "Resumen" }, { valor: "horario", texto: "Horario" }, { valor: "sesiones", texto: "Sesiones" },
          { valor: "inscritos", texto: "Inscritos" }, { valor: "asistencia", texto: "Asistencia y riesgo" }, { valor: "aptos", texto: "Lista de aptos" },
        ]} />
        <div className="pt-4">
          {pestana === "resumen" && <Resumen taller={taller} esAdmin={esAdmin} recargar={recargarTodo} />}
          {pestana === "horario" && <Horario taller={taller} esAdmin={esAdmin} recargar={recargarTodo} />}
          {pestana === "sesiones" && <Sesiones taller={taller} esAdmin={esAdmin} recargarTaller={recargarTodo} />}
          {pestana === "inscritos" && <Inscritos taller={taller} esAdmin={esAdmin} recargarTaller={recargarTodo} />}
          {pestana === "asistencia" && (avance.datos ? <ResumenAsistencia avance={avance.datos} /> : <Cargando />)}
          {pestana === "aptos" && (avance.datos ? <Aptos taller={taller} avance={avance.datos} esAdmin={esAdmin} recargarAvance={() => void avance.recargar()} /> : <Cargando />)}
        </div>
      </Tarjeta>
    </>
  );
}
