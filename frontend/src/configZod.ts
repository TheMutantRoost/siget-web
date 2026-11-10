// Sin compilación JIT de Zod: la CSP del sitio no permite eval. Debe importarse antes que cualquier esquema.
import { z } from "zod";

z.config({ jitless: true });
