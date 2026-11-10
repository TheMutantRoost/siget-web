import axios, { AxiosError } from "axios";

export interface ErrorApi {
  codigo: string;
  mensaje: string;
  detalles?: unknown;
}

function leerCookie(nombre: string): string | null {
  const par = document.cookie.split("; ").find((c) => c.startsWith(`${nombre}=`));
  return par ? decodeURIComponent(par.slice(nombre.length + 1)) : null;
}

export const api = axios.create({ baseURL: "/api/v1", withCredentials: true, timeout: 30000 });

// Doble envío CSRF: el token viaja en la cookie legible y en la cabecera.
api.interceptors.request.use((config) => {
  const metodo = (config.method ?? "get").toUpperCase();
  if (!["GET", "HEAD", "OPTIONS"].includes(metodo)) {
    const csrf = leerCookie("siget_csrf");
    if (csrf) config.headers.set("X-CSRF-Token", csrf);
  }
  return config;
});

type Oyente = (error: ErrorApi) => void;
const oyentesSesion = new Set<Oyente>();
export function alExpirarSesion(fn: Oyente): () => void {
  oyentesSesion.add(fn);
  return () => oyentesSesion.delete(fn);
}

api.interceptors.response.use(
  (r) => r,
  (error: AxiosError<ErrorApi>) => {
    const datos = error.response?.data;
    const normalizado: ErrorApi =
      datos && typeof datos === "object" && "mensaje" in datos
        ? datos
        : { codigo: "red", mensaje: "No se pudo conectar con el servidor. Intente de nuevo." };
    const url = error.config?.url ?? "";
    if (error.response?.status === 401 && !url.includes("/auth/login")) {
      oyentesSesion.forEach((fn) => fn(normalizado));
    }
    return Promise.reject(normalizado);
  },
);

export function mensajeDeError(e: unknown): string {
  if (e && typeof e === "object" && "mensaje" in e) {
    const err = e as ErrorApi;
    if (err.codigo === "validacion" && Array.isArray(err.detalles)) {
      const primero = err.detalles[0] as { campo?: string; mensaje?: string } | undefined;
      if (primero) return `${err.mensaje} ${primero.campo ?? ""}: ${primero.mensaje ?? ""}`.trim();
    }
    return err.mensaje;
  }
  return "Ocurrió un error inesperado.";
}

export function detallesDeConflicto(e: unknown): Record<string, string>[] {
  if (e && typeof e === "object" && "detalles" in e && Array.isArray((e as ErrorApi).detalles)) {
    return (e as { detalles: Record<string, string>[] }).detalles;
  }
  return [];
}

export async function descargar(url: string, nombre: string): Promise<void> {
  const r = await api.get(url, { responseType: "blob" });
  const enlace = document.createElement("a");
  enlace.href = URL.createObjectURL(r.data as Blob);
  enlace.download = nombre;
  enlace.click();
  URL.revokeObjectURL(enlace.href);
}
