import { z } from "zod";

const environmentSchema = z.object({
  VITE_API_BASE_URL: z.string().min(1).default("/"),
});

export const runtimeConfig = environmentSchema.parse(import.meta.env);
