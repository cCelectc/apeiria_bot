import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed, type MaybeRefOrGetter, toValue } from "vue";
import { api } from "@/lib/api";
import { fetchConfig } from "./useConfigEntity";

export function useAdaptersQuery() {
  return useQuery({ queryKey: ["adapters"], queryFn: () => api.adapters.list() });
}

export function useAdapterConfigQuery(name: MaybeRefOrGetter<string>) {
  return useQuery({
    queryKey: computed(() => ["adapter-config", toValue(name)]),
    queryFn: () => fetchConfig(() => api.adapters.config(toValue(name)), "adapter", toValue(name)),
    enabled: computed(() => Boolean(toValue(name))),
    retry: false,
  });
}

export function useSaveAdapterConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: { name: string; data: Record<string, unknown> }) => {
      await api.config.update("adapters", { [vars.name]: vars.data });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["adapter-config"] }),
  });
}

export function useAdapterMutations() {
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: ["adapters"] });
  return {
    install: useMutation({ mutationFn: api.adapters.install, onSuccess: invalidate }),
    uninstall: useMutation({ mutationFn: api.adapters.uninstall, onSuccess: invalidate }),
    setState: useMutation({ mutationFn: api.adapters.setState, onSuccess: invalidate }),
  };
}
