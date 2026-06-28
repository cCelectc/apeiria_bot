import { useQuery } from "@tanstack/vue-query";
import { computed, type MaybeRefOrGetter, toValue } from "vue";
import { api } from "@/lib/api";

export interface LogHistoryParams {
  level?: string;
  q?: string;
  source?: string;
  since?: number;
  until?: number;
  page?: number;
  size?: number;
}

export function useLogHistoryQuery(params: MaybeRefOrGetter<LogHistoryParams>) {
  return useQuery({
    queryKey: computed(() => ["logs-history", toValue(params)]),
    queryFn: () => api.logs.history(toValue(params)),
  });
}
