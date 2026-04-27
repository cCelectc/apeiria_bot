<template>
  <div class="page-view">
    <div class="page-header">
      <h1 class="page-title">{{ t('plugins.title') }}</h1>
    </div>

    <v-alert v-if="errorMessage" density="comfortable" type="error" variant="tonal">
      {{ errorMessage }}
    </v-alert>

    <v-card class="page-panel">
      <v-card-text class="d-flex flex-column ga-5">
        <div class="page-summary-grid">
          <v-sheet class="summary-card" rounded="lg">
            <div class="summary-card__label">{{ t('plugins.coreProtectedCount') }}</div>
            <div class="summary-card__value">{{ systemPlugins.length }}</div>
          </v-sheet>
          <v-sheet class="summary-card" rounded="lg">
            <div class="summary-card__label">{{ t('plugins.userManagedCount') }}</div>
            <div class="summary-card__value">{{ nonSystemPlugins.length }}</div>
          </v-sheet>
          <v-sheet class="summary-card" rounded="lg">
            <div class="summary-card__label">{{ t('plugins.visibleCount') }}</div>
            <div class="summary-card__value">{{ visiblePlugins.length }}</div>
          </v-sheet>
        </div>

        <div class="section-heading">
          <div class="section-heading__main">
            <div class="text-subtitle-1 font-weight-medium">{{ t('plugins.configTitle') }}</div>
            <v-text-field
              v-model.trim="pluginSearch"
              class="plugin-search"
              density="comfortable"
              hide-details
              :label="t('plugins.search')"
              prepend-inner-icon="mdi-magnify"
            />
            <v-btn
              v-if="authStore.role === 'owner'"
              color="primary"
              variant="tonal"
              @click="openManualInstallDialog"
            >
              {{ t('plugins.manualInstall') }}
            </v-btn>
            <v-btn
              v-if="authStore.role === 'owner'"
              color="warning"
              variant="text"
              @click="openOrphanConfigDialog"
            >
              {{ t('plugins.orphanConfigCleanup') }}
            </v-btn>
            <v-btn
              v-if="authStore.role === 'owner'"
              color="primary"
              :loading="updateCheckLoading"
              variant="text"
              @click="runPluginUpdateCheck(true)"
            >
              {{ updateCheckLoading ? t('plugins.checkingUpdates') : t('plugins.checkUpdates') }}
            </v-btn>
          </div>
          <div class="section-heading__actions">
            <div :aria-label="t('plugins.scopeTabs')" class="plugin-scope-tabs segmented-control" role="tablist">
              <button
                :aria-selected="pluginScopeTab === 'managed'"
                class="plugin-scope-tab segmented-control__tab"
                :class="{ 'plugin-scope-tab--active segmented-control__tab--active': pluginScopeTab === 'managed' }"
                role="tab"
                type="button"
                @click="pluginScopeTab = 'managed'"
              >
                {{ t('plugins.tabManaged') }}
              </button>
              <button
                :aria-selected="pluginScopeTab === 'framework'"
                class="plugin-scope-tab segmented-control__tab"
                :class="{ 'plugin-scope-tab--active segmented-control__tab--active': pluginScopeTab === 'framework' }"
                role="tab"
                type="button"
                @click="pluginScopeTab = 'framework'"
              >
                {{ t('plugins.tabFramework') }}
              </button>
            </div>
          </div>
        </div>

        <div v-if="visiblePlugins.length > 0" class="plugins-grid">
          <article
            v-for="item in visiblePlugins"
            :key="item.module_name"
            class="plugin-card surface-gradient-card"
          >
            <div class="plugin-card__top">
              <div class="plugin-card__headline">
                <div class="plugin-card__title-row">
                  <h2 class="plugin-card__title">{{ item.name || item.module_name }}</h2>
                  <v-chip
                    v-if="item.admin_level > 0"
                    color="secondary"
                    size="x-small"
                    variant="tonal"
                  >
                    Lv.{{ item.admin_level }}
                  </v-chip>
                  <v-chip
                    :color="item.plugin_type === 'admin' || item.plugin_type === 'superuser' ? 'warning' : 'default'"
                    size="x-small"
                    variant="tonal"
                  >
                    {{ item.plugin_type }}
                  </v-chip>
                  <v-chip
                    :color="item.is_loaded ? 'success' : 'default'"
                    size="x-small"
                    variant="tonal"
                  >
                    {{ item.is_loaded ? t('plugins.loaded') : t('plugins.notLoaded') }}
                  </v-chip>
                  <v-chip
                    v-if="item.is_explicit"
                    color="primary"
                    size="x-small"
                    variant="tonal"
                  >
                    {{ t('plugins.explicit') }}
                  </v-chip>
                  <v-chip
                    v-if="item.is_dependency"
                    color="info"
                    size="x-small"
                    variant="tonal"
                  >
                    {{ t('plugins.dependency') }}
                  </v-chip>
                  <v-chip
                    v-if="item.is_protected"
                    color="warning"
                    size="x-small"
                    variant="tonal"
                  >
                    {{ t('plugins.protected') }}
                    <v-tooltip v-if="pluginToggleHint(item)" activator="parent" location="top">
                      {{ pluginToggleHint(item) }}
                    </v-tooltip>
                  </v-chip>
                  <v-chip
                    v-if="item.is_pending_uninstall"
                    color="warning"
                    size="x-small"
                    variant="flat"
                  >
                    {{ t('plugins.pendingUninstall') }}
                    <v-tooltip activator="parent" location="top">
                      {{ t('plugins.pendingUninstallHint') }}
                    </v-tooltip>
                  </v-chip>
                </div>
                <div class="plugin-card__subline text-caption text-medium-emphasis">
                  {{ item.module_name }}
                </div>
                <div v-if="pluginMetaSummary(item)" class="plugin-card__subline text-caption text-medium-emphasis">
                  {{ pluginMetaSummary(item) }}
                </div>
                <div
                  v-if="item.child_plugins.length > 0"
                  class="plugin-card__subline text-caption text-medium-emphasis"
                >
                  {{ t('plugins.childPluginCount', { count: item.child_plugins.length }) }}
                </div>
              </div>

              <v-chip :color="sourceColor(item.source)" size="small" variant="tonal">
                {{ sourceLabel(item.source) }}
              </v-chip>
            </div>

            <p v-if="item.description" class="plugin-card__description">
              {{ item.description }}
            </p>

            <div
              v-if="item.child_plugins.length > 0 || item.required_plugins.length > 0 || item.dependent_plugins.length > 0"
              class="plugin-card__relations"
            >
              <v-chip
                v-for="childPlugin in item.child_plugins"
                :key="`child:${item.module_name}:${childPlugin}`"
                color="secondary"
                size="x-small"
                variant="tonal"
              >
                {{ t('plugins.childPlugins') }}: {{ childPlugin }}
              </v-chip>
              <v-chip
                v-for="dependency in item.required_plugins"
                :key="`req:${item.module_name}:${dependency}`"
                color="info"
                size="x-small"
                variant="tonal"
              >
                {{ t('plugins.requires', { name: dependency }) }}
              </v-chip>
              <v-chip
                v-for="dependent in item.dependent_plugins"
                :key="`dep:${item.module_name}:${dependent}`"
                color="warning"
                size="x-small"
                variant="tonal"
              >
                {{ t('plugins.requiredBy', { name: dependent }) }}
              </v-chip>
            </div>

            <div class="plugin-card__footer">
              <div class="plugin-card__footer-bar">
                <div class="plugin-card__actions">
                  <v-tooltip v-if="canUninstallPlugin(item)" location="top">
                    <template #activator="{ props }">
                      <v-btn
                        v-bind="props"
                        color="warning"
                        icon="mdi-trash-can-outline"
                        :loading="uninstallingModule === item.module_name"
                        size="small"
                        variant="text"
                        @click="uninstallPluginItem(item)"
                      />
                    </template>
                    {{ t('plugins.settingsUninstall') }}
                  </v-tooltip>
                  <v-tooltip v-if="pluginProjectUrl(item)" location="top">
                    <template #activator="{ props }">
                      <v-btn
                        v-bind="props"
                        color="primary"
                        :href="pluginProjectUrl(item)"
                        icon="mdi-open-in-new"
                        rel="noopener noreferrer"
                        size="small"
                        target="_blank"
                        variant="text"
                      />
                    </template>
                    {{ t('plugins.projectPage') }}
                  </v-tooltip>
                  <v-tooltip v-if="item.can_view_readme" location="top">
                    <template #activator="{ props }">
                      <v-btn
                        v-bind="props"
                        color="primary"
                        icon="mdi-file-document-outline"
                        :loading="readmeLoadingModule === item.module_name"
                        size="small"
                        variant="text"
                        @click="openReadme(item)"
                      />
                    </template>
                    {{ t('plugins.readme') }}
                  </v-tooltip>
                  <v-tooltip v-if="canUpdatePlugin(item)" location="top">
                    <template #activator="{ props }">
                      <span v-bind="props" class="plugin-card__action-anchor">
                        <v-btn
                          :color="hasPluginUpdate(item) ? 'primary' : undefined"
                          :disabled="updateCheckLoading || !hasPluginUpdate(item)"
                          icon="mdi-update"
                          :loading="packageUpdatingModule === item.module_name"
                          size="small"
                          :variant="hasPluginUpdate(item) ? 'tonal' : 'text'"
                          @click="updatePluginItem(item)"
                        />
                      </span>
                    </template>
                    {{ updateButtonTooltip(item) }}
                  </v-tooltip>
                  <v-tooltip v-if="item.can_edit_config" location="top">
                    <template #activator="{ props }">
                      <v-btn
                        v-bind="props"
                        color="primary"
                        icon="mdi-cog-outline"
                        :loading="settingsLoadingModule === item.module_name"
                        size="small"
                        variant="text"
                        @click="openSettings(item)"
                      />
                    </template>
                    {{ t('plugins.settings') }}
                  </v-tooltip>
                </div>
                <div class="plugin-card__switch-wrap">
                  <v-switch
                    v-if="item.can_enable_disable || item.is_protected || item.is_pending_uninstall"
                    class="plugin-card__switch"
                    color="success"
                    :disabled="!item.can_enable_disable || item.is_protected || item.is_pending_uninstall"
                    hide-details
                    inset
                    :loading="pendingModule === item.module_name"
                    :model-value="item.is_global_enabled"
                    @update:model-value="togglePlugin(item, $event)"
                  />
                  <v-tooltip v-if="pluginToggleHint(item)" activator="parent" location="top">
                    {{ pluginToggleHint(item) }}
                  </v-tooltip>
                </div>
              </div>
            </div>
          </article>
        </div>

        <div v-else class="py-6 text-body-2 text-medium-emphasis text-center">
          {{ t('plugins.noVisiblePlugins') }}
        </div>
      </v-card-text>
    </v-card>

    <v-dialog v-model="settingsDialogVisible" max-width="920">
      <v-card class="settings-dialog-card">
        <v-card-title class="settings-dialog-header">
          <div class="settings-dialog-header__main">
            <div class="settings-dialog-header__title-block">
              <span class="settings-dialog-header__title">
                {{ t('plugins.settingsTitle', { name: settingsPlugin?.name || settingsPlugin?.module_name || '' }) }}
              </span>
              <span class="settings-dialog-header__module text-caption text-medium-emphasis">
                {{ settingsPlugin?.module_name }}
              </span>
            </div>

            <div class="settings-dialog-header__meta">
              <v-chip v-if="settingsState" color="primary" size="small" variant="tonal">
                {{ settingsState.section }}
              </v-chip>
              <v-chip
                v-if="settingsState"
                :color="settingsState.legacy_flatten ? 'warning' : 'default'"
                size="small"
                variant="tonal"
              >
                {{ settingsState.legacy_flatten ? t('plugins.settingsLegacy') : settingsSourceLabel(settingsState.config_source) }}
              </v-chip>
              <v-chip
                v-if="settingsPlugin?.admin_level"
                color="secondary"
                size="small"
                variant="tonal"
              >
                Lv.{{ settingsPlugin.admin_level }}
              </v-chip>
              <v-chip
                v-if="settingsPlugin?.plugin_type"
                :color="settingsPlugin.plugin_type === 'admin' || settingsPlugin.plugin_type === 'superuser' ? 'warning' : 'default'"
                size="small"
                variant="tonal"
              >
                {{ settingsPlugin.plugin_type }}
              </v-chip>
              <span v-if="settingsPlugin" class="settings-dialog-header__summary text-caption text-medium-emphasis">
                {{ pluginMetaSummary(settingsPlugin) || 'unknown' }}
              </span>
              <span
                v-if="settingsPlugin?.installed_package"
                class="settings-dialog-header__summary text-caption text-medium-emphasis"
              >
                {{ t('plugins.settingsInstalledPackage') }}: {{ settingsPlugin.installed_package }}
              </span>
            </div>

            <div
              v-if="settingsPlugin && (settingsPlugin.child_plugins.length > 0 || settingsPlugin.required_plugins.length > 0 || settingsPlugin.dependent_plugins.length > 0)"
              class="settings-dialog-header__relations"
            >
              <div v-if="settingsPlugin.child_plugins.length > 0" class="plugin-detail-tags">
                <span class="text-caption text-medium-emphasis">{{ t('plugins.childPlugins') }}</span>
                <v-chip
                  v-for="childPlugin in settingsPlugin.child_plugins"
                  :key="`detail-child:${childPlugin}`"
                  color="secondary"
                  size="x-small"
                  variant="tonal"
                >
                  {{ childPlugin }}
                </v-chip>
              </div>
              <div v-if="settingsPlugin.required_plugins.length > 0" class="plugin-detail-tags">
                <span class="text-caption text-medium-emphasis">{{ t('plugins.requiredPlugins') }}</span>
                <v-chip
                  v-for="dependency in settingsPlugin.required_plugins"
                  :key="`detail-required:${dependency}`"
                  color="info"
                  size="x-small"
                  variant="tonal"
                >
                  {{ dependency }}
                </v-chip>
              </div>
              <div v-if="settingsPlugin.dependent_plugins.length > 0" class="plugin-detail-tags">
                <span class="text-caption text-medium-emphasis">{{ t('plugins.dependentPlugins') }}</span>
                <v-chip
                  v-for="dependency in settingsPlugin.dependent_plugins"
                  :key="`detail-dependent:${dependency}`"
                  color="warning"
                  size="x-small"
                  variant="tonal"
                >
                  {{ dependency }}
                </v-chip>
              </div>
            </div>

            <v-alert
              v-if="settingsPlugin?.is_pending_uninstall"
              class="mt-3"
              density="comfortable"
              type="warning"
              variant="tonal"
            >
              {{ t('plugins.pendingUninstallDetail') }}
            </v-alert>
          </div>

        </v-card-title>
        <v-card-text class="settings-dialog-card__body d-flex flex-column ga-4">
          <v-alert v-if="settingsErrorMessage" density="comfortable" type="error" variant="tonal">
            {{ settingsErrorMessage }}
          </v-alert>

          <v-progress-linear v-if="settingsDialogLoading" color="primary" indeterminate />

          <div v-if="!settingsDialogLoading" class="settings-shell settings-shell--dialog">
            <SettingsModeBar
              v-model="settingsEditorMode"
              :advanced-label="t('plugins.settingsAdvancedTab')"
              :basic-label="t('plugins.settingsBasicTab')"
              :tablist-label="t('plugins.settingsTitle')"
            >
              <template #actions>
                <v-btn
                  v-if="settingsEditorMode === 'basic'"
                  color="primary"
                  :disabled="!settingsState?.has_config_model || !hasPendingPluginChanges"
                  :loading="settingsSaving"
                  @click="openPluginSettingsPreview"
                >
                  {{ t('plugins.settingsSave') }}
                </v-btn>
              </template>
            </SettingsModeBar>

            <template v-if="settingsEditorMode === 'basic'">
              <div v-if="!settingsState?.has_config_model || settingsFields.length === 0" class="text-body-2 text-medium-emphasis">
                {{ t('plugins.settingsEmpty') }}
              </div>

              <div v-else class="settings-list-panel">
                <section
                  v-for="field in settingsFields"
                  :key="field.key"
                  class="settings-list-row"
                >
                  <div class="settings-list-row__main">
                    <div class="settings-list-row__info">
                      <div class="settings-list-row__label text-subtitle-2 font-weight-medium">
                        {{ field.label || field.key }}
                      </div>
                      <div v-if="field.help" class="settings-list-row__description text-caption text-medium-emphasis">
                        {{ field.help }}
                      </div>
                      <div class="settings-list-row__status">
                        <v-chip
                          v-if="field.has_local_override || pluginEditor.isFieldEditing(field)"
                          color="primary"
                          size="x-small"
                          variant="tonal"
                        >
                          {{ t('plugins.settingsLocalShort') }}
                        </v-chip>
                        <v-chip
                          v-if="!field.editable"
                          color="warning"
                          size="x-small"
                          variant="tonal"
                        >
                          {{ t('plugins.settingsReadonly') }}
                        </v-chip>
                      </div>
                      <div class="settings-list-row__meta text-caption text-medium-emphasis">
                        <span>{{ t('plugins.settingsType') }}: {{ field.type }}</span>
                        <span>{{ t('plugins.settingsValueSource') }}: {{ settingsValueSourceLabel(field.value_source) }}</span>
                        <span v-if="field.global_key">{{ t('plugins.settingsGlobalKey') }}: {{ field.global_key }}</span>
                        <span v-if="field.choices.length > 0">{{ t('plugins.settingsChoices') }}: {{ formatFieldChoices(field.choices) }}</span>
                      </div>
                    </div>

                    <div class="settings-list-row__control">
                      <div class="settings-list-row__actions">
                        <v-btn
                          v-if="!pluginEditor.isFieldEditing(field) && field.editable"
                          class="settings-action settings-action--primary"
                          color="primary"
                          size="small"
                          variant="tonal"
                          @click="pluginEditor.startOverride(field)"
                        >
                          {{ t('plugins.settingsAddOverride') }}
                        </v-btn>
                        <v-btn
                          v-if="pluginEditor.isFieldEditing(field)"
                          class="settings-action"
                          size="small"
                          variant="text"
                          @click="pluginEditor.cancelField(field)"
                        >
                          {{ t('common.cancel') }}
                        </v-btn>
                        <v-btn
                          v-if="field.has_local_override"
                          class="settings-action"
                          color="warning"
                          size="small"
                          variant="text"
                          @click="clearPluginField(field)"
                        >
                          {{ t('plugins.settingsClear') }}
                        </v-btn>
                      </div>

                      <SettingsFieldEditor
                        v-model="settingsForm[field.key]"
                        :array-hint="t('plugins.settingsArrayHint')"
                        :editing="pluginEditor.isFieldEditing(field)"
                        :field="field"
                        :json-hint="t('plugins.settingsJsonHint')"
                      />
                    </div>
                  </div>
                </section>
              </div>
            </template>

            <template v-else>
              <RawSettingsEditor
                v-model="settingsRawText"
                :description="t('plugins.settingsAdvancedDescription')"
                :dirty="hasPendingPluginRawChanges"
                :error-message="settingsRawErrorMessage"
                :loading="settingsRawLoading"
                :reload-label="t('common.refresh')"
                :save-label="t('plugins.settingsSave')"
                :saving="settingsRawSaving"
                :validation-error-column="pluginRawValidationColumn"
                :validation-error-line="pluginRawValidationLine"
                :validation-error-message="pluginRawValidationMessage"
                :validation-pending="pluginRawValidationPending"
                @reload="settingsPlugin && loadPluginRawSettings(settingsPlugin.module_name)"
                @save="openPluginRawPreview"
              />
            </template>
          </div>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="settingsDialogVisible = false">{{ t('common.cancel') }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <SettingsPreviewDialog
      v-model="previewDialogVisible"
      :cancel-label="t('common.cancel')"
      :confirm-label="t('plugins.confirmSave')"
      :current-label="t('plugins.previewCurrent')"
      :current-text="previewCurrentText"
      :items="previewItems"
      :mode="previewMode"
      :next-label="t('plugins.previewNext')"
      :next-text="previewNextText"
      :restart-hint="t('plugins.settingsRestartHint')"
      :saving="previewSaving"
      :title="previewTitle"
      @cancel="previewDialogVisible = false"
      @confirm="confirmPreviewSave"
    />

    <v-dialog v-model="toggleConfirmVisible" max-width="560">
      <v-card>
        <v-card-title>{{ toggleConfirmTitle }}</v-card-title>
        <v-card-text class="d-flex flex-column ga-4">
          <v-alert density="comfortable" type="warning" variant="tonal">
            {{ toggleConfirmSummary }}
          </v-alert>
          <div v-if="toggleConfirmItem" class="confirm-plugin-list">
            <div class="confirm-plugin-item">
              <div class="confirm-plugin-item__title">
                <span class="font-weight-medium">{{ toggleConfirmItem.name || toggleConfirmItem.module_name }}</span>
                <span class="text-caption text-medium-emphasis">{{ toggleConfirmItem.module_name }}</span>
              </div>
              <div v-if="toggleConfirmDependencies.length > 0" class="confirm-plugin-item__relations">
                <v-chip
                  v-for="dependency in toggleConfirmDependencies"
                  :key="`confirm-dependent:${toggleConfirmItem.module_name}:${dependency}`"
                  :color="toggleConfirmNextValue ? 'info' : 'warning'"
                  size="x-small"
                  variant="tonal"
                >
                  {{ toggleConfirmNextValue ? t('plugins.requires', { name: getPluginLabel(dependency) }) : t('plugins.requiredBy', { name: getPluginLabel(dependency) }) }}
                </v-chip>
              </div>
            </div>
          </div>
        </v-card-text>
        <v-card-actions>
          <v-btn variant="text" @click="closeToggleConfirm">{{ t('common.cancel') }}</v-btn>
          <v-spacer />
          <v-btn :color="toggleConfirmNextValue ? 'primary' : 'warning'" :loading="toggleConfirmLoading" @click="confirmToggleAction">
            {{ toggleConfirmNextValue ? t('plugins.confirmEnable') : t('plugins.confirmDisable') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="uninstallConfirmVisible" max-width="560">
      <v-card>
        <v-card-title>{{ t('plugins.settingsUninstall') }}</v-card-title>
        <v-card-text class="d-flex flex-column ga-4">
          <v-alert density="comfortable" type="warning" variant="tonal">
            {{ uninstallConfirmSummary }}
          </v-alert>
          <v-checkbox
            v-model="uninstallRemoveConfig"
            color="warning"
            density="comfortable"
            hide-details
            :label="t('plugins.settingsUninstallRemoveConfig')"
          />
          <div class="text-body-2 text-medium-emphasis">
            {{ t('plugins.settingsUninstallRemoveConfigHint') }}
          </div>
        </v-card-text>
        <v-card-actions>
          <v-btn variant="text" @click="closeUninstallConfirm">{{ t('common.cancel') }}</v-btn>
          <v-spacer />
          <v-btn
            color="warning"
            :loading="Boolean(uninstallingModule)"
            @click="confirmUninstallPlugin"
          >
            {{ t('plugins.settingsUninstall') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="orphanConfigDialogVisible" max-width="680">
      <v-card>
        <v-card-title>{{ t('plugins.orphanConfigCleanup') }}</v-card-title>
        <v-card-text class="d-flex flex-column ga-4">
          <v-alert density="comfortable" type="info" variant="tonal">
            {{ t('plugins.orphanConfigCleanupHint') }}
          </v-alert>
          <v-progress-linear
            v-if="orphanConfigLoading"
            color="primary"
            indeterminate
          />
          <div
            v-else-if="orphanConfigItems.length === 0"
            class="text-body-2 text-medium-emphasis"
          >
            {{ t('plugins.orphanConfigCleanupEmpty') }}
          </div>
          <div v-else class="confirm-plugin-list">
            <div
              v-for="item in orphanConfigItems"
              :key="`${item.section}:${item.module_name || ''}`"
              class="confirm-plugin-item"
            >
              <div class="confirm-plugin-item__title">
                <span class="font-weight-medium">[plugins.{{ item.section }}]</span>
                <span class="text-caption text-medium-emphasis">
                  {{ item.module_name || t('plugins.orphanConfigNoModule') }}
                </span>
              </div>
              <div class="text-caption text-medium-emphasis">
                {{ item.reason }}
              </div>
            </div>
          </div>
        </v-card-text>
        <v-card-actions>
          <v-btn variant="text" @click="orphanConfigDialogVisible = false">{{ t('common.cancel') }}</v-btn>
          <v-spacer />
          <v-btn
            color="warning"
            :disabled="orphanConfigItems.length === 0"
            :loading="orphanConfigCleaning"
            @click="confirmCleanupOrphanConfigs"
          >
            {{ t('plugins.orphanConfigCleanupAction') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="manualInstallDialogVisible" max-width="640">
      <v-card rounded="xl">
        <v-card-title>{{ t('plugins.manualInstall') }}</v-card-title>
        <v-card-text class="d-flex flex-column ga-4">
          <v-alert density="comfortable" type="info" variant="tonal">
            {{ t('plugins.manualInstallHint') }}
          </v-alert>
          <v-select
            v-model="manualInstallSourceType"
            density="comfortable"
            hide-details
            item-title="label"
            item-value="value"
            :items="manualInstallSourceOptions"
            :label="t('plugins.manualInstallSourceType')"
          />
          <v-text-field
            v-model.trim="manualInstallRequirement"
            density="comfortable"
            :hint="manualInstallRequirementHint"
            :label="manualInstallRequirementLabel"
            persistent-hint
          />
          <v-text-field
            v-model.trim="manualInstallModuleName"
            density="comfortable"
            :hint="t('plugins.manualInstallModuleHint')"
            :label="t('plugins.manualInstallModule')"
            persistent-hint
          />
        </v-card-text>
        <v-card-actions>
          <v-btn rounded="xl" variant="text" @click="manualInstallDialogVisible = false">
            {{ t('common.cancel') }}
          </v-btn>
          <v-spacer />
          <v-btn
            color="primary"
            :disabled="!canSubmitManualInstall"
            :loading="manualInstallSubmitting"
            rounded="xl"
            @click="submitManualInstall"
          >
            {{ t('plugins.manualInstallSubmit') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="manualInstallTaskDialogVisible" max-width="840">
      <v-card rounded="xl">
        <v-card-title>{{ manualInstallTask?.title || t('plugins.manualInstallTaskTitle') }}</v-card-title>
        <v-card-text class="d-flex flex-column ga-4">
          <div class="text-body-2 text-medium-emphasis">
            {{ manualInstallTaskStatusLabel }}
          </div>
          <v-alert
            v-if="manualInstallTaskErrorSummary"
            density="comfortable"
            type="error"
            variant="tonal"
          >
            {{ manualInstallTaskErrorSummary }}
          </v-alert>
          <v-progress-linear
            v-if="manualInstallTask?.status === 'pending' || manualInstallTask?.status === 'running'"
            color="primary"
            indeterminate
          />
          <v-sheet class="task-log-card" rounded="lg">
            <pre class="task-log-card__content">{{ manualInstallTask?.logs || t('plugins.manualInstallWaiting') }}</pre>
          </v-sheet>
        </v-card-text>
        <v-card-actions>
          <v-btn rounded="xl" variant="text" @click="manualInstallTaskDialogVisible = false">
            {{ t('common.close') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="packageUpdateTaskDialogVisible" max-width="840">
      <v-card rounded="xl">
        <v-card-title>{{ packageUpdateTask?.title || t('plugins.packageUpdateTaskTitle') }}</v-card-title>
        <v-card-text class="d-flex flex-column ga-4">
          <div class="text-body-2 text-medium-emphasis">
            {{ packageUpdateTaskStatusLabel }}
          </div>
          <v-alert
            v-if="packageUpdateTaskErrorSummary"
            density="comfortable"
            type="error"
            variant="tonal"
          >
            {{ packageUpdateTaskErrorSummary }}
          </v-alert>
          <v-progress-linear
            v-if="packageUpdateTask?.status === 'pending' || packageUpdateTask?.status === 'running'"
            color="primary"
            indeterminate
          />
          <v-sheet class="task-log-card" rounded="lg">
            <pre class="task-log-card__content">{{ packageUpdateTask?.logs || t('plugins.packageUpdateWaiting') }}</pre>
          </v-sheet>
        </v-card-text>
        <v-card-actions>
          <v-btn rounded="xl" variant="text" @click="packageUpdateTaskDialogVisible = false">
            {{ t('common.close') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="readmeDialogVisible" max-width="960">
      <v-card rounded="xl">
        <v-card-title class="d-flex align-center justify-space-between ga-4">
          <div class="d-flex flex-column">
            <span>{{ readmeDialogTitle }}</span>
            <span v-if="readmeFilename" class="text-caption text-medium-emphasis">{{ readmeFilename }}</span>
          </div>
          <v-btn icon="mdi-close" variant="text" @click="readmeDialogVisible = false" />
        </v-card-title>
        <v-card-text class="readme-dialog__body">
          <v-alert v-if="readmeErrorMessage" density="comfortable" type="error" variant="tonal">
            {{ readmeErrorMessage }}
          </v-alert>
          <v-progress-linear v-else-if="readmeLoading" color="primary" indeterminate />
          <div v-else class="readme-card__content markdown-content" v-html="readmeHtml" />
        </v-card-text>
        <v-card-actions>
          <v-btn rounded="xl" variant="text" @click="readmeDialogVisible = false">
            {{ t('common.close') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup lang="ts">
  import type { RawSettingsResponse } from '@/api/settings'
  import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useRoute } from 'vue-router'
  import { getErrorMessage } from '@/api/client'
  import {
    checkPluginUpdates,
    cleanupOrphanPluginConfigs,
    getOrphanPluginConfigs,
    getPluginInstallTask,
    getPluginReadme,
    getPlugins,
    getPluginSettings,
    getPluginSettingsRaw,
    getPluginTogglePreview,
    installManualPlugin,
    type OrphanPluginConfigItem,
    type PluginItem,
    type PluginReadmeResponse,
    type PluginStoreTask,
    type PluginUpdateCheckItem,
    uninstallPlugin,
    updateInstalledPlugin,
    updatePlugin,
    updatePluginSettings,
    updatePluginSettingsRaw,
    validatePluginSettingsRaw,
  } from '@/api/plugins'
  import { useRawTomlValidation } from '@/composables/useRawTomlValidation'
  import { useAuthStore } from '@/stores/auth'
  import { useNoticeStore } from '@/stores/notice'
  import { useRestartStore } from '@/stores/restart'
  import {
    pluginToggleHint as buildPluginToggleHint,
    settingsSourceLabel as buildSettingsSourceLabel,
    settingsValueSourceLabel as buildSettingsValueSourceLabel,
    sourceLabel as buildSourceLabel,
    updateButtonTooltip as buildUpdateButtonTooltip,
    formatFieldChoices,
    hasPluginUpdate as hasPluginUpdateForChecks,
    pluginMetaSummary,
    pluginProjectUrl,
    sourceColor,
  } from '@/views/plugins/display'
  import {
    buildPluginNameMap,
    getNonSystemPlugins,
    getSystemPlugins,
    getVisiblePlugins,
  } from '@/views/plugins/filters'
  import RawSettingsEditor from '@/views/plugins/RawSettingsEditor.vue'
  import { renderReadmeHtml } from '@/views/plugins/readme'
  import {
    buildRevertValues,
    buildSettingsPreviewItems,
    type PluginSettingField,
  } from '@/views/plugins/settingsEditor'
  import SettingsFieldEditor from '@/views/plugins/SettingsFieldEditor.vue'
  import SettingsModeBar from '@/views/plugins/SettingsModeBar.vue'
  import SettingsPreviewDialog from '@/views/plugins/SettingsPreviewDialog.vue'
  import {
    manualInstallTaskStatusLabel as buildManualInstallTaskStatusLabel,
    packageUpdateTaskStatusLabel as buildPackageUpdateTaskStatusLabel,
    summarizeTaskError,
  } from '@/views/plugins/tasks'
  import { useSettingsEditor } from '@/views/plugins/useSettingsEditor'

  const plugins = ref<PluginItem[]>([])
  const loading = ref(false)
  const pendingModule = ref('')
  const errorMessage = ref('')
  const pluginScopeTab = ref<'managed' | 'framework'>('managed')
  const pluginSearch = ref('')
  const manualInstallDialogVisible = ref(false)
  const manualInstallTaskDialogVisible = ref(false)
  const manualInstallSubmitting = ref(false)
  const manualInstallSourceType = ref<'pypi' | 'git' | 'local'>('pypi')
  const manualInstallRequirement = ref('')
  const manualInstallModuleName = ref('')
  const manualInstallTask = ref<PluginStoreTask | null>(null)
  const activeManualInstallRequirement = ref('')
  let manualInstallTaskPollTimer: number | null = null
  const packageUpdateTaskDialogVisible = ref(false)
  const packageUpdateTask = ref<PluginStoreTask | null>(null)
  const packageUpdatingModule = ref('')
  let packageUpdateTaskPollTimer: number | null = null
  const updateCheckLoading = ref(false)
  const pluginUpdateChecks = ref<Record<string, PluginUpdateCheckItem>>({})
  const readmeDialogVisible = ref(false)
  const readmeLoading = ref(false)
  const readmeLoadingModule = ref('')
  const readmeTarget = ref<PluginItem | null>(null)
  const readmeDocument = ref<PluginReadmeResponse | null>(null)
  const readmeErrorMessage = ref('')
  const settingsDialogVisible = ref(false)
  const settingsLoadingModule = ref('')
  const settingsPlugin = ref<PluginItem | null>(null)
  const settingsEditorMode = ref<'basic' | 'advanced'>('basic')
  const settingsRawText = ref('')
  const settingsRawInitialText = ref('')
  const settingsRawLoading = ref(false)
  const settingsRawSaving = ref(false)
  const settingsRawErrorMessage = ref('')
  const previewDialogVisible = ref(false)
  const previewMode = ref<'basic' | 'raw'>('basic')
  const previewAction = ref<'plugin-basic' | 'plugin-raw'>('plugin-basic')
  const toggleConfirmVisible = ref(false)
  const toggleConfirmLoading = ref(false)
  const toggleConfirmItem = ref<PluginItem | null>(null)
  const toggleConfirmNextValue = ref(false)
  const toggleConfirmSummaryText = ref('')
  const toggleConfirmDependencies = ref<string[]>([])
  const uninstallingModule = ref('')
  const uninstallConfirmVisible = ref(false)
  const uninstallConfirmItem = ref<PluginItem | null>(null)
  const uninstallRemoveConfig = ref(false)
  const orphanConfigDialogVisible = ref(false)
  const orphanConfigLoading = ref(false)
  const orphanConfigCleaning = ref(false)
  const orphanConfigItems = ref<OrphanPluginConfigItem[]>([])
  const authStore = useAuthStore()
  const noticeStore = useNoticeStore()
  const restartStore = useRestartStore()
  const { t } = useI18n()
  const route = useRoute()

  const pluginEditor = useSettingsEditor({
    save: payload => updatePluginSettings(settingsPlugin.value!.module_name, payload),
    messages: {
      invalidJson: t('plugins.settingsInvalidJson'),
      loadFailed: t('plugins.settingsLoadFailed'),
      saveFailed: t('plugins.settingsSaveFailed'),
      saveSuccess: t('plugins.settingsSaved'),
    },
    afterSave: ({ previousState, values, clear }) => {
      if (!settingsPlugin.value) return
      restartStore.markPending({
        id: `plugin:settings:${settingsPlugin.value.module_name}`,
        scope: 'plugins',
        summary: t('restart.pendingPluginSettings', {
          name: settingsPlugin.value.name || settingsPlugin.value.module_name,
        }),
        undo: {
          kind: 'plugin-settings',
          moduleName: settingsPlugin.value.module_name,
          values: buildRevertValues(previousState.fields, values, clear),
        },
      })
    },
  })

  const settingsDialogLoading = pluginEditor.loading
  const settingsSaving = pluginEditor.saving
  const settingsErrorMessage = pluginEditor.errorMessage
  const settingsState = pluginEditor.state
  const settingsFields = pluginEditor.fields
  const settingsForm = pluginEditor.form
  const hasPendingPluginChanges = pluginEditor.hasPendingChanges
  const hasPendingPluginRawChanges = computed(() => settingsRawText.value !== settingsRawInitialText.value)
  const previewSaving = computed(() => settingsSaving.value || settingsRawSaving.value)
  const previewTitle = computed(() =>
    previewMode.value === 'basic' ? t('plugins.previewChangesTitle') : t('plugins.previewRawTitle'),
  )
  const previewCurrentText = computed(() => settingsRawInitialText.value)
  const previewNextText = computed(() => settingsRawText.value)
  const previewItems = computed(() =>
    buildSettingsPreviewItems(
      settingsFields.value,
      settingsForm.value,
      pluginEditor.draftOverrides.value,
      pluginEditor.draftClears.value,
      t('plugins.settingsInvalidJson'),
    ),
  )
  const {
    validateNow: validatePluginRawNow,
    validationColumn: pluginRawValidationColumn,
    validationLine: pluginRawValidationLine,
    validationMessage: pluginRawValidationMessage,
    validationPending: pluginRawValidationPending,
  } = useRawTomlValidation({
    text: settingsRawText,
    initialText: settingsRawInitialText,
    fallbackMessage: t('plugins.settingsRawValidateFailed'),
    validate: async text => {
      if (!settingsPlugin.value) {
        return { valid: true, message: null, line: null, column: null }
      }
      return (await validatePluginSettingsRaw(settingsPlugin.value.module_name, { text })).data
    },
  })
  const toggleConfirmTitle = computed(() =>
    toggleConfirmNextValue.value ? t('plugins.enableConfirmTitle') : t('plugins.disableConfirmTitle'),
  )
  const toggleConfirmSummary = computed(() => toggleConfirmSummaryText.value)
  const pluginNameMap = computed(() =>
    buildPluginNameMap(plugins.value),
  )
  const uninstallConfirmSummary = computed(() => {
    if (!uninstallConfirmItem.value) return ''
    const pluginName = uninstallConfirmItem.value.name || uninstallConfirmItem.value.module_name
    if (uninstallConfirmItem.value.installed_package) {
      return t('plugins.settingsUninstallConfirm', {
        name: pluginName,
        package: uninstallConfirmItem.value.installed_package,
      })
    }
    return t('plugins.settingsUninstallConfirmFallback', {
      name: pluginName,
    })
  })
  const systemPlugins = computed(() =>
    getSystemPlugins(plugins.value),
  )

  const nonSystemPlugins = computed(() =>
    getNonSystemPlugins(plugins.value),
  )

  const visiblePlugins = computed(() =>
    getVisiblePlugins(plugins.value, {
      disabledOnly: route.query.enabled === 'disabled',
      scope: pluginScopeTab.value,
      search: pluginSearch.value,
    }),
  )

  const manualInstallSourceOptions = computed(() => [
    { value: 'pypi', label: t('plugins.manualInstallSourcePypi') },
    { value: 'git', label: t('plugins.manualInstallSourceGit') },
    { value: 'local', label: t('plugins.manualInstallSourceLocal') },
  ])

  const manualInstallRequirementLabel = computed(() => {
    if (manualInstallSourceType.value === 'git') {
      return t('plugins.manualInstallGitLabel')
    }
    if (manualInstallSourceType.value === 'local') {
      return t('plugins.manualInstallLocalLabel')
    }
    return t('plugins.manualInstallPackageLabel')
  })

  const manualInstallRequirementHint = computed(() => {
    if (manualInstallSourceType.value === 'git') {
      return t('plugins.manualInstallGitHint')
    }
    if (manualInstallSourceType.value === 'local') {
      return t('plugins.manualInstallLocalHint')
    }
    return t('plugins.manualInstallPackageHint')
  })

  const canSubmitManualInstall = computed(() => manualInstallRequirement.value.trim().length > 0)
  const manualInstallTaskErrorSummary = computed(() => {
    return summarizeTaskError(manualInstallTask.value?.error)
  })
  const manualInstallTaskStatusLabel = computed(() => {
    return buildManualInstallTaskStatusLabel(manualInstallTask.value, t)
  })
  const packageUpdateTaskErrorSummary = computed(() => {
    return summarizeTaskError(packageUpdateTask.value?.error)
  })
  const packageUpdateTaskStatusLabel = computed(() => {
    return buildPackageUpdateTaskStatusLabel(packageUpdateTask.value, t)
  })
  const readmeDialogTitle = computed(() =>
    t('plugins.readmeTitle', {
      name: readmeTarget.value?.name || readmeTarget.value?.module_name || '',
    }),
  )
  const readmeFilename = computed(() => readmeDocument.value?.filename || '')
  const readmeHtml = computed(() =>
    renderReadmeHtml(
      readmeDocument.value?.content || '',
      readmeTarget.value?.module_name,
    ),
  )

  function applyRouteFilters () {
    const searchQuery = route.query.search
    pluginSearch.value = typeof searchQuery === 'string' ? searchQuery : ''
  }

  function sourceLabel (source: string) {
    return buildSourceLabel(source, t)
  }

  function hasPluginUpdate (item: PluginItem) {
    return hasPluginUpdateForChecks(pluginUpdateChecks.value, item)
  }

  function updateButtonTooltip (item: PluginItem) {
    return buildUpdateButtonTooltip(
      pluginUpdateChecks.value,
      item,
      updateCheckLoading.value,
      t,
    )
  }

  function pluginToggleHint (item: PluginItem) {
    return buildPluginToggleHint(item, t)
  }

  function settingsSourceLabel (source: string) {
    return buildSettingsSourceLabel(source, t)
  }

  function settingsValueSourceLabel (source: string) {
    return buildSettingsValueSourceLabel(source, t)
  }

  function getPluginLabel (moduleName: string) {
    return pluginNameMap.value.get(moduleName) || moduleName
  }

  function closeToggleConfirm () {
    toggleConfirmVisible.value = false
    toggleConfirmLoading.value = false
    toggleConfirmItem.value = null
    toggleConfirmNextValue.value = false
    toggleConfirmSummaryText.value = ''
    toggleConfirmDependencies.value = []
  }

  function closeUninstallConfirm () {
    uninstallConfirmVisible.value = false
    uninstallConfirmItem.value = null
    uninstallRemoveConfig.value = false
  }

  async function openOrphanConfigDialog () {
    orphanConfigDialogVisible.value = true
    orphanConfigLoading.value = true
    try {
      orphanConfigItems.value = (await getOrphanPluginConfigs()).data.items
    } catch (error) {
      orphanConfigDialogVisible.value = false
      noticeStore.show(getErrorMessage(error, t('plugins.orphanConfigCleanupFailed')), 'error')
    } finally {
      orphanConfigLoading.value = false
    }
  }

  function openToggleConfirm (
    item: PluginItem,
    enabled: boolean,
    summary: string,
    dependencies: string[],
  ) {
    toggleConfirmItem.value = item
    toggleConfirmNextValue.value = enabled
    toggleConfirmSummaryText.value = summary
    toggleConfirmDependencies.value = dependencies
    toggleConfirmVisible.value = true
  }

  function applyPluginRawState (nextState: RawSettingsResponse) {
    settingsRawText.value = nextState.text
    settingsRawInitialText.value = nextState.text
  }

  async function loadPluginRawSettings (moduleName: string) {
    settingsRawLoading.value = true
    settingsRawErrorMessage.value = ''
    try {
      const response = await getPluginSettingsRaw(moduleName)
      applyPluginRawState(response.data)
    } catch (error) {
      settingsRawErrorMessage.value = getErrorMessage(error, t('plugins.settingsRawLoadFailed'))
    } finally {
      settingsRawLoading.value = false
    }
  }

  async function loadPluginManagement (options?: { forceUpdateRefresh?: boolean }) {
    loading.value = true
    errorMessage.value = ''
    try {
      plugins.value = (await getPlugins()).data
      await runPluginUpdateCheck(options?.forceUpdateRefresh === true)
    } catch (error) {
      errorMessage.value = getErrorMessage(error, t('plugins.loadFailed'))
    } finally {
      loading.value = false
    }
  }

  async function runPluginUpdateCheck (forceRefresh = false) {
    if (updateCheckLoading.value) return
    updateCheckLoading.value = true
    try {
      const response = await checkPluginUpdates({
        force_refresh: forceRefresh || undefined,
      })
      pluginUpdateChecks.value = Object.fromEntries(
        response.data.map(item => [item.module_name, item]),
      )
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('plugins.updateCheckFailed')), 'error')
    } finally {
      updateCheckLoading.value = false
    }
  }

  function openManualInstallDialog () {
    manualInstallSourceType.value = 'pypi'
    manualInstallRequirement.value = ''
    manualInstallModuleName.value = ''
    manualInstallDialogVisible.value = true
  }

  async function submitManualInstall () {
    const requirement = manualInstallRequirement.value.trim()
    if (!requirement) return

    manualInstallSubmitting.value = true
    try {
      const response = await installManualPlugin({
        requirement,
        module_name: manualInstallModuleName.value.trim() || undefined,
      })
      activeManualInstallRequirement.value = requirement
      manualInstallTask.value = response.data
      manualInstallDialogVisible.value = false
      manualInstallTaskDialogVisible.value = true
      startManualInstallTaskPolling(response.data.task_id)
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('plugins.manualInstallFailed')), 'error')
    } finally {
      manualInstallSubmitting.value = false
    }
  }

  function stopManualInstallTaskPolling () {
    if (manualInstallTaskPollTimer !== null) {
      window.clearInterval(manualInstallTaskPollTimer)
      manualInstallTaskPollTimer = null
    }
  }

  function stopPackageUpdateTaskPolling () {
    if (packageUpdateTaskPollTimer !== null) {
      window.clearInterval(packageUpdateTaskPollTimer)
      packageUpdateTaskPollTimer = null
    }
  }

  function startManualInstallTaskPolling (taskId: string) {
    stopManualInstallTaskPolling()
    manualInstallTaskPollTimer = window.setInterval(async () => {
      try {
        const response = await getPluginInstallTask(taskId)
        manualInstallTask.value = response.data
        if (response.data.status === 'succeeded' || response.data.status === 'failed') {
          stopManualInstallTaskPolling()
          if (response.data.status === 'succeeded') {
            const moduleName = typeof response.data.result.module_name === 'string'
              ? response.data.result.module_name
              : ''
            const requirement = typeof response.data.result.requirement === 'string'
              ? response.data.result.requirement
              : activeManualInstallRequirement.value
            restartStore.markPending({
              id: `plugin-manual-install:${moduleName || requirement}`,
              scope: 'plugins',
              summary: t('plugins.manualInstallRestartPending', { name: moduleName || requirement }),
              undo: {
                kind: 'plugin-install',
                packageName: requirement,
                moduleName,
              },
            })
            noticeStore.show(t('plugins.manualInstallSucceeded'), 'success')
            void loadPluginManagement()
          } else {
            noticeStore.show(summarizeTaskError(response.data.error) || t('plugins.manualInstallFailed'), 'error')
          }
        }
      } catch (error) {
        stopManualInstallTaskPolling()
        noticeStore.show(getErrorMessage(error, t('plugins.manualInstallFailed')), 'error')
      }
    }, 1500)
  }

  function startPackageUpdateTaskPolling (taskId: string) {
    stopPackageUpdateTaskPolling()
    packageUpdateTaskPollTimer = window.setInterval(async () => {
      try {
        const response = await getPluginInstallTask(taskId)
        packageUpdateTask.value = response.data
        if (response.data.status === 'succeeded' || response.data.status === 'failed') {
          stopPackageUpdateTaskPolling()
          if (response.data.status === 'succeeded') {
            const moduleName = typeof response.data.result.module_name === 'string'
              ? response.data.result.module_name
              : packageUpdatingModule.value
            const requirement = typeof response.data.result.requirement === 'string'
              ? response.data.result.requirement
              : ''
            restartStore.markPending({
              id: `plugin-package-update:${moduleName || requirement}`,
              scope: 'plugins',
              summary: t('plugins.packageUpdateRestartPending', { name: moduleName || requirement }),
            })
            noticeStore.show(t('plugins.packageUpdateSucceeded'), 'success')
            void loadPluginManagement({ forceUpdateRefresh: true })
          } else {
            noticeStore.show(
              summarizeTaskError(response.data.error) || t('plugins.packageUpdateFailed'),
              'error',
            )
          }
          packageUpdatingModule.value = ''
        }
      } catch (error) {
        stopPackageUpdateTaskPolling()
        packageUpdatingModule.value = ''
        noticeStore.show(getErrorMessage(error, t('plugins.packageUpdateFailed')), 'error')
      }
    }, 1500)
  }

  async function openSettings (item: PluginItem) {
    if (!item.can_edit_config) return
    settingsPlugin.value = item
    settingsDialogVisible.value = true
    settingsEditorMode.value = 'basic'
    settingsDialogLoading.value = true
    settingsLoadingModule.value = item.module_name
    pluginEditor.reset()
    settingsRawText.value = ''
    settingsRawInitialText.value = ''
    settingsRawErrorMessage.value = ''
    try {
      const settingsResponse = await getPluginSettings(item.module_name)
      pluginEditor.applyState(settingsResponse.data)
    } catch (error) {
      settingsErrorMessage.value = getErrorMessage(error, t('plugins.settingsLoadFailed'))
    } finally {
      settingsDialogLoading.value = false
      settingsLoadingModule.value = ''
    }
    await loadPluginRawSettings(item.module_name)
  }

  async function openReadme (item: PluginItem) {
    readmeTarget.value = item
    readmeDialogVisible.value = true
    readmeLoading.value = true
    readmeLoadingModule.value = item.module_name
    readmeDocument.value = null
    readmeErrorMessage.value = ''
    try {
      readmeDocument.value = (await getPluginReadme(item.module_name)).data
    } catch (error) {
      readmeErrorMessage.value = getErrorMessage(error, t('plugins.readmeLoadFailed'))
    } finally {
      readmeLoading.value = false
      readmeLoadingModule.value = ''
    }
  }

  async function saveSettings () {
    if (!settingsPlugin.value || !settingsState.value) return
    await pluginEditor.submit()
  }

  function canUninstallPlugin (item: PluginItem) {
    return authStore.role === 'owner' && item.can_uninstall
  }

  function canUpdatePlugin (item: PluginItem) {
    return (
      authStore.role === 'owner'
      && item.can_package_update
      && !item.is_pending_uninstall
      && !!item.installed_package
    )
  }

  async function updatePluginItem (item: PluginItem) {
    if (!item.installed_package || packageUpdatingModule.value) return
    packageUpdatingModule.value = item.module_name
    try {
      const response = await updateInstalledPlugin(item.module_name, {
        package_name: item.installed_package,
      })
      packageUpdateTask.value = response.data
      packageUpdateTaskDialogVisible.value = true
      startPackageUpdateTaskPolling(response.data.task_id)
    } catch (error) {
      packageUpdatingModule.value = ''
      noticeStore.show(getErrorMessage(error, t('plugins.packageUpdateFailed')), 'error')
    }
  }

  async function uninstallPluginItem (item: PluginItem) {
    uninstallConfirmItem.value = item
    uninstallRemoveConfig.value = false
    uninstallConfirmVisible.value = true
  }

  async function confirmUninstallPlugin () {
    if (!uninstallConfirmItem.value) return
    const item = uninstallConfirmItem.value
    uninstallingModule.value = item.module_name
    try {
      await uninstallPlugin(item.module_name, {
        remove_config: uninstallRemoveConfig.value,
      })
      noticeStore.show(t('plugins.settingsUninstallSucceeded'), 'success')
      if (settingsPlugin.value?.module_name === item.module_name) {
        settingsDialogVisible.value = false
      }
      closeUninstallConfirm()
      await loadPluginManagement()
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('plugins.settingsUninstallFailed')), 'error')
    } finally {
      uninstallingModule.value = ''
    }
  }

  async function confirmCleanupOrphanConfigs () {
    orphanConfigCleaning.value = true
    try {
      const removed = (await cleanupOrphanPluginConfigs()).data.items
      orphanConfigItems.value = removed
      orphanConfigDialogVisible.value = false
      if (removed.length > 0) {
        noticeStore.show(
          t('plugins.orphanConfigCleanupSucceeded', { count: removed.length }),
          'success',
        )
      } else {
        noticeStore.show(t('plugins.orphanConfigCleanupEmpty'), 'info')
      }
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('plugins.orphanConfigCleanupFailed')), 'error')
    } finally {
      orphanConfigCleaning.value = false
    }
  }

  function openPluginSettingsPreview () {
    if (!settingsState.value) return
    const items = previewItems.value
    if (items.length === 0) return
    previewMode.value = 'basic'
    previewAction.value = 'plugin-basic'
    previewDialogVisible.value = true
  }

  async function clearPluginField (field: PluginSettingField) {
    pluginEditor.clearField(field)
  }

  async function savePluginRawSettings () {
    if (!settingsPlugin.value || !hasPendingPluginRawChanges.value) return
    settingsRawSaving.value = true
    settingsRawErrorMessage.value = ''
    const previousText = settingsRawInitialText.value
    try {
      const rawResponse = await updatePluginSettingsRaw(settingsPlugin.value.module_name, {
        text: settingsRawText.value,
      })
      const settingsResponse = await getPluginSettings(settingsPlugin.value.module_name)
      applyPluginRawState(rawResponse.data)
      pluginEditor.applyState(settingsResponse.data)
      restartStore.markPending({
        id: `plugin:raw:${settingsPlugin.value.module_name}`,
        scope: 'plugins',
        summary: t('restart.pendingPluginRaw', {
          name: settingsPlugin.value.name || settingsPlugin.value.module_name,
        }),
        undo: {
          kind: 'plugin-raw',
          moduleName: settingsPlugin.value.module_name,
          text: previousText,
        },
      })
      noticeStore.show(t('plugins.settingsRawSaved'), 'success')
    } catch (error) {
      const message = getErrorMessage(error, t('plugins.settingsRawSaveFailed'))
      settingsRawErrorMessage.value = message
      noticeStore.show(message, 'error')
    } finally {
      settingsRawSaving.value = false
    }
  }

  async function openPluginRawPreview () {
    if (!hasPendingPluginRawChanges.value) return
    if (!await validatePluginRawNow()) return
    previewMode.value = 'raw'
    previewAction.value = 'plugin-raw'
    previewDialogVisible.value = true
  }

  async function confirmPreviewSave () {
    await (previewAction.value === 'plugin-basic' ? saveSettings() : savePluginRawSettings())

    if (!settingsErrorMessage.value && !settingsRawErrorMessage.value) {
      previewDialogVisible.value = false
    }
  }

  async function togglePlugin (item: PluginItem, nextValue: boolean | null) {
    if (item.is_pending_uninstall) {
      noticeStore.show(t('plugins.pendingUninstallHint'), 'warning')
      return
    }
    if (item.is_protected) {
      noticeStore.show(item.protected_reason || t('plugins.cannotDisable'), 'warning')
      return
    }
    const enabled = Boolean(nextValue)
    item.is_global_enabled = !enabled
    pendingModule.value = item.module_name
    errorMessage.value = ''
    try {
      const preview = (await getPluginTogglePreview(item.module_name, enabled)).data
      if (!preview.allowed) {
        const message = preview.blocked_reason || t('plugins.cannotDisable')
        errorMessage.value = message
        noticeStore.show(message, 'warning')
        return
      }
      const dependencies = enabled ? preview.requires_enable : preview.requires_disable
      if (dependencies.length > 0) {
        openToggleConfirm(item, enabled, preview.summary, dependencies)
        return
      }
      await executeToggle(item, enabled, false)
    } catch (error) {
      errorMessage.value = getErrorMessage(error, t('plugins.updateFailed'))
      noticeStore.show(errorMessage.value, 'error')
    } finally {
      pendingModule.value = ''
    }
  }

  async function executeToggle (
    item: PluginItem,
    enabled: boolean,
    cascade: boolean,
  ) {
    const previous = item.is_global_enabled
    item.is_global_enabled = enabled
    pendingModule.value = item.module_name
    errorMessage.value = ''
    try {
      const response = await updatePlugin(item.module_name, enabled, cascade)
      const affectedModules = response.data.affected_modules
      restartStore.markPending({
        id: `plugin:toggle:${item.module_name}`,
        scope: 'plugins',
        summary: t('restart.pendingPluginToggle', {
          name: item.name || item.module_name,
        }),
        undo: {
          kind: 'plugin-toggle',
          moduleName: item.module_name,
          enabled: previous,
        },
      })
      await loadPluginManagement()
      if (settingsPlugin.value) {
        settingsPlugin.value = plugins.value.find(
          candidate => candidate.module_name === settingsPlugin.value?.module_name,
        ) || settingsPlugin.value
      }
      const linkedModules = affectedModules.filter(moduleName => moduleName !== item.module_name)
      const affectedSummary = linkedModules.length > 0
        ? ` (${linkedModules.map(moduleName => getPluginLabel(moduleName)).join(', ')})`
        : ''
      noticeStore.show(
        t('plugins.toggled', {
          name: item.name || item.module_name,
          action: enabled ? t('plugins.enabledAction') : t('plugins.disabledAction'),
        }) + affectedSummary,
        'success',
      )
    } catch (error) {
      item.is_global_enabled = previous
      errorMessage.value = getErrorMessage(error, t('plugins.updateFailed'))
      noticeStore.show(errorMessage.value, 'error')
    } finally {
      pendingModule.value = ''
    }
  }

  async function confirmToggleAction () {
    if (!toggleConfirmItem.value) return
    toggleConfirmLoading.value = true
    try {
      await executeToggle(toggleConfirmItem.value, toggleConfirmNextValue.value, true)
      closeToggleConfirm()
    } finally {
      toggleConfirmLoading.value = false
    }
  }

  onMounted(() => {
    applyRouteFilters()
    void loadPluginManagement()
  })

  watch(() => route.query, () => {
    applyRouteFilters()
  })

  onBeforeUnmount(() => {
    stopManualInstallTaskPolling()
    stopPackageUpdateTaskPolling()
  })
</script>

<style scoped>
.settings-dialog-card {
  display: flex;
  flex-direction: column;
  max-height: min(88vh, 920px);
}

.settings-dialog-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 24px 12px;
}

.settings-dialog-header__main {
  display: flex;
  flex: 1 1 auto;
  min-width: 0;
  flex-direction: column;
  gap: 10px;
}

.settings-dialog-header__title-block {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.settings-dialog-header__title {
  font-size: 1.2rem;
  line-height: 1.3;
  font-weight: 700;
}

.settings-dialog-header__module {
  line-height: 1.35;
}

.settings-dialog-header__meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  min-width: 0;
}

.settings-dialog-header__summary {
  margin-left: 4px;
  white-space: nowrap;
}

.settings-dialog-header__relations {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.settings-dialog-card__body {
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
  padding-top: 0;
}

.settings-shell {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.settings-shell--dialog {
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
}

.settings-list-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: rgb(var(--v-theme-surface-container-low));
  border: 1px solid rgba(var(--v-theme-outline), 0.14);
  border-radius: var(--shape-medium);
}

.settings-shell--dialog .settings-list-panel {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
}

.settings-list-row {
  padding: 18px 20px;
  border-bottom: 1px solid rgba(var(--v-theme-outline), 0.12);
  background:
    linear-gradient(180deg, rgba(var(--v-theme-surface), 0.94), rgba(var(--v-theme-surface), 0.94)),
    linear-gradient(135deg, rgba(var(--v-theme-primary), 0.015), rgba(var(--v-theme-secondary), 0.015));
}

.settings-list-row:last-child {
  border-bottom: 0;
}

.settings-list-row__main {
  display: grid;
  grid-template-columns: minmax(200px, 260px) minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}

.settings-list-row__info {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

.settings-list-row__label {
  line-height: 1.3;
  word-break: break-word;
}

.settings-list-row__description {
  line-height: 1.45;
}

.settings-list-row__status {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  min-height: 20px;
}

.settings-list-row__control {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
  padding: 14px;
  border-radius: var(--shape-medium);
  background: rgba(var(--v-theme-surface), 0.72);
  border: 1px solid rgba(var(--v-theme-outline), 0.2);
  transition:
    border-color var(--motion-fast) var(--motion-ease),
    box-shadow var(--motion-fast) var(--motion-ease),
    background-color var(--motion-fast) var(--motion-ease);
}

.settings-list-row__control:focus-within {
  border-color: rgba(var(--v-theme-primary), 0.3);
  box-shadow: var(--focus-ring);
}

.settings-list-row__actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
  flex-wrap: wrap;
}

.settings-action {
  min-width: 68px;
}

.settings-action--primary {
  font-weight: 600;
}

.settings-list-row__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
  line-height: 1.35;
  word-break: break-word;
}

.settings-list-row__control :deep(.settings-field-editor) {
  width: 100%;
}

.settings-list-row__control :deep(.v-field),
.settings-list-row__control :deep(.v-selection-control) {
  width: 100%;
}

.settings-list-row__control :deep(.v-field--variant-outlined .v-field__outline) {
  color: rgba(var(--v-theme-outline), 0.26);
}

.plugin-scope-tabs {
  flex: 0 0 auto;
  --segmented-max-width: 420px;
}

.plugin-scope-tab {
  min-width: 0;
}

.plugin-search {
  width: 240px;
}

.plugins-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.plugin-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 228px;
  padding: 16px;
  transition:
    transform var(--motion-base) var(--motion-ease),
    box-shadow var(--motion-base) var(--motion-ease),
    border-color var(--motion-base) var(--motion-ease);
}

.plugin-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--elevation-soft-hover);
}

.plugin-card:focus-within {
  box-shadow: var(--focus-ring), var(--elevation-soft);
}

.plugin-card__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.plugin-card__headline {
  min-width: 0;
  display: flex;
  flex: 1 1 220px;
  flex-direction: column;
  gap: 4px;
}

.plugin-card__title-row,
.plugin-card__relations,
.plugin-detail-tags,
.confirm-plugin-item__relations {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.plugin-card__title {
  margin: 0;
  font-size: 1rem;
  line-height: 1.25;
  font-weight: 800;
}

.plugin-card__subline {
  line-height: 1.35;
}

.plugin-card__description {
  margin: 0;
  color: rgba(var(--v-theme-on-surface), 0.76);
  line-height: 1.45;
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
}

.plugin-card__footer {
  margin-top: auto;
}

.plugin-card__footer-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.plugin-card__actions {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  flex-wrap: wrap;
  min-width: 0;
}

.plugin-card__action-anchor {
  display: inline-flex;
}

.plugin-card__actions :deep(.v-btn) {
  min-width: 44px;
  padding-inline: 4px;
  transition:
    background-color var(--motion-fast) var(--motion-ease),
    color var(--motion-fast) var(--motion-ease),
    opacity var(--motion-fast) var(--motion-ease);
}

.plugin-card__actions :deep(.v-btn:hover) {
  opacity: 0.92;
}

.plugin-card__switch :deep(.v-switch) {
  width: 54px;
  margin-inline: 0;
}

.plugin-card__switch-wrap {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex: 0 0 auto;
}

.readme-dialog__body {
  padding-top: 8px;
}

.readme-card__content {
  margin: 0;
  max-height: min(68vh, 720px);
  overflow: auto;
  font-size: 0.95rem;
  line-height: 1.7;
  word-break: break-word;
}

.markdown-content {
  white-space: normal;
}

.markdown-content :deep(h1),
.markdown-content :deep(h2),
.markdown-content :deep(h3),
.markdown-content :deep(h4),
.markdown-content :deep(h5),
.markdown-content :deep(h6) {
  margin: 24px 0 12px;
  line-height: 1.3;
}

.markdown-content :deep(h1) {
  padding-bottom: 0.3em;
  border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  font-size: 1.7rem;
}

.markdown-content :deep(h2) {
  padding-bottom: 0.25em;
  border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  font-size: 1.4rem;
}

.markdown-content :deep(h3) {
  font-size: 1.15rem;
}

.markdown-content :deep(p),
.markdown-content :deep(ul),
.markdown-content :deep(ol),
.markdown-content :deep(pre),
.markdown-content :deep(blockquote),
.markdown-content :deep(table) {
  margin: 0 0 12px;
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  padding-left: 20px;
}

.markdown-content :deep(li) {
  margin: 0.25em 0;
}

.markdown-content :deep(a) {
  color: rgb(var(--v-theme-primary));
  text-decoration: none;
}

.markdown-content :deep(a:hover) {
  text-decoration: underline;
}

.markdown-content :deep(a:focus-visible) {
  outline: none;
  text-decoration: underline;
  box-shadow: var(--focus-ring);
}

.markdown-content :deep(blockquote) {
  padding-left: 14px;
  border-left: 3px solid rgba(var(--v-theme-primary), 0.35);
  color: rgba(var(--v-theme-on-surface), 0.76);
}

.markdown-content :deep(hr) {
  margin: 24px 0;
  border: 0;
  border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.markdown-content :deep(code) {
  padding: 0.1em 0.35em;
  border-radius: var(--shape-xxsmall);
  background: rgba(var(--v-theme-on-surface), 0.08);
  font-family: var(--font-family-mono);
}

.markdown-content :deep(pre code) {
  display: block;
  padding: 12px 14px;
  overflow: auto;
  background: rgba(var(--v-theme-on-surface), 0.06);
  line-height: 1.55;
}

.markdown-content :deep(table) {
  display: block;
  width: 100%;
  overflow-x: auto;
  border-collapse: collapse;
}

.markdown-content :deep(th),
.markdown-content :deep(td) {
  padding: 8px 12px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  text-align: left;
  vertical-align: top;
}

.markdown-content :deep(th) {
  background: rgba(var(--v-theme-on-surface), 0.04);
  font-weight: 700;
}

.markdown-content :deep(img) {
  max-width: 100%;
  height: auto;
}

.markdown-content :deep(.contains-task-list) {
  padding-left: 0;
  list-style: none;
}

.markdown-content :deep(.task-list-item) {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.markdown-content :deep(.task-list-item-checkbox) {
  margin-top: 0.35em;
}

.plugin-detail-meta {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.confirm-plugin-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.confirm-plugin-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 14px;
  border-radius: var(--shape-small);
  background: rgba(var(--v-theme-on-surface), 0.02);
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.confirm-plugin-item__title {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

@media (max-width: 960px) {
  .plugins-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .settings-dialog-header {
    flex-direction: column;
    align-items: stretch;
    padding-bottom: 10px;
  }

  .settings-list-row__main {
    grid-template-columns: 1fr;
  }

  .settings-list-row__control {
    padding: 12px;
  }

  .plugin-card__footer {
    align-items: flex-start;
  }

  .plugin-card__footer-bar {
    align-items: flex-start;
    flex-direction: column;
  }

  .plugin-card__actions {
    width: 100%;
  }

  .plugin-card__switch {
    align-self: flex-end;
  }
}

@media (max-width: 640px) {
  .plugins-grid {
    grid-template-columns: 1fr;
  }

  .plugin-scope-tabs {
    width: 100%;
  }
}
</style>
