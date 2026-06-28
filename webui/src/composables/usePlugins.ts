import type { MaybeRefOrGetter } from "vue";
import { api } from "@/lib/api";
import { createEntityHooks } from "./useConfigEntity";

const plugin = createEntityHooks(api.plugins as Parameters<typeof createEntityHooks>[0], {
  listKey: ["plugins"],
  configKey: ["plugin-config"],
  configSection: "plugins",
  ownerKind: "plugin",
});

export const usePluginsQuery = plugin.useList;
export function usePluginConfigQuery(name: MaybeRefOrGetter<string>) {
  return plugin.useConfig(name);
}
export const useSavePluginConfig = plugin.useSaveConfig;
export const usePluginMutations = plugin.useMutations;
