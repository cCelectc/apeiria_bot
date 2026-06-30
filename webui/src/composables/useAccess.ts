import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed, type MaybeRefOrGetter, toValue } from "vue";
import { api } from "@/lib/api";

export function useAccessRulesQuery() {
  return useQuery({ queryKey: ["access-rules"], queryFn: () => api.access.rulesList() });
}

export function useAccessMutations() {
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: ["access-rules"] });
  return {
    create: useMutation({ mutationFn: api.access.rulesCreate, onSuccess: invalidate }),
    update: useMutation({
      mutationFn: (vars: { id: number; data: Record<string, unknown> }) =>
        api.access.rulesUpdate(vars.id, vars.data),
      onSuccess: invalidate,
    }),
    remove: useMutation({
      mutationFn: (id: number) => api.access.rulesDelete(id),
      onSuccess: invalidate,
    }),
    reorder: useMutation({
      mutationFn: (ids: number[]) => api.access.rulesReorder(ids),
      onSuccess: invalidate,
    }),
  };
}

export function useAccessPreviewQuery(params: MaybeRefOrGetter<{
  subject_type: string;
  subject_id: string;
  plugin_name: string;
} | null>) {
  return useQuery({
    queryKey: computed(() => ["access-preview", toValue(params)]),
    queryFn: () => {
      const p = toValue(params);
      return p ? api.access.rulesPreview(p) : Promise.resolve(null);
    },
    enabled: computed(() => Boolean(toValue(params))),
    retry: false,
  });
}

export function useAccessSubjectsSearchQuery(
  q: MaybeRefOrGetter<string>,
  type: MaybeRefOrGetter<string>,
) {
  return useQuery({
    queryKey: computed(() => ["access-subjects", toValue(q), toValue(type)]),
    queryFn: () => api.access.subjectsSearch(toValue(q), toValue(type)),
    enabled: computed(() => toValue(q).length > 0),
  });
}

export function usePluginNamesQuery() {
  return useQuery({
    queryKey: ["plugins-names"],
    queryFn: () => api.access.pluginsNames(),
    staleTime: 60_000,
  });
}
