import type { AIPersonaBindingItem, AIPersonaItem } from '@/api/ai'
import { computed, reactive, ref } from 'vue'
import { getAIPersonaBindings, getAIPersonas, upsertAIPersona } from '@/api/ai'
import { getErrorMessage } from '@/api/client'
import { useNoticeStore } from '@/stores/notice'

interface PersonaFormState {
  persona_id: string
  name: string
  description: string
  system_prompt: string
  style_prompt: string
  enabled: boolean
}

function buildPersonaSnapshot (form: PersonaFormState) {
  return JSON.stringify({
    persona_id: form.persona_id,
    name: form.name.trim(),
    description: form.description.trim(),
    system_prompt: form.system_prompt.trim(),
    style_prompt: form.style_prompt.trim(),
    enabled: form.enabled,
  })
}

export function useAIPersonasTab (t: (key: string) => string) {
  const noticeStore = useNoticeStore()

  const personas = ref<AIPersonaItem[]>([])
  const personaBindings = ref<AIPersonaBindingItem[]>([])
  const savingPersona = ref(false)
  const personaBaseline = ref('')
  const personaSubmitAttempted = ref(false)
  const personaTouched = reactive({
    name: false,
    description: false,
    system_prompt: false,
  })
  const personaForm = reactive<PersonaFormState>({
    persona_id: '',
    name: '',
    description: '',
    system_prompt: '',
    style_prompt: '',
    enabled: true,
  })

  const selectedPersona = computed(() => (
    personas.value.find(item => item.persona_id === personaForm.persona_id) ?? null
  ))

  const personaErrors = computed(() => ({
    name: personaForm.name.trim().length === 0 ? t('ai.personaNameRequired') : '',
    description: personaForm.description.trim().length === 0 ? t('ai.personaDescriptionRequired') : '',
    system_prompt: personaForm.system_prompt.trim().length === 0 ? t('ai.personaSystemPromptRequired') : '',
  }))

  const displayedPersonaErrors = computed(() => ({
    name: personaTouched.name || personaSubmitAttempted.value ? personaErrors.value.name : '',
    description: personaTouched.description || personaSubmitAttempted.value ? personaErrors.value.description : '',
    system_prompt: personaTouched.system_prompt || personaSubmitAttempted.value ? personaErrors.value.system_prompt : '',
  }))

  const personaValid = computed(() => !personaErrors.value.name && !personaErrors.value.description && !personaErrors.value.system_prompt)
  const personaDirty = computed(() => buildPersonaSnapshot(personaForm) !== personaBaseline.value)
  const isCreatingPersona = computed(() => personaForm.persona_id.length === 0)
  const canSavePersona = computed(() => personaValid.value && personaDirty.value && !savingPersona.value)

  async function loadPersonasData () {
    const [personasResponse, personaBindingsResponse] = await Promise.all([
      getAIPersonas(),
      getAIPersonaBindings(),
    ])
    personas.value = personasResponse.data
    personaBindings.value = personaBindingsResponse.data
    if (!personaForm.persona_id && personas.value.length > 0) {
      selectPersona(personas.value[0])
    }
  }

  function resetPersonaValidation () {
    personaSubmitAttempted.value = false
    personaTouched.name = false
    personaTouched.description = false
    personaTouched.system_prompt = false
  }

  function syncPersonaBaseline () {
    personaBaseline.value = buildPersonaSnapshot(personaForm)
  }

  function touchPersonaField (field: keyof typeof personaTouched) {
    personaTouched[field] = true
  }

  function selectPersona (item: AIPersonaItem) {
    personaForm.persona_id = item.persona_id
    personaForm.name = item.name
    personaForm.description = item.description
    personaForm.system_prompt = item.system_prompt
    personaForm.style_prompt = item.style_prompt
    personaForm.enabled = item.enabled
    syncPersonaBaseline()
    resetPersonaValidation()
  }

  function startCreatePersona () {
    personaForm.persona_id = ''
    personaForm.name = ''
    personaForm.description = ''
    personaForm.system_prompt = ''
    personaForm.style_prompt = ''
    personaForm.enabled = true
    syncPersonaBaseline()
    resetPersonaValidation()
  }

  async function savePersona () {
    personaSubmitAttempted.value = true
    if (!personaValid.value) {
      noticeStore.show(
        personaErrors.value.name || personaErrors.value.description || personaErrors.value.system_prompt || t('ai.personaSaveFailed'),
        'error',
      )
      return
    }
    if (!personaDirty.value) {
      return
    }
    savingPersona.value = true
    try {
      const response = await upsertAIPersona({
        persona_id: personaForm.persona_id || null,
        name: personaForm.name.trim(),
        description: personaForm.description.trim(),
        system_prompt: personaForm.system_prompt.trim(),
        style_prompt: personaForm.style_prompt.trim(),
        enabled: personaForm.enabled,
      })
      if (response.data) {
        await loadPersonasData()
        selectPersona(response.data)
      }
      noticeStore.show(t('ai.personaSaved'), 'success')
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.personaSaveFailed')), 'error')
    } finally {
      savingPersona.value = false
    }
  }

  return {
    canSavePersona,
    displayedPersonaErrors,
    isCreatingPersona,
    loadPersonasData,
    personaBindings,
    personaForm,
    personas,
    savePersona,
    savingPersona,
    selectPersona,
    selectedPersona,
    startCreatePersona,
    touchPersonaField,
  }
}
