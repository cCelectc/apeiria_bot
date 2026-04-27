import type { AIBootstrapResponse } from './types'

import client from '../client'

export function getAIBootstrap () {
  return client.get<AIBootstrapResponse>('/ai/bootstrap')
}
