<script setup lang="ts">
import type { AccessRuleItem } from '@/api/access'
import type { WorkbenchTone } from '@/components/management'
import {
  KeyRound,
  RefreshCw,
  Search,
  Shield,
  Trash2,
} from '@lucide/vue'
import { computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import {
  EmptyState,
  LoadingSkeleton,
  PageScaffold,
  Panel,
  SelectableList,
  SelectableListItem,
  SplitPane,
  StatusBadge,
} from '@/components/management'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { usePermissionsPage } from '@/composables/usePermissionsPage'
import { usePermissionRouteState } from '@/utils/permissionRouteState'
import {
  accessModeValues,
  effectValues,
  ruleKey,
  subjectTypeValues,
} from '@/utils/permissions'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const { applyRouteState, perspective } = usePermissionRouteState(route, router)
const permissions = usePermissionsPage((key, params) => t(key, params || {}))

const perspectiveItems = computed(() => [
  {
    value: 'plugins',
    title: t('permissions.pluginsTab'),
    meta: String(permissions.manageablePluginItems.value.length),
    summary: t('permissions.pluginsSummary'),
  },
  {
    value: 'rules',
    title: t('permissions.rulesTab'),
    meta: String(permissions.rules.value.length),
    summary: t('permissions.rulesSummary'),
  },
] as const)
const selectedPluginAccessModeLabel = computed(() =>
  permissions.selectedPlugin.value?.access_mode === 'default_deny'
    ? t('permissions.accessModeDefaultDeny')
    : t('permissions.accessModeDefaultAllow'),
)
const ruleEffectLabel = computed(() => {
  if (permissions.ruleEffectFilter.value === 'allow') {
    return t('permissions.allow')
  }
  if (permissions.ruleEffectFilter.value === 'deny') {
    return t('permissions.deny')
  }
  return t('permissions.effectAll')
})

function effectLabel(effect: string) {
  return effect === 'allow' ? t('permissions.allow') : t('permissions.deny')
}

function subjectLabel(subjectType: string) {
  return subjectType === 'group' ? t('permissions.group') : t('permissions.user')
}

function effectTone(effect: string): WorkbenchTone {
  return effect === 'allow' ? 'success' : 'warning'
}

function ruleNote(rule: AccessRuleItem) {
  return rule.note || t('permissions.noNote')
}

watch(() => route.query, () => {
  applyRouteState()
})

onMounted(async () => {
  applyRouteState()
  await permissions.loadAll()
})
</script>

<template>
  <PageScaffold
    class="permission-page"
    dense
    :error-message="permissions.errorMessage.value"
    :title="t('permissions.title')"
  >
    <template #actions>
      <div class="permission-page-actions">
        <nav class="permission-perspectives" :aria-label="t('permissions.title')">
          <button
            v-for="item in perspectiveItems"
            :key="item.value"
            :aria-pressed="perspective === item.value"
            class="permission-perspective"
            :class="{ 'permission-perspective--active': perspective === item.value }"
            :title="item.summary"
            type="button"
            @click="perspective = item.value"
          >
            <span class="permission-perspective__label">{{ item.title }}</span>
            <span class="permission-perspective__meta">{{ item.meta }}</span>
          </button>
        </nav>

        <Button
          :disabled="permissions.loading.value"
          variant="secondary"
          @click="permissions.loadAll"
        >
          <RefreshCw :class="{ 'animate-spin': permissions.loading.value }" :size="16" />
          {{ t('common.refresh') }}
        </Button>
      </div>
    </template>

    <SplitPane
      v-if="perspective === 'plugins'"
      class="permission-layout"
      wide-sidebar
    >
      <template #sidebar>
        <Panel :title="t('permissions.pluginsTab')">
          <div class="permission-search">
            <Search :size="16" />
            <Input
              v-model="permissions.pluginSearch.value"
              :aria-label="t('permissions.searchPlugins')"
              :placeholder="t('permissions.searchPlugins')"
            />
          </div>

          <LoadingSkeleton
            v-if="permissions.loading.value && permissions.manageablePluginItems.value.length === 0"
            :rows="6"
          />
          <EmptyState
            v-else-if="permissions.visiblePluginItems.value.length === 0"
            :icon="Shield"
            :title="t('permissions.noPlugins')"
          />
          <SelectableList v-else class="permission-scroll-list">
            <SelectableListItem
              v-for="item in permissions.visiblePluginItems.value"
              :key="item.module_name"
              :active="item.module_name === permissions.selectedPluginModule.value"
              @click="permissions.selectedPluginModule.value = item.module_name"
            >
              <div class="permission-list-row">
                <div>
                  <strong>{{ item.name || item.module_name }}</strong>
                  <span>{{ item.module_name }}</span>
                </div>
                <div>
                  <Badge v-if="!item.is_global_enabled" variant="outline">
                    {{ t('permissions.globalOff') }}
                  </Badge>
                  <Badge
                    v-if="permissions.pluginRuleCount(item.module_name) > 0"
                    variant="secondary"
                  >
                    {{ permissions.pluginRuleCount(item.module_name) }}
                  </Badge>
                </div>
              </div>
            </SelectableListItem>
          </SelectableList>
        </Panel>
      </template>

      <section v-if="permissions.selectedPlugin.value" class="permission-main">
        <Panel
          :subtitle="permissions.selectedPlugin.value.module_name"
          :title="permissions.selectedPlugin.value.name || permissions.selectedPlugin.value.module_name"
        >
          <template #actions>
            <div class="permission-access-control">
              <Label>{{ t('permissions.accessMode') }}</Label>
              <Select
                :disabled="permissions.pendingPluginAccessMode.value"
                :model-value="permissions.selectedPlugin.value.access_mode"
                @update:model-value="permissions.updateSelectedPluginAccessMode"
              >
                <SelectTrigger class="permission-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem
                    v-for="option in accessModeValues"
                    :key="option"
                    :value="option"
                  >
                    {{ option === 'default_deny'
                      ? t('permissions.accessModeDefaultDeny')
                      : t('permissions.accessModeDefaultAllow') }}
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
          </template>

          <div class="permission-state-grid">
            <div>
              <span>{{ t('permissions.accessMode') }}</span>
              <strong>{{ selectedPluginAccessModeLabel }}</strong>
            </div>
            <div>
              <span>{{ t('permissions.explicitRules') }}</span>
              <strong>{{ permissions.selectedPluginRules.value.length }}</strong>
            </div>
            <div>
              <span>{{ t('permissions.pluginScopeTitle') }}</span>
              <strong>
                {{ permissions.selectedPlugin.value.is_global_enabled
                  ? t('permissions.globalOn')
                  : t('permissions.globalOff') }}
              </strong>
            </div>
          </div>
        </Panel>

        <div class="permission-rule-columns">
          <Panel :title="t('permissions.userRules')">
            <div class="permission-rule-subcolumns">
              <section>
                <h3>{{ t('permissions.allow') }}</h3>
                <div
                  v-if="permissions.selectedPluginUserAllowRules.value.length > 0"
                  class="permission-rule-list"
                >
                  <article
                    v-for="rule in permissions.selectedPluginUserAllowRules.value"
                    :key="ruleKey(rule)"
                    class="permission-rule-row"
                  >
                    <div>
                      <strong>{{ rule.subject_id }}</strong>
                      <span>{{ ruleNote(rule) }}</span>
                    </div>
                    <Button size="icon" variant="ghost" @click="permissions.handleDeleteRule(rule)">
                      <Trash2 :size="15" />
                    </Button>
                  </article>
                </div>
                <p v-else class="permission-empty-text">{{ t('permissions.noRules') }}</p>
              </section>

              <section>
                <h3>{{ t('permissions.deny') }}</h3>
                <div
                  v-if="permissions.selectedPluginUserDenyRules.value.length > 0"
                  class="permission-rule-list"
                >
                  <article
                    v-for="rule in permissions.selectedPluginUserDenyRules.value"
                    :key="ruleKey(rule)"
                    class="permission-rule-row"
                  >
                    <div>
                      <strong>{{ rule.subject_id }}</strong>
                      <span>{{ ruleNote(rule) }}</span>
                    </div>
                    <Button size="icon" variant="ghost" @click="permissions.handleDeleteRule(rule)">
                      <Trash2 :size="15" />
                    </Button>
                  </article>
                </div>
                <p v-else class="permission-empty-text">{{ t('permissions.noRules') }}</p>
              </section>
            </div>
          </Panel>

          <Panel :title="t('permissions.groupRules')">
            <div class="permission-rule-subcolumns">
              <section>
                <h3>{{ t('permissions.allow') }}</h3>
                <div
                  v-if="permissions.selectedPluginGroupAllowRules.value.length > 0"
                  class="permission-rule-list"
                >
                  <article
                    v-for="rule in permissions.selectedPluginGroupAllowRules.value"
                    :key="ruleKey(rule)"
                    class="permission-rule-row"
                  >
                    <div>
                      <strong>{{ rule.subject_id }}</strong>
                      <span>{{ ruleNote(rule) }}</span>
                    </div>
                    <Button size="icon" variant="ghost" @click="permissions.handleDeleteRule(rule)">
                      <Trash2 :size="15" />
                    </Button>
                  </article>
                </div>
                <p v-else class="permission-empty-text">{{ t('permissions.noRules') }}</p>
              </section>

              <section>
                <h3>{{ t('permissions.deny') }}</h3>
                <div
                  v-if="permissions.selectedPluginGroupDenyRules.value.length > 0"
                  class="permission-rule-list"
                >
                  <article
                    v-for="rule in permissions.selectedPluginGroupDenyRules.value"
                    :key="ruleKey(rule)"
                    class="permission-rule-row"
                  >
                    <div>
                      <strong>{{ rule.subject_id }}</strong>
                      <span>{{ ruleNote(rule) }}</span>
                    </div>
                    <Button size="icon" variant="ghost" @click="permissions.handleDeleteRule(rule)">
                      <Trash2 :size="15" />
                    </Button>
                  </article>
                </div>
                <p v-else class="permission-empty-text">{{ t('permissions.noRules') }}</p>
              </section>
            </div>
          </Panel>
        </div>

        <Panel :title="t('permissions.createRuleTitle')">
          <div class="permission-form-grid">
            <div class="permission-field">
              <Label>{{ t('permissions.subjectType') }}</Label>
              <Select v-model="permissions.pluginRuleForm.subject_type">
                <SelectTrigger class="permission-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem
                    v-for="option in subjectTypeValues"
                    :key="option"
                    :value="option"
                  >
                    {{ subjectLabel(option) }}
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div class="permission-field">
              <Label>{{ t('permissions.subjectId') }}</Label>
              <Input
                v-model="permissions.pluginRuleForm.subject_id"
                :placeholder="permissions.pluginRuleForm.subject_type === 'group'
                  ? t('permissions.groupIdPlaceholder')
                  : t('permissions.userIdPlaceholder')"
              />
            </div>

            <div class="permission-field">
              <Label>{{ t('permissions.effect') }}</Label>
              <Select v-model="permissions.pluginRuleForm.effect">
                <SelectTrigger class="permission-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem
                    v-for="option in effectValues"
                    :key="option"
                    :value="option"
                  >
                    {{ effectLabel(option) }}
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div class="permission-field permission-field--wide">
              <Label>{{ t('permissions.note') }}</Label>
              <Textarea v-model="permissions.pluginRuleForm.note" />
            </div>

            <div class="permission-form-actions">
              <Button
                :disabled="permissions.creatingRule.value || !permissions.pluginRuleForm.subject_id.trim()"
                @click="permissions.createRuleForPlugin"
              >
                {{ t('permissions.createRule') }}
              </Button>
            </div>
          </div>
        </Panel>
      </section>
    </SplitPane>

    <Panel v-else class="permission-rules-panel" :title="t('permissions.rulesView')">
      <div class="permission-rules-filter">
        <div class="permission-search">
          <Search :size="16" />
          <Input
            v-model="permissions.ruleSearch.value"
            :aria-label="t('permissions.searchRules')"
            :placeholder="t('permissions.searchRules')"
          />
        </div>
        <Select v-model="permissions.ruleEffectFilter.value">
          <SelectTrigger class="permission-select">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="__all__">
              {{ t('permissions.effectAll') }}
            </SelectItem>
            <SelectItem
              v-for="option in effectValues"
              :key="option"
              :value="option"
            >
              {{ effectLabel(option) }}
            </SelectItem>
          </SelectContent>
        </Select>
        <Badge variant="secondary">
          {{ ruleEffectLabel }}
        </Badge>
      </div>

      <div class="permission-rules-table">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{{ t('permissions.subjectType') }}</TableHead>
              <TableHead>{{ t('permissions.subjectId') }}</TableHead>
              <TableHead>{{ t('permissions.pluginModule') }}</TableHead>
              <TableHead>{{ t('permissions.effect') }}</TableHead>
              <TableHead>{{ t('permissions.note') }}</TableHead>
              <TableHead class="text-right">{{ t('common.actions') }}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow
              v-for="rule in permissions.filteredRuleItems.value"
              :key="ruleKey(rule)"
            >
              <TableCell>{{ subjectLabel(rule.subject_type) }}</TableCell>
              <TableCell class="monospace">{{ rule.subject_id }}</TableCell>
              <TableCell class="monospace">{{ rule.plugin_module }}</TableCell>
              <TableCell>
                <StatusBadge :label="effectLabel(rule.effect)" :tone="effectTone(rule.effect)" />
              </TableCell>
              <TableCell>{{ ruleNote(rule) }}</TableCell>
              <TableCell class="text-right">
                <Button size="icon" variant="ghost" @click="permissions.handleDeleteRule(rule)">
                  <Trash2 :size="15" />
                </Button>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>

      <div class="permission-rule-card-list">
        <article
          v-for="rule in permissions.filteredRuleItems.value"
          :key="ruleKey(rule)"
          class="permission-rule-card"
        >
          <div class="permission-rule-card__header">
            <div>
              <strong>{{ rule.subject_id }}</strong>
              <span>{{ subjectLabel(rule.subject_type) }}</span>
            </div>
            <StatusBadge :label="effectLabel(rule.effect)" :tone="effectTone(rule.effect)" />
          </div>
          <div class="permission-rule-card__line">
            <span>{{ t('permissions.pluginModule') }}</span>
            <strong>{{ rule.plugin_module }}</strong>
          </div>
          <div class="permission-rule-card__line">
            <span>{{ t('permissions.note') }}</span>
            <strong>{{ ruleNote(rule) }}</strong>
          </div>
          <div class="permission-rule-card__actions">
            <Button variant="ghost" @click="permissions.handleDeleteRule(rule)">
              <Trash2 :size="15" />
              {{ t('common.delete') }}
            </Button>
          </div>
        </article>
      </div>

      <EmptyState
        v-if="permissions.filteredRuleItems.value.length === 0"
        :icon="KeyRound"
        :title="t('permissions.noRules')"
      />
    </Panel>
  </PageScaffold>
</template>
