import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed } from "vue";
import type { ComputedRef } from "vue";
import { api } from "@/lib/api";
import { useConfigQuery } from "./useConfig";

const qc = () => useQueryClient();

export function useConfigSchema(section: string) {
  return useQuery({
    queryKey: ["configSchema", section],
    queryFn: () => api.config.schema(section),
  });
}

function _useSectionConfig(section: string): {
  data: ComputedRef<Record<string, unknown> | undefined>;
  isLoading: ComputedRef<boolean>;
  isError: ComputedRef<boolean>;
  error: ComputedRef<Error | null>;
  refetch: () => Promise<unknown>;
} {
  const query = useConfigQuery();
  return {
    data: computed(() => (query.data.value as Record<string, unknown>)?.[section] as Record<string, unknown> | undefined),
    isLoading: computed(() => query.isLoading.value),
    isError: computed(() => query.isError.value),
    error: computed(() => query.error.value as Error | null),
    refetch: () => query.refetch(),
  };
}

export function useNonebotConfig() {
  return _useSectionConfig("nonebot");
}

export function useApeiriaConfig() {
  return _useSectionConfig("apeiria");
}

export function useSaveNonebotConfig() {
  return useMutation({
    mutationFn: async (data: Record<string, unknown>) => {
      await api.config.update("nonebot", data);
    },
    onSuccess: () => {
      qc().invalidateQueries({ queryKey: ["config"] });
    },
  });
}

export function useSaveApeiriaConfig() {
  return useMutation({
    mutationFn: async (data: Record<string, unknown>) => {
      await api.config.update("apeiria", data);
    },
    onSuccess: () => {
      qc().invalidateQueries({ queryKey: ["config"] });
    },
  });
}
