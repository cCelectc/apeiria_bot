import type { ConfigContract } from "@/types";

export function emptyContract(ownerKind: "plugin" | "adapter", ownerId: string): ConfigContract {
  return {
    namespace: null,
    is_scoped: false,
    owner_kind: ownerKind,
    owner_id: ownerId,
    source: "none",
    fields: [],
    json_schema: {},
  };
}

export async function fetchConfig(
  apiCall: () => Promise<ConfigContract & { values?: Record<string, unknown> }>,
  ownerKind: "plugin" | "adapter",
  ownerId: string,
): Promise<{ schema: ConfigContract; values: Record<string, unknown> }> {
  try {
    const res = await apiCall();
    return { schema: res as ConfigContract, values: res.values || {} };
  } catch (e) {
    if ((e as { status?: number }).status === 404) {
      return {
        schema: emptyContract(ownerKind, ownerId),
        values: {} as Record<string, unknown>,
      };
    }
    throw e;
  }
}
