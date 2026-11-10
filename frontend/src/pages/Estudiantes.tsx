import { zodResolver } from "@hookform/resolvers/zod";
import { History, Pencil, Plus, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { api, mensajeDeError } from "../api/cliente";
import type { Carrera, Estudiante, Pagina, TipoDocumento } from "../api/tipos";
import { Alerta, Boton, Campo, Cargando, Celda, Encabezado, Insignia, Modal, Paginacion, Selector, Tabla, Tarjeta } from "../components/ui";
import { useNotificar } from "../contexts/Notificaciones";
import { useApi } from "../hooks/useApi";
import { fecha, nombreEstudiante } from "../utils/formato";

const opcional = z.string().trim().transform((v) => (v === "" ? null : v));
const esquema = z.object({
  tipo_documento_id: z.coerce.number<string>().int().positive("Seleccione el tipo."),
  numero_documento: z.string().trim().min(1, "Obligatorio."),
  codigo_universitario: z.string().trim().min(1, "Obligatorio."),
  nombres: z.string().trim().min(1, "Obligatorio."),
  apellido_paterno: z.string().trim().min(1, "Obligatorio."),
  apellido_materno: opcional,
  fecha_nacimiento: opcional,
  carrera_id: z.coerce.number<string>().int().positive("Seleccione la carrera."),
  ciclo_actual: z.string().trim().transform((v) => (v === "" ? null : Number(v))),
  email: z.union([z.literal(""), z.email("Correo inválido.")]).transform((v) => (v === "" ? null : v)),
  telefono: opcional,
  estado: z.enum(["Activo", "Inactivo", "Egresado"]),
});
type Entrada = z.input<typeof esquema>;
type Salida = z.output<typeof esquema>;

function Formulario({ estudiante, tipos, carreras, alGuardar, alCancelar }: { estudiante: Estudiante | null; tipos: TipoDocumento[]; carreras: Carrera[]; alGuardar: () => void; alCancelar: () => void }) {
  const notificar = useNotificar();
  const [error, setError] = useState<string | null>(null);
  const { register, handleSubmit, watch, formState: { errors, isSubmitting } } = useForm<Entrada, unknown, Salida>({
    resolver: zodResolver(esquema),
    defaultValues: estudiante
      ? {
          ...estudiante,
          tipo_documento_id: String(estudiante.tipo_documento_id),
          carrera_id: String(estudiante.carrera_id),
          apellido_materno: estudiante.apellido_materno ?? "",
          fecha_nacimiento: estudiante.fecha_nacimiento ?? "",
          ciclo_actual: estudiante.ciclo_actual ? String(estudiante.ciclo_actual) : "",
          email: estudiante.email ?? "",
          telefono: estudiante.telefono ?? "",
        }
      : { tipo_documento_id: "1", estado: "Activo", carrera_id: "", apellido_materno: "", fecha_nacimiento: "", ciclo_actual: "", email: "", telefono: "" },
  });
  const tipo = tipos.find((t) => String(t.id) === String(watch("tipo_documento_id")));

  const enviar = async (d: Salida) => {
    setError(null);
    try {
      if (estudiante) await api.put(`/estudiantes/${estudiante.id}`, d);
      else await api.post("/estudiantes", d);
      notificar.exito(estudiante ? "Estudiante actualizado." : "Estudiante registrado.");
      alGuardar();
    } catch (e) {
      setError(mensajeDeError(e));
    }
  };

  return (
    <form onSubmit={handleSubmit(enviar)} className="space-y-4" noValidate>
      {error && <Alerta tipo="error">{error}</Alerta>}
      <fieldset className="grid gap-3 sm:grid-cols-2">
        <legend className="mb-2 text-sm font-semibold text-slate-700">Identificación</legend>
        <Selector etiqueta="Tipo de documento" obligatorio opciones={tipos.map((t) => ({ valor: t.id, texto: t.nombre }))} error={errors.tipo_documento_id?.message} {...register("tipo_documento_id")} />
        <Campo etiqueta="Número de documento" obligatorio inputMode={tipo?.solo_digitos ? "numeric" : "text"} maxLength={tipo?.longitud_max ?? 20}
          ayuda={tipo ? (tipo.longitud_min === tipo.longitud_max ? `${tipo.longitud_min} ${tipo.solo_digitos ? "dígitos" : "caracteres"}` : `Entre ${tipo.longitud_min} y ${tipo.longitud_max} caracteres`) : undefined}
          error={errors.numero_documento?.message} {...register("numero_documento")} />
        <Campo etiqueta="Código universitario" obligatorio error={errors.codigo_universitario?.message} {...register("codigo_universitario")} />
        <Selector etiqueta="Estado" opciones={["Activo", "Inactivo", "Egresado"].map((e) => ({ valor: e, texto: e }))} {...register("estado")} />
      </fieldset>
      <fieldset className="grid gap-3 sm:grid-cols-3">
        <legend className="mb-2 text-sm font-semibold text-slate-700">Datos personales</legend>
        <Campo etiqueta="Nombres" obligatorio error={errors.nombres?.message} {...register("nombres")} />
        <Campo etiqueta="Apellido paterno" obligatorio error={errors.apellido_paterno?.message} {...register("apellido_paterno")} />
        <Campo etiqueta="Apellido materno" {...register("apellido_materno")} />
        <Campo etiqueta="Fecha de nacimiento" type="date" {...register("fecha_nacimiento")} />
        <Campo etiqueta="Correo" type="email" error={errors.email?.message} {...register("email")} />
        <Campo etiqueta="Teléfono" inputMode="tel" {...register("telefono")} />
      </fieldset>
      <fieldset className="grid gap-3 sm:grid-cols-2">
        <legend className="mb-2 text-sm font-semibold text-slate-700">Datos académicos</legend>
        <Selector etiqueta="Carrera" obligatorio vacio="Seleccione…" opciones={carreras.filter((c) => c.activo).map((c) => ({ valor: c.id, texto: c.nombre }))} error={errors.carrera_id?.message} {...register("carrera_id")} />
        <Campo etiqueta="Ciclo actual" type="number" min={1} max={14} {...register("ciclo_actual")} />
      </fieldset>
      <div className="flex justify-end gap-2">
        <Boton variante="secundario" onClick={alCancelar}>Cancelar</Boton>
        <Boton type="submit" cargando={isSubmitting}>Guardar</Boton>
      </div>
    </form>
  );
}

function Historial({ estudiante }: { estudiante: Estudiante }) {
  const { datos, cargando } = useApi<{ id: number; estado: string; fecha_inscripcion: string; taller_codigo: string; taller_nombre: string }[]>(`/estudiantes/${estudiante.id}/inscripciones`);
  if (cargando || !datos) return <Cargando />;
  return (
    <Tabla encabezados={["Taller", "Inscripción", "Estado"]} vacio={!datos.length}>
      {datos.map((i) => (
        <tr key={i.id}><Celda>{i.taller_codigo} · {i.taller_nombre}</Celda><Celda>{fecha(i.fecha_inscripcion)}</Celda><Celda><Insignia color={i.estado === "Activo" ? "verde" : "gris"}>{i.estado}</Insignia></Celda></tr>
      ))}
    </Tabla>
  );
}

export function Estudiantes() {
  const [pagina, setPagina] = useState(1);
  const [texto, setTexto] = useState("");
  const [busqueda, setBusqueda] = useState("");
  const [carrera, setCarrera] = useState("");
  const [editando, setEditando] = useState<Estudiante | null | undefined>(undefined);
  const [historial, setHistorial] = useState<Estudiante | null>(null);
  const tipos = useApi<TipoDocumento[]>("/catalogos/tipos-documento");
  const carreras = useApi<Carrera[]>("/catalogos/carreras");
  const { datos, cargando, error, recargar } = useApi<Pagina<Estudiante>>("/estudiantes", { pagina, tamano: 20, texto: busqueda, carrera_id: carrera });

  useEffect(() => {
    const t = setTimeout(() => { setBusqueda(texto); setPagina(1); }, 350);
    return () => clearTimeout(t);
  }, [texto]);

  return (
    <>
      <Encabezado titulo="Estudiantes" descripcion="Padrón de estudiantes" acciones={<Boton icono={<Plus className="h-4 w-4" />} onClick={() => setEditando(null)}>Nuevo estudiante</Boton>} />
      <Tarjeta>
        <div className="mb-3 grid gap-3 sm:grid-cols-3">
          <div className="relative sm:col-span-2">
            <Campo etiqueta="Buscar" placeholder="Documento, código, nombres o apellidos" value={texto} onChange={(e) => setTexto(e.target.value)} />
            <Search className="pointer-events-none absolute right-3 bottom-2.5 h-4 w-4 text-slate-400" aria-hidden />
          </div>
          <Selector etiqueta="Carrera" value={carrera} onChange={(e) => { setCarrera(e.target.value); setPagina(1); }} vacio="Todas" opciones={(carreras.datos ?? []).map((c) => ({ valor: c.id, texto: c.nombre }))} />
        </div>
        {error && <Alerta tipo="error">{error}</Alerta>}
        {cargando || !datos ? <Cargando /> : (
          <>
            <Tabla encabezados={["Código", "Documento", "Apellidos y nombres", "Carrera", "Estado", ""]} vacio={!datos.items.length}>
              {datos.items.map((e) => (
                <tr key={e.id} className="hover:bg-slate-50">
                  <Celda>{e.codigo_universitario}</Celda>
                  <Celda>{e.tipo_documento.codigo} {e.numero_documento}</Celda>
                  <Celda className="font-medium">{nombreEstudiante(e)}</Celda>
                  <Celda>{e.carrera.nombre}</Celda>
                  <Celda><Insignia color={e.estado === "Activo" ? "verde" : e.estado === "Egresado" ? "azul" : "gris"}>{e.estado}</Insignia></Celda>
                  <Celda className="text-right">
                    <Boton variante="fantasma" aria-label="Historial" icono={<History className="h-4 w-4" />} onClick={() => setHistorial(e)} />
                    <Boton variante="fantasma" aria-label="Editar" icono={<Pencil className="h-4 w-4" />} onClick={() => setEditando(e)} />
                  </Celda>
                </tr>
              ))}
            </Tabla>
            <Paginacion pagina={pagina} tamano={20} total={datos.total} alCambiar={setPagina} />
          </>
        )}
      </Tarjeta>
      <Modal abierto={editando !== undefined} titulo={editando ? "Editar estudiante" : "Nuevo estudiante"} alCerrar={() => setEditando(undefined)} ancho="max-w-3xl">
        {editando !== undefined && tipos.datos && carreras.datos && (
          <Formulario estudiante={editando} tipos={tipos.datos} carreras={carreras.datos} alCancelar={() => setEditando(undefined)} alGuardar={() => { setEditando(undefined); void recargar(); }} />
        )}
      </Modal>
      <Modal abierto={!!historial} titulo={historial ? `Historial de ${nombreEstudiante(historial)}` : ""} alCerrar={() => setHistorial(null)}>
        {historial && <Historial estudiante={historial} />}
      </Modal>
    </>
  );
}
