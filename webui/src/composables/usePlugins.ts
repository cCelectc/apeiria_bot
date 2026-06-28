import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed, type MaybeRefOrGetter, toValue } from "vue";
import { api } from "@/lib/api";
import { fetchConfig } from "./useConfigEntity";

export function usePluginsQuery() {
  return useQuery({ queryKey: ["plugins"], queryFn: () => api.plugins.list() });
}

export function usePluginConfigQuery(name: MaybeRefOrGetter<string>) {
  return useQuery({
    queryKey: computed(() => ["plugin-config", toValue(name)]),
    queryFn: () => fetchConfig(() => api.plugins.config(toValue(name)), "plugin", toValue(name)),
    enabled: computed(() => Boolean(toValue(name))),
    retry: false,
  });
}

export function useSavePluginConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: { name: string; data: Record<string, unknown> }) => {
      await api.config.update("plugins", { [vars.name]: vars.data });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["plugin-config"] }),
  });
}

export function usePluginMutations() {
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: ["plugins"] });
  return {
    install: useMutation({
      mutationFn: (vars: { name: string; pkg: string }) =>
        api.plugins.install(vars).then((r) => r.task_id),
      onSuccess: invalidate,
    }),
    uninstall: useMutation({
      mutationFn: (vars: { name: string; keep_config?: boolean }) =>
        api.plugins.uninstall(vars).then((r) => r.task_id),
      onSuccess: invalidate,
    }),
    setState: useMutation({ mutationFn: api.plugins.setState, onSuccess: invalidate }),
  };
}
