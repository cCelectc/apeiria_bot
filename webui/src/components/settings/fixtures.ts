import type { SettingField, SettingSchema } from '@/utils/settingsEditor'

function schema(overrides: Partial<SettingSchema>): SettingSchema {
  return {
    type: 'str',
    item_type: null,
    key_type: null,
    choices: [],
    allows_null: false,
    fields: [],
    item_schema: null,
    key_schema: null,
    value_schema: null,
    ...overrides,
  }
}

function field(overrides: Partial<SettingField>): SettingField {
  return {
    key: 'setting',
    label: 'Setting',
    type: 'str',
    editor: 'input',
    item_type: null,
    key_type: null,
    schema: null,
    default: '',
    help: '',
    choices: [],
    base_value: '',
    current_value: '',
    local_value: null,
    value_source: 'default',
    has_local_override: false,
    allows_null: false,
    editable: true,
    type_category: 'text_like',
    order: 0,
    secret: false,
    ...overrides,
  }
}

const nestedRuleSchema = schema({
  type: 'RuleConfig',
  fields: [
    {
      key: 'pattern',
      label: 'Pattern',
      help: '',
      default: '*',
      schema: schema({ type: 'str' }),
    },
    {
      key: 'weight',
      label: 'Weight',
      help: '',
      default: 1,
      schema: schema({ type: 'int' }),
    },
  ],
})

export const settingsFieldEditorFixtures = [
  field({ key: 'scalar', current_value: 'hello' }),
  field({
    key: 'choice',
    editor: 'select',
    choices: [
      { title: 'Alpha', value: 'alpha' },
      { title: 'Beta', value: 'beta' },
    ],
    current_value: 'alpha',
  }),
  field({
    key: 'nullable_bool',
    type: 'bool',
    editor: 'switch',
    allows_null: true,
    current_value: null,
  }),
  field({
    key: 'chips',
    type: 'list',
    editor: 'chips',
    type_category: 'sequence',
    item_type: 'str',
    current_value: ['one', 'two'],
  }),
  field({
    key: 'nested_object',
    type: 'AppearanceConfig',
    editor: 'nested_object',
    type_category: 'object',
    schema: schema({
      type: 'AppearanceConfig',
      fields: [
        {
          key: 'theme',
          label: 'Theme',
          help: '',
          default: 'system',
          schema: schema({
            type: 'str',
            choices: [
              { title: 'System', value: 'system' },
              { title: 'Dark', value: 'dark' },
            ],
          }),
        },
      ],
    }),
    current_value: { theme: 'system' },
  }),
  field({
    key: 'nested_sequence',
    type: 'list',
    editor: 'nested_sequence',
    type_category: 'sequence',
    schema: schema({
      type: 'list',
      item_schema: {
        key: 'item',
        label: 'Item',
        help: '',
        default: { pattern: '*', weight: 1 },
        schema: nestedRuleSchema,
      },
    }),
    current_value: [{ pattern: '*', weight: 1 }],
  }),
  field({
    key: 'nested_mapping',
    type: 'dict',
    editor: 'nested_mapping',
    type_category: 'mapping',
    schema: schema({
      type: 'dict',
      key_type: 'str',
      value_schema: {
        key: 'value',
        label: 'Value',
        help: '',
        default: { pattern: '*', weight: 1 },
        schema: nestedRuleSchema,
      },
    }),
    current_value: { default: { pattern: '*', weight: 1 } },
  }),
  field({
    key: 'readonly_payload',
    editor: 'readonly',
    type_category: 'mapping',
    editable: false,
    current_value: { raw: true },
  }),
] satisfies SettingField[]
