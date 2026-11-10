import { zodResolver } from "@hookform/resolvers/zod";
import { ClipboardList } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Navigate, useNavigate } from "react-router";
import { z } from "zod";

import { mensajeDeError } from "../api/cliente";
import { Alerta, Boton, Campo } from "../components/ui";
import { useAuth } from "../contexts/Auth";

const esquema = z.object({
  username: z.string().trim().min(1, "Ingrese su usuario."),
  password: z.string().min(1, "Ingrese su contraseña."),
});
type Datos = z.infer<typeof esquema>;

export function Login() {
  const { usuario, iniciar, aviso } = useAuth();
  const navegar = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const { register, handleSubmit, formState } = useForm<Datos>({ resolver: zodResolver(esquema) });

  if (usuario) return <Navigate to="/" replace />;

  const enviar = async (d: Datos) => {
    setError(null);
    try {
      await iniciar(d.username, d.password);
      navegar("/", { replace: true });
    } catch (e) {
      setError(mensajeDeError(e));
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-marca-800 to-marca-900 p-4">
      <div className="w-full max-w-sm rounded-lg bg-white p-6 shadow-xl">
        <div className="mb-6 flex items-center gap-3">
          <div className="rounded-lg bg-marca-700 p-2 text-white"><ClipboardList className="h-6 w-6" aria-hidden /></div>
          <div>
            <h1 className="text-lg font-semibold">SIGET WEB</h1>
            <p className="text-xs text-slate-500">Universidad Nacional de Barranca</p>
          </div>
        </div>
        <form onSubmit={handleSubmit(enviar)} className="space-y-4" noValidate>
          {aviso && !error && <Alerta tipo="advertencia">{aviso}</Alerta>}
          {error && <Alerta tipo="error">{error}</Alerta>}
          <Campo etiqueta="Usuario" autoComplete="username" autoFocus obligatorio error={formState.errors.username?.message} {...register("username")} />
          <Campo etiqueta="Contraseña" type="password" autoComplete="current-password" obligatorio error={formState.errors.password?.message} {...register("password")} />
          <Boton type="submit" className="w-full" cargando={formState.isSubmitting}>Ingresar</Boton>
        </form>
      </div>
    </div>
  );
}
