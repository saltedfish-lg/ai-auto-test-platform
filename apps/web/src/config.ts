import { z } from "zod";

const environmentSchema = z.object({
  VITE_API_BASE_URL: z.string().default(""),
});

const environment = environmentSchema.parse(import.meta.env);

export function normalizeApiBaseUrl(baseUrl: string): string {
  const normalized = baseUrl.trim();
  return normalized === "/" ? "" : normalized.replace(/\/+$/, "");
}

export const runtimeConfig = {
  VITE_API_BASE_URL: normalizeApiBaseUrl(environment.VITE_API_BASE_URL),
};
