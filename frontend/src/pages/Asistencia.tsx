import { ArrowLeft, Lock } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { api, mensajeDeError } from "../api/cliente";
import type { EstadoAsistencia, HojaAsistencia } from "../api/tipos";
import { Alerta, Boton, Cargando, Celda, Encabezado, Tabla, Tarjeta, Vacio } from "../components/ui";
import { useNotificar } from "../contexts/Notificaciones";
import { useApi } from "../hooks/useApi";
import { diaDeFecha, fecha, hora, nombreEstudiante } from "../utils/formato";

const OPCIONES: { valor: EstadoAsistencia; texto: string; clase: string }[] = [
  { valor: "P", texto: "Presente", clase: "peer-checked:bg-green-600 peer-checked:text-white peer-checked:border-green-600" },
  { valor: "A", texto: "Ausente", clase: "peer-checked:bg-red-600 peer-checked:text-white peer-checked:border-red-600" },
  { valor: "J", texto: "Justificado", clase: "peer-checked:bg-amber-500 peer-checked:text-white peer-checked:border-amber-500" },
];

interface Fila { estado: EstadoAsistencia | null; observacion: string }

export function Asistencia() {
  const { id } = useParams();
  const navegar = useNavigate();
  const notificar = useNotificar();
  const { datos: hoja, cargando, error, recargar } = useApi<HojaAsistencia>(`/sesiones/${id}/asistencia`);
  const [filas, setFilas] = useState<Record<number, Fila>>({});
  const [guardando, setGuardando] = useState(false);
  const [errorGuardar, setErrorGuardar] = useState<string | null>(null);

  useEffect(() => {
    if (hoja) setFilas(Object.fromEntries(hoja.filas.map((f) => [f.inscripcion_id, { estado: f.estado, observacion: f.observacion ?? "" }])));
  }, [hoja]);

  if (error) return <Alerta tipo="error">{error}</Alerta>;
  if (cargando || !hoja) return <Cargando />;

  const editable = hoja.puede_editar;
  const pendientes = hoja.filas.filter((f) => !filas[f.inscripcion_id]?.estado).length;
  const sinObservacion = hoja.filas.filter((f) => filas[f.inscripcion_id]?.estado === "J" && !filas[f.inscripcion_id]?.observacion.trim()).length;
  const marcarTodos = (estado: EstadoAsistencia) => setFilas((x) => Object.fromEntries(Object.entries(x).map(([k, v]) => [k, { ...v, estado }])));

  const guardar = async () => {
    setErrorGuardar(null);
    setGuardando(true);
    try {
      await api.put(`/sesiones/${id}/asistencia`, {
        registros: hoja.filas.map((f) => ({ inscripcion_id: f.inscripcion_id, estado: filas[f.inscripcion_id]!.estado, observacion: filas[f.inscripcion_id]!.observacion.trim() || null })),
      });
      notificar.exito("Asistencia guardada.");
      navegar(`/talleres/${hoja.taller_id}?pestana=sesiones`);
    } catch (e) {
      setErrorGuardar(mensajeDeError(e));
      void recargar();
    } finally {
      setGuardando(false);
    }
  };

  return (
    <>
      <Link to={`/talleres/${hoja.taller_id}?pestana=sesiones`} className="mb-2 inline-flex items-center gap-1 text-sm text-marca-700 hover:underline"><ArrowLeft className="h-4 w-4" aria-hidden /> {hoja.taller}</Link>
      <Encabezado titulo={`Asistencia · Sesión N.° ${hoja.sesion.numero_sesion}`} descripcion={`${diaDeFecha(hoja.sesion.fecha)} ${fecha(hoja.sesion.fecha)} · ${hora(hoja.sesion.hora_inicio)}–${hora(hoja.sesion.hora_fin)} · ${hoja.sesion.estado}`} />
      <div className="mb-3 space-y-2">
        {!editable && <Alerta tipo="advertencia"><span className="inline-flex items-center gap-1"><Lock className="h-4 w-4" aria-hidden /> {hoja.motivo_bloqueo}</span></Alerta>}
        {editable && hoja.congelada && <Alerta tipo="info">{hoja.primer_registro ? "Primer registro tardío: está dentro del plazo permitido." : "Sesión congelada: está editando con autorización (o como administrador)."}</Alerta>}
        {errorGuardar && <Alerta tipo="error">{errorGuardar}</Alerta>}
      </div>
      <Tarjeta acciones={editable && hoja.filas.length > 0 && <><Boton variante="secundario" onClick={() => marcarTodos("P")}>Todos presentes</Boton></>}>
        {!hoja.filas.length ? <Vacio titulo="El taller no tiene inscritos activos." /> : (
          <Tabla encabezados={["Estudiante", "Asistencia", "Observación"]}>
            {hoja.filas.map((f) => {
              const fila = filas[f.inscripcion_id] ?? { estado: null, observacion: "" };
              return (
                <tr key={f.inscripcion_id}>
                  <Celda className="font-medium">{nombreEstudiante(f.estudiante)}<p className="text-xs font-normal text-slate-500">{f.estudiante.codigo_universitario}</p></Celda>
                  <Celda>
                    <fieldset className="flex gap-1" disabled={!editable}>
                      <legend className="sr-only">Asistencia de {nombreEstudiante(f.estudiante)}</legend>
                      {OPCIONES.map((o) => (
                        <label key={o.valor} className="cursor-pointer">
                          <input type="radio" className="peer sr-only" name={`a-${f.inscripcion_id}`} checked={fila.estado === o.valor}
                            onChange={() => setFilas((x) => ({ ...x, [f.inscripcion_id]: { ...fila, estado: o.valor } }))} />
                          <span className={`inline-block rounded-md border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-600 peer-focus-visible:ring-2 peer-focus-visible:ring-marca-500 ${o.clase}`} title={o.texto}>{o.valor}</span>
                        </label>
                      ))}
                    </fieldset>
                  </Celda>
                  <Celda>
                    <input aria-label="Observación" disabled={!editable} value={fila.observacion} maxLength={255}
                      placeholder={fila.estado === "J" ? "Obligatoria para J" : "Opcional"}
                      onChange={(e) => setFilas((x) => ({ ...x, [f.inscripcion_id]: { ...fila, observacion: e.target.value } }))}
                      className={`w-64 rounded-md border px-2 py-1 text-sm ${fila.estado === "J" && !fila.observacion.trim() ? "border-red-400" : "border-slate-300"}`} />
                  </Celda>
                </tr>
              );
            })}
          </Tabla>
        )}
        {editable && hoja.filas.length > 0 && (
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-slate-600">{pendientes ? `Faltan ${pendientes} estudiantes por marcar.` : "Todos los estudiantes tienen asistencia."}{sinObservacion ? ` ${sinObservacion} justificados sin observación.` : ""}</p>
            <Boton onClick={guardar} cargando={guardando} disabled={pendientes > 0 || sinObservacion > 0}>Guardar asistencia</Boton>
          </div>
        )}
      </Tarjeta>
    </>
  );
}
