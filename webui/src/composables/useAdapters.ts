import type { MaybeRefOrGetter } from "vue";
import { api } from "@/lib/api";
import { createEntityHooks } from "./useConfigEntity";

const adapter = createEntityHooks(api.adapters as Parameters<typeof createEntityHooks>[0], {
  listKey: ["adapters"],
  configKey: ["adapter-config"],
  configSection: "adapters",
  ownerKind: "adapter",
});

export const useAdaptersQuery = adapter.useList;
export function useAdapterConfigQuery(name: MaybeRefOrGetter<string>) {
  return adapter.useConfig(name);
}
export const useSaveAdapterConfig = adapter.useSaveConfig;
export const useAdapterMutations = adapter.useMutations;
