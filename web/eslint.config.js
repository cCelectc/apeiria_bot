import vuetify from 'eslint-config-vuetify'

export default await vuetify(
  {
    ignore: {
      extendIgnore: ['package.json', 'pnpm-lock.yaml'],
    },
  },
  {
    rules: {
      'vue/padding-line-between-tags': 'off',
    },
  },
)
