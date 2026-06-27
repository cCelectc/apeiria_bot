import { keepPreviousData, useQuery } from "@tanstack/vue-query";
import { computed, type MaybeRefOrGetter, toValue } from "vue";
import { api } from "@/lib/api";

export const STORE_PAGE_SIZE = 60;

export function useStorePluginsQuery(
  query: MaybeRefOrGetter<string>,
  page: MaybeRefOrGetter<number> = 1,
  enabled: MaybeRefOrGetter<boolean> = true,
) {
  return useQuery({
    queryKey: computed(() => ["store-plugins", toValue(query), toValue(page)]),
    queryFn: () =>
      api.store.searchPlugins(
        toValue(query),
        STORE_PAGE_SIZE,
        (toValue(page) - 1) * STORE_PAGE_SIZE,
      ),
    enabled: computed(() => toValue(enabled)),
    placeholderData: keepPreviousData,
  });
}

export function useStoreAdaptersQuery(
  query: MaybeRefOrGetter<string>,
  page: MaybeRefOrGetter<number> = 1,
  enabled: MaybeRefOrGetter<boolean> = true,
) {
  return useQuery({
    queryKey: computed(() => ["store-adapters", toValue(query), toValue(page)]),
    queryFn: () =>
      api.store.searchAdapters(
        toValue(query),
        STORE_PAGE_SIZE,
        (toValue(page) - 1) * STORE_PAGE_SIZE,
      ),
    enabled: computed(() => toValue(enabled)),
    placeholderData: keepPreviousData,
  });
}
