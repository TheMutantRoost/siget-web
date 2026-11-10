import { Pencil, Plus } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { api, mensajeDeError } from "../api/cliente";
import type { Ambiente, Area, Carrera, Ciclo, Facultad, Sede } from "../api/tipos";
import { Alerta, Boton, Campo, Cargando, Celda, Encabezado, Insignia, Modal, Pestanas, Selector, Tabla, Tarjeta } from "../components/ui";
import { useNotificar } from "../contexts/Notificaciones";
import { useApi } from "../hooks/useApi";
import { fecha } from "../utils/formato";

type Tipo = "sedes" | "ambientes" | "areas" | "facultades" | "carreras" | "ciclos";

interface CampoDef {
  nombre: string;
  etiqueta: string;
  tipo?: "text" | "number" | "date" | "estado" | "activo" | "select";
  opciones?: { valor: string | number; texto: string }[];
  obligatorio?: boolean;
}

function FormularioGenerico({ tipo, campos, registro, alListo }: { tipo: Tipo; campos: CampoDef[]; registro: Record<string, unknown> | null; alListo: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const { register, handleSubmit, formState: { isSubmitting } } = useForm<Record<string, string>>({
    defaultValues: Object.fromEntries(campos.map((c) => [c.nombre, registro ? String(registro[c.nombre] ?? "") : c.tipo === "estado" ? "Activo" : c.tipo === "activo" ? "true" : ""])),
  });
  const enviar = async (d: Record<string, string>) => {
    setError(null);
    const cuerpo = Object.fromEntries(campos.map((c) => {
      const v = d[c.nombre] ?? "";
      if (c.tipo === "number" || c.tipo === "select") return [c.nombre, v === "" ? null : Number(v)];
      if (c.tipo === "activo") return [c.nombre, v === "true"];
      return [c.nombre, v];
    }));
    try {
      if (registro) await api.put(`/catalogos/${tipo}/${registro.id as number}`, cuerpo);
      else await api.post(`/catalogos/${tipo}`, cuerpo);
      alListo();
    } catch (e) {
      setError(mensajeDeError(e));
    }
  };
  return (
    <form onSubmit={handleSubmit(enviar)} className="space-y-3" noValidate>
      {error && <Alerta tipo="error">{error}</Alerta>}
      {campos.map((c) => {
        if (c.tipo === "estado") return <Selector key={c.nombre} etiqueta={c.etiqueta} opciones={[{ valor: "Activo", texto: "Activo" }, { valor: "Inactivo", texto: "Inactivo" }]} {...register(c.nombre)} />;
        if (c.tipo === "activo") return <Selector key={c.nombre} etiqueta={c.etiqueta} opciones={[{ valor: "true", texto: "Activo" }, { valor: "false", texto: "Inactivo" }]} {...register(c.nombre)} />;
        if (c.tipo === "select") return <Selector key={c.nombre} etiqueta={c.etiqueta} obligatorio={c.obligatorio} vacio="Seleccione…" opciones={c.opciones ?? []} disabled={!!registro && c.nombre === "sede_id"} {...register(c.nombre)} />;
        return <Campo key={c.nombre} etiqueta={c.etiqueta} type={c.tipo ?? "text"} obligatorio={c.obligatorio} {...register(c.nombre)} />;
      })}
      <div className="flex justify-end"><Boton type="submit" cargando={isSubmitting}>Guardar</Boton></div>
    </form>
  );
}

export function Catalogos() {
  const notificar = useNotificar();
  const [tipo, setTipo] = useState<Tipo>("sedes");
  const [editando, setEditando] = useState<Record<string, unknown> | null | undefined>(undefined);
  const sedes = useApi<Sede[]>("/catalogos/sedes");
  const facultades = useApi<Facultad[]>("/catalogos/facultades");
  const { datos, cargando, error, recargar } = useApi<Record<string, unknown>[]>(`/catalogos/${tipo}`);

  const campos: Record<Tipo, CampoDef[]> = {
    sedes: [{ nombre: "nombre", etiqueta: "Nombre", obligatorio: true }, { nombre: "direccion", etiqueta: "Dirección", obligatorio: true }, { nombre: "estado", etiqueta: "Estado", tipo: "estado" }],
    ambientes: [
      { nombre: "sede_id", etiqueta: "Sede", tipo: "select", obligatorio: true, opciones: (sedes.datos ?? []).map((s) => ({ valor: s.id, texto: s.nombre })) },
      { nombre: "codigo", etiqueta: "Código (único en la sede)", obligatorio: true }, { nombre: "nombre", etiqueta: "Nombre", obligatorio: true },
      { nombre: "capacidad", etiqueta: "Capacidad", tipo: "number" }, { nombre: "estado", etiqueta: "Estado", tipo: "estado" },
    ],
    areas: [{ nombre: "nombre", etiqueta: "Nombre", obligatorio: true }, { nombre: "activo", etiqueta: "Estado", tipo: "activo" }],
    facultades: [{ nombre: "codigo", etiqueta: "Código", obligatorio: true }, { nombre: "nombre", etiqueta: "Nombre", obligatorio: true }, { nombre: "activo", etiqueta: "Estado", tipo: "activo" }],
    carreras: [
      { nombre: "facultad_id", etiqueta: "Facultad", tipo: "select", obligatorio: true, opciones: (facultades.datos ?? []).map((f) => ({ valor: f.id, texto: f.nombre })) },
      { nombre: "codigo", etiqueta: "Código", obligatorio: true }, { nombre: "nombre", etiqueta: "Nombre", obligatorio: true }, { nombre: "activo", etiqueta: "Estado", tipo: "activo" },
    ],
    ciclos: [{ nombre: "nombre", etiqueta: "Nombre (p. ej. 2026-II)", obligatorio: true }, { nombre: "fecha_inicio", etiqueta: "Inicio", tipo: "date", obligatorio: true }, { nombre: "fecha_fin", etiqueta: "Fin", tipo: "date", obligatorio: true }],
  };

  const activarCiclo = async (c: Ciclo) => {
    if (!confirm(`¿Activar el ciclo ${c.nombre}? El ciclo activo actual se desactivará.`)) return;
    try {
      await api.post(`/catalogos/ciclos/${c.id}/activar`);
      notificar.exito(`Ciclo ${c.nombre} activado.`);
      void recargar();
    } catch (e) {
      notificar.error(mensajeDeError(e));
    }
  };

  const filas = datos ?? [];
  const estadoInsignia = (activo: boolean) => <Insignia color={activo ? "verde" : "gris"}>{activo ? "Activo" : "Inactivo"}</Insignia>;

  return (
    <>
      <Encabezado titulo="Sedes y catálogos" descripcion="Datos que carga la institución" acciones={<Boton icono={<Plus className="h-4 w-4" />} onClick={() => setEditando(null)}>Agregar</Boton>} />
      <Tarjeta>
        <Pestanas valor={tipo} alCambiar={(t) => { setTipo(t); setEditando(undefined); }} opciones={[
          { valor: "sedes", texto: "Sedes" }, { valor: "ambientes", texto: "Ambientes" }, { valor: "areas", texto: "Áreas" },
          { valor: "facultades", texto: "Facultades" }, { valor: "carreras", texto: "Carreras" }, { valor: "ciclos", texto: "Ciclos académicos" },
        ]} />
        <div className="pt-3">
          {error && <Alerta tipo="error">{error}</Alerta>}
          {cargando ? <Cargando /> : (
            <Tabla encabezados={tipo === "sedes" ? ["Nombre", "Dirección", "Estado", ""] : tipo === "ambientes" ? ["Sede", "Código", "Nombre", "Capacidad", "Estado", ""] : tipo === "carreras" ? ["Código", "Nombre", "Facultad", "Estado", ""] : tipo === "ciclos" ? ["Nombre", "Inicio", "Fin", "Estado", ""] : tipo === "facultades" ? ["Código", "Nombre", "Estado", ""] : ["Nombre", "Estado", ""]} vacio={!filas.length}>
              {filas.map((f) => (
                <tr key={f.id as number}>
                  {tipo === "sedes" && <><Celda className="font-medium">{(f as unknown as Sede).nombre}</Celda><Celda>{(f as unknown as Sede).direccion}</Celda><Celda>{estadoInsignia((f as unknown as Sede).estado === "Activo")}</Celda></>}
                  {tipo === "ambientes" && <><Celda>{(f as unknown as Ambiente).sede.nombre}</Celda><Celda>{(f as unknown as Ambiente).codigo}</Celda><Celda>{(f as unknown as Ambiente).nombre}</Celda><Celda>{(f as unknown as Ambiente).capacidad ?? "—"}</Celda><Celda>{estadoInsignia((f as unknown as Ambiente).estado === "Activo")}</Celda></>}
                  {tipo === "areas" && <><Celda className="font-medium">{(f as unknown as Area).nombre}</Celda><Celda>{estadoInsignia((f as unknown as Area).activo)}</Celda></>}
                  {tipo === "facultades" && <><Celda>{(f as unknown as Facultad).codigo}</Celda><Celda className="font-medium">{(f as unknown as Facultad).nombre}</Celda><Celda>{estadoInsignia((f as unknown as Facultad).activo)}</Celda></>}
                  {tipo === "carreras" && <><Celda>{(f as unknown as Carrera).codigo}</Celda><Celda className="font-medium">{(f as unknown as Carrera).nombre}</Celda><Celda>{(f as unknown as Carrera).facultad.nombre}</Celda><Celda>{estadoInsignia((f as unknown as Carrera).activo)}</Celda></>}
                  {tipo === "ciclos" && <><Celda className="font-medium">{(f as unknown as Ciclo).nombre}</Celda><Celda>{fecha((f as unknown as Ciclo).fecha_inicio)}</Celda><Celda>{fecha((f as unknown as Ciclo).fecha_fin)}</Celda><Celda>{(f as unknown as Ciclo).activo ? <Insignia color="verde">Activo</Insignia> : <Insignia>Inactivo</Insignia>}</Celda></>}
                  <Celda className="text-right">
                    {tipo === "ciclos"
                      ? !(f as unknown as Ciclo).activo && <Boton variante="fantasma" onClick={() => activarCiclo(f as unknown as Ciclo)}>Activar</Boton>
                      : <Boton variante="fantasma" aria-label="Editar" icono={<Pencil className="h-4 w-4" />} onClick={() => setEditando(f)} />}
                  </Celda>
                </tr>
              ))}
            </Tabla>
          )}
        </div>
      </Tarjeta>
      <Modal abierto={editando !== undefined} titulo={editando ? "Editar registro" : "Nuevo registro"} alCerrar={() => setEditando(undefined)}>
        {editando !== undefined && (
          <FormularioGenerico tipo={tipo} campos={campos[tipo]} registro={editando} alListo={() => { setEditando(undefined); notificar.exito("Guardado."); void recargar(); if (tipo === "sedes") void sedes.recargar(); if (tipo === "facultades") void facultades.recargar(); }} />
        )}
      </Modal>
    </>
  );
}
