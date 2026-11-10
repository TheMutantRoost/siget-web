import { AlertTriangle, CheckCircle2, ChevronLeft, ChevronRight, Info, Loader2, X, XCircle } from "lucide-react";
import {
  forwardRef,
  useEffect,
  useId,
  useRef,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";

type Variante = "primario" | "secundario" | "peligro" | "fantasma";
const VARIANTES: Record<Variante, string> = {
  primario: "bg-marca-700 text-white hover:bg-marca-800 disabled:bg-marca-700/50",
  secundario: "bg-white text-slate-700 border border-slate-300 hover:bg-slate-50 disabled:text-slate-400",
  peligro: "bg-red-600 text-white hover:bg-red-700 disabled:bg-red-600/50",
  fantasma: "text-marca-700 hover:bg-marca-50 disabled:text-slate-400",
};

export function Boton({
  variante = "primario",
  cargando = false,
  icono,
  children,
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variante?: Variante; cargando?: boolean; icono?: ReactNode }) {
  return (
    <button
      type="button"
      {...props}
      disabled={props.disabled || cargando}
      className={`inline-flex items-center justify-center gap-2 rounded-md px-3.5 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed ${VARIANTES[variante]} ${className}`}
    >
      {cargando ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : icono}
      {children}
    </button>
  );
}

const claseControl =
  "block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-xs placeholder:text-slate-400 focus:border-marca-500 focus:outline-none focus:ring-2 focus:ring-marca-100 disabled:bg-slate-100 aria-invalid:border-red-500";

interface PropsCampo {
  etiqueta: string;
  error?: string;
  obligatorio?: boolean;
  ayuda?: string;
}

function Envoltura({ id, etiqueta, error, obligatorio, ayuda, children }: PropsCampo & { id: string; children: ReactNode }) {
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="block text-sm font-medium text-slate-700">
        {etiqueta}
        {obligatorio && <span className="text-red-600" aria-hidden> *</span>}
      </label>
      {children}
      {ayuda && !error && <p className="text-xs text-slate-500">{ayuda}</p>}
      {error && <p id={`${id}-error`} className="text-xs text-red-600" role="alert">{error}</p>}
    </div>
  );
}

export const Campo = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & PropsCampo>(
  function Campo({ etiqueta, error, obligatorio, ayuda, ...props }, ref) {
    const id = useId();
    return (
      <Envoltura id={id} etiqueta={etiqueta} error={error} obligatorio={obligatorio} ayuda={ayuda}>
        <input id={id} ref={ref} aria-invalid={!!error} aria-required={obligatorio} aria-describedby={error ? `${id}-error` : undefined} className={claseControl} {...props} />
      </Envoltura>
    );
  },
);

export const Selector = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement> & PropsCampo & { opciones: { valor: string | number; texto: string }[]; vacio?: string }>(
  function Selector({ etiqueta, error, obligatorio, ayuda, opciones, vacio, ...props }, ref) {
    const id = useId();
    return (
      <Envoltura id={id} etiqueta={etiqueta} error={error} obligatorio={obligatorio} ayuda={ayuda}>
        <select id={id} ref={ref} aria-invalid={!!error} aria-required={obligatorio} className={claseControl} {...props}>
          {vacio !== undefined && <option value="">{vacio}</option>}
          {opciones.map((o) => (
            <option key={o.valor} value={o.valor}>{o.texto}</option>
          ))}
        </select>
      </Envoltura>
    );
  },
);

export const AreaTexto = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement> & PropsCampo>(
  function AreaTexto({ etiqueta, error, obligatorio, ayuda, ...props }, ref) {
    const id = useId();
    return (
      <Envoltura id={id} etiqueta={etiqueta} error={error} obligatorio={obligatorio} ayuda={ayuda}>
        <textarea id={id} ref={ref} rows={3} aria-invalid={!!error} className={claseControl} {...props} />
      </Envoltura>
    );
  },
);

export function Tarjeta({ titulo, acciones, children, className = "" }: { titulo?: ReactNode; acciones?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`min-w-0 rounded-lg border border-slate-200 bg-white shadow-xs ${className}`}>
      {(titulo || acciones) && (
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-4 py-3">
          {titulo && <h2 className="text-base font-semibold text-slate-800">{titulo}</h2>}
          {acciones && <div className="flex flex-wrap gap-2">{acciones}</div>}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

type TipoAlerta = "info" | "exito" | "advertencia" | "error";
const ALERTAS: Record<TipoAlerta, { clase: string; Icono: typeof Info }> = {
  info: { clase: "border-marca-100 bg-marca-50 text-marca-800", Icono: Info },
  exito: { clase: "border-green-200 bg-green-50 text-green-800", Icono: CheckCircle2 },
  advertencia: { clase: "border-amber-200 bg-amber-50 text-amber-900", Icono: AlertTriangle },
  error: { clase: "border-red-200 bg-red-50 text-red-800", Icono: XCircle },
};

export function Alerta({ tipo = "info", children }: { tipo?: TipoAlerta; children: ReactNode }) {
  const { clase, Icono } = ALERTAS[tipo];
  return (
    <div role={tipo === "error" ? "alert" : "status"} className={`flex gap-2 rounded-md border px-3 py-2 text-sm ${clase}`}>
      <Icono className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <div>{children}</div>
    </div>
  );
}

export function Cargando({ texto = "Cargando…" }: { texto?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-10 text-sm text-slate-500" role="status">
      <Loader2 className="h-5 w-5 animate-spin" aria-hidden /> {texto}
    </div>
  );
}

export function Vacio({ titulo, children }: { titulo: string; children?: ReactNode }) {
  return (
    <div className="py-10 text-center">
      <p className="text-sm font-medium text-slate-700">{titulo}</p>
      {children && <div className="mt-1 text-sm text-slate-500">{children}</div>}
    </div>
  );
}

const INSIGNIAS = {
  gris: "bg-slate-100 text-slate-700",
  azul: "bg-marca-100 text-marca-800",
  verde: "bg-green-100 text-green-800",
  ambar: "bg-amber-100 text-amber-900",
  rojo: "bg-red-100 text-red-800",
};
export function Insignia({ color = "gris", children }: { color?: keyof typeof INSIGNIAS; children: ReactNode }) {
  return <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${INSIGNIAS[color]}`}>{children}</span>;
}

export function Modal({ abierto, titulo, alCerrar, children, pie, ancho = "max-w-lg" }: { abierto: boolean; titulo: string; alCerrar: () => void; children: ReactNode; pie?: ReactNode; ancho?: string }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (abierto && !d.open) d.showModal();
    if (!abierto && d.open) d.close();
  }, [abierto]);
  return (
    <dialog
      ref={ref}
      onCancel={(e) => { e.preventDefault(); alCerrar(); }}
      className={`m-auto w-[calc(100%-2rem)] ${ancho} rounded-lg p-0 shadow-xl backdrop:bg-slate-900/40`}
      aria-labelledby="titulo-modal"
    >
      {abierto && (
        <div className="flex max-h-[90vh] flex-col">
          <header className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
            <h2 id="titulo-modal" className="text-base font-semibold">{titulo}</h2>
            <button type="button" onClick={alCerrar} className="rounded p-1 text-slate-500 hover:bg-slate-100" aria-label="Cerrar">
              <X className="h-5 w-5" />
            </button>
          </header>
          <div className="overflow-y-auto p-4">{children}</div>
          {pie && <footer className="flex justify-end gap-2 border-t border-slate-200 px-4 py-3">{pie}</footer>}
        </div>
      )}
    </dialog>
  );
}

export function Paginacion({ pagina, tamano, total, alCambiar }: { pagina: number; tamano: number; total: number; alCambiar: (p: number) => void }) {
  const paginas = Math.max(1, Math.ceil(total / tamano));
  return (
    <nav className="flex items-center justify-between gap-2 pt-3 text-sm text-slate-600" aria-label="Paginación">
      <span>{total} registros · página {pagina} de {paginas}</span>
      <div className="flex gap-1">
        <Boton variante="secundario" disabled={pagina <= 1} onClick={() => alCambiar(pagina - 1)} aria-label="Página anterior" icono={<ChevronLeft className="h-4 w-4" />} />
        <Boton variante="secundario" disabled={pagina >= paginas} onClick={() => alCambiar(pagina + 1)} aria-label="Página siguiente" icono={<ChevronRight className="h-4 w-4" />} />
      </div>
    </nav>
  );
}

export function Tabla({ encabezados, children, vacio }: { encabezados: ReactNode[]; children: ReactNode; vacio?: boolean }) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50">
          <tr>
            {encabezados.map((h, i) => (
              <th key={i} scope="col" className="whitespace-nowrap px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">{children}</tbody>
      </table>
      {vacio && <Vacio titulo="No hay registros para mostrar." />}
    </div>
  );
}

export function Celda({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <td className={`whitespace-nowrap px-3 py-2 ${className}`}>{children}</td>;
}

export function Pestanas<T extends string>({ valor, opciones, alCambiar }: { valor: T; opciones: { valor: T; texto: string }[]; alCambiar: (v: T) => void }) {
  return (
    <div role="tablist" className="flex gap-1 overflow-x-auto border-b border-slate-200">
      {opciones.map((o) => (
        <button
          key={o.valor}
          role="tab"
          type="button"
          aria-selected={valor === o.valor}
          onClick={() => alCambiar(o.valor)}
          className={`whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium ${valor === o.valor ? "border-marca-700 text-marca-800" : "border-transparent text-slate-500 hover:text-slate-700"}`}
        >
          {o.texto}
        </button>
      ))}
    </div>
  );
}

export function Encabezado({ titulo, descripcion, acciones }: { titulo: string; descripcion?: string; acciones?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">{titulo}</h1>
        {descripcion && <p className="text-sm text-slate-500">{descripcion}</p>}
      </div>
      {acciones && <div className="flex flex-wrap gap-2">{acciones}</div>}
    </div>
  );
}
