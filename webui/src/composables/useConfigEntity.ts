import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed, type MaybeRefOrGetter, toValue } from "vue";
import { api } from "@/lib/api";
import type { ConfigContract } from "@/types";

interface EntityConfig {
  listKey: string[];
  configKey: string[];
  configSection: string;
  ownerKind: "plugin" | "adapter";
}

function emptyContract(ownerKind: string, ownerId: string): ConfigContract {
  return {
    namespace: null,
    is_scoped: false,
    owner_kind: ownerKind as ConfigContract["owner_kind"],
    owner_id: ownerId,
    source: "none",
    fields: [],
    json_schema: {},
  };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function createEntityHooks(ent: any, cfg: EntityConfig) {
  function useList() {
    return useQuery({ queryKey: cfg.listKey, queryFn: () => ent.list() });
  }

  function useConfig(name: MaybeRefOrGetter<string>) {
    return useQuery({
      queryKey: computed(() => [...cfg.configKey, toValue(name)]),
      queryFn: async () => {
        const id = toValue(name);
        try {
          const res = await ent.config(id);
          return { schema: res as ConfigContract, values: res.values || {} };
        } catch (e) {
          if ((e as { status?: number }).status === 404) {
            return {
              schema: emptyContract(cfg.ownerKind, id),
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

  function useSaveConfig() {
    const qc = useQueryClient();
    return useMutation({
      mutationFn: async (vars: { name: string; data: Record<string, unknown> }) => {
        await api.config.update(cfg.configSection, { [vars.name]: vars.data });
      },
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: cfg.configKey });
      },
    });
  }

  function useMutations() {
    const qc = useQueryClient();
    const invalidate = () => qc.invalidateQueries({ queryKey: cfg.listKey });
    return {
      install: useMutation({ mutationFn: ent.install, onSuccess: invalidate }),
      uninstall: useMutation({ mutationFn: ent.uninstall, onSuccess: invalidate }),
      setState: useMutation({ mutationFn: ent.setState, onSuccess: invalidate }),
    };
  }

  return { useList, useConfig, useSaveConfig, useMutations };
}
