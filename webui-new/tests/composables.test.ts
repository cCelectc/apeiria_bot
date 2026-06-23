import { describe, it, expect, vi } from "vitest"
import { useRequest } from "@/composables/useRequest"
import { useForm } from "@/composables/useForm"
import { z } from "zod"

describe("useRequest", () => {
  it("returns loading state initially", () => {
    const { loading } = useRequest("test", async () => "hello")
    expect(loading.value).toBe(true)
  })

  it("sets data after fetch", async () => {
    const { data, loading } = useRequest("test-fetch", async () => "result")
    await vi.waitFor(() => !loading.value)
    expect(data.value).toBe("result")
    expect(loading.value).toBe(false)
  })

  it("handles errors", async () => {
    const { error, loading } = useRequest("test-error", async () => {
      throw new Error("fail")
    })
    await vi.waitFor(() => !loading.value)
    expect(error.value).toBe("fail")
  })

  it("mutate updates data optimistically", () => {
    const { data, mutate } = useRequest("test-mutate", () => Promise.resolve([1]))
    mutate((prev) => [...(prev ?? []), 2])
    expect(data.value).toEqual([2])  // prev is undefined before fetch resolves
  })
})

describe("useForm", () => {
  const schema = z.object({
    name: z.string().min(1, "Required"),
    age: z.coerce.number().min(0),
  })

  it("returns form and errors", () => {
    const { form, errors } = useForm({
      schema,
      onSubmit: async () => {},
    })
    expect(form.name).toBeUndefined()
    expect(Object.keys(errors)).toHaveLength(0)
  })

  it("validates on submit", async () => {
    const onSubmit = vi.fn()
    const { form, errors, submit } = useForm({ schema, onSubmit })
    form.name = ""
    const ok = await submit()
    expect(ok).toBe(false)
    expect(errors.name).toBe("Required")
    expect(onSubmit).not.toHaveBeenCalled()
  })
})
