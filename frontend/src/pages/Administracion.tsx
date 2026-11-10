import { Plus } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { api, mensajeDeError } from "../api/cliente";
import type { Pagina, Parametro, RegistroAuditoria, UsuarioAdmin } from "../api/tipos";
import { Alerta, Boton, Campo, Cargando, Celda, Encabezado, Insignia, Modal, Paginacion, Selector, Tabla, Tarjeta } from "../components/ui";
import { useAuth } from "../contexts/Auth";
import { useNotificar } from "../contexts/Notificaciones";
import { useApi } from "../hooks/useApi";
import { fechaHora } from "../utils/formato";

export function Usuarios() {
  const notificar = useNotificar();
  const { usuario: yo } = useAuth();
  const [pagina, setPagina] = useState(1);
  const { datos, cargando, error, recargar } = useApi<Pagina<UsuarioAdmin>>("/usuarios", { pagina, tamano: 20 });
  const [nuevo, setNuevo] = useState(false);
  const [clave, setClave] = useState<{ username: string; password_temporal: string } | null>(null);
  const { register, handleSubmit, reset, formState: { isSubmitting } } = useForm<{ username: string; email: string; nombres: string; apellido_paterno: string; rol: string }>({ defaultValues: { rol: "Operador" } });
  const [errorForm, setErrorForm] = useState<string | null>(null);

  const accion = async (u: UsuarioAdmin, ruta: string, texto: string) => {
    try {
      const r = await api.post(`/usuarios/${u.id}/${ruta}`);
      if (ruta === "restablecer-password") setClave(r.data as { username: string; password_temporal: string });
      else notificar.exito(texto);
      void recargar();
    } catch (e) {
      notificar.error(mensajeDeError(e));
    }
  };
  const crear = async (d: { username: string; email: string; nombres: string; apellido_paterno: string; rol: string }) => {
    setErrorForm(null);
    try {
      const r = await api.post("/usuarios", { ...d, apellido_materno: null });
      setNuevo(false);
      reset();
      setClave(r.data as { username: string; password_temporal: string });
      void recargar();
    } catch (e) {
      setErrorForm(mensajeDeError(e));
    }
  };

  return (
    <>
      <Encabezado titulo="Usuarios" descripcion="Los usuarios docentes se crean desde el módulo Docentes" acciones={<Boton icono={<Plus className="h-4 w-4" />} onClick={() => setNuevo(true)}>Nuevo usuario</Boton>} />
      <Tarjeta>
        {error && <Alerta tipo="error">{error}</Alerta>}
        {cargando || !datos ? <Cargando /> : (
          <>
            <Tabla encabezados={["Usuario", "Nombre", "Rol", "Último acceso", "Estado", ""]} vacio={!datos.items.length}>
              {datos.items.map((u) => (
                <tr key={u.id}>
                  <Celda className="font-medium">{u.username}</Celda>
                  <Celda>{u.nombres} {u.apellido_paterno}</Celda>
                  <Celda>{u.rol_nombre}</Celda>
                  <Celda>{fechaHora(u.ultimo_acceso)}</Celda>
                  <Celda>
                    <div className="flex gap-1">
                      <Insignia color={u.activo ? "verde" : "gris"}>{u.activo ? "Activo" : "Inactivo"}</Insignia>
                      {u.bloqueado_hasta && <Insignia color="rojo">Bloqueado</Insignia>}
                    </div>
                  </Celda>
                  <Celda className="text-right">
                    {u.bloqueado_hasta && <Boton variante="fantasma" onClick={() => accion(u, "desbloquear", "Usuario desbloqueado.")}>Desbloquear</Boton>}
                    <Boton variante="fantasma" onClick={() => { if (confirm(`¿Restablecer la contraseña de ${u.username}?`)) void accion(u, "restablecer-password", ""); }}>Restablecer clave</Boton>
                    <Boton variante="fantasma" onClick={() => accion(u, "cerrar-sesiones", "Sesiones cerradas.")}>Cerrar sesiones</Boton>
                    {u.id !== yo?.id && (
                      <Boton variante="fantasma" onClick={() => { if (confirm(`¿${u.activo ? "Desactivar" : "Activar"} a ${u.username}?`)) void accion(u, u.activo ? "desactivar" : "activar", u.activo ? "Usuario desactivado." : "Usuario activado."); }}>{u.activo ? "Desactivar" : "Activar"}</Boton>
                    )}
                  </Celda>
                </tr>
              ))}
            </Tabla>
            <Paginacion pagina={pagina} tamano={20} total={datos.total} alCambiar={setPagina} />
          </>
        )}
      </Tarjeta>
      <Modal abierto={nuevo} titulo="Nuevo usuario" alCerrar={() => setNuevo(false)}>
        <form onSubmit={handleSubmit(crear)} className="space-y-3" noValidate>
          {errorForm && <Alerta tipo="error">{errorForm}</Alerta>}
          <Campo etiqueta="Usuario" obligatorio {...register("username", { required: true })} />
          <Campo etiqueta="Correo" type="email" obligatorio {...register("email", { required: true })} />
          <Campo etiqueta="Nombres" obligatorio {...register("nombres", { required: true })} />
          <Campo etiqueta="Apellido paterno" obligatorio {...register("apellido_paterno", { required: true })} />
          <Selector etiqueta="Rol" opciones={[{ valor: "Operador", texto: "Operador" }, { valor: "Administrador", texto: "Administrador" }]} {...register("rol")} />
          <div className="flex justify-end"><Boton type="submit" cargando={isSubmitting}>Crear</Boton></div>
        </form>
      </Modal>
      <Modal abierto={!!clave} titulo="Contraseña temporal" alCerrar={() => setClave(null)} pie={<Boton onClick={() => setClave(null)}>Entendido</Boton>}>
        {clave && (
          <div className="space-y-2 text-sm">
            <Alerta tipo="exito">Entregue esta contraseña al usuario. Se muestra una sola vez y deberá cambiarla al ingresar.</Alerta>
            <p>Usuario: <code className="rounded bg-slate-100 px-1">{clave.username}</code></p>
            <p>Contraseña: <code className="rounded bg-slate-100 px-1 select-all">{clave.password_temporal}</code></p>
          </div>
        )}
      </Modal>
    </>
  );
}

export function Auditoria() {
  const [pagina, setPagina] = useState(1);
  const [modulo, setModulo] = useState("");
  const [detalle, setDetalle] = useState<RegistroAuditoria | null>(null);
  const { datos, cargando, error } = useApi<Pagina<RegistroAuditoria>>("/auditoria", { pagina, tamano: 25, modulo });
  const modulos = ["seguridad", "usuarios", "catalogos", "estudiantes", "docentes", "talleres", "sesiones", "inscripciones", "asistencia", "aptos", "parametros"];
  return (
    <>
      <Encabezado titulo="Auditoría" descripcion="Registro inalterable de operaciones" />
      <Tarjeta>
        <div className="mb-3 w-60"><Selector etiqueta="Módulo" value={modulo} onChange={(e) => { setModulo(e.target.value); setPagina(1); }} vacio="Todos" opciones={modulos.map((m) => ({ valor: m, texto: m }))} /></div>
        {error && <Alerta tipo="error">{error}</Alerta>}
        {cargando || !datos ? <Cargando /> : (
          <>
            <Tabla encabezados={["Fecha", "Usuario", "IP", "Módulo", "Evento", "Registro", ""]} vacio={!datos.items.length}>
              {datos.items.map((a) => (
                <tr key={a.id}>
                  <Celda>{fechaHora(a.created_at)}</Celda>
                  <Celda>{a.usuario_id ?? "consola"}</Celda>
                  <Celda>{a.ip ?? "—"}</Celda>
                  <Celda>{a.modulo}</Celda>
                  <Celda>{a.evento}</Celda>
                  <Celda>{a.entidad} {a.registro_id}</Celda>
                  <Celda><Boton variante="fantasma" onClick={() => setDetalle(a)}>Ver</Boton></Celda>
                </tr>
              ))}
            </Tabla>
            <Paginacion pagina={pagina} tamano={25} total={datos.total} alCambiar={setPagina} />
          </>
        )}
      </Tarjeta>
      <Modal abierto={!!detalle} titulo={detalle ? `${detalle.modulo} · ${detalle.evento}` : ""} alCerrar={() => setDetalle(null)} ancho="max-w-2xl">
        {detalle && (
          <div className="grid gap-3 sm:grid-cols-2">
            <div><p className="mb-1 text-xs font-semibold text-slate-500">ANTES</p><pre className="max-h-80 overflow-auto rounded bg-slate-50 p-2 text-xs">{JSON.stringify(detalle.datos_anteriores, null, 2)}</pre></div>
            <div><p className="mb-1 text-xs font-semibold text-slate-500">DESPUÉS</p><pre className="max-h-80 overflow-auto rounded bg-slate-50 p-2 text-xs">{JSON.stringify(detalle.datos_nuevos, null, 2)}</pre></div>
          </div>
        )}
      </Modal>
    </>
  );
}

export function Parametros() {
  const notificar = useNotificar();
  const { datos, cargando, error, recargar } = useApi<Parametro[]>("/parametros");
  const [valores, setValores] = useState<Record<string, string>>({});
  const guardar = async (p: Parametro) => {
    try {
      await api.put(`/parametros/${p.clave}`, { valor: Number(valores[p.clave] ?? p.valor) });
      notificar.exito("Parámetro actualizado.");
      void recargar();
    } catch (e) {
      notificar.error(mensajeDeError(e));
    }
  };
  return (
    <>
      <Encabezado titulo="Parámetros del sistema" descripcion="Cada cambio queda registrado en la auditoría" />
      <Tarjeta>
        {error && <Alerta tipo="error">{error}</Alerta>}
        {cargando || !datos ? <Cargando /> : (
          <Tabla encabezados={["Parámetro", "Descripción", "Rango", "Valor", ""]}>
            {datos.map((p) => (
              <tr key={p.clave}>
                <Celda className="font-mono text-xs">{p.clave}</Celda>
                <Celda className="whitespace-normal text-slate-600">{p.descripcion}</Celda>
                <Celda>{p.minimo}–{p.maximo}</Celda>
                <Celda><input aria-label={`Valor de ${p.clave}`} type="number" min={p.minimo} max={p.maximo} className="w-24 rounded-md border border-slate-300 px-2 py-1 text-sm" value={valores[p.clave] ?? p.valor} onChange={(e) => setValores((v) => ({ ...v, [p.clave]: e.target.value }))} /></Celda>
                <Celda><Boton variante="secundario" disabled={(valores[p.clave] ?? String(p.valor)) === String(p.valor)} onClick={() => guardar(p)}>Guardar</Boton></Celda>
              </tr>
            ))}
          </Tabla>
        )}
      </Tarjeta>
    </>
  );
}
