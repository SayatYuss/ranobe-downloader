<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { api, type Book, type Chapter, type Job } from './api'

const reference = ref('')
const loading = ref(false)
const chaptersLoading = ref(false)
const sending = ref(false)
const error = ref('')
const book = ref<Book | null>(null)
const chapters = ref<Chapter[]>([])
const branchId = ref<number | null>(null)
const scope = ref<'all' | 'range' | 'first' | 'last'>('all')
const startId = ref<number | null>(null)
const endId = ref<number | null>(null)
const format = ref('epub')
const jobs = ref<Job[]>([])
const selectedTab = ref<'new' | 'tasks'>('new')
let poller: ReturnType<typeof setInterval> | null = null
let lookupSeq = 0

const selectedBranch = computed(() => book.value?.translations.find(t => t.branch_id === branchId.value))
const fromIndex = computed(() => chapters.value.findIndex(c => c.id === startId.value))
const toIndex = computed(() => chapters.value.findIndex(c => c.id === endId.value))
const chosenCount = computed(() => {
  const n = chapters.value.length
  if (scope.value === 'all') return n
  if (scope.value === 'first' || scope.value === 'last') return Math.min(10, n)
  if (fromIndex.value < 0 || toIndex.value < fromIndex.value) return 0
  return toIndex.value - fromIndex.value + 1
})
const canDownload = computed(() => !!book.value && !sending.value && !chaptersLoading.value && chosenCount.value > 0)
const activeCount = computed(() => jobs.value.filter(j => ['queued', 'running', 'cancelling'].includes(j.state)).length)

function explain(e: unknown) { return e instanceof Error ? e.message : 'Произошла ошибка' }
function chapterLabel(ch: Chapter) { return (ch.volume && ch.volume !== '0' ? 'Том ' + ch.volume + ' · ' : '') + 'Глава ' + ch.number + (ch.name ? ' — ' + ch.name : '') }
function setScope(value: string) {
  if (!['all', 'range', 'first', 'last'].includes(value)) return
  scope.value = value as 'all' | 'range' | 'first' | 'last'
  if (value === 'range' && chapters.value.length) {
    startId.value = chapters.value[0].id
    endId.value = chapters.value[chapters.value.length - 1].id
  }
}
async function findBook() {
  if (!reference.value.trim()) return
  const seq = ++lookupSeq
  loading.value = true; error.value = ''; book.value = null; chapters.value = []
  try {
    const found = await api.book(reference.value.trim())
    if (seq !== lookupSeq) return
    book.value = found
    branchId.value = found.translations.length === 1 ? found.translations[0].branch_id : null
    if (found.translations.length <= 1) await loadChapters()
  } catch (e) { if (seq === lookupSeq) error.value = explain(e) }
  finally { if (seq === lookupSeq) loading.value = false }
}
async function loadChapters() {
  if (!book.value) return
  const seq = ++lookupSeq
  chaptersLoading.value = true; error.value = ''; chapters.value = []
  try {
    const data = await api.chapters(reference.value.trim(), branchId.value)
    if (seq !== lookupSeq) return
    chapters.value = data.chapters
    setScope('all')
  } catch (e) { if (seq === lookupSeq) error.value = explain(e) }
  finally { if (seq === lookupSeq) chaptersLoading.value = false }
}
async function branchChanged() { await loadChapters() }
async function refreshJobs() {
  try { jobs.value = (await api.jobs()).jobs } catch { /* keep prior jobs when offline */ }
}
async function startDownload() {
  if (!canDownload.value) return
  sending.value = true; error.value = ''
  try {
    let from: number | undefined, to: number | undefined
    if (scope.value === 'range') {
      from = startId.value ?? undefined
      to = endId.value ?? undefined
    } else if (scope.value === 'first' && chapters.value.length) {
      to = chapters.value[Math.min(9, chapters.value.length - 1)].id
    } else if (scope.value === 'last' && chapters.value.length) {
      from = chapters.value[Math.max(0, chapters.value.length - 10)].id
    }
    await api.create({ reference: reference.value.trim(), branch_id: branchId.value, format: format.value, resume: true, ...(from !== undefined ? { chapter_start_id: from } : {}), ...(to !== undefined ? { chapter_end_id: to } : {}) })
    selectedTab.value = 'tasks'
    await refreshJobs()
  } catch (e) { error.value = explain(e) }
  finally { sending.value = false }
}
async function cancel(job: Job) {
  try { await api.cancel(job.id); await refreshJobs() } catch (e) { error.value = explain(e) }
}
async function remove(job: Job) {
  try { await api.remove(job.id); await refreshJobs() } catch (e) { error.value = explain(e) }
}
function progress(job: Job) { return job.total ? Math.min(100, Math.round(job.current * 100 / job.total)) : 0 }
function status(job: Job) {
  return ({ queued: 'В очереди', running: 'Скачивание', cancelling: 'Отменяется', cancelled: 'Отменено', failed: 'Ошибка', completed: 'Готово' } as Record<string, string>)[job.state] || job.state
}
watch(branchId, () => { startId.value = null; endId.value = null })
onMounted(() => { void refreshJobs(); poller = setInterval(() => void refreshJobs(), 1800) })
onUnmounted(() => { if (poller) clearInterval(poller) })
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand"><div class="brand-mark">R</div><div><strong>Ranobe<span>DL</span></strong><small>YOUR READING LIBRARY</small></div></div>
      <div class="nav-label">РАБОЧЕЕ ПРОСТРАНСТВО</div>
      <button :class="['nav-item', { active: selectedTab === 'new' }]" @click="selectedTab = 'new'"><span>⌕</span> Новая загрузка</button>
      <button :class="['nav-item', { active: selectedTab === 'tasks' }]" @click="selectedTab = 'tasks'"><span>▤</span> Загрузки <em v-if="activeCount">{{ activeCount }}</em></button>
      <div class="sidebar-bottom"><div class="side-dot"></div><span>Локальный сервер</span><span class="side-label">API</span></div>
    </aside>

    <main class="main">
      <div class="topbar"><span>Библиотека <span class="crumb">/ {{ selectedTab === 'new' ? 'Новая загрузка' : 'Загрузки' }}</span></span><div class="top-right"><span class="tiny-dot"></span> RANOBELIB DOWNLOADER</div></div>

      <section v-if="selectedTab === 'new'" class="content">
        <div class="eyebrow">СКАЧИВАНИЕ КНИГ</div>
        <h1>Твои истории. <span>Твои правила.</span></h1>
        <p class="lead">Сохраняй любимые ранобэ в удобном формате — целиком или только нужные главы.</p>

        <div class="search-panel">
          <label for="reference">ССЫЛКА НА ПРОИЗВЕДЕНИЕ</label>
          <div class="search-line"><span class="link-symbol">↗</span><input id="reference" v-model="reference" placeholder="https://ranobelib.me/ru/manga/..." @keyup.enter="findBook"/><button class="primary" :disabled="loading || !reference.trim()" @click="findBook">{{ loading ? 'Поиск…' : 'Найти книгу' }} <span>→</span></button></div>
          <div class="hint">Поддерживаются ссылки на произведения RanobeLib</div>
        </div>

        <div v-if="error" class="error" role="alert">{{ error }}</div>
        <div v-if="loading" class="loading-card"><div class="spinner"></div> Получаем метаданные произведения…</div>

        <template v-if="book && !loading">
          <div class="section-header"><h2>Произведение</h2><span class="section-tag">НАЙДЕНО</span></div>
          <div class="book-card">
            <div class="book-icon">✦</div>
            <div class="book-info"><div class="category">RANOBELIB · РАНОБЭ</div><h3>{{ book.title }}</h3><p>{{ book.authors.join(', ') || 'Автор не указан' }}</p><div class="book-stats"><span>▤ {{ book.chapter_count }} глав</span><span>◈ {{ book.translations.length || 1 }} {{ book.translations.length === 1 ? 'перевод' : 'переводов' }}</span></div></div>
          </div>

          <div v-if="book.translations.length > 1" class="block"><div class="step-title"><span class="step-number">01</span><div><h2>Выберите перевод</h2><p>Главы будут загружены из выбранной ветки</p></div></div>
            <div class="field"><label for="translation">КОМАНДА ПЕРЕВОДА</label><select id="translation" v-model="branchId" @change="branchChanged"><option :value="null" disabled>Выберите перевод</option><option v-for="tr in book.translations" :key="tr.branch_id" :value="tr.branch_id">{{ tr.name || 'Перевод #' + tr.branch_id }} · {{ tr.chapter_count }} глав</option></select></div>
          </div>
          <div v-if="book.translations.length <= 1 || branchId !== null" class="block"><div class="step-title"><span class="step-number">0{{ book.translations.length > 1 ? '2' : '1' }}</span><div><h2>Выберите главы</h2><p>Можно скачать всё произведение или отдельный диапазон</p></div></div>
            <div v-if="chaptersLoading" class="muted">Загружаем список глав…</div>
            <template v-else-if="chapters.length">
              <div class="scope-grid">
                <button v-for="opt in [{ v: 'all', icon: '▦', name: 'Вся книга', sub: 'Все доступные главы' }, { v: 'first', icon: 'Ⅰ', name: 'Первые 10', sub: 'Начало истории' }, { v: 'last', icon: '↧', name: 'Последние 10', sub: 'Самые новые главы' }, { v: 'range', icon: '⇄', name: 'Диапазон', sub: 'Выбрать вручную' }]" :key="opt.v" :class="['scope-option', { selected: scope === opt.v }]" @click="setScope(opt.v)"><span class="opt-icon">{{ opt.icon }}</span><strong>{{ opt.name }}</strong><small>{{ opt.sub }}</small><span v-if="scope === opt.v" class="selected-mark">✓</span></button>
              </div>
              <div v-if="scope === 'range'" class="range-grid"><div class="field"><label for="start">НАЧАЛЬНАЯ ГЛАВА</label><select id="start" v-model="startId"><option v-for="ch in chapters" :key="ch.id" :value="ch.id">{{ chapterLabel(ch) }}</option></select></div><div class="field"><label for="end">КОНЕЧНАЯ ГЛАВА</label><select id="end" v-model="endId"><option v-for="ch in chapters" :key="ch.id" :value="ch.id">{{ chapterLabel(ch) }}</option></select></div></div>
              <div class="selection-summary"><span>◉</span> Выбрано глав: <strong>{{ chosenCount }}</strong> <span class="summary-right">из {{ chapters.length }} доступных</span></div>
            </template>
            <div v-else class="muted">Нет доступных глав для этого перевода.</div>
          </div>
          <div v-if="chapters.length && !chaptersLoading" class="block"><div class="step-title"><span class="step-number">0{{ book.translations.length > 1 ? '3' : '2' }}</span><div><h2>Формат книги</h2><p>Выбери формат для своего устройства</p></div></div>
            <div class="formats"><button v-for="f in [{ id: 'epub', name: 'EPUB', sub: 'Для электронных читалок' }, { id: 'txt', name: 'TXT', sub: 'Обычный текст' }, { id: 'html', name: 'HTML', sub: 'Для браузера' }]" :key="f.id" :class="['format-option', { selected: format === f.id }]" @click="format = f.id"><span class="format-file">▤</span><strong>{{ f.name }}</strong><small>{{ f.sub }}</small><span v-if="format === f.id" class="selected-mark">✓</span></button></div>
          </div>
          <div v-if="chapters.length && !chaptersLoading" class="download-action"><div><strong>Всё готово</strong><p>{{ chosenCount }} глав · {{ format.toUpperCase() }} · с кешированием</p></div><button class="primary large" :disabled="!canDownload" @click="startDownload">{{ sending ? 'Запускаем…' : 'Начать скачивание' }} <span>↓</span></button></div>
        </template>
        <div v-else-if="!loading" class="empty-preview"><div class="preview-icon">▧</div><strong>Твоя следующая книга начинается здесь</strong><p>Вставь ссылку выше, чтобы получить информацию о произведении и настроить загрузку.</p></div>
      </section>

      <section v-else class="content"><div class="eyebrow">ЦЕНТР ЗАГРУЗОК</div><h1>Твои <span>загрузки.</span></h1><p class="lead">Отслеживай прогресс, скачивай готовые файлы и управляй очередью.</p>
        <div class="queue-stats"><div><small>ВСЕГО ЗАДАЧ</small><strong>{{ jobs.length }}</strong></div><div><small>АКТИВНЫЕ</small><strong>{{ activeCount }}</strong></div><div><small>ГОТОВЫЕ</small><strong>{{ jobs.filter(j => j.state === 'completed').length }}</strong></div></div>
        <div v-if="error" class="error" role="alert">{{ error }}</div>
        <div v-if="!jobs.length" class="empty-preview"><div class="preview-icon">⇩</div><strong>Пока нет загрузок</strong><p>Добавь свою первую книгу, чтобы увидеть её здесь.</p><button class="secondary" @click="selectedTab = 'new'">Новая загрузка →</button></div>
        <div v-for="job in [...jobs].reverse()" :key="job.id" class="job-card"><div class="job-head"><div class="job-icon">▤</div><div class="job-main"><strong>Книга · {{ job.format.toUpperCase() }}</strong><small>ID {{ job.id.slice(0, 12) }}</small></div><span :class="['job-status', job.state]">{{ status(job) }}</span></div>
          <div v-if="job.state === 'running' || job.state === 'queued' || job.state === 'cancelling'" class="job-progress"><div class="progress-label"><span>{{ job.state === 'queued' ? 'В очереди · позиция ' + (job.queue_position ?? '—') : job.message || status(job) }}</span><strong>{{ progress(job) }}%</strong></div><div class="progress-track"><div :style="{ width: progress(job) + '%' }"></div></div></div>
          <p v-if="job.error" class="job-error">{{ job.error }}</p>
          <div class="job-actions"><a v-if="job.state === 'completed'" class="download-link" :href="api.file(job.id)">↓ Скачать файл</a><button v-if="['queued','running'].includes(job.state)" @click="cancel(job)">Отменить</button><button v-if="['completed','failed','cancelled'].includes(job.state)" @click="remove(job)">Удалить</button></div>
        </div>
      </section>
      <footer><span>Ranobe Downloader · Open source</span><span>Сделано для тех, кто любит читать ✦</span></footer>
    </main>
  </div>
</template>
