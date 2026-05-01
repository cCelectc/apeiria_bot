import { createVuetify } from 'vuetify'
import '@mdi/font/css/materialdesignicons.css'
import 'vuetify/styles'

const THEME_STORAGE_KEY = 'apeiria-theme'
const initialTheme
  = typeof window !== 'undefined' && localStorage.getItem(THEME_STORAGE_KEY) === 'light'
    ? 'light'
    : 'dark'

export default createVuetify({
  theme: {
    defaultTheme: initialTheme,
    themes: {
      light: {
        dark: false,
        colors: {
          'primary': '#1565C0',
          'on-primary': '#FFFFFF',
          'primary-container': '#D6E4FF',
          'on-primary-container': '#001C3B',
          'secondary': '#42A5F5',
          'on-secondary': '#FFFFFF',
          'secondary-container': '#D7EEFF',
          'on-secondary-container': '#001D33',
          'accent': '#7C4DFF',
          'tertiary': '#7C4DFF',
          'on-tertiary': '#FFFFFF',
          'tertiary-container': '#EADDFF',
          'on-tertiary-container': '#2B0B60',
          'background': '#F7F9FC',
          'surface': '#FCFCFF',
          'surface-bright': '#FCFCFF',
          'surface-light': '#F4F6FA',
          'surface-variant': '#E1E7F1',
          'surface-container-low': '#F7F9FD',
          'surface-container': '#F1F4F9',
          'surface-container-high': '#EBEEF4',
          'on-surface-variant': '#43474E',
          'outline': '#73777F',
          'outline-variant': '#C3C7CF',
          'error': '#BA1A1A',
          'warning': '#FB8C00',
          'success': '#43A047',
          'info': '#1E88E5',
        },
      },
      dark: {
        dark: true,
        colors: {
          'primary': '#A7C8FF',
          'on-primary': '#003061',
          'primary-container': '#00488A',
          'on-primary-container': '#D6E4FF',
          'secondary': '#8FD0FF',
          'on-secondary': '#003354',
          'secondary-container': '#004B77',
          'on-secondary-container': '#D7EEFF',
          'accent': '#CFBDFF',
          'tertiary': '#CFBDFF',
          'on-tertiary': '#43178E',
          'tertiary-container': '#5D34C5',
          'on-tertiary-container': '#EADDFF',
          'background': '#10131A',
          'surface': '#11141B',
          'surface-bright': '#373A42',
          'surface-light': '#1A1D24',
          'surface-variant': '#43474E',
          'surface-container-low': '#171A21',
          'surface-container': '#1C1F26',
          'surface-container-high': '#262930',
          'on-surface-variant': '#C3C7CF',
          'outline': '#8D9199',
          'outline-variant': '#43474E',
          'error': '#FFB4AB',
          'warning': '#FFB95C',
          'success': '#89D38E',
          'info': '#8CCFFF',
        },
      },
    },
  },
  defaults: {
    VCard: { rounded: 'md', elevation: 0 },
    VBtn: { rounded: 'md' },
    VChip: { rounded: 'sm' },
    VTextField: { variant: 'outlined', density: 'comfortable', flat: true },
    VTextarea: { variant: 'outlined', density: 'comfortable', flat: true },
    VSelect: { variant: 'outlined', density: 'comfortable', flat: true },
    VAutocomplete: { variant: 'outlined', density: 'comfortable', flat: true },
    VCombobox: { variant: 'outlined', density: 'comfortable', flat: true },
    VDataTable: { density: 'comfortable' },
    VSheet: { rounded: 'md' },
    VDialog: { scrim: 'rgba(17, 19, 26, 0.42)' },
  },
})
