import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router";
import { z } from "zod";

import { api, mensajeDeError } from "../api/cliente";
import { Alerta, Boton, Campo, Tarjeta } from "../components/ui";
import { useAuth } from "../contexts/Auth";

const esquema = z
  .object({
    actual: z.string().min(1, "Ingrese su contraseña actual."),
    nueva: z.string().min(10, "Mínimo 10 caracteres."),
    repetir: z.string(),
  })
  .refine((d) => d.nueva === d.repetir, { path: ["repetir"], message: "Las contraseñas no coinciden." });
type Datos = z.infer<typeof esquema>;

export function CambiarPassword() {
  const { usuario, recargar } = useAuth();
  const navegar = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const { register, handleSubmit, formState } = useForm<Datos>({ resolver: zodResolver(esquema) });

  const enviar = async (d: Datos) => {
    setError(null);
    try {
      await api.post("/auth/cambiar-password", { actual: d.actual, nueva: d.nueva });
      await recargar();
      navegar("/", { replace: true });
    } catch (e) {
      setError(mensajeDeError(e));
    }
  };

  return (
    <div className="mx-auto max-w-md">
      <Tarjeta titulo="Cambiar contraseña">
        <form onSubmit={handleSubmit(enviar)} className="space-y-4" noValidate>
          {usuario?.debe_cambiar_password && <Alerta tipo="advertencia">Por seguridad, debe cambiar su contraseña antes de continuar.</Alerta>}
          {error && <Alerta tipo="error">{error}</Alerta>}
          <Campo etiqueta="Contraseña actual" type="password" autoComplete="current-password" obligatorio error={formState.errors.actual?.message} {...register("actual")} />
          <Campo etiqueta="Nueva contraseña" type="password" autoComplete="new-password" obligatorio ayuda="Mínimo 10 caracteres, combinando letras y números o símbolos." error={formState.errors.nueva?.message} {...register("nueva")} />
          <Campo etiqueta="Repetir nueva contraseña" type="password" autoComplete="new-password" obligatorio error={formState.errors.repetir?.message} {...register("repetir")} />
          <Boton type="submit" cargando={formState.isSubmitting}>Guardar</Boton>
        </form>
      </Tarjeta>
    </div>
  );
}
