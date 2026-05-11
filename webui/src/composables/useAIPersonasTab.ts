import type { AIPersonaBindingItem, AIPersonaItem } from '@/api/ai'
import { computed, reactive, ref } from 'vue'
import {
  getAIPersonaBindings,
  getAIPersonas,
  upsertAIPersona,
} from '@/api/ai'
import { getErrorMessage } from '@/api/client'
import { useNoticeStore } from '@/stores/notice'

export interface PersonaFormState {
  persona_id: string
  name: string
  description: string
  system_prompt: string
  style_prompt: string
  enabled: boolean
}

function buildPersonaSnapshot(form: PersonaFormState) {
  return JSON.stringify({
    description: form.description.trim(),
    enabled: form.enabled,
    name: form.name.trim(),
    persona_id: form.persona_id,
    style_prompt: form.style_prompt.trim(),
    system_prompt: form.system_prompt.trim(),
  })
}

export function useAIPersonasTab(t: (key: string) => string) {
  const noticeStore = useNoticeStore()

  const personas = ref<AIPersonaItem[]>([])
  const personaBindings = ref<AIPersonaBindingItem[]>([])
  const loadingPersonas = ref(false)
  const savingPersona = ref(false)
  const personaBaseline = ref('')
  const personaSubmitAttempted = ref(false)
  const personaTouched = reactive({
    description: false,
    name: false,
    system_prompt: false,
  })
  const personaForm = reactive<PersonaFormState>({
    description: '',
    enabled: true,
    name: '',
    persona_id: '',
    style_prompt: '',
    system_prompt: '',
  })

  const selectedPersona = computed(() => (
    personas.value.find(item => item.persona_id === personaForm.persona_id) ?? null
  ))
  const selectedPersonaBindingCount = computed(() => (
    personaBindings.value.filter(item => item.persona_id === personaForm.persona_id).length
  ))
  const personaErrors = computed(() => ({
    description: personaForm.description.trim().length === 0
      ? t('ai.personaDescriptionRequired')
      : '',
    name: personaForm.name.trim().length === 0
      ? t('ai.personaNameRequired')
      : '',
    system_prompt: personaForm.system_prompt.trim().length === 0
      ? t('ai.personaSystemPromptRequired')
      : '',
  }))
  const displayedPersonaErrors = computed(() => ({
    description: personaTouched.description || personaSubmitAttempted.value
      ? personaErrors.value.description
      : '',
    name: personaTouched.name || personaSubmitAttempted.value
      ? personaErrors.value.name
      : '',
    system_prompt: personaTouched.system_prompt || personaSubmitAttempted.value
      ? personaErrors.value.system_prompt
      : '',
  }))
  const personaValid = computed(() => (
    !personaErrors.value.description
    && !personaErrors.value.name
    && !personaErrors.value.system_prompt
  ))
  const personaDirty = computed(() => buildPersonaSnapshot(personaForm) !== personaBaseline.value)
  const isCreatingPersona = computed(() => personaForm.persona_id.length === 0)
  const canSavePersona = computed(() => (
    personaValid.value
    && personaDirty.value
    && !savingPersona.value
  ))

  function resetPersonaValidation() {
    personaSubmitAttempted.value = false
    personaTouched.description = false
    personaTouched.name = false
    personaTouched.system_prompt = false
  }

  function syncPersonaBaseline() {
    personaBaseline.value = buildPersonaSnapshot(personaForm)
  }

  function touchPersonaField(field: keyof typeof personaTouched) {
    personaTouched[field] = true
  }

  function selectPersona(item: AIPersonaItem) {
    personaForm.description = item.description
    personaForm.enabled = item.enabled
    personaForm.name = item.name
    personaForm.persona_id = item.persona_id
    personaForm.style_prompt = item.style_prompt
    personaForm.system_prompt = item.system_prompt
    syncPersonaBaseline()
    resetPersonaValidation()
  }

  function startCreatePersona() {
    personaForm.description = ''
    personaForm.enabled = true
    personaForm.name = ''
    personaForm.persona_id = ''
    personaForm.style_prompt = ''
    personaForm.system_prompt = ''
    syncPersonaBaseline()
    resetPersonaValidation()
  }

  async function loadPersonasData() {
    loadingPersonas.value = true
    try {
      const [personasResponse, bindingsResponse] = await Promise.all([
        getAIPersonas(),
        getAIPersonaBindings(),
      ])
      personas.value = personasResponse.data
      personaBindings.value = bindingsResponse.data
      const current = personas.value.find(item => item.persona_id === personaForm.persona_id)
      if (current) {
        selectPersona(current)
      } else if (!personaForm.persona_id && personas.value.length > 0) {
        selectPersona(personas.value[0])
      }
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.loadFailed')), 'error')
    } finally {
      loadingPersonas.value = false
    }
  }

  async function savePersona() {
    personaSubmitAttempted.value = true
    if (!personaValid.value) {
      noticeStore.show(
        personaErrors.value.name
        || personaErrors.value.description
        || personaErrors.value.system_prompt
        || t('ai.personaSaveFailed'),
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
        description: personaForm.description.trim(),
        enabled: personaForm.enabled,
        name: personaForm.name.trim(),
        persona_id: personaForm.persona_id || null,
        style_prompt: personaForm.style_prompt.trim(),
        system_prompt: personaForm.system_prompt.trim(),
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
    loadingPersonas,
    personaBindings,
    personaForm,
    personas,
    savePersona,
    savingPersona,
    selectPersona,
    selectedPersona,
    selectedPersonaBindingCount,
    startCreatePersona,
    touchPersonaField,
  }
}
