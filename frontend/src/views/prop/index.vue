<template>
  <section class="page" data-module="prop">
    <header class="page-head">
      <div>
        <h2>道具管理管理</h2>
        <p class="page-desc">维护道具，围绕道具编号、道具名称、道具类别、所属场次做登记、筛选与借出/归还/损毁流转。</p>
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
        <input v-model="keyword" placeholder="按道具编号检索" />
      </label>
      <label class="filter-item">
        <span>使用状态</span>
        <select v-model="statusFilter">
          <option value="">全部</option>
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
          <td v-for="column in columns" :key="column">{{ row[column] || '—' }}</td>
          <td class="row-actions">
            <template v-if="allowedActions(row).length">
              <button
                v-for="action in allowedActions(row)"
                :key="action"
                class="link"
                type="button"
                :disabled="actingId === row.id"
                @click="runAction(action, row)"
              >
                {{ action }}
              </button>
            </template>
            <span v-else class="page-desc">终态，无可用动作</span>
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

import { request } from '@/api/client'

type Row = Record<string, string | number | boolean | string[] | null>

const ENDPOINT = '/api/prop'
// 库存口径（在库/已借出/已归还/已损毁）以后端 /meta 下发为准，页面不再自维护一份。
const columns = ['道具编号', '道具名称', '道具类别', '所属场次', '保管人员', '采购单价', '使用状态', '归还日期']

const rows = ref<Row[]>([])
const total = ref(0)
const stats = ref<{ label: string, value: number }[]>([])
const statuses = ref<string[]>([])
const errorMessage = ref('')
const keyword = ref('')
const statusFilter = ref('')
const actingId = ref<number | string | null>(null)

function allowedActions(row: Row): string[] {
  const actions = row.actions
  return Array.isArray(actions) ? (actions as string[]) : []
}

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
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
  actingId.value = row.id as number
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok) {
      // HTTP 层错误（如 404/400）：展示后端 detail，而不是泛化的“操作失败”。
      throw new Error(payload?.detail ?? `动作被拒绝（HTTP ${response.status}）`)
    }
    if (!payload?.ok) {
      // 业务层拦截（非法流转）：必须把后端原因展示出来，避免“点了没反应/无法归还”。
      throw new Error(payload?.message ?? '动作未生效，请刷新后核对库存状态')
    }
    await Promise.all([reload(), loadStats()])
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '道具管理操作失败'
  } finally {
    actingId.value = null
  }
}

async function loadMeta() {
  const response = await request(`${ENDPOINT}/meta`)
  if (!response.ok) {
    throw new Error(`道具规则读取失败（HTTP ${response.status}）`)
  }
  const payload = await response.json()
  statuses.value = payload.statuses ?? []
}

async function loadStats() {
  const response = await request(`${ENDPOINT}/stats`)
  if (!response.ok) {
    return
  }
  const payload = await response.json()
  stats.value = payload.cards ?? []
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (keyword.value.trim()) {
    query.set('keyword', keyword.value.trim())
  }
  if (statusFilter.value) {
    query.set('status', statusFilter.value)
  }
  const suffix = query.toString() ? `?${query.toString()}` : ''
  try {
    const response = await request(`${ENDPOINT}${suffix}`)
    if (!response.ok) {
      throw new Error('道具列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '道具管理列表读取失败'
  }
}

onMounted(() => {
  void Promise.all([loadMeta(), loadStats(), reload()]).catch((error: unknown) => {
    errorMessage.value = error instanceof Error ? error.message : '道具页面初始化失败'
  })
})
</script>
