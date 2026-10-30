import type { PetConfig } from "@petforge/pet-schema";

const API_BASE = "/api";

export interface PetRecord {
  id: string;
  name: string;
  config: PetConfig;
  originalImage: string | null;
  processedImage: string | null;
  modelUrl: string | null;
  createdAt: string;
  updatedAt: string;
}

interface ApiEnvelope<T> {
  data: T | null;
  error: { code: string; message: string } | null;
}

export function imageUrl(path: string | null): string | null {
  if (!path) return null;
  if (/^https?:\/\//.test(path)) return path;
  return path;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new Error("无法连接 PetForge 服务，请稍后重试。");
  }
  let payload: ApiEnvelope<T>;
  try {
    payload = (await response.json()) as ApiEnvelope<T>;
  } catch {
    throw new Error(`本机处理服务返回异常（${response.status}）。请确认服务正在运行；首次处理可能需要下载模型，请稍后重试。`);
  }
  if (!response.ok || payload.error || payload.data === null) {
    throw new Error(payload.error?.message ?? `请求失败（${response.status}）`);
  }
  return payload.data;
}

export const api = {
  createPet: (name: string) => request<PetRecord>("/pets", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }) }),
  readPet: (id: string) => request<PetRecord>(`/pets/${id}`),
  upload: (id: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<PetRecord>(`/pets/${id}/image`, { method: "POST", body: form });
  },
  useOriginal: (id: string) => request<PetRecord>(`/pets/${id}/use-original`, { method: "POST" }),
  removeBackground: (id: string) => request<{ status: "processed" | "not_generated"; provider: string; imageUrl: string; width: number; height: number; note: string }>(`/pets/${id}/remove-background`, { method: "POST" }),
  generateModel: (id: string) => request<{ status: "generated"; provider: string; modelUrl: string; note: string }>(`/pets/${id}/generate-model`, { method: "POST" }),
  restoreOriginal: (id: string) => request<{ restored: boolean }>(`/pets/${id}/restore-original`, { method: "POST" }),
  save: (id: string, config: PetConfig) => request<PetRecord>(`/pets/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: config.name, appearance: config.appearance, behavior: config.behavior, window: config.window }),
  }),
  launch: (id: string) => request<{ started: boolean; petId: string }>(`/pets/${id}/launch`, { method: "POST" }),
  export: async (id: string) => {
    let response: Response;
    try {
      response = await fetch(`${API_BASE}/pets/${id}/export`, { method: "POST" });
    } catch {
      throw new Error("无法连接 PetForge 服务，请稍后重试。");
    }
    if (!response.ok) {
      let payload: ApiEnvelope<never>;
      try { payload = (await response.json()) as ApiEnvelope<never>; }
      catch { throw new Error(`导出服务返回异常（${response.status}），请检查本机服务。`); }
      throw new Error(payload.error?.message ?? `导出失败（${response.status}）`);
    }
    return response.blob();
  },
};
