import { useCallback, useEffect, useState } from "react";

import { api, mensajeDeError } from "../api/cliente";

/** Carga datos de la API y expone estado de carga, error y una función para recargar. */
export function useApi<T>(url: string | null, params?: Record<string, unknown>) {
  const [datos, setDatos] = useState<T | null>(null);
  const [cargando, setCargando] = useState(!!url);
  const [error, setError] = useState<string | null>(null);
  const clave = JSON.stringify(params ?? {});

  const recargar = useCallback(async () => {
    if (!url) return;
    setCargando(true);
    setError(null);
    try {
      const limpio = Object.fromEntries(Object.entries(JSON.parse(clave) as Record<string, unknown>).filter(([, v]) => v !== "" && v !== null && v !== undefined));
      const r = await api.get<T>(url, { params: limpio });
      setDatos(r.data);
    } catch (e) {
      setError(mensajeDeError(e));
    } finally {
      setCargando(false);
    }
  }, [url, clave]);

  useEffect(() => {
    void recargar();
  }, [recargar]);

  return { datos, cargando, error, recargar, setDatos };
}
