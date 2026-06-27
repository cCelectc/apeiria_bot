import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed, type MaybeRefOrGetter, toValue } from "vue";
import { api } from "@/lib/api";
import type { ConfigContract } from "@/types";

function emptyContract(ownerId: string): ConfigContract {
  return {
    namespace: null,
    is_scoped: false,
    owner_kind: "adapter",
    owner_id: ownerId,
    source: "none",
    fields: [],
    json_schema: {},
  };
}

export function useAdaptersQuery() {
  return useQuery({
    queryKey: ["adapters"],
    queryFn: () => api.adapters.list(),
  });
}

export function useAdapterConfigQuery(name: MaybeRefOrGetter<string>) {
  return useQuery({
    queryKey: computed(() => ["adapter-config", toValue(name)]),
    queryFn: async () => {
      const id = toValue(name);
      try {
        const res = await api.adapters.config(id);
        return { schema: res as ConfigContract, values: res.values || {} };
      } catch (e) {
        if ((e as { status?: number }).status === 404) {
          return {
            schema: emptyContract(id),
            values: {} as Record<string, unknown>,
          };
        }
        throw e;
      }
    },
    enabled: computed(() => Boolean(toValue(name))),
    retry: false,
  });
}

export function useSaveAdapterConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: {
      name: string;
      data: Record<string, unknown>;
    }) => {
      await api.config.update("adapters", { [vars.name]: vars.data });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["adapter-config"] });
    },
  });
}

export function useAdapterMutations() {
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: ["adapters"] });
  return {
    install: useMutation({
      mutationFn: api.adapters.install,
      onSuccess: invalidate,
    }),
    uninstall: useMutation({
      mutationFn: api.adapters.uninstall,
      onSuccess: invalidate,
    }),
    setState: useMutation({
      mutationFn: api.adapters.setState,
      onSuccess: invalidate,
    }),
  };
}
