export interface Translation { branch_id: number; name: string | null; chapter_count: number }
export interface Book { id: number; title: string; slug_url: string; authors: string[]; chapter_count: number; translations: Translation[] }
export interface Chapter { id: number; volume: string; number: string; name: string | null }
export type JobState = 'queued' | 'running' | 'cancelling' | 'cancelled' | 'failed' | 'completed'
export interface Job { id: string; format: string; state: JobState; current: number; total: number; message: string; error: string | null; queue_position: number | null }
export interface JobList { jobs: Job[]; queued: number; running: number; max_workers: number; max_queue: number }
export interface DownloadOptions { reference: string; branch_id: number | null; format: string; resume: boolean; chapter_start_id?: number; chapter_end_id?: number }

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch('/api' + path, init)
  if (!response.ok) {
    let reason = 'HTTP ' + response.status
    try { const data = await response.json(); if (typeof data.detail === 'string') reason = data.detail } catch { /* non-JSON error */ }
    throw new Error(reason)
  }
  if (response.status === 204) return undefined as T
  return await response.json() as T
}
export const api = {
  book(reference: string) { return request<Book>('/books?' + new URLSearchParams({ reference })) },
  chapters(reference: string, branch: number | null) {
    const q = new URLSearchParams({ reference })
    if (branch !== null) q.set('branch_id', String(branch))
    return request<{ chapters: Chapter[] }>('/books/chapters?' + q)
  },
  create(options: DownloadOptions) { return request<Job>('/downloads', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(options) }) },
  get(id: string) { return request<Job>('/downloads/' + encodeURIComponent(id)) },
  jobs() { return request<JobList>('/downloads') },
  cancel(id: string) { return request<Job>('/downloads/' + encodeURIComponent(id) + '/cancel', { method: 'POST' }) },
  remove(id: string) { return request<void>('/downloads/' + encodeURIComponent(id), { method: 'DELETE' }) },
  file(id: string) { return '/api/downloads/' + encodeURIComponent(id) + '/file' },
}
