import { reactive, ref, isReactive } from "vue"
import type { ZodSchema } from "zod"
import { flattenZodErrors } from "@/utils/zod"

type FormData = Record<string, unknown>

interface UseFormOptions<T extends FormData> {
  schema: ZodSchema<T>
  onSubmit: (data: T) => Promise<void>
  initialValues?: Partial<T>
  onSuccess?: () => void
}

interface UseFormReturn<T extends FormData> {
  form: T
  errors: Record<string, string>
  submitting: ReturnType<typeof ref<boolean>>
  submit: () => Promise<boolean>
  reset: () => void
  setFieldError: (field: string, message: string) => void
}

export function useForm<T extends FormData>({
  schema,
  onSubmit,
  initialValues,
  onSuccess,
}: UseFormOptions<T>): UseFormReturn<T> {
  const defaultValues = { ...initialValues } as T
  const form = isReactive(defaultValues) ? defaultValues : reactive({ ...defaultValues }) as T
  const errors = reactive<Record<string, string>>({})
  const submitting = ref(false)

  function clearErrors(): void {
    for (const key of Object.keys(errors)) {
      delete errors[key]
    }
  }

  function setFieldError(field: string, message: string): void {
    errors[field] = message
  }

  function reset(): void {
    clearErrors()
    for (const key of Object.keys(form)) {
      delete (form as Record<string, unknown>)[key]
    }
    if (initialValues) {
      Object.assign(form, initialValues)
    }
  }

  async function submit(): Promise<boolean> {
    clearErrors()

    const result = schema.safeParse(form)
    if (!result.success) {
      const flat = flattenZodErrors(result.error)
      for (const [field, message] of Object.entries(flat)) {
        errors[field] = message
      }
      return false
    }

    submitting.value = true
    try {
      await onSubmit(result.data as T)
      onSuccess?.()
      return true
    } catch {
      return false
    } finally {
      submitting.value = false
    }
  }

  return { form, errors, submitting, submit, reset, setFieldError }
}
