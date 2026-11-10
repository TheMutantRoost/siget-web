import { CalendarClock, KeyRound, Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { api, detallesDeConflicto, mensajeDeError } from "../api/cliente";
import type { Area, Docente, TipoDocumento } from "../api/tipos";
import { Alerta, Boton, Campo, Cargando, Celda, Encabezado, Insignia, Modal, Selector, Tabla, Tarjeta } from "../components/ui";
import { useNotificar } from "../contexts/Notificaciones";
import { useApi } from "../hooks/useApi";
import { DIAS, DIAS_CORTOS, hora } from "../utils/formato";

interface DatosDocente {
  username: string;
  email: string;
  tipo_documento_id: string;
  numero_documento: string;
  nombres: string;
  apellido_paterno: string;
  apellido_materno: string;
  telefono: string;
  area_ids: string[];
}

function FormularioDocente({ docente, tipos, areas, alGuardar, alCancelar }: { docente: Docente | null; tipos: TipoDocumento[]; areas: Area[]; alGuardar: (clave?: { username: string; password_temporal: string }) => void; alCancelar: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const { register, handleSubmit, formState: { isSubmitting } } = useForm<DatosDocente>({
    defaultValues: docente
      ? { nombres: docente.nombres, apellido_paterno: docente.apellido_paterno, apellido_materno: docente.apellido_materno ?? "", telefono: docente.telefono ?? "", area_ids: docente.areas.map((a) => String(a.id)) }
      : { tipo_documento_id: "1", area_ids: [] },
  });
  const enviar = async (d: DatosDocente) => {
    setError(null);
    const area_ids = d.area_ids.map(Number);
    if (!area_ids.length) { setError("Seleccione al menos un área autorizada."); return; }
    try {
      if (docente) {
        await api.patch(`/docentes/${docente.id}`, { nombres: d.nombres, apellido_paterno: d.apellido_paterno, apellido_materno: d.apellido_materno || null, telefono: d.telefono || null, area_ids });
        alGuardar();
      } else {
        const r = await api.post<{ username: string; password_temporal: string }>("/docentes", { ...d, tipo_documento_id: Number(d.tipo_documento_id), apellido_materno: d.apellido_materno || null, telefono: d.telefono || null, area_ids });
        alGuardar(r.data);
      }
    } catch (e) {
      setError(mensajeDeError(e));
    }
  };
  return (
    <form onSubmit={handleSubmit(enviar)} className="space-y-4" noValidate>
      {error && <Alerta tipo="error">{error}</Alerta>}
      {!docente && (
        <fieldset className="grid gap-3 sm:grid-cols-2">
          <legend className="mb-2 text-sm font-semibold text-slate-700">Usuario de acceso</legend>
          <Campo etiqueta="Usuario" obligatorio ayuda="Letras, números, punto o guion." {...register("username", { required: true })} />
          <Campo etiqueta="Correo" type="email" obligatorio {...register("email", { required: true })} />
          <Selector etiqueta="Tipo de documento" obligatorio opciones={tipos.map((t) => ({ valor: t.id, texto: t.nombre }))} {...register("tipo_documento_id")} />
          <Campo etiqueta="Número de documento" obligatorio {...register("numero_documento", { required: true })} />
        </fieldset>
      )}
      <fieldset className="grid gap-3 sm:grid-cols-2">
        <legend className="mb-2 text-sm font-semibold text-slate-700">Datos personales</legend>
        <Campo etiqueta="Nombres" obligatorio {...register("nombres", { required: true })} />
        <Campo etiqueta="Apellido paterno" obligatorio {...register("apellido_paterno", { required: true })} />
        <Campo etiqueta="Apellido materno" {...register("apellido_materno")} />
        <Campo etiqueta="Teléfono" {...register("telefono")} />
      </fieldset>
      <fieldset>
        <legend className="mb-2 text-sm font-semibold text-slate-700">Áreas autorizadas <span className="text-red-600">*</span></legend>
        <div className="flex flex-wrap gap-3">
          {areas.filter((a) => a.activo).map((a) => (
            <label key={a.id} className="flex items-center gap-2 text-sm"><input type="checkbox" value={a.id} {...register("area_ids")} /> {a.nombre}</label>
          ))}
        </div>
      </fieldset>
      <div className="flex justify-end gap-2">
        <Boton variante="secundario" onClick={alCancelar}>Cancelar</Boton>
        <Boton type="submit" cargando={isSubmitting}>Guardar</Boton>
      </div>
    </form>
  );
}

interface BloqueEdicion { dia_semana: number; hora_inicio: string; hora_fin: string }

function EditorDisponibilidad({ docente, alGuardar }: { docente: Docente; alGuardar: () => void }) {
  const [bloques, setBloques] = useState<BloqueEdicion[]>(docente.disponibilidad.map((d) => ({ dia_semana: d.dia_semana, hora_inicio: hora(d.hora_inicio), hora_fin: hora(d.hora_fin) })));
  const [error, setError] = useState<string | null>(null);
  const [guardando, setGuardando] = useState(false);
  const cambiar = (i: number, campo: keyof BloqueEdicion, valor: string) => setBloques((b) => b.map((x, j) => (j === i ? { ...x, [campo]: campo === "dia_semana" ? Number(valor) : valor } : x)));
  const guardar = async () => {
    setError(null);
    setGuardando(true);
    try {
      await api.put(`/docentes/${docente.id}/disponibilidad`, bloques);
      alGuardar();
    } catch (e) {
      const d = detallesDeConflicto(e);
      setError(mensajeDeError(e) + (d.length > 1 ? ` (${d.length} sesiones afectadas)` : ""));
    } finally {
      setGuardando(false);
    }
  };
  return (
    <div className="space-y-3">
      <Alerta>El docente solo puede asignarse a talleres cuyas sesiones caen dentro de estos bloques.</Alerta>
      {error && <Alerta tipo="error">{error}</Alerta>}
      {bloques.map((b, i) => (
        <div key={i} className="grid grid-cols-[1fr_1fr_1fr_auto] items-end gap-2">
          <Selector etiqueta="Día" value={b.dia_semana} onChange={(e) => cambiar(i, "dia_semana", e.target.value)} opciones={[1, 2, 3, 4, 5, 6, 7].map((d) => ({ valor: d, texto: DIAS[d]! }))} />
          <Campo etiqueta="Desde" type="time" value={b.hora_inicio} onChange={(e) => cambiar(i, "hora_inicio", e.target.value)} />
          <Campo etiqueta="Hasta" type="time" value={b.hora_fin} onChange={(e) => cambiar(i, "hora_fin", e.target.value)} />
          <Boton variante="fantasma" aria-label="Quitar bloque" icono={<Trash2 className="h-4 w-4" />} onClick={() => setBloques((x) => x.filter((_, j) => j !== i))} />
        </div>
      ))}
      <div className="flex justify-between">
        <Boton variante="secundario" icono={<Plus className="h-4 w-4" />} onClick={() => setBloques((b) => [...b, { dia_semana: 1, hora_inicio: "08:00", hora_fin: "13:00" }])}>Agregar bloque</Boton>
        <Boton onClick={guardar} cargando={guardando}>Guardar disponibilidad</Boton>
      </div>
    </div>
  );
}

export function Docentes() {
  const notificar = useNotificar();
  const { datos, cargando, error, recargar } = useApi<Docente[]>("/docentes");
  const tipos = useApi<TipoDocumento[]>("/catalogos/tipos-documento");
  const areas = useApi<Area[]>("/catalogos/areas");
  const [editando, setEditando] = useState<Docente | null | undefined>(undefined);
  const [disponibilidad, setDisponibilidad] = useState<Docente | null>(null);
  const [clave, setClave] = useState<{ username: string; password_temporal: string } | null>(null);

  const alternarActivo = async (d: Docente) => {
    try {
      await api.patch(`/docentes/${d.id}`, { activo: !d.activo });
      notificar.exito(d.activo ? "Docente desactivado." : "Docente activado.");
      void recargar();
    } catch (e) {
      notificar.error(mensajeDeError(e));
    }
  };

  return (
    <>
      <Encabezado titulo="Docentes" descripcion="Cada docente tiene su usuario de acceso, sus áreas autorizadas y su disponibilidad" acciones={<Boton icono={<Plus className="h-4 w-4" />} onClick={() => setEditando(null)}>Nuevo docente</Boton>} />
      <Tarjeta>
        {error && <Alerta tipo="error">{error}</Alerta>}
        {cargando || !datos ? <Cargando /> : (
          <Tabla encabezados={["Docente", "Documento", "Áreas", "Disponibilidad", "Estado", ""]} vacio={!datos.length}>
            {datos.map((d) => (
              <tr key={d.id}>
                <Celda><p className="font-medium">{d.nombre_completo}</p><p className="text-xs text-slate-500">{d.email}</p></Celda>
                <Celda>{d.numero_documento}</Celda>
                <Celda><div className="flex flex-wrap gap-1">{d.areas.map((a) => <Insignia key={a.id} color="azul">{a.nombre}</Insignia>)}</div></Celda>
                <Celda className="text-xs">{d.disponibilidad.length ? d.disponibilidad.map((b) => `${DIAS_CORTOS[b.dia_semana]} ${hora(b.hora_inicio)}–${hora(b.hora_fin)}`).join(" · ") : <Insignia color="ambar">Sin registrar</Insignia>}</Celda>
                <Celda><Insignia color={d.activo ? "verde" : "gris"}>{d.activo ? "Activo" : "Inactivo"}</Insignia></Celda>
                <Celda className="text-right">
                  <Boton variante="fantasma" aria-label="Disponibilidad" icono={<CalendarClock className="h-4 w-4" />} onClick={() => setDisponibilidad(d)} />
                  <Boton variante="fantasma" aria-label="Editar" icono={<Pencil className="h-4 w-4" />} onClick={() => setEditando(d)} />
                  <Boton variante="fantasma" onClick={() => { if (confirm(`¿${d.activo ? "Desactivar" : "Activar"} a ${d.nombre_completo}?`)) void alternarActivo(d); }}>{d.activo ? "Desactivar" : "Activar"}</Boton>
                </Celda>
              </tr>
            ))}
          </Tabla>
        )}
      </Tarjeta>
      <Modal abierto={editando !== undefined} titulo={editando ? "Editar docente" : "Nuevo docente"} alCerrar={() => setEditando(undefined)} ancho="max-w-2xl">
        {editando !== undefined && tipos.datos && areas.datos && (
          <FormularioDocente docente={editando} tipos={tipos.datos} areas={areas.datos} alCancelar={() => setEditando(undefined)}
            alGuardar={(c) => { setEditando(undefined); if (c) setClave(c); else notificar.exito("Docente actualizado."); void recargar(); }} />
        )}
      </Modal>
      <Modal abierto={!!disponibilidad} titulo={disponibilidad ? `Disponibilidad de ${disponibilidad.nombre_completo}` : ""} alCerrar={() => setDisponibilidad(null)} ancho="max-w-2xl">
        {disponibilidad && <EditorDisponibilidad docente={disponibilidad} alGuardar={() => { setDisponibilidad(null); notificar.exito("Disponibilidad guardada."); void recargar(); }} />}
      </Modal>
      <Modal abierto={!!clave} titulo="Docente creado" alCerrar={() => setClave(null)} pie={<Boton onClick={() => setClave(null)}>Entendido</Boton>}>
        {clave && (
          <div className="space-y-3">
            <Alerta tipo="exito">Entregue estas credenciales al docente. La contraseña se muestra una sola vez y deberá cambiarla al ingresar.</Alerta>
            <p className="flex items-center gap-2 text-sm"><KeyRound className="h-4 w-4" aria-hidden /> Usuario: <code className="rounded bg-slate-100 px-1">{clave.username}</code></p>
            <p className="text-sm">Contraseña temporal: <code className="rounded bg-slate-100 px-1 select-all">{clave.password_temporal}</code></p>
            <p className="text-sm text-slate-600">Luego registre su disponibilidad: sin ella no se le puede asignar un taller.</p>
          </div>
        )}
      </Modal>
    </>
  );
}
