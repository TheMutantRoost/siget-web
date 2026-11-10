import { CheckCircle2, X, XCircle } from "lucide-react";
import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

interface Aviso { id: number; tipo: "exito" | "error"; texto: string }
interface Contexto { exito: (t: string) => void; error: (t: string) => void }

const Ctx = createContext<Contexto | null>(null);

export function ProveedorNotificaciones({ children }: { children: ReactNode }) {
  const [avisos, setAvisos] = useState<Aviso[]>([]);
  const quitar = useCallback((id: number) => setAvisos((a) => a.filter((x) => x.id !== id)), []);
  const agregar = useCallback((tipo: Aviso["tipo"], texto: string) => {
    const id = Date.now() + Math.random();
    setAvisos((a) => [...a, { id, tipo, texto }]);
    setTimeout(() => quitar(id), tipo === "error" ? 8000 : 4000);
  }, [quitar]);
  const valor = { exito: (t: string) => agregar("exito", t), error: (t: string) => agregar("error", t) };
  return (
    <Ctx.Provider value={valor}>
      {children}
      <div className="fixed right-4 bottom-4 z-50 flex w-[min(24rem,calc(100%-2rem))] flex-col gap-2" aria-live="polite">
        {avisos.map((a) => (
          <div key={a.id} className={`flex items-start gap-2 rounded-md border bg-white px-3 py-2 text-sm shadow-lg ${a.tipo === "exito" ? "border-green-300" : "border-red-300"}`}>
            {a.tipo === "exito" ? <CheckCircle2 className="mt-0.5 h-4 w-4 text-green-600" aria-hidden /> : <XCircle className="mt-0.5 h-4 w-4 text-red-600" aria-hidden />}
            <p className="flex-1">{a.texto}</p>
            <button type="button" onClick={() => quitar(a.id)} aria-label="Cerrar aviso" className="text-slate-400 hover:text-slate-600"><X className="h-4 w-4" /></button>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}

export function useNotificar(): Contexto {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useNotificar fuera de ProveedorNotificaciones");
  return ctx;
}
