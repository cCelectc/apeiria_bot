<template>
  <PageScaffold
    class="permission-workbench"
    dense
    :error-message="errorMessage"
    full-height
    :title="t('permissions.title')"
  >
    <template #actions>
      <v-btn :loading="loading" variant="tonal" @click="loadAll">{{ t('common.refresh') }}</v-btn>
    </template>

    <div class="permission-perspectives">
      <button
        v-for="item in perspectiveItems"
        :key="item.value"
        class="permission-perspective"
        :class="{ 'permission-perspective--active': perspective === item.value }"
        type="button"
        @click="perspective = item.value"
      >
        <span class="permission-perspective__label">{{ item.title }}</span>
        <span class="permission-perspective__meta">{{ item.meta }}</span>
      </button>
    </div>

    <v-fade-transition mode="out-in">
      <div v-if="perspective === 'plugins'" key="plugins" class="permission-view">
        <SplitPane class="permission-layout" full-height>
          <template #sidebar>
            <SelectableList class="permission-sidebar">
              <template #filters>
                <v-text-field
                  v-model="pluginSearch"
                  class="permission-sidebar__search"
                  clearable
                  density="compact"
                  hide-details
                  :placeholder="t('permissions.searchPlugins')"
                  prepend-inner-icon="mdi-magnify"
                  single-line
                  variant="outlined"
                />
              </template>

              <SelectableListItem
                v-for="item in visiblePlugins"
                :key="item.module_name"
                :active="item.module_name === selectedPluginModule"
                :subtitle="item.module_name"
                :title="item.name || item.module_name"
                :warning="!item.is_global_enabled || item.is_protected"
                @click="selectedPluginModule = item.module_name"
              >
                <template #meta>
                  <v-chip
                    v-if="!item.is_global_enabled"
                    color="warning"
                    size="x-small"
                    variant="tonal"
                  >
                    {{ t('permissions.globalOff') }}
                  </v-chip>

                  <v-chip
                    v-if="item.is_protected"
                    color="error"
                    size="x-small"
                    variant="tonal"
                  >
                    {{ t('permissions.protected') }}
                  </v-chip>

                  <v-chip
                    v-if="pluginRuleCount(item.module_name) > 0"
                    color="primary"
                    size="x-small"
                    variant="tonal"
                  >
                    {{ pluginRuleCount(item.module_name) }}
                  </v-chip>
                </template>
              </SelectableListItem>
            </SelectableList>
          </template>

          <section v-if="selectedPlugin" class="permission-main">
            <DetailPanel
              class="permission-panel permission-panel--hero"
              :subtitle="selectedPlugin.module_name"
              :title="selectedPlugin.name || selectedPlugin.module_name"
            >
              <template #actions>
                <div class="permission-inline-stat permission-inline-stat--control">
                  <span class="permission-inline-stat__label">{{ t('permissions.accessMode') }}</span>

                  <v-select
                    class="permission-access-mode"
                    density="compact"
                    hide-details
                    item-title="title"
                    item-value="value"
                    :items="accessModeOptions"
                    :loading="pendingPluginAccessMode"
                    :model-value="selectedPlugin.access_mode"
                    @update:model-value="updateSelectedPluginAccessMode"
                  />
                </div>

                <div class="permission-inline-stat">
                  <span class="permission-inline-stat__label">{{ t('permissions.explicitRules') }}</span>
                  <span class="permission-inline-stat__value">{{ selectedPluginRules.length }}</span>
                </div>
              </template>
            </DetailPanel>

            <div class="permission-grid">
              <v-card class="permission-panel surface-elevated-panel">
                <v-card-title>{{ t('permissions.userRules') }}</v-card-title>

                <v-card-text class="permission-rule-columns">
                  <div>
                    <div class="permission-section-title">{{ t('permissions.allow') }}</div>

                    <div v-if="selectedPluginUserAllowRules.length > 0" class="permission-rule-list">
                      <div
                        v-for="rule in selectedPluginUserAllowRules"
                        :key="ruleKey(rule)"
                        class="permission-rule-row"
                      >
                        <div>
                          <div class="font-weight-medium">{{ rule.subject_id }}</div>
                          <div class="text-caption text-medium-emphasis">{{ rule.note || t('permissions.noNote') }}</div>
                        </div>

                        <v-btn icon="mdi-delete" size="small" variant="text" @click="handleDeleteRule(rule)" />
                      </div>
                    </div>

                    <div v-else class="permission-empty">{{ t('permissions.noRules') }}</div>
                  </div>

                  <div>
                    <div class="permission-section-title">{{ t('permissions.deny') }}</div>

                    <div v-if="selectedPluginUserDenyRules.length > 0" class="permission-rule-list">
                      <div
                        v-for="rule in selectedPluginUserDenyRules"
                        :key="ruleKey(rule)"
                        class="permission-rule-row"
                      >
                        <div>
                          <div class="font-weight-medium">{{ rule.subject_id }}</div>
                          <div class="text-caption text-medium-emphasis">{{ rule.note || t('permissions.noNote') }}</div>
                        </div>

                        <v-btn icon="mdi-delete" size="small" variant="text" @click="handleDeleteRule(rule)" />
                      </div>
                    </div>

                    <div v-else class="permission-empty">{{ t('permissions.noRules') }}</div>
                  </div>
                </v-card-text>
              </v-card>

              <v-card class="permission-panel surface-elevated-panel">
                <v-card-title>{{ t('permissions.groupRules') }}</v-card-title>

                <v-card-text class="permission-rule-columns">
                  <div>
                    <div class="permission-section-title">{{ t('permissions.allow') }}</div>

                    <div v-if="selectedPluginGroupAllowRules.length > 0" class="permission-rule-list">
                      <div
                        v-for="rule in selectedPluginGroupAllowRules"
                        :key="ruleKey(rule)"
                        class="permission-rule-row"
                      >
                        <div>
                          <div class="font-weight-medium">{{ rule.subject_id }}</div>
                          <div class="text-caption text-medium-emphasis">{{ rule.note || t('permissions.noNote') }}</div>
                        </div>

                        <v-btn icon="mdi-delete" size="small" variant="text" @click="handleDeleteRule(rule)" />
                      </div>
                    </div>

                    <div v-else class="permission-empty">{{ t('permissions.noRules') }}</div>
                  </div>

                  <div>
                    <div class="permission-section-title">{{ t('permissions.deny') }}</div>

                    <div v-if="selectedPluginGroupDenyRules.length > 0" class="permission-rule-list">
                      <div
                        v-for="rule in selectedPluginGroupDenyRules"
                        :key="ruleKey(rule)"
                        class="permission-rule-row"
                      >
                        <div>
                          <div class="font-weight-medium">{{ rule.subject_id }}</div>
                          <div class="text-caption text-medium-emphasis">{{ rule.note || t('permissions.noNote') }}</div>
                        </div>

                        <v-btn icon="mdi-delete" size="small" variant="text" @click="handleDeleteRule(rule)" />
                      </div>
                    </div>

                    <div v-else class="permission-empty">{{ t('permissions.noRules') }}</div>
                  </div>
                </v-card-text>
              </v-card>
            </div>

            <v-card class="permission-panel surface-elevated-panel">
              <v-card-title>{{ t('permissions.createRuleTitle') }}</v-card-title>

              <v-card-text class="permission-form-grid">
                <v-select
                  v-model="pluginRuleForm.subject_type"
                  density="comfortable"
                  hide-details
                  :items="subjectTypeOptions"
                  :label="t('permissions.subjectType')"
                />

                <v-text-field
                  v-model="pluginRuleForm.subject_id"
                  density="comfortable"
                  hide-details
                  :label="t('permissions.subjectId')"
                  :placeholder="pluginRuleForm.subject_type === 'group' ? t('permissions.groupIdPlaceholder') : t('permissions.userIdPlaceholder')"
                />

                <v-select
                  v-model="pluginRuleForm.effect"
                  density="comfortable"
                  hide-details
                  :items="effectOptions"
                  :label="t('permissions.effect')"
                />

                <v-text-field
                  v-model="pluginRuleForm.note"
                  density="comfortable"
                  hide-details
                  :label="t('permissions.note')"
                />

                <div class="permission-form-grid__actions">
                  <v-btn
                    color="primary"
                    :disabled="!pluginRuleForm.subject_id.trim()"
                    :loading="creatingRule"
                    @click="createRuleForPlugin"
                  >
                    {{ t('permissions.createRule') }}
                  </v-btn>
                </div>
              </v-card-text>
            </v-card>

          </section>
        </SplitPane>
      </div>

      <div v-else-if="perspective === 'users'" key="users" class="permission-view">
        <SplitPane class="permission-layout" full-height>
          <template #sidebar>
            <SelectableList class="permission-sidebar">
              <template #filters>
                <v-text-field
                  v-model="userSearch"
                  class="permission-sidebar__search"
                  clearable
                  density="compact"
                  hide-details
                  :placeholder="t('permissions.searchUsers')"
                  prepend-inner-icon="mdi-magnify"
                  single-line
                  variant="outlined"
                />
              </template>

              <SelectableListItem
                v-for="item in visibleUserEntries"
                :key="item.user_id"
                :active="item.user_id === selectedUserId"
                :subtitle="t('permissions.userGroupsMeta', { count: item.groups })"
                :title="item.user_id"
                @click="selectedUserId = item.user_id"
              >
                <template #meta>
                  <v-chip v-if="item.rules > 0" color="primary" size="x-small" variant="tonal">
                    {{ item.rules }}
                  </v-chip>
                </template>
              </SelectableListItem>
            </SelectableList>
          </template>

          <section v-if="selectedUserId" class="permission-main">
            <DetailPanel
              class="permission-panel permission-panel--hero"
              :subtitle="t('permissions.userRulesAndLevels')"
              :title="selectedUserId"
            >
              <template #meta>
                <div class="permission-panel__eyebrow">{{ t('permissions.userView') }}</div>
              </template>
            </DetailPanel>

            <div class="permission-grid">
              <v-card class="permission-panel surface-elevated-panel">
                <v-card-title>{{ t('permissions.createRuleTitle') }}</v-card-title>

                <v-card-text class="permission-form-grid">
                  <v-select
                    v-model="userRuleForm.effect"
                    density="comfortable"
                    hide-details
                    :items="effectOptions"
                    :label="t('permissions.effect')"
                  />

                  <v-autocomplete
                    v-model="userRuleForm.plugin_module"
                    clearable
                    density="comfortable"
                    hide-details
                    item-title="title"
                    item-value="value"
                    :items="pluginModuleOptions"
                    :label="t('permissions.pluginModule')"
                  />

                  <v-text-field
                    v-model="userRuleForm.note"
                    density="comfortable"
                    hide-details
                    :label="t('permissions.note')"
                  />

                  <div class="permission-form-grid__actions">
                    <v-btn
                      color="primary"
                      :disabled="!userRuleForm.plugin_module.trim()"
                      :loading="creatingRule"
                      @click="createRuleForUser"
                    >
                      {{ t('permissions.createRule') }}
                    </v-btn>
                  </div>
                </v-card-text>
              </v-card>

              <v-card class="permission-panel surface-elevated-panel">
                <v-card-title>{{ t('permissions.userRules') }}</v-card-title>

                <v-card-text class="permission-rule-list">
                  <div
                    v-for="rule in selectedUserRules"
                    :key="ruleKey(rule)"
                    class="permission-rule-row"
                  >
                    <div>
                      <div class="font-weight-medium">{{ rule.plugin_module }}</div>

                      <div class="text-caption text-medium-emphasis">
                        {{ rule.effect === 'allow' ? t('permissions.allow') : t('permissions.deny') }}
                      </div>
                    </div>

                    <v-btn icon="mdi-delete" size="small" variant="text" @click="handleDeleteRule(rule)" />
                  </div>

                  <div v-if="selectedUserRules.length === 0" class="permission-empty">{{ t('permissions.noRules') }}</div>
                </v-card-text>
              </v-card>
            </div>

            <v-card class="permission-panel surface-elevated-panel">
              <v-card-title>{{ t('permissions.userLevels') }}</v-card-title>

              <v-card-text class="permission-rule-list">
                <div
                  v-for="entry in selectedUserLevels"
                  :key="`${entry.user_id}:${entry.group_id}`"
                  class="permission-rule-row"
                >
                  <div>
                    <div class="font-weight-medium">{{ entry.group_id }}</div>
                  </div>

                  <v-select
                    class="permission-level-select"
                    density="compact"
                    hide-details
                    :items="levelOptions"
                    :model-value="entry.level"
                    @update:model-value="updateLevel(entry, $event)"
                  />
                </div>

                <div v-if="selectedUserLevels.length === 0" class="permission-empty">{{ t('permissions.noUsers') }}</div>
              </v-card-text>
            </v-card>
          </section>
        </SplitPane>
      </div>

      <div v-else key="overview" class="permission-view">
        <v-card class="permission-panel surface-elevated-panel">
          <v-card-title>{{ t('permissions.rulesView') }}</v-card-title>

          <v-card-text class="permission-stack">
            <FilterBar
              :apply-label="t('common.applyFilters')"
              :close-label="t('common.close')"
              compact
              :overflow-label="t('common.filters')"
              :overflow-title="t('permissions.rulesView')"
            >
              <template #filters>
                <v-text-field
                  v-model="ruleSearch"
                  clearable
                  density="comfortable"
                  hide-details
                  :label="t('permissions.searchRules')"
                  prepend-inner-icon="mdi-magnify"
                />
              </template>

              <template #summary>
                <v-chip size="small" variant="tonal">
                  {{ ruleEffectLabel }}
                </v-chip>
              </template>

              <template #overflow>
                <v-select
                  v-model="ruleEffectFilter"
                  density="comfortable"
                  hide-details
                  :items="ruleEffectOptions"
                  :label="t('permissions.effect')"
                />
              </template>
            </FilterBar>

            <v-data-table
              class="permission-rules-table"
              density="comfortable"
              :headers="ruleHeaders"
              :items="filteredRules"
              :loading="loading"
            >
              <template #item.subject_type="{ value }">
                {{ value === 'user' ? t('permissions.user') : t('permissions.group') }}
              </template>

              <template #item.effect="{ value }">
                <v-chip :color="value === 'allow' ? 'success' : 'warning'" size="small" variant="tonal">
                  {{ value === 'allow' ? t('permissions.allow') : t('permissions.deny') }}
                </v-chip>
              </template>

              <template #item.actions="{ item }">
                <v-btn icon="mdi-delete" size="small" variant="text" @click="handleDeleteRule(item)" />
              </template>
            </v-data-table>

            <div class="permission-rule-cards">
              <article
                v-for="rule in filteredRules"
                :key="ruleKey(rule)"
                class="permission-rule-card"
              >
                <div class="permission-rule-card__header">
                  <div>
                    <div class="permission-rule-card__title">{{ rule.subject_id }}</div>
                    <div class="permission-rule-card__meta">
                      {{ rule.subject_type === 'user' ? t('permissions.user') : t('permissions.group') }}
                    </div>
                  </div>

                  <v-chip
                    :color="rule.effect === 'allow' ? 'success' : 'warning'"
                    size="small"
                    variant="tonal"
                  >
                    {{ rule.effect === 'allow' ? t('permissions.allow') : t('permissions.deny') }}
                  </v-chip>
                </div>

                <div class="permission-rule-card__line">
                  <span>{{ t('permissions.pluginModule') }}</span>
                  <strong>{{ rule.plugin_module }}</strong>
                </div>

                <div class="permission-rule-card__line">
                  <span>{{ t('permissions.note') }}</span>
                  <strong>{{ rule.note || t('permissions.noNote') }}</strong>
                </div>

                <div class="permission-rule-card__actions">
                  <v-btn
                    color="warning"
                    prepend-icon="mdi-delete"
                    size="small"
                    variant="text"
                    @click="handleDeleteRule(rule)"
                  >
                    {{ t('common.delete') }}
                  </v-btn>
                </div>
              </article>

              <div v-if="filteredRules.length === 0" class="permission-empty">
                {{ t('permissions.noRules') }}
              </div>
            </div>
          </v-card-text>
        </v-card>
      </div>
    </v-fade-transition>
  </PageScaffold>
</template>

<script setup lang="ts">
  import type { PluginItem } from '@/api/plugins'
  import { computed, onMounted, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useRoute, useRouter } from 'vue-router'
  import {
    type AccessRuleItem,
    getAccessRules,
    getUsers,
    type UserLevelItem,
  } from '@/api/access'
  import { getErrorMessage } from '@/api/client'
  import { getPlugins } from '@/api/plugins'
  import {
    DetailPanel,
    FilterBar,
    PageScaffold,
    SelectableList,
    SelectableListItem,
    SplitPane,
  } from '@/components/workbench'
  import { useNoticeStore } from '@/stores/notice'
  import {
    filteredRules as filterRules,
    ruleKey,
  } from '@/views/permissions/filters'
  import {
    accessModeOptions as buildAccessModeOptions,
    effectOptions as buildEffectOptions,
    perspectiveItems as buildPerspectiveItems,
    ruleEffectOptions as buildRuleEffectOptions,
    ruleHeaders as buildRuleHeaders,
    subjectTypeOptions as buildSubjectTypeOptions,
    levelOptions,
  } from '@/views/permissions/options'
  import { usePermissionPluginPerspective } from '@/views/permissions/usePermissionPluginPerspective'
  import { usePermissionRouteState } from '@/views/permissions/usePermissionRouteState'
  import { usePermissionRules } from '@/views/permissions/usePermissionRules'
  import { usePermissionUserPerspective } from '@/views/permissions/usePermissionUserPerspective'

  const route = useRoute()
  const router = useRouter()
  const { t } = useI18n()
  const noticeStore = useNoticeStore()

  const { applyRouteState, perspective } = usePermissionRouteState(route, router)
  const loading = ref(false)
  const errorMessage = ref('')

  const plugins = ref<PluginItem[]>([])
  const rules = ref<AccessRuleItem[]>([])
  const users = ref<UserLevelItem[]>([])

  const ruleSearch = ref('')
  const ruleEffectFilter = ref<'all' | 'allow' | 'deny'>('all')

  const { createRule, creatingRule, handleDeleteRule } = usePermissionRules({
    errorMessage,
    noticeStore,
    rules,
    t,
  })
  const {
    createRuleForPlugin,
    ensurePluginSelection,
    pendingPluginAccessMode,
    pluginModuleOptions,
    pluginRuleCount,
    pluginRuleForm,
    pluginSearch,
    selectedPlugin,
    selectedPluginGroupAllowRules,
    selectedPluginGroupDenyRules,
    selectedPluginModule,
    selectedPluginRules,
    selectedPluginUserAllowRules,
    selectedPluginUserDenyRules,
    updateSelectedPluginAccessMode,
    visiblePlugins,
  } = usePermissionPluginPerspective({
    createRule,
    errorMessage,
    noticeStore,
    plugins,
    rules,
    t,
  })
  const {
    createRuleForUser,
    ensureUserSelection,
    selectedUserId,
    selectedUserLevels,
    selectedUserRules,
    updateLevel,
    userEntries,
    userRuleForm,
    userSearch,
    visibleUserEntries,
  } = usePermissionUserPerspective({
    createRule,
    errorMessage,
    noticeStore,
    rules,
    t,
    users,
  })

  const perspectiveItems = computed(() =>
    buildPerspectiveItems({
      plugins: plugins.value.length,
      rules: rules.value.length,
      users: userEntries.value.length,
    }, t),
  )

  const ruleHeaders = computed(() => buildRuleHeaders(t))
  const subjectTypeOptions = computed(() => buildSubjectTypeOptions(t))
  const effectOptions = computed(() => buildEffectOptions(t))
  const accessModeOptions = computed(() => buildAccessModeOptions(t))
  const ruleEffectOptions = computed(() => buildRuleEffectOptions(t))
  const ruleEffectLabel = computed(() => (
    ruleEffectOptions.value.find(item => item.value === ruleEffectFilter.value)?.title
    || t('permissions.effect')
  ))

  const filteredRules = computed(() =>
    filterRules(rules.value, {
      effect: ruleEffectFilter.value,
      search: ruleSearch.value,
    }),
  )

  function ensureSelections (): void {
    ensurePluginSelection()
    ensureUserSelection()
  }

  async function loadAll (): Promise<void> {
    loading.value = true
    errorMessage.value = ''
    try {
      const [pluginsResponse, rulesResponse, usersResponse] = await Promise.all([
        getPlugins(),
        getAccessRules(),
        getUsers(),
      ])
      plugins.value = pluginsResponse.data
      rules.value = rulesResponse.data
      users.value = usersResponse.data
      ensureSelections()
    } catch (error) {
      errorMessage.value = getErrorMessage(error, t('permissions.loadFailed'))
    } finally {
      loading.value = false
    }
  }

  watch(() => route.query, () => {
    applyRouteState()
  })

  onMounted(async () => {
    applyRouteState()
    await loadAll()
  })
</script>

<style scoped>
.permission-workbench {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: calc(100dvh - (var(--page-gutter) * 2));
  min-height: 0;
  overflow: hidden;
}

.permission-view {
  overflow: hidden;
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.permission-perspectives {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  flex: 0 0 auto;
}

.permission-perspective {
  border: 1px solid rgba(var(--v-theme-outline-variant), var(--surface-border-opacity));
  border-radius: var(--shape-medium);
  padding: 12px 16px;
  text-align: left;
  cursor: pointer;
  background: rgb(var(--v-theme-surface-container-low));
  transition:
    border-color var(--motion-base) var(--motion-ease),
    background var(--motion-base) var(--motion-ease),
    transform var(--motion-base) var(--motion-ease);
}

.permission-perspective:hover {
  border-color: rgba(var(--v-theme-primary), 0.28);
}

.permission-perspective:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring);
}

.permission-perspective--active {
  border-color: rgba(var(--v-theme-primary), 0.4);
  background: rgba(var(--v-theme-primary), 0.08);
  transform: translateY(-1px);
}

.permission-perspective__label {
  display: block;
  font-weight: 700;
}

.permission-perspective__meta {
  display: block;
  margin-top: 2px;
  color: rgba(var(--v-theme-on-surface), 0.64);
}

.permission-layout {
  min-height: 0;
  flex: 1 1 auto;
}

.permission-sidebar {
  height: 100%;
}

.permission-sidebar__search {
  flex: 0 0 auto;
}

.permission-sidebar__search :deep(.v-field) {
  border-radius: var(--shape-small);
}

.permission-sidebar__search :deep(.v-field__input) {
  min-height: 36px;
  padding-top: 0;
  padding-bottom: 0;
}

.permission-main {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding-right: 4px;
}

.permission-panel--hero {
  flex: 0 0 auto;
}

.permission-inline-stat {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 88px;
}

.permission-inline-stat--control {
  min-width: 156px;
}

.permission-inline-stat__label {
  color: rgba(var(--v-theme-on-surface), 0.64);
  font-size: 0.75rem;
  font-weight: 700;
}

.permission-inline-stat__value {
  font-size: 1.05rem;
  font-weight: 800;
}

.permission-access-mode {
  max-width: 156px;
}

.permission-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.permission-panel :deep(.v-card-title) {
  font-size: 0.96rem;
  font-weight: 700;
  padding-bottom: 8px;
}

.permission-panel :deep(.v-card-text) {
  padding-top: 8px;
}

.permission-stack {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.permission-rule-cards {
  display: none;
}

.permission-stat {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid rgba(var(--v-theme-outline), 0.12);
}

.permission-stat:last-child {
  border-bottom: 0;
}

.permission-stat__label {
  color: rgba(var(--v-theme-on-surface), 0.64);
}

.permission-stat__value {
  font-weight: 800;
}

.permission-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.permission-form-grid__actions {
  display: flex;
  align-items: center;
}

.permission-rule-columns {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.permission-section-title {
  margin-bottom: 8px;
  font-weight: 700;
}

.permission-rule-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.permission-rule-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid rgba(var(--v-theme-outline), 0.12);
}

.permission-rule-row:last-child {
  border-bottom: 0;
}

.permission-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.permission-empty {
  color: rgba(var(--v-theme-on-surface), 0.64);
  padding: 4px 0;
}

.permission-level-select {
  max-width: 120px;
}

@media (max-width: 1100px) {
  .permission-perspectives {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .permission-grid,
  .permission-rule-columns,
  .permission-form-grid {
    grid-template-columns: 1fr;
  }

  .permission-panel--hero {
    flex-direction: column;
    align-items: stretch;
  }

  .permission-workbench {
    height: auto;
    overflow: visible;
  }

  .permission-layout,
  .permission-view,
  .permission-main {
    overflow: visible;
  }

  .permission-rules-table {
    display: none;
  }

  .permission-rule-cards {
    display: grid;
    gap: 10px;
  }

  .permission-rule-card {
    display: flex;
    min-width: 0;
    flex-direction: column;
    gap: 10px;
    padding: 12px;
    border: 1px solid rgba(var(--v-theme-outline-variant), var(--surface-border-opacity));
    border-radius: var(--shape-panel);
    background: rgb(var(--v-theme-surface-container-low));
  }

  .permission-rule-card__header {
    display: flex;
    min-width: 0;
    align-items: flex-start;
    justify-content: space-between;
    gap: 10px;
  }

  .permission-rule-card__title,
  .permission-rule-card__line strong {
    min-width: 0;
    overflow-wrap: anywhere;
  }

  .permission-rule-card__title {
    font-weight: 700;
  }

  .permission-rule-card__meta,
  .permission-rule-card__line span {
    color: rgba(var(--v-theme-on-surface), 0.64);
    font-size: 0.82rem;
  }

  .permission-rule-card__line {
    display: grid;
    gap: 3px;
  }

  .permission-rule-card__actions {
    display: flex;
    justify-content: flex-end;
  }
}
</style>
