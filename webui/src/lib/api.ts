import router from "@/router";
import { useAuthStore } from "@/stores/auth";
import type {
  Adapter,
  ConfigContract,
  LogHistory,
  LoginResponse,
  Plugin,
  StatusInfo,
  StoreSearchResult,
} from "@/types";

const BASE = "/api";

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const auth = useAuthStore();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (auth.token) headers.Authorization = `Bearer ${auth.token}`;

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (res.status === 401) {
    auth.clearSession();
    if (router.currentRoute.value.name !== "login") {
      void router.push({ name: "login" });
    }
    throw new Error("未授权，请重新登录");
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = (await res.json()) as { detail?: string };
      if (data.detail) detail = data.detail;
    } catch {
      // ignore non-JSON error bodies
    }
    const err = new Error(detail) as Error & { status?: number };
    err.status = res.status;
    throw err;
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  auth: {
    login: (data: { username: string; password: string }) =>
      request<LoginResponse>("POST", "/auth/login", data),
    changePassword: (data: { old_password: string; new_password: string }) =>
      request<{ ok: boolean }>("POST", "/auth/change-password", data),
  },
  status: {
    get: () => request<StatusInfo>("GET", "/status"),
  },
  plugins: {
    list: () => request<{ plugins: Plugin[] }>("GET", "/plugins/list"),
    install: (data: { name: string; pkg: string }) =>
      request<{ ok: boolean }>("POST", "/plugins/install", data),
    uninstall: (data: { name: string; keep_config?: boolean }) =>
      request<{ ok: boolean }>("POST", "/plugins/uninstall", data),
    setState: (data: { name: string; enabled: boolean }) =>
      request<{ ok: boolean }>("POST", "/plugins/state", data),
    config: (name: string) =>
      request<ConfigContract & { values: Record<string, unknown> }>(
        "GET",
        `/plugins/${name}/config`,
      ),
  },
  adapters: {
    list: () => request<{ adapters: Adapter[] }>("GET", "/adapters/list"),
    install: (data: { name: string; pkg: string; module_name: string }) =>
      request<{ ok: boolean }>("POST", "/adapters/install", data),
    uninstall: (data: { name: string; keep_config?: boolean }) =>
      request<{ ok: boolean }>("POST", "/adapters/uninstall", data),
    setState: (data: { name: string; enabled: boolean }) =>
      request<{ ok: boolean }>("POST", "/adapters/state", data),
    config: (name: string) =>
      request<ConfigContract & { values: Record<string, unknown> }>(
        "GET",
        `/adapters/${name}/config`,
      ),
  },
  config: {
    get: () => request<Record<string, unknown>>("GET", "/config"),
    update: (section: string, data: Record<string, unknown>) =>
      request<{ ok: boolean }>("PUT", `/config/${section}`, data),
    schema: (section: string) =>
      request<ConfigContract>("GET", `/config/schema/${section}`),
  },
  store: {
    searchPlugins: (q: string, limit = 60, offset = 0) =>
      request<StoreSearchResult>(
        "GET",
        `/store/plugins?q=${encodeURIComponent(q)}&limit=${limit}&offset=${offset}`,
      ),
    searchAdapters: (q: string, limit = 60, offset = 0) =>
      request<StoreSearchResult>(
        "GET",
        `/store/adapters?q=${encodeURIComponent(q)}&limit=${limit}&offset=${offset}`,
      ),
  },
  logs: {
    history: (params: {
      level?: string;
      q?: string;
      page?: number;
      size?: number;
    }) => {
      const sp = new URLSearchParams();
      if (params.level) sp.set("level", params.level);
      if (params.q) sp.set("q", params.q);
      sp.set("page", String(params.page ?? 1));
      sp.set("size", String(params.size ?? 100));
      return request<LogHistory>("GET", `/logs/history?${sp.toString()}`);
    },
  },
};
