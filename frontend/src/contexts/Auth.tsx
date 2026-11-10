import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

import { alExpirarSesion, api } from "../api/cliente";
import type { UsuarioSesion } from "../api/tipos";

interface ContextoAuth {
  usuario: UsuarioSesion | null;
  cargando: boolean;
  aviso: string | null;
  iniciar: (username: string, password: string) => Promise<UsuarioSesion>;
  salir: () => Promise<void>;
  recargar: () => Promise<void>;
}

const Ctx = createContext<ContextoAuth | null>(null);

export function ProveedorAuth({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<UsuarioSesion | null>(null);
  const [cargando, setCargando] = useState(true);
  const [aviso, setAviso] = useState<string | null>(null);

  const recargar = useCallback(async () => {
    try {
      const r = await api.get<UsuarioSesion>("/auth/me");
      setUsuario(r.data);
    } catch {
      setUsuario(null);
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    void recargar();
    return alExpirarSesion((e) => {
      setUsuario(null);
      setAviso(e.mensaje);
    });
  }, [recargar]);

  const iniciar = useCallback(async (username: string, password: string) => {
    const r = await api.post<{ usuario: UsuarioSesion }>("/auth/login", { username, password });
    setUsuario(r.data.usuario);
    setAviso(null);
    return r.data.usuario;
  }, []);

  const salir = useCallback(async () => {
    try {
      await api.post("/auth/logout");
    } finally {
      setUsuario(null);
    }
  }, []);

  return <Ctx.Provider value={{ usuario, cargando, aviso, iniciar, salir, recargar }}>{children}</Ctx.Provider>;
}

export function useAuth(): ContextoAuth {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth fuera de ProveedorAuth");
  return ctx;
}
