import type { Component } from 'vue'

export type WorkbenchTone = 'default' | 'success' | 'warning' | 'error' | 'info'

export interface WorkbenchMetricItem {
  key: string
  label: string
  value: string | number
  hint?: string
  icon?: Component
  tone?: WorkbenchTone
}

export interface WorkbenchTableColumn {
  key: string
  label: string
  align?: 'left' | 'center' | 'right'
}
