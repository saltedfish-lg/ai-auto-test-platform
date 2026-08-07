import { runtimeConfig } from "../config";
import { ApiClient } from "../generated/client";

export const apiClient = new ApiClient(runtimeConfig.VITE_API_BASE_URL);
