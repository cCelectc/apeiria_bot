import client from "@/api/client"

export const updateService = {
  getStatus() { return client.get("/update/status").then(r => r.data) },
  refresh() { return client.post("/update/refresh").then(r => r.data) },
  plan(data?: Record<string, unknown>) { return client.post("/update/plan", data ?? {}).then(r => r.data) },
  createTask(data: Record<string, unknown>) { return client.post("/update/tasks", data).then(r => r.data) },
  getTask(id: string) { return client.get(`/update/tasks/${id}`).then(r => r.data) },
}
