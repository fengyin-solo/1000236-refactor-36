<template>
  <section class="page" data-module="prop">
    <header class="page-head">
      <div>
        <h2>道具管理</h2>
        <p class="page-desc">维护道具，围绕道具编号、道具名称、道具类别、所属场次做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记道具</button>
        <button class="btn" type="button" @click="exportRows">导出道具管理清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>道具编号</span>
        <input v-model="filters.keyword" placeholder="按道具编号检索" />
      </label>
      <label class="filter-item">
        <span>使用状态</span>
        <select v-model="filters.status">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in row.available_actions ?? []"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
            <span v-if="!(row.available_actions ?? []).length">—</span>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无道具管理数据，可先登记道具</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条道具管理记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { fetchJson, request } from '@/api/client'

type Row = Record<string, string | number | null> & { available_actions?: string[] }
type StatItem = { label: string; value: number }

const ENDPOINT = '/api/prop'
const columns = ["道具编号", "道具名称", "道具类别", "所属场次", "保管人员", "采购单价", "使用状态", "归还日期"]

const rows = ref<Row[]>([])
const total = ref(0)
const stats = ref<StatItem[]>([])
const statuses = ref<string[]>([])
const errorMessage = ref('')
const filters = ref({ keyword: '', status: '' })

function resetFilters() {
  filters.value = { keyword: '', status: '' }
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '道具登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok || !payload?.ok) {
      throw new Error(payload?.message ?? `道具管理动作未生效（接口返回 ${response.status}）`)
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '道具管理操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (filters.value.keyword) query.set('keyword', filters.value.keyword)
  if (filters.value.status) query.set('status', filters.value.status)
  try {
    const [listPayload, statsPayload] = await Promise.all([
      fetchJson<{ items?: Row[]; total?: number }>(`${ENDPOINT}?${query.toString()}`),
      fetchJson<{ stats?: StatItem[] }>(`${ENDPOINT}/stats`),
    ])
    rows.value = listPayload.items ?? []
    total.value = listPayload.total ?? rows.value.length
    stats.value = statsPayload.stats ?? []
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '道具管理列表读取失败'
  }
}

async function loadMeta() {
  try {
    const meta = await fetchJson<{ statuses?: string[] }>(`${ENDPOINT}/meta`)
    statuses.value = meta.statuses ?? []
  } catch {
    statuses.value = []
  }
}

onMounted(() => {
  void loadMeta()
  void reload()
})
</script>
