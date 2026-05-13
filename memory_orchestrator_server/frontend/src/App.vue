<template>
  <div class="app">
    <header class="app-header">
      <div class="logo">
        <svg width="18" height="18" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <linearGradient id="mo-logo-bg" x1="4" y1="3" x2="28" y2="29" gradientUnits="userSpaceOnUse">
              <stop stop-color="#0f172a"/>
              <stop offset="1" stop-color="#1d4ed8"/>
            </linearGradient>
            <linearGradient id="mo-logo-line" x1="8" y1="8" x2="24" y2="24" gradientUnits="userSpaceOnUse">
              <stop stop-color="#67e8f9"/>
              <stop offset="1" stop-color="#a7f3d0"/>
            </linearGradient>
          </defs>
          <rect x="1" y="1" width="30" height="30" rx="7" fill="url(#mo-logo-bg)"/>
          <path d="M8 11.5H12.2L15.5 8.5H20.5" stroke="url(#mo-logo-line)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          <path d="M8 20.5H12.2L15.5 23.5H24" stroke="url(#mo-logo-line)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          <path d="M11 16H21" stroke="#93c5fd" stroke-width="2" stroke-linecap="round"/>
          <path d="M20.5 8.5L24 12V20.5" stroke="#60a5fa" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          <circle cx="8" cy="11.5" r="2" fill="#22d3ee"/>
          <circle cx="8" cy="20.5" r="2" fill="#22d3ee"/>
          <circle cx="11" cy="16" r="2.3" fill="#bfdbfe"/>
          <circle cx="21" cy="16" r="2.3" fill="#bfdbfe"/>
          <circle cx="24" cy="12" r="2" fill="#34d399"/>
          <circle cx="24" cy="20.5" r="2" fill="#34d399"/>
        </svg>
        <h1>Memory Orchestrator</h1>
      </div>
      <div class="stats-row" v-if="stats">
        <span class="stat-sep">·</span>
        <span class="stat-total">{{ t('{n} total', {n: stats.total}) }}</span>
        <span v-for="(v, k) in stats.by_type" :key="k" :class="['badge', k]">
          <span class="badge-dot"></span>{{ k }} <strong>{{ v }}</strong>
        </span>
      </div>
      <div class="header-spacer"></div>
      <div class="header-actions">
        <button @click="toggleTheme" class="btn-theme" :title="isDark ? t('Switch to light') : t('Switch to dark')">
          <svg v-if="isDark" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
            <circle cx="12" cy="12" r="4"/><line x1="12" y1="2" x2="12" y2="5"/><line x1="12" y1="19" x2="12" y2="22"/>
            <line x1="4.22" y1="4.22" x2="6.34" y2="6.34"/><line x1="17.66" y1="17.66" x2="19.78" y2="19.78"/>
            <line x1="2" y1="12" x2="5" y2="12"/><line x1="19" y1="12" x2="22" y2="12"/>
            <line x1="4.22" y1="19.78" x2="6.34" y2="17.66"/><line x1="17.66" y1="6.34" x2="19.78" y2="4.22"/>
          </svg>
          <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
          </svg>
        </button>
        <button @click="toggleLang" class="btn-theme" :title="lang === 'en' ? '切换中文' : 'Switch to English'">
          <span style="font-size:11px;font-weight:600;letter-spacing:0">{{ lang === 'en' ? '中' : 'EN' }}</span>
        </button>
        <button @click="openSettings" class="btn-theme" :title="t('Settings')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="3"/>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
          </svg>
        </button>
        <button v-if="!loginOpen" @click="openAdmin" class="btn-theme btn-admin" :title="t('Admin')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
          </svg>
        </button>
        <button v-if="!loginOpen" @click="logout" class="btn-theme btn-logout" :title="t('Logout')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>
          </svg>
        </button>
        <button @click="load" class="btn-refresh" :class="{ loading: isLoading }" :title="t('Refresh')">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" :class="{ spinning: isLoading }">
            <path d="M13 7A6 6 0 1 1 7 1a6 6 0 0 1 4.243 1.757L13 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            <path d="M9 4h4V0" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          {{ t('Refresh') }}
        </button>
      </div>
    </header>

    <div class="toolbar">
      <div class="filter-bar">
        <div class="filter-project-wrap">
          <span class="filter-at">@</span>
          <select class="project-select" v-model="selectedProject" @change="load()">
            <option value="">{{ t('All') }}</option>
            <option v-for="p in projects" :key="p.id" :value="p.slug" :title="p.slug">
              {{ p.display_name || p.slug }}
            </option>
          </select>
        </div>
        <span class="filter-sep-v"></span>
        <div class="type-tabs">
          <button :class="['type-tab', selectedType === '' ? 'active' : '']" @click="selectedType = ''; load()">{{ t('All') }}</button>
          <button v-for="tp in ['user','feedback','project','reference']" :key="tp"
            :class="['type-tab', 'type-tab-' + tp, selectedType === tp ? 'active' : '']"
            @click="selectedType = tp; load()">{{ t(tp) }}</button>
        </div>
      </div>
      <div class="toolbar-right">
        <button @click="openDuplicates" class="btn-toolbar-action" :title="t('Duplicates')">
          <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
            <rect x="1" y="1" width="5" height="5" rx="1" stroke="currentColor" stroke-width="1.3"/>
            <rect x="5" y="5" width="5" height="5" rx="1" stroke="currentColor" stroke-width="1.3"/>
          </svg>
          {{ t('Duplicates') }}
        </button>
        <button @click="openConflicts" class="btn-toolbar-action" :title="t('Conflicts')">
          <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
            <path d="M1 10L10 1" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
            <path d="M3 1H1V3" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M8 10H10V8" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          {{ t('Conflicts') }}
        </button>
        <input ref="importFileRef" type="file" accept=".sql" style="display:none" @change="onImportFile" />
        <div class="search-wrap">
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
            <circle cx="5.5" cy="5.5" r="4" stroke="#6e7681" stroke-width="1.3"/>
            <line x1="8.5" y1="8.5" x2="12" y2="12" stroke="#6e7681" stroke-width="1.3" stroke-linecap="round"/>
          </svg>
          <input v-model="searchText" :placeholder="t('Search…')" class="search-input" />
        </div>
        <button v-if="selectedProject || selectedType || searchText" @click="resetFilters" class="btn-reset" :title="t('Reset')">
          <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
            <line x1="1" y1="1" x2="10" y2="10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            <line x1="10" y1="1" x2="1" y2="10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
          {{ t('Reset') }}
        </button>
        <span class="toolbar-sep"></span>
        <button @click="openWrite" class="btn-new" :title="t('New memory') + ' (N)'">
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <line x1="6" y1="1" x2="6" y2="11" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
            <line x1="1" y1="6" x2="11" y2="6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
          </svg>
          {{ t('New') }}
        </button>
      </div>
    </div>

    <div class="table-wrap">
      <table>
        <colgroup>
          <col style="width:36px">
          <col style="width:36px">
          <col style="width:180px">
          <col style="width:90px">
          <col style="width:160px">
          <col>
          <col style="width:64px">
          <col style="width:96px">
          <col style="width:80px">
        </colgroup>
        <thead>
          <tr>
            <th class="col-check" :class="{ 'has-selection': selectedIds.size > 0 }">
              <input type="checkbox" class="row-check" ref="selectAllRef"
                :checked="allSelected" @change="toggleSelectAll" />
            </th>
            <th class="source-col" :title="t('Source')"></th>
            <!-- project: folder icon -->
            <th><span class="th-inner"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>{{ t('Project') }}</span></th>
            <th class="type-col"><span class="th-inner"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>{{ t('Type') }}</span></th>
            <th><span class="th-inner"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>{{ t('Name') }}</span></th>
            <!-- description: align-left icon -->
            <th><span class="th-inner"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="17" y1="10" x2="3" y2="10"/><line x1="21" y1="6" x2="3" y2="6"/><line x1="21" y1="14" x2="3" y2="14"/><line x1="17" y1="18" x2="3" y2="18"/></svg>{{ t('Description') }}</span></th>
            <th class="sortable col-hits" @click="toggleSort('hits')">
              <span class="th-inner"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>{{ t('Hits') }}<span class="sort-icon" v-if="sortBy === 'hits'">{{ sortDesc ? '↓' : '↑' }}</span></span>
            </th>
            <th class="sortable col-updated" @click="toggleSort('time')">
              <span class="th-inner"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>{{ t('Updated') }}<span class="sort-icon" v-if="sortBy === 'time'">{{ sortDesc ? '↓' : '↑' }}</span></span>
            </th>
            <th class="col-actions"></th>
          </tr>
        </thead>
        <tbody>
          <template v-for="m in paged" :key="m.id">
            <tr @click="openDetail(m)" :class="['type-' + m.type, { active: detailTarget?.id === m.id, selected: selectedIds.has(m.id) }]">
              <td class="col-check" @click.stop>
                <input type="checkbox" class="row-check" :checked="selectedIds.has(m.id)" @change="toggleSelect(m.id)" />
              </td>
              <td class="source-col">
                <span :class="['source-badge', sourceClass(m.source_client)]" @mouseenter="showTip($event, sourceLabel(m.source_client))" @mouseleave="hideTip">
                  <img class="source-icon" :src="sourceIconUrl(m.source_client)" :alt="sourceLabel(m.source_client)" />
                </span>
              </td>
              <td class="project-cell" @mouseenter="showTip($event, projectDisplayName(m.project_id) || '—')" @mouseleave="hideTip">
                <span v-if="projectDisplayName(m.project_id)" class="plain-cell-text">{{ projectCellText(m.project_id) }}</span>
                <span v-else class="hit-zero">—</span>
              </td>
              <td class="type-col"><span :class="['tag', m.type]">{{ t(m.type) }}</span></td>
              <td class="name" @mouseenter="showTip($event, m.name)" @mouseleave="hideTip">{{ m.name }}</td>
              <td><div class="desc" @mouseenter="showTip($event, m.description)" @mouseleave="hideTip">{{ m.description }}</div></td>
              <td class="hit col-hits" :class="{ 'hit-active': m.hit_count > 0 }">
                <span v-if="m.hit_count > 0" class="hit-num">{{ m.hit_count }}</span>
                <span v-else class="hit-zero">—</span>
              </td>
              <td class="date col-updated"><span :title="fmtDate(m.updated_at)">{{ relTime(m.updated_at) }}</span></td>
              <td class="col-actions">
                <div class="row-actions">
                  <button class="btn-edit-quick" @click.stop="openEdit(m)" :title="t('Edit')" :aria-label="t('Edit')">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                    </svg>
                  </button>
                  <button class="btn-clone-quick" @click.stop="openClone(m)" :title="t('Clone')" :aria-label="t('Clone')">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                      <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                    </svg>
                  </button>
                  <button class="btn-del" @click.stop="del(m)" :title="t('Delete')" :aria-label="t('Delete')">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                      <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
                    </svg>
                  </button>

                </div>
              </td>
            </tr>
          </template>
          <tr v-if="paged.length === 0">
            <td colspan="9" class="empty">
              <div class="empty-inner">
                <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round" opacity="0.25">
                  <ellipse cx="12" cy="5" rx="9" ry="3"/>
                  <path d="M3 5v4c0 1.66 4.03 3 9 3s9-1.34 9-3V5"/>
                  <path d="M3 9v4c0 1.66 4.03 3 9 3s9-1.34 9-3V9"/>
                  <path d="M3 13v4c0 1.66 4.03 3 9 3s9-1.34 9-3v-4"/>
                </svg>
                <span>{{ searchText || selectedType || selectedProject ? t('No memories match the current filters') : t('No memories yet — start a Claude Code session to capture some') }}</span>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="footer" v-if="filtered.length > 0">
      <div class="pagination">
        <button class="page-btn" :disabled="page === 1" @click="page = 1">«</button>
        <button class="page-btn" :disabled="page === 1" @click="page--">‹</button>
        <span class="page-info">{{ t('Page {p} / {t} · {n} total', {p: page, t: totalPages, n: filtered.length}) }}</span>
        <button class="page-btn" :disabled="page === totalPages" @click="page++">›</button>
        <button class="page-btn" :disabled="page === totalPages" @click="page = totalPages">»</button>
        <select class="page-size-select" v-model="pageSize">
          <option :value="20">{{ t('{n} / page', {n: 20}) }}</option>
          <option :value="50">{{ t('{n} / page', {n: 50}) }}</option>
          <option :value="100">{{ t('{n} / page', {n: 100}) }}</option>
        </select>
      </div>
    </div>
  </div>
  <Teleport to="body">
    <div v-if="tip.visible" class="tooltip-popup" :style="{ left: tip.x + 'px', top: tip.y + 'px' }">{{ tip.text }}</div>

    <!-- ── API Tokens modal ── -->
    <div v-if="adminOpen" class="modal-overlay" @click.self="adminOpen = false">
      <div class="modal admin-modal">
        <div class="modal-header">
          <span class="modal-title">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" style="margin-right:6px;vertical-align:-2px"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
            {{ t('API Tokens') }}
          </span>
          <div style="display:flex;align-items:center;gap:8px">
            <button class="btn-new admin-create-toggle" @click="adminCreateOpen = !adminCreateOpen">
              <svg width="11" height="11" viewBox="0 0 12 12" fill="none"><line x1="6" y1="1" x2="6" y2="11" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><line x1="1" y1="6" x2="11" y2="6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
              {{ t('New') }}
            </button>
            <button class="modal-close" @click="adminOpen = false">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <line x1="1" y1="1" x2="11" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                <line x1="11" y1="1" x2="1" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              </svg>
            </button>
          </div>
        </div>

        <div class="admin-modal-body">
          <div v-if="adminCreateOpen" class="admin-create-form">
            <select v-model="adminNewKind" class="admin-select">
              <option value="ui_admin">ui_admin</option>
              <option value="mcp_client">mcp_client</option>
            </select>
            <input v-model="adminNewName" class="admin-input" :placeholder="t('Name…')" @keydown.enter="adminCreate" />
            <button class="btn-save admin-create-btn" :disabled="!adminNewName || adminCreating" @click="adminCreate">
              {{ adminCreating ? t('Saving…') : t('Create') }}
            </button>
            <button class="btn-cancel" @click="adminCreateOpen = false">{{ t('Cancel') }}</button>
          </div>

          <div v-if="adminCreatedToken" class="admin-new-token-banner">
            <span class="admin-new-token-label">{{ t('Token value (save this — shown only once):') }}</span>
            <code class="admin-new-token-value copyable" @click="copy(adminCreatedToken)" :title="t('Click to copy')">{{ adminCreatedToken }}</code>
            <span class="copy-hint" v-if="copied === adminCreatedToken">{{ t('Copied') }}</span>
            <button class="btn-cancel admin-dismiss" @click="adminCreatedToken = ''">{{ t('Close') }}</button>
          </div>

          <div v-if="adminLoading" class="admin-empty">{{ t('Loading…') }}</div>
          <div v-else-if="!adminTokens.length" class="admin-empty">{{ t('No tokens yet.') }}</div>
          <table v-else class="admin-table">
            <thead>
              <tr>
                <th>{{ t('Kind') }}</th>
                <th>{{ t('Name') }}</th>
                <th>{{ t('Status') }}</th>
                <th>{{ t('Created') }}</th>
                <th>{{ t('Last used') }}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="tok in adminTokens" :key="tok.id" :class="{ 'admin-row-disabled': !tok.enabled }">
                <td><span :class="['admin-kind-badge', tok.kind === 'ui_admin' ? 'admin-kind-ui' : 'admin-kind-mcp']">{{ tok.kind }}</span></td>
                <td class="admin-name-cell">{{ tok.name }}</td>
                <td>
                  <button
                    :class="['admin-toggle', tok.enabled ? 'admin-toggle-on' : 'admin-toggle-off']"
                    @click="adminToggle(tok)"
                    :title="tok.enabled ? t('Disable') : t('Enable')"
                  >
                    <span class="admin-toggle-knob"></span>
                  </button>
                  <span class="admin-status-text">{{ tok.enabled ? t('Enabled') : t('Disabled') }}</span>
                </td>
                <td class="admin-date">{{ relTime(tok.created_at) }}</td>
                <td class="admin-date">{{ tok.last_used_at ? relTime(tok.last_used_at) : '—' }}</td>
                <td class="admin-actions-cell">
                  <button class="btn-cancel admin-reset" @click="openTokenAction(tok, 'reset')" :title="t('Reset')">
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.5 9a9 9 0 0 1 14.9-3.4L23 10"/><path d="M20.5 15a9 9 0 0 1-14.9 3.4L1 14"/></svg>
                    {{ t('Reset') }}
                  </button>
                  <button class="btn-token-revoke admin-revoke" @click="openTokenAction(tok, 'revoke')" :title="t('Revoke')">
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>
                    {{ t('Revoke') }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div v-if="loginOpen" class="modal-overlay login-overlay">
      <div class="login-modal">
        <div class="login-logo">
          <svg width="28" height="28" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <linearGradient id="ll-bg" x1="4" y1="3" x2="28" y2="29" gradientUnits="userSpaceOnUse">
                <stop stop-color="#0f172a"/><stop offset="1" stop-color="#1d4ed8"/>
              </linearGradient>
              <linearGradient id="ll-line" x1="8" y1="8" x2="24" y2="24" gradientUnits="userSpaceOnUse">
                <stop stop-color="#67e8f9"/><stop offset="1" stop-color="#a7f3d0"/>
              </linearGradient>
            </defs>
            <rect x="1" y="1" width="30" height="30" rx="7" fill="url(#ll-bg)"/>
            <path d="M8 11.5H12.2L15.5 8.5H20.5" stroke="url(#ll-line)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M8 20.5H12.2L15.5 23.5H24" stroke="url(#ll-line)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M11 16H21" stroke="#93c5fd" stroke-width="2" stroke-linecap="round"/>
            <path d="M20.5 8.5L24 12V20.5" stroke="#60a5fa" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <circle cx="8" cy="11.5" r="2" fill="#22d3ee"/>
            <circle cx="8" cy="20.5" r="2" fill="#22d3ee"/>
            <circle cx="11" cy="16" r="2.3" fill="#bfdbfe"/>
            <circle cx="21" cy="16" r="2.3" fill="#bfdbfe"/>
            <circle cx="24" cy="12" r="2" fill="#34d399"/>
            <circle cx="24" cy="20.5" r="2" fill="#34d399"/>
          </svg>
          <span class="login-title">Memory Orchestrator</span>
        </div>
        <p class="login-subtitle">{{ t('Enter your UI admin token to continue') }}</p>
        <form class="login-form" @submit.prevent="submitLogin">
          <input
            ref="loginInputRef"
            v-model="loginInput"
            class="login-input"
            type="password"
            :placeholder="t('Paste token here…')"
            autocomplete="current-password"
            autofocus
          />
          <div v-if="loginError" class="login-error">{{ loginError }}</div>
          <div class="login-actions">
            <button class="login-btn" type="submit" :disabled="!loginInput || loginLoading">
              <svg v-if="loginLoading" width="13" height="13" viewBox="0 0 13 13" fill="none" class="spinning">
                <circle cx="6.5" cy="6.5" r="5" stroke="currentColor" stroke-width="1.5" stroke-dasharray="8 16" stroke-linecap="round"/>
              </svg>
              <svg v-else width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>
              </svg>
              {{ t('Sign in') }}
            </button>
          </div>
        </form>
      </div>
    </div>
    <div v-if="detailTarget" class="modal-overlay" @click.self="detailTarget = null">
      <div class="detail-modal">
        <div :class="['write-header', 'type-header-' + detailTarget.type]">
          <div style="display:flex;align-items:center;gap:8px;">
            <span :class="['tag', detailTarget.type]" style="font-size:10px;padding:1px 6px">{{ t(detailTarget.type) }}</span>
            <span class="write-title">{{ t('Memory Details') }}</span>
          </div>
          <div class="write-header-right">
            <button class="btn-header-edit" @click="openEdit(detailTarget); detailTarget = null" :title="t('Edit')">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
              </svg>
            </button>
            <button class="modal-close" @click="detailTarget = null">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <line x1="1" y1="1" x2="11" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                <line x1="11" y1="1" x2="1" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              </svg>
            </button>
          </div>
        </div>
        <div class="detail-modal-body">
          <div class="detail-hero">
            <div class="detail-hero-name">{{ detailTarget.name }}</div>
            <div v-if="detailTarget.description" class="detail-hero-desc">{{ detailTarget.description }}</div>
          </div>
          <div class="content-block">
            <div class="block-label">{{ t('Content') }}</div>
            <div class="md-body" v-html="md(detailTarget.content)"></div>
          </div>
          <div v-if="detailTarget.why" class="content-block">
            <div class="block-label">{{ t('Why') }}</div>
            <div class="md-body" v-html="md(detailTarget.why)"></div>
          </div>
          <div v-if="detailTarget.how_to_apply" class="content-block">
            <div class="block-label">{{ t('How to Apply') }}</div>
            <div class="md-body" v-html="md(detailTarget.how_to_apply)"></div>
          </div>
          <div class="meta-strip">
            <span class="meta-item"><strong>{{ sourceLabel(detailTarget.source_client) }}</strong></span>
            <span class="meta-sep">·</span>
            <span class="meta-item">{{ t('Hits') }} <strong>{{ detailTarget.hit_count }}</strong></span>
            <template v-if="detailTarget.last_hit_at">
              <span class="meta-sep">·</span>
              <span class="meta-item">{{ fmtDateTime(detailTarget.last_hit_at) }}</span>
            </template>
          </div>
          <details class="meta-ids">
            <summary class="meta-ids-toggle">IDs</summary>
            <div class="meta-ids-body">
              <span class="meta-item">
                ID: <code class="copyable" @click.stop="copy(detailTarget.id)" :title="t('Click to copy')">{{ detailTarget.id }}</code>
                <span class="copy-hint" v-if="copied === detailTarget.id">{{ t('Copied') }}</span>
              </span>
              <span class="meta-sep">·</span>
              <span class="meta-item">
                Project: <code class="copyable" @click.stop="copy(detailTarget.project_id)" :title="t('Click to copy')">{{ detailTarget.project_id }}</code>
                <span class="copy-hint" v-if="copied === detailTarget.project_id">{{ t('Copied') }}</span>
              </span>
            </div>
          </details>
        </div>
      </div>
    </div>
    <div v-if="settingsOpen" class="modal-overlay">
      <div class="modal">
        <div class="modal-header">
          <span class="modal-title">{{ t('Advanced') }}</span>
          <button class="modal-close" @click="settingsOpen = false">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <line x1="1" y1="1" x2="11" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              <line x1="11" y1="1" x2="1" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
          </button>
        </div>
        <div class="settings-tabs">
          <button :class="['settings-tab', {active: settingsTab === 'settings'}]" @click="settingsTab = 'settings'">{{ t('Settings') }}</button>
          <button :class="['settings-tab', {active: settingsTab === 'scoring'}]" @click="settingsTab = 'scoring'">{{ t('Scoring') }}</button>
          <button :class="['settings-tab', {active: settingsTab === 'backup'}]" @click="settingsTab = 'backup'">{{ t('Backup') }}</button>
        </div>
        <div v-if="settingsTab === 'settings'" class="modal-body">
          <div class="settings-group">
            <div class="settings-group-title">{{ t('Extraction Model') }}</div>
            <label class="field-row">
              <span class="field-label" @mouseenter="showTip($event, t('OpenAI-compatible API base URL'))" @mouseleave="hideTip">{{ t('Base URL') }}</span>
              <input v-model="form.extraction_base_url" class="field-input" placeholder="https://api.openai.com/v1" />
            </label>
            <label class="field-row">
              <span class="field-label" @mouseenter="showTip($event, t('API key for the extraction model endpoint'))" @mouseleave="hideTip">{{ t('API Key') }}</span>
              <input v-model="form.extraction_api_key" class="field-input" type="password" :placeholder="form.extraction_api_key === KEY_SENTINEL ? t('●●●●●● (saved — leave to keep)') : t('sk-… (enter to set)')" />
            </label>
            <label class="field-row">
              <span class="field-label" @mouseenter="showTip($event, t('Model name used to extract memories from session transcripts'))" @mouseleave="hideTip">{{ t('Model') }}</span>
              <div class="combobox-wrap">
                <input
                  v-model="form.extraction_model"
                  class="field-input combobox-input"
                  placeholder="gpt-4o-mini"
                  autocomplete="off"
                  @focus="onModelFocus"
                  @blur="onModelBlur"
                  @input="modelHighlight = -1"
                  @keydown="onModelKeydown"
                />
                <svg v-if="availableModels.length" class="combobox-chevron" :class="{open: modelDropOpen}" width="10" height="10" viewBox="0 0 10 10" fill="none">
                  <path d="M2 3.5L5 6.5L8 3.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                <div v-if="modelDropOpen && modelFilteredList.length" class="combobox-dropdown">
                  <div
                    v-for="(m, i) in modelFilteredList" :key="m"
                    :class="['combobox-option', {highlighted: i === modelHighlight, selected: m === form.extraction_model}]"
                    @mousedown.prevent="selectModel(m)"
                  >
                    <span class="combobox-check">
                      <svg v-if="m === form.extraction_model" width="11" height="11" viewBox="0 0 11 11" fill="none">
                        <path d="M1.5 5.5L4.5 8.5L9.5 2.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                      </svg>
                    </span>
                    {{ m }}
                  </div>
                </div>
              </div>
              <button class="btn-fetch-models" @click.prevent="fetchModels" :disabled="!form.extraction_base_url || isFetchingModels" type="button" :title="t('Model')">
                <svg v-if="!isFetchingModels" width="11" height="11" viewBox="0 0 11 11" fill="none">
                  <path d="M10 5.5A4.5 4.5 0 1 1 5.5 1" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
                  <path d="M7 1h3v3" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                <svg v-else width="11" height="11" viewBox="0 0 11 11" fill="none" class="spinning">
                  <circle cx="5.5" cy="5.5" r="4" stroke="currentColor" stroke-width="1.4" stroke-dasharray="6 14" stroke-linecap="round"/>
                </svg>
              </button>
            </label>
          </div>
          <div class="settings-group">
            <div class="settings-group-title">{{ t('Hooks') }}</div>
            <label class="field-row">
              <span class="field-label" @mouseenter="showTip($event, t('Minimum seconds between two ingest triggers for the same session'))" @mouseleave="hideTip">{{ t('Ingest cooldown') }}</span>
              <input v-model="form.hook_cooldown_sec" class="field-input" :placeholder="t('300 (seconds)')" />
            </label>
            <label class="field-row">
              <span class="field-label" @mouseenter="showTip($event, t('Minimum number of new user turns required to trigger ingest'))" @mouseleave="hideTip">{{ t('Min turns') }}</span>
              <input v-model="form.hook_min_turns" class="field-input" placeholder="1" />
            </label>
            <label class="field-row">
              <span class="field-label" @mouseenter="showTip($event, t('Max tokens of memory context injected into each prompt via the UserPromptSubmit hook'))" @mouseleave="hideTip">{{ t('Context tokens') }}</span>
              <input v-model="form.hook_budget_tokens" class="field-input" placeholder="1500" />
            </label>
          </div>
          <div class="settings-group">
            <div class="settings-group-title">{{ t('MCP / Service') }}</div>
            <label class="field-row">
              <span class="field-label" @mouseenter="showTip($event, t('Default number of memories returned by search_memory when top_k is not specified by the caller'))" @mouseleave="hideTip">{{ t('Search top_k') }}</span>
              <input v-model="form.search_top_k" class="field-input" placeholder="3" />
            </label>
            <label class="field-row">
              <span class="field-label" @mouseenter="showTip($event, t('Cosine similarity threshold (0–1) above which an existing memory is considered a duplicate on save'))" @mouseleave="hideTip">{{ t('Dup threshold') }}</span>
              <input v-model="form.dup_threshold" class="field-input" placeholder="0.92" />
            </label>
          </div>
        </div>
        <div v-else-if="settingsTab === 'scoring'" class="modal-body scoring-body">
          <!-- Hybrid Score Weights -->
          <div class="settings-group">
            <div class="settings-group-title">
              {{ t('Hybrid Score Weights') }}
              <span class="weight-sum-badge" :class="weightSumOk ? 'ok' : 'err'">Σ = {{ weightSum }}</span>
            </div>
            <div class="score-row">
              <span class="score-lbl">{{ t('Cosine') }}</span>
              <input type="range" min="0" max="1" step="0.01" v-model="form.score_cosine_weight" class="score-slider" />
              <input type="number" min="0" max="1" step="0.01" v-model="form.score_cosine_weight" class="score-num" />
            </div>
            <div class="score-row">
              <span class="score-lbl">{{ t('Importance') }}</span>
              <input type="range" min="0" max="1" step="0.01" v-model="form.score_importance_weight" class="score-slider" />
              <input type="number" min="0" max="1" step="0.01" v-model="form.score_importance_weight" class="score-num" />
            </div>
            <div class="score-row">
              <span class="score-lbl">{{ t('Recency') }}</span>
              <input type="range" min="0" max="1" step="0.01" v-model="form.score_recency_weight" class="score-slider" />
              <input type="number" min="0" max="1" step="0.01" v-model="form.score_recency_weight" class="score-num" />
            </div>
            <div class="weight-bar">
              <div class="wb-seg wb-cosine" :style="{flex: wf('score_cosine_weight', 0.6)}">
                <span v-if="wf('score_cosine_weight', 0.6) >= 0.14">{{ t('Cosine') }}</span>
              </div>
              <div class="wb-seg wb-importance" :style="{flex: wf('score_importance_weight', 0.3)}">
                <span v-if="wf('score_importance_weight', 0.3) >= 0.10">{{ t('Imp.') }}</span>
              </div>
              <div class="wb-seg wb-recency" :style="{flex: wf('score_recency_weight', 0.1)}">
                <span v-if="wf('score_recency_weight', 0.1) >= 0.07">{{ t('Rec.') }}</span>
              </div>
            </div>
            <div v-if="!weightSumOk" class="score-warn">
              ⚠ {{ t('Weights should sum to 1.0') }} ({{ t('current') }}: {{ weightSum }})
            </div>
          </div>

          <!-- Recency Decay -->
          <div class="settings-group">
            <div class="settings-group-title">{{ t('Recency Decay') }}</div>
            <div class="score-row">
              <span class="score-lbl">{{ t('Half-life (days)') }}</span>
              <input type="range" min="1" max="365" step="1" v-model="form.score_recency_half_life" class="score-slider" />
              <input type="number" min="1" max="365" step="1" v-model="form.score_recency_half_life" class="score-num" />
            </div>
            <div class="score-hint">30d → {{ decayPct(30) }}% &nbsp;·&nbsp; 60d → {{ decayPct(60) }}% &nbsp;·&nbsp; 180d → {{ decayPct(180) }}%</div>
          </div>

          <!-- Type Multipliers -->
          <div class="settings-group">
            <div class="settings-group-title">{{ t('Type Multipliers') }}</div>
            <div v-for="tp in ['feedback','project','user','reference']" :key="tp" class="score-row">
              <span class="score-lbl type-lbl">{{ t(tp) }}</span>
              <div class="type-bar-track">
                <div class="type-bar-fill" :style="{width: typeBarPct(form['score_type_' + tp])}"></div>
              </div>
              <input type="number" min="0.1" max="3" step="0.1" v-model="form['score_type_' + tp]" class="score-num" />
            </div>
            <div class="score-hint">{{ t('1.0 = neutral · >1.0 boosts rank · <1.0 reduces rank') }}</div>
          </div>

          <!-- Reranker -->
          <div class="settings-group">
            <div class="settings-group-title">{{ t('Reranker') }}</div>
            <div class="score-row">
              <span class="score-lbl">{{ t('Enabled') }}</span>
              <label class="score-toggle">
                <input type="checkbox" :checked="form.rerank_enabled === 'true'" @change="form.rerank_enabled = $event.target.checked ? 'true' : 'false'" />
                <span class="score-toggle-track"><span class="score-toggle-thumb"></span></span>
              </label>
              <span class="score-toggle-state">{{ form.rerank_enabled === 'true' ? t('On') : t('Off') }}</span>
            </div>
            <div class="score-row" :class="{dimmed: form.rerank_enabled !== 'true'}">
              <span class="score-lbl">{{ t('Blend ratio') }}</span>
              <input type="range" min="0" max="1" step="0.05" v-model="form.score_rerank_blend" class="score-slider" :disabled="form.rerank_enabled !== 'true'" />
              <input type="number" min="0" max="1" step="0.05" v-model="form.score_rerank_blend" class="score-num" :disabled="form.rerank_enabled !== 'true'" />
            </div>
            <div class="score-hint" v-if="form.rerank_enabled === 'true'">
              final = {{ blendFmt }}×{{ t('reranker') }} + {{ counterBlendFmt }}×{{ t('hybrid') }}
            </div>
          </div>

          <!-- Graph -->
          <div class="settings-group">
            <div class="settings-group-title">{{ t('Graph') }}</div>
            <div class="score-row">
              <span class="score-lbl">{{ t('Graph enabled') }}</span>
              <label class="score-toggle">
                <input type="checkbox" :checked="form.graph_enabled === 'true'" @change="form.graph_enabled = $event.target.checked ? 'true' : 'false'" />
                <span class="score-toggle-track"><span class="score-toggle-thumb"></span></span>
              </label>
              <span class="score-toggle-state">{{ form.graph_enabled === 'true' ? t('On') : t('Off') }}</span>
            </div>
            <div class="score-row" :class="{dimmed: form.graph_enabled !== 'true'}">
              <span class="score-lbl">{{ t('Hop depth') }}</span>
              <input type="range" min="1" max="5" step="1" v-model="form.graph_hop_depth" class="score-slider" :disabled="form.graph_enabled !== 'true'" />
              <input type="number" min="1" max="5" step="1" v-model="form.graph_hop_depth" class="score-num" :disabled="form.graph_enabled !== 'true'" />
            </div>
          </div>
        </div>
        <div v-else class="modal-body backup-tab-body">
          <div class="settings-group">
            <div class="settings-group-title">{{ t('Export') }}</div>
            <p class="backup-desc">{{ t('Download a full SQL backup of the database (pg_dump).') }}</p>
            <button class="btn-save backup-action-btn" @click="exportMemories(); settingsOpen = false">
              <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
                <path d="M5.5 1v6.5M2.5 5l3 3 3-3" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
                <line x1="1.5" y1="9.5" x2="9.5" y2="9.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
              </svg>
              {{ t('Download Backup') }}
            </button>
          </div>
          <div class="settings-group">
            <div class="settings-group-title">{{ t('Restore') }}</div>
            <p class="backup-desc">{{ t('Upload a .sql file to restore the database. Existing data will be overwritten.') }}</p>
            <button class="btn-save backup-action-btn" @click="openImport()">
              <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
                <path d="M5.5 7.5V1M2.5 4l3-3 3 3" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
                <line x1="1.5" y1="9.5" x2="9.5" y2="9.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
              </svg>
              {{ t('Select .sql file…') }}
            </button>
          </div>
        </div>
        <div class="modal-footer">
          <template v-if="settingsTab === 'settings'">
            <span :class="['save-hint', saveHint.startsWith('Error') ? 'err' : 'ok']" v-if="saveHint">{{ saveHint }}</span>
            <button class="btn-cancel" @click="settingsOpen = false">{{ t('Cancel') }}</button>
            <button class="btn-save" @click="saveSettings" :disabled="isSaving">{{ isSaving ? t('Saving…') : t('Save') }}</button>
          </template>
          <template v-else>
            <button class="btn-cancel" @click="settingsOpen = false">{{ t('Close') }}</button>
          </template>
        </div>
      </div>
    </div>
    <div v-if="deleteTarget" class="modal-overlay">
      <div class="modal modal-sm">
        <div class="modal-header">
          <span class="modal-title">{{ t('Delete memory') }}</span>
          <button class="modal-close" @click="deleteTarget = null">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <line x1="1" y1="1" x2="11" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              <line x1="11" y1="1" x2="1" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
          </button>
        </div>
        <div class="modal-body delete-modal-body">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="delete-icon">
            <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
          </svg>
          <p class="delete-confirm-text">{{ t('Delete {name}?', {name: ''}) }}<strong>{{ deleteTarget.name }}</strong></p>
          <p class="delete-confirm-sub">{{ t('This memory will be soft-deleted and removed from context injection.') }}</p>
        </div>
        <div class="modal-footer">
          <button class="btn-cancel" @click="deleteTarget = null">{{ t('Cancel') }}</button>
          <button class="btn-danger" @click="confirmDelete" :disabled="isDeleting">{{ isDeleting ? t('Deleting…') : t('Delete') }}</button>
        </div>
      </div>
    </div>
    <div v-if="tokenActionTarget" class="modal-overlay" @click.self="tokenActionTarget = null">
      <div class="modal modal-sm">
        <div class="modal-header">
          <span class="modal-title">{{ tokenActionTarget.action === 'reset' ? t('Reset token') : t('Revoke token') }}</span>
          <button class="modal-close" @click="tokenActionTarget = null">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <line x1="1" y1="1" x2="11" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              <line x1="11" y1="1" x2="1" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
          </button>
        </div>
        <div class="modal-body delete-modal-body">
          <svg v-if="tokenActionTarget.action === 'reset'" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="delete-icon" style="color:var(--accent)">
            <polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.5 9a9 9 0 0 1 14.9-3.4L23 10"/><path d="M20.5 15a9 9 0 0 1-14.9 3.4L1 14"/>
          </svg>
          <svg v-else width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="delete-icon">
            <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
          </svg>
          <p class="delete-confirm-text"><strong>{{ tokenActionTarget.tok.name }}</strong></p>
          <p class="delete-confirm-sub">{{ tokenActionTarget.action === 'reset' ? t('Reset token desc') : t('Revoke token desc') }}</p>
        </div>
        <div class="modal-footer">
          <button class="btn-cancel" @click="tokenActionTarget = null">{{ t('Cancel') }}</button>
          <button :class="tokenActionTarget.action === 'reset' ? 'btn-save' : 'btn-danger'" @click="confirmTokenAction" :disabled="isTokenActioning">
            {{ isTokenActioning ? t('Processing…') : (tokenActionTarget.action === 'reset' ? t('Reset') : t('Revoke')) }}
          </button>
        </div>
      </div>
    </div>
    <div v-if="editTarget" class="modal-overlay" @click.self="editTarget = null">
      <div class="write-modal">
        <div :class="['write-header', editTarget?.type ? 'type-header-' + editTarget.type : '']">
          <div class="write-header-left">
            <div style="display:flex;align-items:center;gap:8px;">
              <span v-if="editTarget" :class="['tag', editTarget.type]" style="font-size:10px;padding:1px 6px">{{ t(editTarget.type) }}</span>
              <span class="write-title">{{ t('Edit Memory') }}</span>
            </div>
            <div v-if="editTarget?.name" class="write-subtitle">{{ editTarget.name }}</div>
          </div>
          <div class="write-header-right">
            <button class="modal-close" @click="editTarget = null">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <line x1="1" y1="1" x2="11" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                <line x1="11" y1="1" x2="1" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              </svg>
            </button>
          </div>
        </div>
        <div class="write-body">
          <div class="write-section">
            <label class="write-field-label">{{ t('Name') }}</label>
            <input class="write-input" v-model="editForm.name" />
          </div>
          <div class="write-section">
            <label class="write-field-label">{{ t('Description') }}</label>
            <textarea class="write-input write-textarea" v-model="editForm.description" rows="2" style="min-height:56px" />
          </div>
          <div class="write-section write-section-grow">
            <label class="write-field-label">{{ t('Content') }}</label>
            <textarea class="write-input write-textarea" v-model="editForm.content" rows="6" />
          </div>
          <div class="write-section">
            <label class="write-field-label">{{ t('Why') }}</label>
            <input class="write-input" v-model="editForm.why" />
          </div>
          <div class="write-section">
            <label class="write-field-label">{{ t('How to apply') }}</label>
            <input class="write-input" v-model="editForm.how_to_apply" />
          </div>
          <div class="write-section write-section-row">
            <div class="write-section-half">
              <label class="write-field-label">{{ t('Importance') }}</label>
              <select class="write-input write-select" v-model.number="editForm.importance">
                <option v-for="n in [1,2,3,4,5]" :key="n" :value="n">{{ n }}</option>
              </select>
            </div>
          </div>
          <p v-if="editError" class="save-hint err" style="margin-top:4px">{{ editError }}</p>
        </div>
        <div class="write-footer">
          <button class="btn-cancel" @click="editTarget = null">{{ t('Cancel') }}</button>
          <button class="btn-save" :disabled="isEditSaving" @click="saveEdit">{{ isEditSaving ? t('Saving…') : t('Save') }}</button>
        </div>
      </div>
    </div>
    <div v-if="writeOpen" class="modal-overlay" @click.self="writeOpen = false">
      <div class="write-modal">
        <div class="write-header">
          <span class="write-title">{{ t('New Memory') }}</span>
          <div class="write-header-right">
            <kbd class="kbd-hint">N</kbd>
            <button class="modal-close" @click="writeOpen = false">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <line x1="1" y1="1" x2="11" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                <line x1="11" y1="1" x2="1" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              </svg>
            </button>
          </div>
        </div>
        <div class="write-body">
          <div class="write-type-tabs">
            <button v-for="tp in ['user','feedback','project','reference']" :key="tp"
              :class="['type-tab', 'type-tab-' + tp, writeForm.type === tp ? 'active' : '']"
              @click="writeForm.type = tp">{{ t(tp) }}</button>
          </div>
          <div class="write-section">
            <label class="write-field-label">{{ t('Name') }}</label>
            <input class="write-input" v-model="writeForm.name" :placeholder="t('Short identifier…')" ref="writeNameRef" />
          </div>
          <div class="write-section">
            <label class="write-field-label">{{ t('Description') }}</label>
            <input class="write-input" v-model="writeForm.description" :placeholder="t('One-line summary…')" />
          </div>
          <div class="write-section write-section-grow">
            <label class="write-field-label">{{ t('Content') }}</label>
            <textarea class="write-input write-textarea" v-model="writeForm.content" :placeholder="t('Full memory content…')" rows="6" />
          </div>
          <div class="write-collapsible" :class="{open: writeShowExtra}">
            <button class="write-extra-toggle" @click="writeShowExtra = !writeShowExtra">
              <svg :class="['write-extra-chevron', {open: writeShowExtra}]" width="10" height="10" viewBox="0 0 10 10" fill="none">
                <path d="M2 3.5L5 6.5L8 3.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
              {{ t('Optional fields') }}
            </button>
            <div v-if="writeShowExtra" class="write-extra-fields">
              <div class="write-section">
                <label class="write-field-label">{{ t('Why') }}</label>
                <input class="write-input" v-model="writeForm.why" :placeholder="t('Reason or motivation…')" />
              </div>
              <div class="write-section">
                <label class="write-field-label">{{ t('How to apply') }}</label>
                <input class="write-input" v-model="writeForm.how_to_apply" :placeholder="t('When / how to use this…')" />
              </div>
              <div class="write-section write-section-row">
                <div class="write-section-half">
                  <label class="write-field-label">{{ t('Importance') }}</label>
                  <select class="write-input write-select" v-model.number="writeForm.importance">
                    <option v-for="n in [1,2,3,4,5]" :key="n" :value="n">{{ n }}</option>
                  </select>
                </div>
                <div class="write-section-half">
                  <label class="write-field-label">{{ t('Project') }}</label>
                  <select class="write-input write-select" v-model="writeForm.project_id">
                    <option value="">{{ t('Global (*)') }}</option>
                    <option v-for="p in projects" :key="p.id" :value="p.slug">{{ p.display_name || p.slug }}</option>
                  </select>
                </div>
              </div>
            </div>
          </div>
          <p v-if="writeError" class="save-hint err" style="margin-top:4px">{{ writeError }}</p>
        </div>
        <div class="write-footer">
          <span class="write-target-hint">
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
              <circle cx="5" cy="5" r="4" stroke="currentColor" stroke-width="1.2"/>
              <line x1="5" y1="3" x2="5" y2="5.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
              <circle cx="5" cy="7" r="0.6" fill="currentColor"/>
            </svg>
            {{ writeForm.project_id ? writeForm.project_id : t('Global (*)') }}
          </span>
          <button class="btn-cancel" @click="writeOpen = false">{{ t('Cancel') }}</button>
          <button class="btn-save" :disabled="isWriteSaving || !writeForm.name || !writeForm.content" @click="submitWrite">
            {{ isWriteSaving ? t('Saving…') : t('Write') }}
          </button>
        </div>
      </div>
    </div>
    <div v-if="cloneSource" class="modal-overlay" @click.self="cloneSource = null">
      <div class="modal modal-clone">
        <div class="modal-header">
          <span class="modal-title">{{ t('Clone Memory') }}</span>
          <button class="modal-close" @click="cloneSource = null">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <line x1="1" y1="1" x2="11" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              <line x1="11" y1="1" x2="1" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
          </button>
        </div>
        <div class="modal-body clone-modal-body">
          <div class="clone-source-card">
            <div class="clone-source-meta">
              <span :class="['badge', cloneSource.type]">
                <span class="badge-dot"></span>{{ t(cloneSource.type) }}
              </span>
              <span class="clone-source-project">{{ projectDisplayName(cloneSource.project_id) || t('Global (*)') }}</span>
            </div>
            <div class="clone-source-name">{{ cloneSource.name }}</div>
            <div v-if="cloneSource.description" class="clone-source-desc">{{ cloneSource.description }}</div>
          </div>
          <label class="field-row clone-target-row">
            <span class="field-label">{{ t('Clone to project') }}</span>
            <select v-model="cloneSlug" class="field-input">
              <option value="">{{ t('— Select project —') }}</option>
              <option v-for="p in projects" :key="p.id" :value="p.slug">{{ p.display_name || p.slug }}</option>
            </select>
          </label>
          <div v-if="cloneError" class="clone-status err">{{ cloneError }}</div>
          <div v-if="cloneDone" class="clone-status ok">{{ t('Cloned ✓') }}</div>
        </div>
        <div class="modal-footer">
          <button class="btn-cancel" @click="cloneSource = null">{{ t('Cancel') }}</button>
          <button class="btn-save" :disabled="!cloneSlug || isCloning" @click="doClone">
            {{ isCloning ? t('Cloning…') : t('Clone') }}
          </button>
        </div>
      </div>
    </div>
    <Transition name="bulk">
      <div v-if="selectedIds.size > 0" class="bulk-bar">
        <span class="bulk-count">{{ selectedIds.size }} {{ t('selected') }}</span>
        <button class="bulk-clear" @click="selectedIds.clear()">×</button>
        <span class="bulk-sep">|</span>
        <template v-if="!bulkConfirmDelete">
          <button class="bulk-btn bulk-btn-danger" @click="bulkConfirmDelete = true">{{ t('Delete') }}</button>
        </template>
        <template v-else>
          <span class="bulk-confirm-text">{{ t('Delete {n}?', {n: selectedIds.size}) }}</span>
          <button class="bulk-btn bulk-btn-danger" :disabled="isBulkDeleting" @click="bulkDelete">{{ isBulkDeleting ? t('Deleting…') : t('Yes') }}</button>
          <button class="bulk-btn" @click="bulkConfirmDelete = false">{{ t('No') }}</button>
        </template>
        <span class="bulk-sep">|</span>
        <select class="bulk-move-select" v-model="bulkMoveTarget">
          <option value="">{{ t('Move to…') }}</option>
          <option v-for="p in projects" :key="p.id" :value="p.slug">{{ p.display_name || p.slug }}</option>
        </select>
        <button class="bulk-btn" :disabled="!bulkMoveTarget || isBulkMoving" @click="bulkMove">
          {{ isBulkMoving ? t('Moving…') : t('Move') }}
        </button>
      </div>
    </Transition>
    <div v-if="importModalOpen" class="modal-overlay">
      <div class="modal modal-sm">
        <div class="modal-header">
          <span class="modal-title">{{ t('Import Memories') }}</span>
          <button class="modal-close" @click="importModalOpen = false">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <line x1="1" y1="1" x2="11" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              <line x1="11" y1="1" x2="1" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
          </button>
        </div>
        <div class="modal-body delete-modal-body">
          <template v-if="!importProgress.running && importProgress.total === 0">
            <p class="delete-confirm-text">{{ importPreview?.name }}</p>
            <p class="delete-confirm-sub">{{ t('This will overwrite existing data.') }}</p>
          </template>
          <template v-else-if="importProgress.running">
            <p class="delete-confirm-text">{{ t('Restoring…') }}</p>
          </template>
          <template v-else-if="importProgress.total === 1">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="color:var(--green);opacity:0.8">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
            <p class="delete-confirm-text">{{ t('Restored ✓') }}</p>
          </template>
          <template v-else-if="importProgress.total === -1">
            <p class="delete-confirm-text" style="color:var(--red)">{{ t('Restore failed') }}</p>
            <pre class="delete-confirm-sub" style="white-space:pre-wrap;font-size:11px;max-height:120px;overflow-y:auto">{{ importProgress.errorMsg }}</pre>
          </template>
        </div>
        <div class="modal-footer">
          <button class="btn-cancel" @click="importModalOpen = false">{{ importProgress.total !== 0 ? t('Close') : t('Cancel') }}</button>
          <button v-if="importProgress.total === 0" class="btn-save" @click="confirmImport" :disabled="importProgress.running">{{ t('Import') }}</button>
        </div>
      </div>
    </div>
    <div v-if="duplicatesOpen" class="modal-overlay">
      <div class="modal modal-xl">
        <div class="modal-header">
          <span class="modal-title">{{ t('Duplicates') }} <span v-if="!duplicatesLoading" class="dup-count">({{ duplicatePairs.length }})</span></span>
          <button class="modal-close" @click="duplicatesOpen = false">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <line x1="1" y1="1" x2="11" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              <line x1="11" y1="1" x2="1" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
          </button>
        </div>
        <div class="dup-toolbar">
          <label class="dup-threshold">
            <span>{{ t('Threshold') }}</span>
            <input
              class="dup-threshold-slider"
              type="range"
              min="0.80"
              max="0.98"
              step="0.01"
              v-model="duplicateThreshold"
              :aria-label="t('Threshold')"
            />
            <output class="dup-threshold-value">{{ duplicateThreshold }}</output>
          </label>
          <button class="dup-refresh" :disabled="duplicatesLoading" @click="scanDuplicates">
            {{ duplicatesLoading ? t('Loading…') : t('Scan') }}
          </button>
        </div>
        <div v-if="duplicateError" class="dup-error">{{ duplicateError }}</div>
        <div class="modal-body dup-modal-body">
          <div v-if="duplicatesLoading" class="empty-state">{{ t('Loading…') }}</div>
          <div v-else-if="duplicatePairs.length === 0" class="empty-state">{{ t('No duplicates found') }}</div>
          <div v-else class="dup-list">
            <div v-for="(pair, i) in duplicatePairs" :key="pair.id1 + pair.id2" class="dup-pair">
              <div class="dup-side">
                <div class="dup-meta"><span :class="['badge', pair.type1]">{{ t(pair.type1) }}</span><span class="dup-proj" :title="pair.project_slug1">{{ projectSlugMap[pair.project_slug1] || pair.project_slug1 }}</span></div>
                <div class="dup-name">{{ pair.name1 }}</div>
                <div class="dup-desc">{{ pair.description1 }}</div>
                <div class="dup-content">{{ pair.content1 }}</div>
                <button class="btn-dup-del" @click="deleteDupMem(pair.id1, i)">{{ t('Delete') }}</button>
              </div>
              <div class="dup-center">
                <div class="dup-sim">{{ Math.round(pair.similarity * 100) }}%</div>
                <button class="btn-dup-skip" @click="duplicatePairs.splice(i, 1)">{{ t('Skip') }}</button>
              </div>
              <div class="dup-side">
                <div class="dup-meta"><span :class="['badge', pair.type2]">{{ t(pair.type2) }}</span><span class="dup-proj" :title="pair.project_slug2">{{ projectSlugMap[pair.project_slug2] || pair.project_slug2 }}</span></div>
                <div class="dup-name">{{ pair.name2 }}</div>
                <div class="dup-desc">{{ pair.description2 }}</div>
                <div class="dup-content">{{ pair.content2 }}</div>
                <button class="btn-dup-del" @click="deleteDupMem(pair.id2, i)">{{ t('Delete') }}</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div v-if="conflictsOpen" class="modal-overlay">
      <div class="modal modal-xl">
        <div class="modal-header">
          <span class="modal-title">{{ t('Conflicts') }} <span v-if="!conflictsLoading" class="dup-count">({{ conflictPairs.length }})</span></span>
          <button class="modal-close" @click="conflictsOpen = false">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <line x1="1" y1="1" x2="11" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              <line x1="11" y1="1" x2="1" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
          </button>
        </div>
        <div class="dup-toolbar">
          <label class="dup-threshold">
            <span>{{ t('Min similarity') }}</span>
            <input
              class="dup-threshold-slider"
              type="range"
              min="0.40"
              max="0.85"
              step="0.01"
              v-model="conflictMinSim"
              :aria-label="t('Min similarity')"
            />
            <output class="dup-threshold-value">{{ conflictMinSim }}</output>
          </label>
          <button class="dup-refresh" :disabled="conflictsLoading" @click="scanConflicts">
            {{ conflictsLoading ? t('Loading…') : t('Scan') }}
          </button>
        </div>
        <div v-if="conflictError" class="dup-error">{{ conflictError }}</div>
        <div class="modal-body dup-modal-body">
          <div v-if="conflictsLoading" class="empty-state">{{ t('Loading…') }}</div>
          <div v-else-if="conflictPairs.length === 0" class="empty-state">{{ t('No conflicts found') }}</div>
          <div v-else class="dup-list">
            <div v-for="(pair, i) in conflictPairs" :key="pair.id1 + pair.id2" class="dup-pair">
              <div class="dup-side">
                <div class="dup-meta"><span :class="['badge', pair.type1]">{{ t(pair.type1) }}</span><span class="dup-proj" :title="pair.project_slug1">{{ projectSlugMap[pair.project_slug1] || pair.project_slug1 }}</span></div>
                <div class="dup-name">{{ pair.name1 }}</div>
                <div class="dup-desc">{{ pair.description1 }}</div>
                <div class="dup-content">{{ pair.content1 }}</div>
                <button class="btn-dup-del" @click="deleteConflictMem(pair.id1)">{{ t('Delete') }}</button>
              </div>
              <div class="dup-center">
                <div class="dup-sim">{{ Math.round(pair.similarity * 100) }}%</div>
                <button class="btn-dup-skip" @click="conflictPairs.splice(i, 1)">{{ t('Skip') }}</button>
              </div>
              <div class="dup-side">
                <div class="dup-meta"><span :class="['badge', pair.type2]">{{ t(pair.type2) }}</span><span class="dup-proj" :title="pair.project_slug2">{{ projectSlugMap[pair.project_slug2] || pair.project_slug2 }}</span></div>
                <div class="dup-name">{{ pair.name2 }}</div>
                <div class="dup-desc">{{ pair.description2 }}</div>
                <div class="dup-content">{{ pair.content2 }}</div>
                <button class="btn-dup-del" @click="deleteConflictMem(pair.id2)">{{ t('Delete') }}</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { marked } from 'marked'
import enLocale from './locales/en.json'
import zhLocale from './locales/zh.json'

marked.setOptions({ breaks: true, gfm: true })
function md(text) {
  if (!text) return ''
  // ensure \n is treated as real newline (in case stored as escaped)
  const normalized = text.replace(/\\n/g, '\n')
  return marked.parse(normalized)
}

const copied = ref(null)
async function copy(text) {
  await navigator.clipboard.writeText(text)
  copied.value = text
  setTimeout(() => { copied.value = null }, 1500)
}

const BASE = '/api'

// ── Auth ──
const loginOpen = ref(false)
const loginInput = ref('')
const loginError = ref('')
const loginLoading = ref(false)

function apiFetch(url, opts = {}) {
  return fetch(url, opts)
}

async function submitLogin() {
  loginLoading.value = true
  loginError.value = ''
  try {
    const r = await fetch(`${BASE}/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: loginInput.value }),
    })
    if (r.status === 401) {
      loginError.value = t('Invalid token')
      return
    }
    loginOpen.value = false
    loginInput.value = ''
    projects.value = await apiFetch(`${BASE}/projects`).then(r => r.json())
    await load()
  } catch (e) {
    loginError.value = e.message
  } finally {
    loginLoading.value = false
  }
}

async function skipLogin() {
  loginLoading.value = true
  loginError.value = ''
  try {
    const r = await fetch(`${BASE}/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: '' }),
    })
    if (r.status === 401) {
      loginError.value = t('Server requires a token — please enter one')
      return
    }
    loginOpen.value = false
    projects.value = await apiFetch(`${BASE}/projects`).then(r => r.json())
    await load()
  } catch (e) {
    loginError.value = e.message
  } finally {
    loginLoading.value = false
  }
}

async function logout() {
  await fetch(`${BASE}/logout`, { method: 'POST' })
  loginOpen.value = true
  memories.value = []
  projects.value = []
  stats.value = null
}

// ── i18n ──
const lang = ref(localStorage.getItem('mo-lang') || 'en')
const _locales = { en: enLocale, zh: zhLocale }
function toggleLang() {
  lang.value = lang.value === 'en' ? 'zh' : 'en'
  localStorage.setItem('mo-lang', lang.value)
}
function t(key, vars) {
  const locale = _locales[lang.value] || _locales.en
  const str = locale[key] ?? key
  if (!vars) return str
  return str.replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? ''))
}

const projects = ref([])
const projectMap = computed(() => Object.fromEntries(projects.value.map(p => [p.id, p.display_name || p.slug])))
const projectSlugMap = computed(() => Object.fromEntries(projects.value.map(p => [p.slug, p.display_name || p.slug])))
const memories = ref([])
const stats = ref(null)
const selectedProject = ref('')
const selectedType = ref('')
const searchText = ref('')
const detailTarget = ref(null)
const sortDesc = ref(true)
const sortBy = ref('time')
const isLoading = ref(false)

async function load() {
  isLoading.value = true
  try {
    const params = new URLSearchParams()
    if (selectedProject.value) params.set('project_slug', selectedProject.value)
    if (selectedType.value) params.set('type', selectedType.value)
    if (searchText.value) params.set('q', searchText.value)
    params.set('limit', '200')
    params.set('sort_by', sortBy.value)
    params.set('sort_desc', sortDesc.value ? 'true' : 'false')
    const [memsRes, stRes] = await Promise.all([
      apiFetch(`${BASE}/memories?${params}`),
      apiFetch(`${BASE}/stats${selectedProject.value ? '?project_slug=' + selectedProject.value : ''}`)
    ])
    if (memsRes.status === 401) { loginOpen.value = true; return }
    const [mems, st] = await Promise.all([memsRes.json(), stRes.json()])
    memories.value = mems
    stats.value = st
  } finally {
    isLoading.value = false
  }
}

const deleteTarget = ref(null)
const isDeleting = ref(false)
const tokenActionTarget = ref(null)
const isTokenActioning = ref(false)
function del(m) { deleteTarget.value = m }
async function confirmDelete() {
  if (!deleteTarget.value) return
  isDeleting.value = true
  try {
    await apiFetch(`${BASE}/memories/${deleteTarget.value.id}`, { method: 'DELETE' })
    deleteTarget.value = null
    await load()
  } finally {
    isDeleting.value = false
  }
}

const filtered = computed(() => memories.value)

let searchTimer = null
watch(searchText, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(load, 300)
})

const moveTarget = ref({})
const moved = ref(null)
const isMoving = ref({})
const moveError = ref({})
async function moveMemory(m) {
  const slug = moveTarget.value[m.id]
  if (!slug) return
  isMoving.value[m.id] = true
  moveError.value[m.id] = ''
  try {
    const r = await apiFetch(`${BASE}/memories/${m.id}/move?project_slug=${encodeURIComponent(slug)}`, { method: 'PATCH' })
    if (!r.ok) {
      const err = await r.json().catch(() => ({}))
      moveError.value[m.id] = `Failed: ${err.detail || r.statusText}`
      setTimeout(() => { moveError.value[m.id] = '' }, 3000)
      return
    }
    moved.value = m.id
    setTimeout(() => { moved.value = null }, 1800)
    moveTarget.value[m.id] = ''
    await load()
  } finally {
    isMoving.value[m.id] = false
  }
}

const cloneSource = ref(null)
const cloneSlug = ref('')
const isCloning = ref(false)
const cloneError = ref('')
const cloneDone = ref(false)
function openClone(m) {
  cloneSource.value = m
  cloneSlug.value = ''
  cloneError.value = ''
  cloneDone.value = false
}
async function doClone() {
  if (!cloneSource.value || !cloneSlug.value) return
  isCloning.value = true
  cloneError.value = ''
  try {
    const r = await apiFetch(`${BASE}/memories/${cloneSource.value.id}/clone?project_slug=${encodeURIComponent(cloneSlug.value)}`, { method: 'POST' })
    if (!r.ok) {
      const err = await r.json().catch(() => ({}))
      cloneError.value = err.detail || r.statusText
      return
    }
    cloneDone.value = true
    await load()
    setTimeout(() => { cloneSource.value = null }, 1500)
  } finally {
    isCloning.value = false
  }
}

const editTarget = ref(null)
const editForm = ref({})
const isEditSaving = ref(false)
const editError = ref('')
function openEdit(m) {
  editTarget.value = m
  editForm.value = {
    name: m.name,
    description: m.description,
    content: m.content,
    why: m.why || '',
    how_to_apply: m.how_to_apply || '',
    importance: m.importance,
  }
  editError.value = ''
}
async function saveEdit() {
  if (!editTarget.value) return
  isEditSaving.value = true
  editError.value = ''
  try {
    const r = await apiFetch(`${BASE}/memories/${editTarget.value.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(editForm.value),
    })
    if (!r.ok) {
      const err = await r.json().catch(() => ({}))
      editError.value = `Failed: ${err.detail || r.statusText}`
      return
    }
    editTarget.value = null
    await load()
  } finally {
    isEditSaving.value = false
  }
}

const writeOpen = ref(false)
const writeShowExtra = ref(false)
const writeNameRef = ref(null)
const isWriteSaving = ref(false)
const writeError = ref('')
const writeForm = ref({ type: 'feedback', name: '', description: '', content: '', why: '', how_to_apply: '', importance: 3, project_id: '' })

function openWrite() {
  writeForm.value = { type: 'feedback', name: '', description: '', content: '', why: '', how_to_apply: '', importance: 3, project_id: '' }
  writeError.value = ''
  writeShowExtra.value = false
  writeOpen.value = true
  setTimeout(() => writeNameRef.value?.focus(), 50)
}

async function submitWrite() {
  if (!writeForm.value.name || !writeForm.value.content) return
  isWriteSaving.value = true
  writeError.value = ''
  try {
    const payload = { ...writeForm.value }
    if (!payload.project_id) delete payload.project_id
    if (!payload.why) delete payload.why
    if (!payload.how_to_apply) delete payload.how_to_apply
    const r = await apiFetch(`${BASE}/memories`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    if (!r.ok) {
      const err = await r.json().catch(() => ({}))
      writeError.value = `Failed: ${err.detail || r.statusText}`
      return
    }
    writeOpen.value = false
    await load()
  } finally {
    isWriteSaving.value = false
  }
}

// ── Bulk operations ──
const selectedIds = ref(new Set())
const isBulkDeleting = ref(false)
const isBulkMoving = ref(false)
const bulkMoveTarget = ref('')
const bulkConfirmDelete = ref(false)
const selectAllRef = ref(null)

const allSelected = computed(() =>
  paged.value.length > 0 && paged.value.every(m => selectedIds.value.has(m.id))
)
const someSelected = computed(() =>
  paged.value.some(m => selectedIds.value.has(m.id)) && !allSelected.value
)
function toggleSelect(id) {
  if (selectedIds.value.has(id)) selectedIds.value.delete(id)
  else selectedIds.value.add(id)
}
function toggleSelectAll() {
  if (allSelected.value) paged.value.forEach(m => selectedIds.value.delete(m.id))
  else paged.value.forEach(m => selectedIds.value.add(m.id))
}
async function bulkDelete() {
  if (!selectedIds.value.size) return
  isBulkDeleting.value = true
  try {
    const ids = [...selectedIds.value]
    const r = await apiFetch(`${BASE}/memories/batch-delete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids }),
    })
    if (!r.ok) return
    selectedIds.value.clear()
    bulkConfirmDelete.value = false
    await load()
  } finally {
    isBulkDeleting.value = false
  }
}
async function bulkMove() {
  if (!bulkMoveTarget.value || !selectedIds.value.size) return
  isBulkMoving.value = true
  try {
    const ids = [...selectedIds.value]
    const r = await apiFetch(`${BASE}/memories/batch-move`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids, project_slug: bulkMoveTarget.value }),
    })
    if (!r.ok) return
    selectedIds.value.clear()
    bulkMoveTarget.value = ''
    await load()
  } finally {
    isBulkMoving.value = false
  }
}

// ── Import / Export ──
const importFileRef = ref(null)
const importPreview = ref(null)
const importModalOpen = ref(false)
const importProgress = ref({ done: 0, total: 0, skipped: 0, errors: 0, running: false })

async function exportMemories() {
  const r = await apiFetch(`${BASE}/backup`)
  if (!r.ok) { alert('Backup failed: ' + (await r.text())); return }
  const blob = await r.blob()
  const cd = r.headers.get('Content-Disposition') || ''
  const match = cd.match(/filename="([^"]+)"/)
  const filename = match ? match[1] : `mo-backup-${new Date().toISOString().slice(0, 10)}.sql`
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename
  document.body.appendChild(a); a.click(); document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
function openImport() { importFileRef.value?.click() }
async function onImportFile(e) {
  const file = e.target.files?.[0]
  if (!file) return
  e.target.value = ''
  importPreview.value = { file, name: file.name, size: file.size }
  importProgress.value = { done: 0, total: 0, skipped: 0, errors: 0, running: false, errorMsg: '' }
  importModalOpen.value = true
}
async function confirmImport() {
  if (!importPreview.value?.file) return
  importProgress.value.running = true
  try {
    const fd = new FormData()
    fd.append('file', importPreview.value.file)
    const r = await apiFetch(`${BASE}/restore`, { method: 'POST', body: fd })
    if (!r.ok) {
      const text = await r.text()
      importProgress.value.errors = 1
      importProgress.value.running = false
      importProgress.value.total = -1
      importProgress.value.errorMsg = text.slice(0, 400)
      return
    }
    importProgress.value.done = 1
    importProgress.value.total = 1
    importProgress.value.running = false
    await load()
  } catch (err) {
    importProgress.value.errors = 1
    importProgress.value.running = false
    importProgress.value.total = -1
    importProgress.value.errorMsg = String(err)
  }
}

// ── Duplicates ──
const duplicatesOpen = ref(false)
const duplicatePairs = ref([])
const duplicatesLoading = ref(false)
const duplicateError = ref('')
const duplicateThreshold = ref('0.92')
const DUP_THRESHOLD_MIN = 0.80
const DUP_THRESHOLD_MAX = 0.98

function normalizeDuplicateThreshold(value) {
  const n = Number(value)
  if (!Number.isFinite(n)) return '0.92'
  return Math.min(DUP_THRESHOLD_MAX, Math.max(DUP_THRESHOLD_MIN, n)).toFixed(2)
}

async function openDuplicates() {
  duplicatesOpen.value = true
  try {
    const settings = await apiFetch(`${BASE}/settings`).then(r => r.ok ? r.json() : null)
    duplicateThreshold.value = normalizeDuplicateThreshold(settings?.dup_threshold || '0.92')
  } catch {
    duplicateThreshold.value = '0.92'
  }
  await scanDuplicates()
}

async function scanDuplicates() {
  duplicatesLoading.value = true
  duplicateError.value = ''
  duplicatePairs.value = []
  try {
    const params = new URLSearchParams()
    if (selectedProject.value) params.set('project_slug', selectedProject.value)
    if (selectedType.value) params.set('type', selectedType.value)
    duplicateThreshold.value = normalizeDuplicateThreshold(duplicateThreshold.value)
    params.set('threshold', duplicateThreshold.value)
    const qs = params.toString()
    const r = await apiFetch(`${BASE}/duplicates${qs ? '?' + qs : ''}`)
    if (!r.ok) {
      const text = await r.text()
      duplicateError.value = `Scan failed (${r.status}): ${text.slice(0, 180) || r.statusText}`
      return
    }
    duplicatePairs.value = await r.json()
  } catch (err) {
    duplicateError.value = `Scan failed: ${err?.message || err}`
  } finally {
    duplicatesLoading.value = false
  }
}

async function deleteDupMem(id, pairIdx) {
  const r = await apiFetch(`${BASE}/memories/${id}`, { method: 'DELETE' })
  if (r.ok || r.status === 204) {
    duplicatePairs.value = duplicatePairs.value.filter(pair => pair.id1 !== id && pair.id2 !== id)
    await load()
  }
}

const conflictsOpen = ref(false)
const conflictPairs = ref([])
const conflictsLoading = ref(false)
const conflictError = ref('')
const conflictMinSim = ref('0.50')

async function openConflicts() {
  conflictsOpen.value = true
  await scanConflicts()
}

async function scanConflicts() {
  conflictsLoading.value = true
  conflictError.value = ''
  conflictPairs.value = []
  try {
    const params = new URLSearchParams()
    if (selectedProject.value) params.set('project_slug', selectedProject.value)
    if (selectedType.value) params.set('type', selectedType.value)
    params.set('min_sim', conflictMinSim.value)
    const qs = params.toString()
    const r = await apiFetch(`${BASE}/conflicts${qs ? '?' + qs : ''}`)
    if (!r.ok) {
      const txt = await r.text()
      conflictError.value = `Scan failed (${r.status}): ${txt.slice(0, 180) || r.statusText}`
      return
    }
    conflictPairs.value = await r.json()
  } catch (err) {
    conflictError.value = `Scan failed: ${err?.message || err}`
  } finally {
    conflictsLoading.value = false
  }
}

async function deleteConflictMem(id) {
  const r = await apiFetch(`${BASE}/memories/${id}`, { method: 'DELETE' })
  if (r.ok || r.status === 204) {
    conflictPairs.value = conflictPairs.value.filter(pair => pair.id1 !== id && pair.id2 !== id)
    await load()
  }
}

const page = ref(1)
const pageSize = ref(20)
const totalPages = computed(() => Math.max(1, Math.ceil(filtered.value.length / pageSize.value)))

const paged = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filtered.value.slice(start, start + pageSize.value)
})

watch([filtered, pageSize], () => { page.value = 1 })

const tip = ref({ visible: false, text: '', x: 0, y: 0 })
function showTip(e, text) {
  if (!text || text === '—') return
  const r = e.currentTarget.getBoundingClientRect()
  tip.value = { visible: true, text, x: r.left, y: r.top - 6 }
}
function hideTip() { tip.value.visible = false }

const IMP_COLORS = ['', '#f85149', '#d29922', '#e3b341', '#58a6ff', '#3fb950']
function impColor(n) { return IMP_COLORS[Math.min(Math.max(n, 1), 5)] }

const PROJECT_COLOR_CLASSES = ['project', 'feedback', 'user', 'reference']
function projectColorClass(id) {
  let h = 0
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) & 0xff
  return PROJECT_COLOR_CLASSES[h % PROJECT_COLOR_CLASSES.length]
}
function projectAbbr(id) {
  const name = projectMap.value[id] || ''
  if (!name) return '?'
  const seg = name.split(/[/\\:]/).filter(Boolean).pop() || name
  const words = seg.split(/[-_\s]+/).filter(Boolean)
  if (words.length >= 2) return (words[0][0] + words[1][0]).toUpperCase()
  return seg.slice(0, 2).toUpperCase()
}

function projectDisplayName(id) {
  return projectMap.value[id] || ''
}

function projectCellText(id) {
  const name = projectDisplayName(id)
  return name.length > 20 ? `${name.slice(0, 20)}...` : name
}

function sourceClass(source) {
  return source === 'codex' ? 'codex' : 'claude'
}
function sourceIconUrl(source) {
  const tone = isDark.value ? 'dark' : 'light'
  return source === 'codex'
    ? `/ui/assets/openai-${tone}.svg`
    : `/ui/assets/claude-${tone}.svg`
}
function sourceLabel(source) {
  return source === 'codex' ? 'Codex' : 'Claude Code'
}

function toggleSort(col) {
  if (sortBy.value === col) { sortDesc.value = !sortDesc.value } else { sortBy.value = col; sortDesc.value = true }
  page.value = 1
  load()
}
function openDetail(m) { detailTarget.value = m }
function resetFilters() {
  selectedProject.value = ''
  selectedType.value = ''
  searchText.value = ''
  load()
}
const browserTz = Intl.DateTimeFormat().resolvedOptions().timeZone || null

function _fmt(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (browserTz) {
    try {
      const parts = new Intl.DateTimeFormat('sv', {
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
        timeZoneName: 'short',
        hour12: false, timeZone: browserTz,
      }).formatToParts(d)
      const get = t => parts.find(p => p.type === t)?.value ?? ''
      const zone = get('timeZoneName')
      return `${get('year')}-${get('month')}-${get('day')} ${get('hour')}:${get('minute')}:${get('second')}${zone ? ' ' + zone : ''}`
    } catch { /* fall through */ }
  }
  return d.toLocaleDateString('sv') + ' ' + d.toLocaleTimeString('en-GB', { hour12: false })
}
function fmtDate(iso) { return _fmt(iso) }
function fmtDateTime(iso) { return _fmt(iso) }
function relTime(iso) {
  if (!iso) return '—'
  const diff = (Date.now() - new Date(iso).getTime()) / 1000
  if (diff < 60) return 'just now'
  if (diff < 3600) return Math.floor(diff / 60) + 'm'
  if (diff < 86400) return Math.floor(diff / 3600) + 'h'
  if (diff < 86400 * 7) return Math.floor(diff / 86400) + 'd'
  if (diff < 86400 * 30) return Math.floor(diff / (86400 * 7)) + 'w'
  return Math.floor(diff / (86400 * 30)) + 'mo'
}

const storedTheme = localStorage.getItem('mo-theme')
const isDark = ref(storedTheme ? storedTheme === 'dark' : true)

// ── Settings modal ──
const settingsOpen = ref(false)
const settingsTab = ref('settings')
const isSaving = ref(false)
const saveHint = ref('')
const availableModels = ref([])
const isFetchingModels = ref(false)
const modelDropOpen = ref(false)
const modelHighlight = ref(-1)
const form = ref({ extraction_base_url: '', extraction_model: '', extraction_api_key: '', embed_model: '', embed_dim: '', hook_cooldown_sec: '', hook_min_turns: '', hook_budget_tokens: '', search_top_k: '', dup_threshold: '', db_dsn: '', http_port: '', rerank_enabled: 'false', rerank_model: '', score_cosine_weight: '', score_importance_weight: '', score_recency_weight: '', score_recency_half_life: '', score_rerank_blend: '', score_type_feedback: '', score_type_project: '', score_type_user: '', score_type_reference: '' })

const modelFilteredList = computed(() => {
  if (!availableModels.value.length) return []
  const q = (form.value.extraction_model || '').toLowerCase()
  if (!q) return availableModels.value
  return availableModels.value.filter(m => m.toLowerCase().includes(q))
})
function onModelFocus() {
  if (availableModels.value.length) modelDropOpen.value = true
  modelHighlight.value = -1
}
function onModelBlur() {
  setTimeout(() => { modelDropOpen.value = false; modelHighlight.value = -1 }, 150)
}
function onModelKeydown(e) {
  if (!modelDropOpen.value) {
    if (e.key === 'ArrowDown' || e.key === 'Enter') { modelDropOpen.value = true; e.preventDefault() }
    return
  }
  const list = modelFilteredList.value
  if (e.key === 'ArrowDown') {
    modelHighlight.value = Math.min(modelHighlight.value + 1, list.length - 1)
    e.preventDefault()
  } else if (e.key === 'ArrowUp') {
    modelHighlight.value = Math.max(modelHighlight.value - 1, -1)
    e.preventDefault()
  } else if (e.key === 'Enter') {
    if (modelHighlight.value >= 0 && list[modelHighlight.value]) {
      selectModel(list[modelHighlight.value])
    }
    e.preventDefault()
  } else if (e.key === 'Escape') {
    modelDropOpen.value = false
    modelHighlight.value = -1
  }
}
function selectModel(m) {
  form.value.extraction_model = m
  modelDropOpen.value = false
  modelHighlight.value = -1
}

async function fetchModels() {
  if (!form.value.extraction_base_url) return
  isFetchingModels.value = true
  try {
    const params = new URLSearchParams({ base_url: form.value.extraction_base_url })
    const key = form.value.extraction_api_key
    const headers = {}
    if (key && key !== '***' && key !== KEY_SENTINEL && key !== '')
      headers['X-Api-Key'] = key
    const models = await apiFetch(`${BASE}/models?${params}`, { headers }).then(r => r.ok ? r.json() : [])
    availableModels.value = models
    if (models.length) modelDropOpen.value = true
  } finally {
    isFetchingModels.value = false
  }
}

// Scoring tab helpers
function wf(key, def) { return Math.max(0, parseFloat(form.value[key]) || def) }
const weightSum = computed(() => {
  const s = wf('score_cosine_weight', 0.6) + wf('score_importance_weight', 0.3) + wf('score_recency_weight', 0.1)
  return (Math.round(s * 100) / 100).toFixed(2)
})
const weightSumOk = computed(() => Math.abs(parseFloat(weightSum.value) - 1.0) < 0.015)
function decayPct(days) {
  const h = parseFloat(form.value.score_recency_half_life) || 60
  return Math.round(Math.exp(-days / h) * 100)
}
function typeBarPct(val) {
  return Math.round(Math.min(3, Math.max(0, parseFloat(val) || 1)) / 3 * 100) + '%'
}
const blendFmt = computed(() => (parseFloat(form.value.score_rerank_blend) || 0.8).toFixed(2))
const counterBlendFmt = computed(() => (1 - (parseFloat(form.value.score_rerank_blend) || 0.8)).toFixed(2))

const KEY_SENTINEL = '__keep__'

async function openSettings() {
  const data = await apiFetch(`${BASE}/settings`).then(r => r.json())
  form.value = { ...data, extraction_api_key: data.extraction_api_key === '***' ? KEY_SENTINEL : (data.extraction_api_key || '') }
  availableModels.value = []
  modelDropOpen.value = false
  modelHighlight.value = -1
  settingsTab.value = 'settings'
  settingsOpen.value = true
}

async function saveSettings() {
  isSaving.value = true
  saveHint.value = ''
  try {
    const payload = Object.fromEntries(
      Object.entries(form.value).filter(([k, v]) => {
        if (k === 'extraction_api_key') return v !== KEY_SENTINEL && v !== ''
        return v !== ''
      })
    )
    const r = await apiFetch(`${BASE}/settings`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
    if (!r.ok) {
      const err = await r.json().catch(() => ({}))
      saveHint.value = `Error ${r.status}: ${err.detail || r.statusText}`
      return
    }
    saveHint.value = t('Saved')
    setTimeout(() => { saveHint.value = ''; settingsOpen.value = false }, 1200)
  } catch (e) {
    saveHint.value = `Error: ${e.message}`
  } finally {
    isSaving.value = false
  }
}
function applyTheme() {
  document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light')
}
function toggleTheme() {
  isDark.value = !isDark.value
  localStorage.setItem('mo-theme', isDark.value ? 'dark' : 'light')
  applyTheme()
}

// ── Admin modal ──
const adminOpen = ref(false)
const adminTokens = ref([])
const adminLoading = ref(false)
const adminCreateOpen = ref(false)
const adminNewKind = ref('mcp_client')
const adminNewName = ref('')
const adminCreating = ref(false)
const adminCreatedToken = ref('')

async function openAdmin() {
  adminOpen.value = true
  await adminLoad()
}

async function adminLoad() {
  adminLoading.value = true
  try {
    const r = await apiFetch(`${BASE}/tokens`)
    if (r.status === 401) { loginOpen.value = true; return }
    adminTokens.value = await r.json()
  } finally {
    adminLoading.value = false
  }
}

async function adminCreate() {
  if (!adminNewName.value) return
  adminCreating.value = true
  try {
    const r = await apiFetch(`${BASE}/tokens`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind: adminNewKind.value, name: adminNewName.value }),
    })
    if (!r.ok) return
    const data = await r.json()
    adminCreatedToken.value = data.token
    adminNewName.value = ''
    adminCreateOpen.value = false
    await adminLoad()
  } finally {
    adminCreating.value = false
  }
}

async function adminToggle(tok) {
  await apiFetch(`${BASE}/tokens/${tok.id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled: !tok.enabled }),
  })
  await adminLoad()
}

function openTokenAction(tok, action) {
  tokenActionTarget.value = { tok, action }
}

async function confirmTokenAction() {
  if (!tokenActionTarget.value) return
  const { tok, action } = tokenActionTarget.value
  isTokenActioning.value = true
  try {
    if (action === 'reset') {
      const r = await apiFetch(`${BASE}/tokens/${tok.id}/reset`, { method: 'POST' })
      if (r.ok) {
        const data = await r.json()
        adminCreatedToken.value = data.token
        await adminLoad()
      }
    } else {
      await apiFetch(`${BASE}/tokens/${tok.id}`, { method: 'DELETE' })
      await adminLoad()
    }
  } finally {
    isTokenActioning.value = false
    tokenActionTarget.value = null
  }
}

onMounted(async () => {
  watch(someSelected, v => { if (selectAllRef.value) selectAllRef.value.indeterminate = v })
  applyTheme()
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      if (writeOpen.value) { writeOpen.value = false; return }
      if (editTarget.value) { editTarget.value = null; return }
      if (detailTarget.value) { detailTarget.value = null; return }
    }
    if (e.key === 'n' && !e.ctrlKey && !e.metaKey && !e.altKey &&
        !['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName)) {
      e.preventDefault()
      openWrite()
    }
  })
  const projRes = await apiFetch(`${BASE}/projects`)
  if (projRes.status === 401) {
    loginOpen.value = true
    return
  }
  projects.value = await projRes.json()
  await load()
})
</script>

<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

/* ── Shared tokens (layout, radii, timing) ── */
:root {
  --radius-sm: 2px;
  --radius-md: 4px;
  --radius-lg: 6px;
  --transition: 150ms ease;
}

/* ── Light theme (default) ── */
:root,
[data-theme="light"] {
  --bg:             #ECF2F8;
  --bg-secondary:   #E2EBF5;
  --surface:        rgba(255,255,255,0.94);
  --surface-2:      #DDE8F2;
  --surface-panel:  rgba(245,250,255,0.86);
  --border:         #A8C0D4;
  --border-subtle:  rgba(100,140,180,0.22);
  --border-hover:   #5A9ACA;
  --text-primary:   #0E1C28;
  --text-secondary: #2E4A60;
  --text-muted:     #5E7888;
  --text:           var(--text-primary);
  --muted:          var(--text-muted);
  --accent:         #006AFF;
  --accent-strong:  #0080FF;
  --accent-dim:     rgba(0,106,255,0.10);
  --green:          #00A878;
  --green-dim:      rgba(0,168,120,0.10);
  --green-border:   rgba(0,168,120,0.24);
  --blue:           #0066EE;
  --blue-dim:       rgba(0,102,238,0.10);
  --blue-border:    rgba(0,102,238,0.24);
  --purple:         #7B3AED;
  --purple-dim:     rgba(123,58,237,0.10);
  --purple-border:  rgba(123,58,237,0.22);
  --orange:         #C05A00;
  --orange-dim:     rgba(192,90,0,0.10);
  --orange-border:  rgba(192,90,0,0.24);
  --red:            #CC2020;
  --red-dim:        rgba(204,32,32,0.10);
  --grid-line:      rgba(0,106,255,0.06);
  --scan-line:      rgba(0,106,255,0.05);
  --row-hover:      rgba(0,106,255,0.05);
  --row-active:     rgba(0,106,255,0.10);
  --shadow:         rgba(10,20,40,0.12);
  --glow:           rgba(0,106,255,0.20);
}

/* ── Dark theme — Cyberpunk void ── */
[data-theme="dark"] {
  --bg:             #06080F;
  --bg-secondary:   #090D18;
  --surface:        rgba(10,14,26,0.95);
  --surface-2:      #0C1122;
  --surface-panel:  rgba(8,11,22,0.82);
  --border:         rgba(0,212,140,0.18);
  --border-subtle:  rgba(0,212,140,0.08);
  --border-hover:   rgba(0,240,165,0.42);
  --text-primary:   #C8E8F2;
  --text-secondary: #5E8AA8;
  --text-muted:     #304858;
  --text:           var(--text-primary);
  --muted:          var(--text-muted);
  --accent:         #00D48A;
  --accent-strong:  #00F0A8;
  --accent-dim:     rgba(0,212,138,0.10);
  --green:          #00D48A;
  --green-dim:      rgba(0,212,138,0.10);
  --green-border:   rgba(0,212,138,0.28);
  --blue:           #00C8F5;
  --blue-dim:       rgba(0,200,245,0.10);
  --blue-border:    rgba(0,200,245,0.28);
  --purple:         #B090F8;
  --purple-dim:     rgba(176,144,248,0.12);
  --purple-border:  rgba(176,144,248,0.28);
  --orange:         #F0A030;
  --orange-dim:     rgba(240,160,48,0.11);
  --orange-border:  rgba(240,160,48,0.28);
  --red:            #FF4466;
  --red-dim:        rgba(255,68,102,0.12);
  --grid-line:      rgba(0,200,245,0.05);
  --scan-line:      rgba(0,212,138,0.06);
  --row-hover:      rgba(0,212,138,0.05);
  --row-active:     rgba(0,212,138,0.11);
  --shadow:         rgba(0,0,0,0.85);
  --glow:           rgba(0,212,138,0.32);
  --glow-blue:      rgba(0,200,245,0.24);
}

body {
  font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, 'Cascadia Code', monospace;
  background:
    linear-gradient(90deg, var(--grid-line) 1px, transparent 1px),
    linear-gradient(0deg, var(--grid-line) 1px, transparent 1px),
    linear-gradient(180deg, var(--scan-line), transparent 28%),
    var(--bg);
  background-size: 32px 32px, 32px 32px, 100% 100%, auto;
  color: var(--text-primary);
  font-size: 13px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}
body::after {
  content: '';
  position: fixed;
  inset: 0;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(0,0,0,0.018) 2px,
    rgba(0,0,0,0.018) 3px
  );
  pointer-events: none;
  z-index: 9998;
}
[data-theme="dark"] body::after {
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(0,0,0,0.055) 2px,
    rgba(0,0,0,0.055) 3px
  );
}

html, body { height: 100%; overflow: hidden; }
.app {
  width: 100%;
  max-width: 1600px;
  margin: 0 auto;
  padding: 6px 16px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  height: 100vh;
}

/* ── Header ── */
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 10px;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  background: var(--surface-panel);
  box-shadow: 0 10px 32px -28px var(--shadow), inset 0 1px 0 rgba(255,255,255,0.08);
  backdrop-filter: blur(12px);
}
[data-theme="dark"] .app-header {
  border-color: rgba(0,212,138,0.20);
  box-shadow: 0 0 0 1px rgba(0,212,138,0.06), 0 8px 32px -16px rgba(0,0,0,0.9), inset 0 1px 0 rgba(0,212,138,0.05);
}

.logo { display: flex; align-items: center; gap: 8px; }
.header-spacer { flex: 1; }
.stat-sep { color: var(--text-muted); }
h1 {
  font-family: 'Orbitron', ui-monospace, SFMono-Regular, monospace;
  font-size: 12px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: 0.10em;
  text-transform: uppercase;
}
[data-theme="dark"] h1 {
  color: var(--accent);
  text-shadow: 0 0 14px rgba(0,212,138,0.45);
}

.stats-row { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; }
.stat-total { font-size: 11px; color: var(--text-muted); margin-right: 2px; }

.badge {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 1px 6px 1px 5px; border-radius: 20px;
  font-size: 10px; font-weight: 500; border: 1px solid transparent;
  white-space: nowrap;
}
.badge strong { font-weight: 700; }
.badge-dot { width: 5px; height: 5px; border-radius: 50%; }

.badge.feedback { background: var(--green-dim); color: var(--green); border-color: var(--green-border); }
.badge.feedback .badge-dot { background: var(--green); }
.badge.project { background: var(--blue-dim); color: var(--blue); border-color: var(--blue-border); }
.badge.project .badge-dot { background: var(--blue); }
.badge.user { background: var(--purple-dim); color: var(--purple); border-color: var(--purple-border); }
.badge.user .badge-dot { background: var(--purple); }
.badge.reference { background: var(--orange-dim); color: var(--orange); border-color: var(--orange-border); }
.badge.reference .badge-dot { background: var(--orange); }

.header-actions { display: flex; align-items: center; gap: 8px; }

.btn-theme {
  display: flex; align-items: center; justify-content: center;
  width: 30px; height: 30px;
  background: var(--surface-panel); color: var(--text-secondary);
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  cursor: pointer; transition: background var(--transition), color var(--transition), border-color var(--transition), box-shadow var(--transition);
}
.btn-theme:hover { background: var(--surface-2); color: var(--accent); border-color: var(--border-hover); box-shadow: 0 0 0 3px var(--accent-dim); }
.btn-theme:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

.btn-refresh {
  display: inline-flex; align-items: center; gap: 6px;
  background: var(--surface-panel); color: var(--text-secondary);
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  padding: 6px 12px; font-size: 12px; cursor: pointer;
  transition: background var(--transition), color var(--transition), border-color var(--transition), box-shadow var(--transition);
  white-space: nowrap;
}
.btn-refresh:hover { background: var(--surface-2); color: var(--accent); border-color: var(--border-hover); box-shadow: 0 0 0 3px var(--accent-dim); }
.btn-refresh:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

@keyframes spin { to { transform: rotate(360deg); } }
.spinning { animation: spin 0.7s linear infinite; }

/* ── Toolbar ── */
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 10px;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  background: var(--surface-panel);
  backdrop-filter: blur(12px);
}
[data-theme="dark"] .toolbar {
  border-color: rgba(0,212,138,0.12);
  box-shadow: inset 0 1px 0 rgba(0,212,138,0.04);
}

.filter-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
}
.filter-project-wrap {
  display: flex;
  align-items: center;
  gap: 5px;
  flex-shrink: 0;
}
.filter-at {
  font-size: 12px;
  color: var(--text-muted);
  font-weight: 600;
  letter-spacing: -0.02em;
  user-select: none;
}
.project-select {
  background: none;
  border: none;
  border-bottom: 1px solid var(--border);
  color: var(--text-primary);
  font-family: inherit;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  padding: 2px 18px 2px 0;
  outline: none;
  appearance: none;
  -webkit-appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%23888' stroke-width='1.4' stroke-linecap='round' stroke-linejoin='round' fill='none'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 2px center;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: border-color var(--transition), color var(--transition);
}
.project-select:focus { border-bottom-color: var(--accent); }
.project-select option { background: var(--surface); color: var(--text-primary); }
.filter-sep-v {
  width: 1px;
  height: 16px;
  background: var(--border-subtle);
  flex-shrink: 0;
}
.type-tabs {
  display: flex;
  align-items: stretch;
  gap: 0;
  border-bottom: 1px solid var(--border-subtle);
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: none;
  min-width: 0;
}
.type-tabs::-webkit-scrollbar { display: none; }
.type-tab {
  padding: 3px 10px 5px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.10em;
  text-transform: uppercase;
  color: var(--text-muted);
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  position: relative;
  bottom: -1px;
  transition: color 120ms ease, border-color 120ms ease;
  flex-shrink: 0;
  white-space: nowrap;
  font-family: inherit;
}
.type-tab:hover { color: var(--text-secondary); }
.type-tab.active { color: var(--accent); border-bottom-color: var(--accent); }
.type-tab-feedback.active { color: var(--green); border-bottom-color: var(--green); }
.type-tab-project.active { color: var(--blue); border-bottom-color: var(--blue); }
.type-tab-user.active { color: var(--purple); border-bottom-color: var(--purple); }
.type-tab-reference.active { color: var(--orange); border-bottom-color: var(--orange); }

.toolbar-right {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex: 0 0 auto;
  min-width: 0;
}

.search-wrap {
  display: flex; align-items: center; gap: 8px;
  background: var(--surface-panel); border: 1px solid var(--border);
  border-radius: var(--radius-sm); padding: 5px 10px;
  min-width: 160px; max-width: 240px;
  transition: border-color var(--transition), box-shadow var(--transition);
}
.search-wrap:focus-within { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-dim); }
.search-input {
  background: none; border: none; outline: none;
  color: var(--text-primary); font-size: 12px; width: 100%;
}
.search-input::placeholder { color: var(--text-muted); }

/* ── Table ── */
.table-wrap {
  border: 1px solid var(--border); border-radius: var(--radius-lg);
  overflow: hidden; overflow-x: auto;
  flex: 1; overflow-y: auto; min-height: 0;
  background: var(--surface-panel);
  box-shadow: 0 18px 48px -36px var(--shadow), inset 0 1px 0 rgba(255,255,255,0.06);
  backdrop-filter: blur(12px);
}
[data-theme="dark"] .table-wrap {
  border-color: rgba(0,212,138,0.16);
  box-shadow: 0 0 0 1px rgba(0,212,138,0.05), 0 18px 48px -36px rgba(0,0,0,0.95);
}

table { width: 100%; border-collapse: collapse; table-layout: fixed; }

thead { position: sticky; top: 0; z-index: 2; background: var(--surface); box-shadow: 0 1px 0 var(--border), 0 10px 22px -18px var(--shadow); }
th {
  padding: 5px 10px; text-align: left;
  color: var(--text-muted); font-weight: 600; font-size: 10.5px;
  text-transform: uppercase; letter-spacing: 0.07em;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
  font-family: 'JetBrains Mono', ui-monospace, monospace;
}
.th-inner {
  display: inline-flex; align-items: center; gap: 5px;
}
[data-theme="dark"] th {
  color: var(--accent);
  opacity: 0.55;
  border-bottom-color: rgba(0,212,138,0.18);
}

tbody tr {
  transition: background var(--transition), box-shadow var(--transition);
  cursor: pointer;
}
tbody tr:hover td { background: var(--row-hover); }
tbody tr.active td { background: var(--row-active) !important; }
tbody tr.active:hover td { background: var(--row-active) !important; }

/* Type-colored left accent stripe */
tbody tr.type-feedback td.col-check { border-left: 3px solid var(--green); }
tbody tr.type-project td.col-check { border-left: 3px solid var(--blue); }
tbody tr.type-user td.col-check { border-left: 3px solid var(--purple); }
tbody tr.type-reference td.col-check { border-left: 3px solid var(--orange); }
[data-theme="dark"] tbody tr.type-feedback td.col-check { box-shadow: inset 3px 0 8px -2px rgba(0,212,138,0.35); }
[data-theme="dark"] tbody tr.type-project td.col-check { box-shadow: inset 3px 0 8px -2px rgba(0,200,245,0.35); }
[data-theme="dark"] tbody tr.type-user td.col-check { box-shadow: inset 3px 0 8px -2px rgba(176,144,248,0.35); }
[data-theme="dark"] tbody tr.type-reference td.col-check { box-shadow: inset 3px 0 8px -2px rgba(240,160,48,0.35); }
/* Row hover — glow left line */
[data-theme="dark"] tbody tr.type-feedback:hover td { box-shadow: none; }
[data-theme="dark"] tbody tr.type-feedback:hover td.col-check { box-shadow: inset 3px 0 12px -1px rgba(0,212,138,0.6); }
[data-theme="dark"] tbody tr.type-project:hover td.col-check { box-shadow: inset 3px 0 12px -1px rgba(0,200,245,0.6); }
[data-theme="dark"] tbody tr.type-user:hover td.col-check { box-shadow: inset 3px 0 12px -1px rgba(176,144,248,0.6); }
[data-theme="dark"] tbody tr.type-reference:hover td.col-check { box-shadow: inset 3px 0 12px -1px rgba(240,160,48,0.6); }

td {
  padding: 4px 10px;
  border-bottom: 1px solid var(--border-subtle);
  vertical-align: middle;
  text-align: left;
}
tbody tr:last-child td { border-bottom: none; }

/* Type tags */
.tag {
  display: inline-block; padding: 2px 8px;
  border-radius: 20px; font-size: 11px; font-weight: 600;
  letter-spacing: 0.02em; border: 1px solid transparent;
}
.tag.feedback { background: var(--green-dim); color: var(--green); border-color: var(--green-border); }
.tag.project   { background: var(--blue-dim);   color: var(--blue);   border-color: var(--blue-border); }
.tag.user      { background: var(--purple-dim); color: var(--purple); border-color: var(--purple-border); }
.tag.reference { background: var(--orange-dim); color: var(--orange); border-color: var(--orange-border); }
[data-theme="dark"] .tag.feedback { box-shadow: 0 0 8px rgba(0,212,138,0.20); }
[data-theme="dark"] .tag.project   { box-shadow: 0 0 8px rgba(0,200,245,0.20); }
[data-theme="dark"] .tag.user      { box-shadow: 0 0 8px rgba(176,144,248,0.20); }
[data-theme="dark"] .tag.reference { box-shadow: 0 0 8px rgba(240,160,48,0.20); }

.project-cell { max-width: 180px; }
.type-col { }
.plain-cell-text {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-secondary);
  font-size: 12px;
}
.source-col { text-align: center; }
.source-badge {
  display: inline-flex; align-items: center; justify-content: center;
  width: 20px; height: 20px; cursor: default;
}
.source-icon { width: 15px; height: 15px; display: block; opacity: 0.95; }
.name {
  font-weight: 600; max-width: 180px; color: var(--text-primary);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
[data-theme="dark"] .name { color: #D8F0FA; }
[data-theme="dark"] tbody tr:hover .name { color: #fff; }
.desc {
  color: var(--text-secondary); max-width: 320px;
  display: -webkit-box; -webkit-line-clamp: 1; -webkit-box-orient: vertical;
  overflow: hidden; line-height: 1.45;
}

/* Importance */
.imp { display: flex; align-items: center; gap: 8px; }
.imp-track {
  width: 36px; height: 4px; background: var(--border);
  border-radius: 2px; overflow: hidden; flex-shrink: 0;
}
.imp-fill {
  height: 100%; border-radius: 2px;
  background: linear-gradient(90deg, var(--accent), var(--accent-strong));
  transition: width 300ms ease;
}
[data-theme="dark"] .imp-fill {
  box-shadow: 0 0 6px var(--accent);
}
.imp-num { color: var(--text-secondary); font-size: 12px; font-variant-numeric: tabular-nums; }

/* Hit count */
.hit { text-align: center; }
.hit-pill {
  display: inline-block; background: var(--blue-dim); color: var(--blue);
  border: 1px solid var(--blue-border);
  padding: 2px 8px; border-radius: 4px;
  font-size: 12px; font-weight: 600; font-variant-numeric: tabular-nums;
  min-width: 28px; text-align: center;
  font-family: 'JetBrains Mono', ui-monospace, monospace;
}
[data-theme="dark"] .hit-pill {
  box-shadow: 0 0 8px rgba(0,200,245,0.25);
}
.hit-num {
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-size: 12px;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}
[data-theme="dark"] .hit-num { color: rgba(0,200,245,0.7); }
.hit-zero { color: var(--text-muted); }

.date { color: var(--text-muted); white-space: nowrap; font-size: 12px; font-variant-numeric: tabular-nums; }

.sortable { cursor: pointer; user-select: none; }
.sortable:hover { color: var(--text-secondary); }
.sort-icon { display: inline-block; margin-left: 3px; color: var(--accent); }

/* Sticky right columns */
.col-hits    { position: sticky; right: 176px; }
.col-updated { position: sticky; right: 80px; }
.col-actions { position: sticky; right: 0; }
thead .col-hits, thead .col-updated, thead .col-actions {
  z-index: 3; background: var(--surface);
}
td.col-hits, td.col-updated, td.col-actions {
  z-index: 1; background: var(--surface-panel);
  box-shadow: -1px 0 0 var(--border-subtle);
}
td.col-hits { box-shadow: -2px 0 0 var(--border-subtle); }
tbody tr:hover td.col-hits,
tbody tr:hover td.col-updated,
tbody tr:hover td.col-actions { background: var(--row-hover); }
tbody tr.active td.col-hits,
tbody tr.active td.col-updated,
tbody tr.active td.col-actions { background: var(--row-active) !important; }

/* Delete button */
.btn-edit-quick {
  display: flex; align-items: center; justify-content: center;
  width: 26px; height: 26px; background: none;
  border: 1px solid transparent; border-radius: var(--radius-sm);
  color: var(--text-muted); cursor: pointer;
  transition: background var(--transition), color var(--transition), border-color var(--transition);
  opacity: 0; flex-shrink: 0;
}
tr:hover .btn-edit-quick { opacity: 1; }
.btn-edit-quick:hover { background: var(--accent-dim); color: var(--accent); border-color: var(--blue-border); }
.btn-edit-quick:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; opacity: 1; }
.btn-del {
  display: flex; align-items: center; justify-content: center;
  width: 26px; height: 26px; background: none;
  border: 1px solid transparent; border-radius: var(--radius-sm);
  color: var(--text-muted); cursor: pointer;
  transition: background var(--transition), color var(--transition), border-color var(--transition);
  opacity: 0; flex-shrink: 0;
}
tr:hover .btn-del { opacity: 1; }
.btn-del:hover { background: var(--red-dim); color: var(--red); border-color: rgba(207,34,46,0.25); }
[data-theme="dark"] .btn-del:hover { border-color: rgba(248,81,73,0.3); }
.btn-del:focus-visible { outline: 2px solid var(--red); outline-offset: 2px; opacity: 1; }
.btn-clone-quick {
  display: flex; align-items: center; justify-content: center;
  width: 26px; height: 26px; background: none;
  border: 1px solid transparent; border-radius: var(--radius-sm);
  color: var(--text-muted); cursor: pointer;
  transition: background var(--transition), color var(--transition), border-color var(--transition);
  opacity: 0; flex-shrink: 0;
}
tr:hover .btn-clone-quick { opacity: 1; }
.btn-clone-quick:hover { background: var(--accent-dim); color: var(--accent); border-color: var(--blue-border); }
.btn-clone-quick:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; opacity: 1; }
.modal-clone { width: 420px; }
.clone-modal-body {
  padding: 14px 16px;
  gap: 14px;
}
.clone-source-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface-2);
}
.clone-source-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.clone-source-project {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-muted);
  font-size: 11px;
}
.clone-source-name {
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 600;
  line-height: 1.4;
  word-break: break-word;
}
.clone-source-desc {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.clone-target-row {
  align-items: flex-start;
}
.clone-target-row .field-label {
  padding-top: 7px;
}
.clone-status {
  border-radius: var(--radius-sm);
  padding: 8px 10px;
  font-size: 12px;
  line-height: 1.4;
}
.clone-status.ok {
  color: var(--green);
  background: var(--green-dim);
}
.clone-status.err {
  color: var(--red);
  background: var(--red-dim);
}

.detail {
  padding: 0;
  display: flex; flex-direction: column; gap: 8px;
}
.detail-summary {
  display: grid;
  grid-template-columns: minmax(180px, 0.35fr) minmax(260px, 1fr);
  gap: 8px;
}
.detail-summary-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.detail-summary-text {
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.5;
  background: var(--bg);
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-subtle);
  overflow-wrap: anywhere;
}
.content-block { display: flex; flex-direction: column; gap: 4px; }
.detail-modal-body {
  max-height: min(72vh, 760px);
  padding: 14px;
}

.block-label {
  display: flex; align-items: center; gap: 6px;
  font-size: 10px; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.08em; color: var(--text-muted);
}
.block-label::before {
  content: ''; display: inline-block;
  width: 2px; height: 10px; border-radius: 1px;
  background: var(--accent); flex-shrink: 0;
}
.detail-hero {
  padding-bottom: 14px;
  border-bottom: 1px solid var(--border-subtle);
}
.detail-hero-name {
  font-size: 15px; font-weight: 700; color: var(--text-primary);
  line-height: 1.4; margin-bottom: 5px; overflow-wrap: anywhere;
}
.detail-hero-desc {
  font-size: 12px; color: var(--text-muted); line-height: 1.55;
}
.meta-strip {
  display: flex; flex-wrap: wrap; align-items: center;
  gap: 4px 0; font-size: 11px; color: var(--text-muted);
  padding-top: 10px; border-top: 1px solid var(--border-subtle);
}
.meta-ids { margin-top: 4px; }
.meta-ids-toggle {
  font-size: 10px; color: var(--text-muted); cursor: pointer;
  user-select: none; list-style: none; display: flex; align-items: center; gap: 4px;
}
.meta-ids-toggle::-webkit-details-marker { display: none; }
.meta-ids-toggle::before { content: '▸'; font-size: 9px; }
details[open] > .meta-ids-toggle::before { content: '▾'; }
.meta-ids-body {
  display: flex; flex-wrap: wrap; align-items: center;
  gap: 4px 0; padding-top: 4px; font-size: 11px;
}
.write-type-tabs {
  display: flex; border-bottom: 1px solid var(--border-subtle);
  margin: 0 -16px 8px; padding: 0 16px;
}

pre {
  white-space: pre-wrap; word-break: break-word;
  color: var(--text-primary); font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', ui-monospace, monospace;
  font-size: 12px; line-height: 1.6;
  background: var(--bg); padding: 10px 12px;
  border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);
}

.md-body {
  color: var(--text-secondary); font-size: 13px; line-height: 1.75;
  background: var(--bg); padding: 12px 14px;
  border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);
}
/* paragraphs */
.md-body p { margin: 0 0 9px; }
.md-body p:last-child { margin-bottom: 0; }

/* headings — monospace + left accent bar */
.md-body h1,.md-body h2,.md-body h3 {
  color: var(--text-primary); font-weight: 700; margin: 14px 0 6px;
  font-family: 'JetBrains Mono','Cascadia Code',ui-monospace,monospace;
  display: flex; align-items: center; gap: 8px; letter-spacing: 0.02em;
}
.md-body h1::before,.md-body h2::before,.md-body h3::before {
  content: ''; display: inline-block; flex-shrink: 0;
  background: var(--accent); border-radius: 1px;
  box-shadow: 0 0 6px var(--accent);
}
.md-body h1::before { width: 3px; height: 15px; }
.md-body h2::before { width: 3px; height: 13px; }
.md-body h3::before { width: 2px; height: 11px; opacity: 0.7; }
.md-body h1 { font-size: 15px; } .md-body h2 { font-size: 14px; } .md-body h3 { font-size: 13px; }

/* lists — tech markers */
.md-body ul { list-style: none; padding-left: 16px; margin: 6px 0 10px; }
.md-body ol { list-style-type: decimal; padding-left: 22px; margin: 6px 0 10px; color: var(--accent); }
.md-body ol li { color: var(--text-secondary); }
.md-body ul ul { margin: 2px 0 2px; }
.md-body li { margin: 4px 0; line-height: 1.65; display: list-item; position: relative; }
.md-body ul > li::before {
  content: '›'; position: absolute; left: -14px;
  color: var(--accent); font-weight: 700; font-size: 13px; line-height: 1.65;
}
.md-body ul ul > li::before { content: '·'; left: -12px; opacity: 0.6; }

/* inline code — glow */
.md-body code {
  background: var(--surface-2); border: 1px solid var(--border);
  padding: 1px 5px; border-radius: 3px;
  font-family: 'JetBrains Mono','Cascadia Code',ui-monospace,monospace;
  font-size: 11.5px; color: var(--accent-strong);
  box-shadow: 0 0 6px rgba(0,212,138,0.18);
}

/* code blocks — terminal style */
.md-body pre {
  position: relative;
  background: var(--bg-secondary, var(--bg));
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  border-radius: 5px; padding: 12px 14px 10px;
  overflow-x: auto; margin: 10px 0;
  box-shadow: inset 0 0 20px rgba(0,0,0,0.15), 0 0 8px rgba(0,212,138,0.06);
}
.md-body pre::before {
  content: '● ● ●'; position: absolute; top: 6px; right: 10px;
  font-size: 8px; letter-spacing: 3px;
  color: var(--border); pointer-events: none;
}
.md-body pre code {
  background: none; border: none; padding: 0;
  color: var(--text-primary); box-shadow: none;
  font-size: 12px; line-height: 1.6;
}

/* blockquote — accent glow strip */
.md-body blockquote {
  border-left: 3px solid var(--accent);
  background: var(--accent-dim);
  padding: 7px 12px; color: var(--text-muted);
  margin: 8px 0; border-radius: 0 4px 4px 0;
  box-shadow: inset 0 0 12px rgba(0,212,138,0.04);
  font-style: italic;
}

/* strong — accent color */
.md-body strong { color: var(--accent-strong); font-weight: 700; }

/* links */
.md-body a { color: var(--accent); text-decoration: none; border-bottom: 1px solid rgba(0,212,138,0.3); }
.md-body a:hover { border-bottom-color: var(--accent); }

/* table */
.md-body table { width: 100%; border-collapse: collapse; margin: 10px 0; font-size: 12px; }
.md-body th {
  background: var(--accent-dim); color: var(--accent);
  font-family: 'JetBrains Mono',ui-monospace,monospace; font-size: 11px;
  text-transform: uppercase; letter-spacing: 0.06em;
  padding: 6px 10px; border: 1px solid var(--border); text-align: left;
}
.md-body td { padding: 5px 10px; border: 1px solid var(--border-subtle); color: var(--text-secondary); vertical-align: top; }
.md-body tr:nth-child(even) td { background: rgba(0,0,0,0.04); }

/* hr — gradient line */
.md-body hr {
  border: none; height: 1px; margin: 12px 0;
  background: linear-gradient(90deg, var(--accent), transparent);
  opacity: 0.4;
}

.meta-row {
  display: flex; align-items: center; gap: 4px; flex-wrap: wrap;
  row-gap: 4px;
}
.meta-item { font-size: 11px; color: var(--text-muted); }
.meta-item strong { color: var(--text-secondary); }
.meta-item code {
  background: var(--surface); border: 1px solid var(--border);
  padding: 0 4px; border-radius: 3px;
  font-family: ui-monospace, monospace; font-size: 11px;
  color: var(--text-secondary); word-break: break-all;
}
.meta-sep { color: var(--border); }

.copyable {
  cursor: pointer;
  transition: background var(--transition), color var(--transition);
}
.copyable:hover { background: var(--accent-dim); color: var(--accent); border-color: var(--blue-border); }

.copy-hint {
  display: inline-block; margin-left: 4px;
  font-size: 10px; color: var(--green);
  animation: fade-hint 1.5s ease forwards;
}
@keyframes fade-hint {
  0%   { opacity: 1; transform: translateY(0); }
  70%  { opacity: 1; transform: translateY(-2px); }
  100% { opacity: 0; transform: translateY(-4px); }
}

/* Empty state */
.empty td { border: none !important; }
.empty-inner {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; gap: 10px;
  padding: 28px 16px; color: var(--text-muted); font-size: 13px;
}

/* Move row */
.move-row {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding-top: 2px; border-top: 1px solid var(--border-subtle); margin-top: 2px;
}
.move-select {
  background: var(--surface); color: var(--text-primary);
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  padding: 4px 8px; font-size: 12px; cursor: pointer; min-width: 180px;
}
.btn-move {
  background: var(--accent-dim); color: var(--accent);
  border: 1px solid var(--blue-border); border-radius: var(--radius-sm);
  padding: 4px 12px; font-size: 12px; cursor: pointer;
  transition: background var(--transition);
}
.btn-move:hover:not(:disabled) { background: var(--blue-dim); }
.btn-move:disabled { opacity: 0.4; cursor: default; }

/* Reset button */
.btn-reset {
  display: inline-flex; align-items: center; gap: 5px;
  background: var(--surface-panel); color: var(--text-muted);
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  padding: 6px 10px; font-size: 12px; cursor: pointer;
  transition: background var(--transition), color var(--transition), border-color var(--transition);
  white-space: nowrap;
}
.btn-reset:hover { background: var(--red-dim); color: var(--red); border-color: var(--red); }

/* Footer & Pagination */
.footer { padding: 0 4px; }
.pagination {
  display: flex; align-items: center; justify-content: flex-end; gap: 4px;
  font-size: 12px; color: var(--text-muted);
}
.page-btn {
  background: var(--surface); color: var(--text-secondary);
  border: 1px solid var(--border); border-radius: 4px;
  width: 26px; height: 26px; display: flex; align-items: center; justify-content: center;
  cursor: pointer; font-size: 13px; transition: background var(--transition), color var(--transition);
}
.page-btn:hover:not(:disabled) { background: var(--surface-2); color: var(--text-primary); border-color: var(--border-hover); }
.page-btn:disabled { opacity: 0.35; cursor: default; }
.page-info { padding: 0 8px; font-variant-numeric: tabular-nums; white-space: nowrap; }
.page-size-select {
  background: var(--surface); color: var(--text-secondary);
  border: 1px solid var(--border); border-radius: 4px;
  padding: 3px 6px; font-size: 11px; cursor: pointer; margin-left: 8px;
}

/* Scrollbar */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }
::-webkit-scrollbar-thumb:hover { background: var(--border-hover); }
* { scrollbar-width: thin; scrollbar-color: var(--border) transparent; }
[data-theme="dark"] ::-webkit-scrollbar-thumb {
  background: rgba(0,212,138,0.22);
  box-shadow: 0 0 4px rgba(0,212,138,0.4);
}
[data-theme="dark"] ::-webkit-scrollbar-thumb:hover {
  background: rgba(0,212,138,0.5);
}
[data-theme="dark"] * { scrollbar-color: rgba(0,212,138,0.25) transparent; }

body { margin: 0; }

/* Tooltip */
.tooltip-popup {
  position: fixed;
  z-index: 9999;
  max-width: 380px;
  transform: translateY(-100%);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 7px 11px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
  pointer-events: none;
  box-shadow: 0 6px 20px var(--shadow);
}

/* Modal */
@keyframes overlay-in { from { opacity: 0; } to { opacity: 1; } }
@keyframes modal-in {
  from { opacity: 0; transform: scale(0.96) translateY(10px); }
  to   { opacity: 1; transform: scale(1)    translateY(0); }
}
.modal-overlay {
  position: fixed; inset: 0; z-index: 1000;
  background:
    linear-gradient(90deg, rgba(0,212,138,0.06) 1px, transparent 1px),
    linear-gradient(0deg, rgba(0,212,138,0.06) 1px, transparent 1px),
    rgba(2,4,10,0.66);
  background-size: 28px 28px;
  display: flex; align-items: center; justify-content: center;
  animation: overlay-in 150ms ease;
  backdrop-filter: blur(5px);
}
.modal {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-lg); width: 440px; max-width: 95vw;
  box-shadow: 0 24px 70px var(--shadow), 0 0 0 1px rgba(0,212,138,0.06), 0 0 40px -28px var(--glow);
  display: flex; flex-direction: column;
  animation: modal-in 200ms cubic-bezier(0.16, 1, 0.3, 1);
  backdrop-filter: blur(14px);
}
.modal-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 16px 12px; border-bottom: 1px solid var(--border-subtle);
  background: linear-gradient(90deg, var(--accent-dim), transparent 62%);
}
.modal-title {
  font-family: 'Orbitron', ui-monospace, SFMono-Regular, monospace;
  font-size: 12px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.modal-close {
  display: flex; align-items: center; justify-content: center;
  width: 22px; height: 22px; background: none; border: none;
  color: var(--text-muted); cursor: pointer; border-radius: 4px;
  transition: background var(--transition), color var(--transition);
}
.modal-close:hover { background: var(--red-dim); color: var(--red); }
.settings-tabs { display: flex; border-bottom: 1px solid var(--border); padding: 0 12px; background: var(--surface-panel); }
.settings-tab { padding: 8px 14px; font-size: 12px; font-weight: 500; color: var(--muted); background: transparent; border: none; border-bottom: 2px solid transparent; cursor: pointer; margin-bottom: -1px; transition: color 0.15s, border-color 0.15s; }
.settings-tab:hover { color: var(--text); }
.settings-tab.active { color: var(--accent); border-bottom-color: var(--accent); }
.backup-tab-body { padding: 16px; display: flex; flex-direction: column; gap: 20px; }
.backup-desc { font-size: 12px; color: var(--muted); margin: 0 0 10px; }
.backup-action-btn { display: inline-flex; align-items: center; gap: 6px; padding: 7px 14px; }
.modal-body { padding: 12px; display: flex; flex-direction: column; gap: 12px; overflow-y: auto; max-height: calc(90vh - 120px); }
.settings-group { display: flex; flex-direction: column; gap: 8px; }
.settings-group-title {
  font-size: 10px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.06em; color: var(--text-muted);
}
.field-row { display: flex; align-items: center; gap: 8px; }
.field-label { font-size: 12px; color: var(--text-secondary); width: 80px; flex-shrink: 0; cursor: help; }
.field-input {
  flex: 1; background: var(--surface-panel); color: var(--text-primary);
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  padding: 6px 9px; font-size: 12px; outline: none;
  transition: border-color var(--transition), box-shadow var(--transition), background var(--transition);
}
.field-input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-dim); background: var(--surface); }
.field-input::placeholder { color: var(--text-muted); }
.modal-footer {
  display: flex; align-items: center; justify-content: flex-end; gap: 8px;
  padding: 12px 16px; border-top: 1px solid var(--border-subtle);
}
.save-hint { font-size: 12px; margin-right: auto; }
.save-hint.ok { color: var(--green); }
.save-hint.err { color: var(--red); }
.btn-cancel {
  background: var(--surface-panel); color: var(--text-secondary);
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  padding: 5px 14px; font-size: 12px; cursor: pointer;
  transition: background var(--transition), color var(--transition), border-color var(--transition);
}
.btn-cancel:hover { background: var(--surface-2); color: var(--text-primary); border-color: var(--border-hover); }
.btn-save {
  background: linear-gradient(135deg, var(--accent), var(--accent-strong)); color: #fff;
  border: none; border-radius: var(--radius-sm);
  padding: 5px 16px; font-size: 12px; cursor: pointer; font-weight: 500;
  transition: opacity var(--transition), box-shadow var(--transition), transform var(--transition);
  box-shadow: 0 0 18px -8px var(--glow);
}
.btn-save:hover:not(:disabled) { opacity: 0.9; box-shadow: 0 0 22px -6px var(--glow); transform: translateY(-1px); }
.btn-save:disabled { opacity: 0.45; cursor: default; }

/* ── Scoring tab ─────────────────────────────────────────── */
.scoring-body { padding: 12px; display: flex; flex-direction: column; gap: 12px; overflow-y: auto; max-height: calc(90vh - 120px); }
.score-row { display: flex; align-items: center; gap: 8px; margin: 0; }
.score-lbl { font-size: 11px; color: var(--text-muted); width: 78px; flex-shrink: 0; }
.type-lbl { font-size: 11.5px; font-weight: 600; text-transform: capitalize; color: var(--text-secondary); }
.score-slider { flex: 1; height: 4px; accent-color: var(--accent); cursor: pointer; }
.score-num {
  width: 54px; text-align: right; padding: 3px 5px;
  font-size: 11px; border: 1px solid var(--border); border-radius: var(--radius-sm);
  background: var(--surface-panel); color: var(--text-primary); outline: none;
}
.score-num:focus { border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-dim); }
.score-num:disabled { opacity: 0.4; cursor: default; }
.score-slider:disabled { opacity: 0.3; cursor: default; }
.score-hint { font-size: 10px; color: var(--text-muted); padding-left: 86px; margin-top: -2px; }
.score-warn { font-size: 10.5px; color: #e05050; font-weight: 500; padding-left: 86px; margin-top: 2px; }
.weight-sum-badge { font-size: 10.5px; font-weight: 700; margin-left: 8px; padding: 1px 7px; border-radius: 20px; }
.weight-sum-badge.ok  { background: var(--accent-dim); color: var(--accent); }
.weight-sum-badge.err { background: rgba(224,80,80,0.12); color: #e05050; }
.weight-bar { display: flex; height: 16px; border-radius: 4px; overflow: hidden; gap: 1px; margin: 4px 0 2px; }
.wb-seg { display: flex; align-items: center; justify-content: center; font-size: 9.5px; font-weight: 600; color: #fff; transition: flex 0.15s; min-width: 2px; }
.wb-cosine     { background: #4a87e8; }
.wb-importance { background: #8a5bbf; }
.wb-recency    { background: #2eb87a; }
.type-bar-track { flex: 1; height: 7px; background: var(--border-subtle); border-radius: 4px; overflow: hidden; }
.type-bar-fill  { height: 100%; background: var(--accent); border-radius: 4px; transition: width 0.1s; }
.score-toggle { position: relative; display: inline-flex; align-items: center; width: 34px; height: 19px; flex-shrink: 0; }
.score-toggle input { opacity: 0; width: 0; height: 0; position: absolute; }
.score-toggle-track {
  position: absolute; inset: 0; background: var(--border); border-radius: 19px; cursor: pointer;
  transition: background 0.2s;
}
.score-toggle-thumb {
  position: absolute; height: 13px; width: 13px; left: 3px; top: 3px;
  background: #fff; border-radius: 50%; transition: transform 0.2s; pointer-events: none;
}
.score-toggle input:checked ~ .score-toggle-track { background: var(--accent); }
.score-toggle input:checked ~ .score-toggle-track .score-toggle-thumb { transform: translateX(15px); }
.score-toggle-state { font-size: 11px; color: var(--text-muted); min-width: 22px; }
.score-row.dimmed { opacity: 0.38; pointer-events: none; }

.modal-sm { width: 360px; }
.modal-edit { width: 560px; }
.modal-lg { width: 700px; }
.modal-xl { width: 860px; }

/* ── Duplicates ── */
.dup-modal-body { padding: 0; max-height: 70vh; overflow-y: auto; }
.dup-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
  background: var(--surface-panel);
}
.dup-threshold {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--text-muted);
}
.dup-threshold-slider {
  width: 180px;
  height: 24px;
  accent-color: var(--accent);
  cursor: pointer;
}
.dup-threshold-value {
  min-width: 34px;
  color: var(--text-primary);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  text-align: right;
}
.dup-refresh {
  height: 24px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface-2);
  color: var(--text-secondary);
  padding: 3px 8px;
  font-size: 11px;
  cursor: pointer;
}
.dup-refresh:hover:not(:disabled) { color: var(--text-primary); border-color: var(--border-hover); }
.dup-refresh { margin-left: auto; }
.dup-refresh:disabled { opacity: 0.5; cursor: default; }
.dup-error {
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
  color: #ef4444;
  background: rgba(239, 68, 68, 0.08);
  font-size: 12px;
}
.dup-list { display: flex; flex-direction: column; }
.dup-pair { display: grid; grid-template-columns: 1fr 72px 1fr; gap: 0; border-bottom: 1px solid var(--border); padding: 12px 16px; align-items: start; }
.dup-pair:last-child { border-bottom: none; }
.dup-side { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.dup-meta { display: flex; align-items: center; gap: 6px; margin-bottom: 2px; overflow: hidden; }
.dup-proj { font-size: 10px; color: var(--muted); font-family: monospace; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
.dup-name { font-size: 13px; font-weight: 500; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.dup-desc { font-size: 11px; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.dup-content {
  font-size: 11px;
  line-height: 1.45;
  color: var(--text-secondary);
  background: var(--bg);
  border: 1px solid var(--border-subtle);
  border-radius: 5px;
  padding: 6px 8px;
  margin: 3px 0 6px;
  max-height: 120px;
  overflow-y: auto;
  white-space: pre-wrap;
}
.btn-dup-del { align-self: flex-start; font-size: 11px; padding: 2px 8px; border: 1px solid var(--border-strong); border-radius: 4px; background: transparent; color: var(--danger, #e5534b); cursor: pointer; }
.btn-dup-del:hover { background: rgba(229,83,75,0.08); }
.dup-center { display: flex; flex-direction: column; align-items: center; justify-content: flex-start; padding-top: 4px; gap: 6px; }
.dup-sim { font-size: 13px; font-weight: 600; color: var(--accent); }
.btn-dup-skip { font-size: 10px; color: var(--muted); background: transparent; border: none; cursor: pointer; padding: 2px 4px; }
.btn-dup-skip:hover { color: var(--text); }
.dup-count { font-size: 13px; font-weight: 400; color: var(--muted); }
.field-row-inline { align-items: center; flex-direction: row; gap: 12px; }
.field-select-sm { width: 80px !important; }
.action-row { display: flex; gap: 8px; margin-top: 4px; }
.btn-edit {
  background: var(--bg-secondary); color: var(--text-secondary);
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  padding: 4px 14px; font-size: 11px; cursor: pointer; font-weight: 500;
  transition: background var(--transition), color var(--transition);
}
.btn-edit:hover { background: var(--accent-dim); color: var(--accent); border-color: var(--accent); }
.delete-modal-body {
  display: flex; flex-direction: column; align-items: center;
  gap: 10px; padding: 24px 20px 20px; text-align: center;
}
.delete-icon { color: var(--red); opacity: 0.7; }
.delete-confirm-text { font-size: 14px; font-weight: 500; color: var(--text-primary); }
.delete-confirm-text strong { color: var(--red); word-break: break-all; }
.delete-confirm-sub { font-size: 12px; color: var(--text-muted); line-height: 1.5; }
.btn-danger {
  background: var(--red); color: #fff;
  border: none; border-radius: var(--radius-sm);
  padding: 5px 16px; font-size: 12px; cursor: pointer; font-weight: 500;
  transition: opacity var(--transition);
}
.btn-danger:hover:not(:disabled) { opacity: 0.85; }
.btn-danger:disabled { opacity: 0.45; cursor: default; }

.btn-fetch-models {
  display: flex; align-items: center; justify-content: center;
  width: 26px; height: 26px; flex-shrink: 0;
  background: var(--surface-2); color: var(--text-muted);
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  cursor: pointer; transition: background var(--transition), color var(--transition);
}
.btn-fetch-models:hover:not(:disabled) { background: var(--accent-dim); color: var(--accent); border-color: var(--blue-border); }
.btn-fetch-models:disabled { opacity: 0.35; cursor: default; }


/* ── Project badge ── */
.project-badge {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 24px; height: 18px; padding: 0 4px;
  border-radius: 4px; font-size: 10px; font-weight: 700;
  letter-spacing: 0.04em; border: 1px solid transparent; cursor: default;
}
.project-badge.feedback { background: var(--green-dim); color: var(--green); border-color: var(--green-border); }
.project-badge.project  { background: var(--blue-dim);  color: var(--blue);  border-color: var(--blue-border); }
.project-badge.user     { background: var(--purple-dim); color: var(--purple); border-color: var(--purple-border); }
.project-badge.reference { background: var(--orange-dim); color: var(--orange); border-color: var(--orange-border); }

/* ── Row actions ── */
.row-actions {
  display: flex; align-items: center; justify-content: flex-end; gap: 4px;
}

/* ── Combobox ── */
.combobox-wrap {
  position: relative; flex: 1; display: flex; align-items: center;
}
.combobox-input { padding-right: 24px; }
.combobox-chevron {
  position: absolute; right: 7px; color: var(--text-muted);
  pointer-events: none; transition: transform var(--transition);
  flex-shrink: 0;
}
.combobox-chevron.open { transform: rotate(180deg); }
.combobox-dropdown {
  position: absolute; top: calc(100% + 4px); left: 0; right: 0; z-index: 200;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: 0 14px 34px var(--shadow), 0 0 28px -22px var(--glow);
  max-height: 200px; overflow-y: auto;
  padding: 4px;
  backdrop-filter: blur(12px);
}
.combobox-option {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 8px; border-radius: var(--radius-sm);
  font-size: 12px; color: var(--text-primary); cursor: pointer;
  transition: background var(--transition);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.combobox-option:hover,
.combobox-option.highlighted { background: var(--surface-2); }
.combobox-option.selected { color: var(--accent); }
/* ── Type stripe (3px colored top border inside panel) ── */
.type-stripe { height: 3px; flex-shrink: 0; }
.type-stripe.feedback { background: var(--green); }
.type-stripe.project  { background: var(--blue); }
.type-stripe.user     { background: var(--purple); }
.type-stripe.reference { background: var(--orange); }

/* ── Write / Edit modal (centered) ── */
.write-modal {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  width: 60vw; max-width: 60vw;
  max-height: 88vh;
  display: flex; flex-direction: column;
  box-shadow: 0 24px 70px var(--shadow), 0 0 0 1px rgba(0,212,138,0.06), 0 0 40px -28px var(--glow);
  animation: modal-in 200ms cubic-bezier(0.16, 1, 0.3, 1);
  overflow: hidden;
}
.write-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 16px; border-bottom: 1px solid var(--border-subtle);
  flex-shrink: 0;
  background: linear-gradient(90deg, var(--accent-dim), transparent 68%);
}
.write-title {
  font-family: ui-monospace, SFMono-Regular, 'Cascadia Code', 'Segoe UI', system-ui, sans-serif;
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
}
.write-header-right { display: flex; align-items: center; gap: 8px; }
.write-header-left { display: flex; flex-direction: column; gap: 2px; min-width: 0; flex: 1; }
.write-subtitle {
  font-size: 11px; color: var(--text-muted);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  max-width: 320px;
}
/* type-tinted header backgrounds */
.write-header.type-header-feedback { background: linear-gradient(90deg, var(--green-dim), transparent 72%); }
.write-header.type-header-project  { background: linear-gradient(90deg, var(--blue-dim),  transparent 72%); }
.write-header.type-header-user     { background: linear-gradient(90deg, var(--purple-dim), transparent 72%); }
.write-header.type-header-reference { background: linear-gradient(90deg, var(--orange-dim), transparent 72%); }
/* detail modal — centered, wider */
.detail-modal {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  width: 60vw; max-width: 60vw;
  max-height: 88vh;
  display: flex; flex-direction: column;
  box-shadow: 0 24px 70px var(--shadow), 0 0 0 1px rgba(0,212,138,0.06), 0 0 40px -28px var(--glow);
  animation: modal-in 200ms cubic-bezier(0.16, 1, 0.3, 1);
  overflow: hidden;
}
.detail-modal-body {
  flex: 1; overflow-y: auto;
  padding: 0 20px 20px;
}
/* inline edit button in panel header */
.btn-header-edit {
  background: transparent; color: var(--text-muted);
  border: none; border-radius: var(--radius-sm);
  padding: 4px; display: flex; align-items: center; justify-content: center;
  cursor: pointer;
  transition: color var(--transition), background var(--transition);
}
.btn-header-edit:hover { color: var(--accent); background: var(--accent-dim); }
.kbd-hint {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 18px; height: 18px; padding: 0 4px;
  background: var(--surface-2); border: 1px solid var(--border);
  border-radius: 4px; font-size: 10px; font-weight: 600;
  color: var(--text-muted); font-family: ui-monospace, monospace;
}
.write-body {
  flex: 1; overflow-y: auto; padding: 16px;
  display: flex; flex-direction: column; gap: 12px; min-height: 0;
}
.write-section { display: flex; flex-direction: column; gap: 4px; }
.write-section-grow { flex: 1; }
.write-section-row { flex-direction: row; gap: 12px; align-items: flex-start; }
.write-section-half { flex: 1; display: flex; flex-direction: column; gap: 4px; }
.write-section-label {
  font-size: 10px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.06em; color: var(--text-muted); margin-bottom: 2px;
}
.write-field-label {
  font-size: 11px; color: var(--text-muted); font-weight: 500;
}
.write-input {
  background: var(--surface-panel); color: var(--text-primary);
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  padding: 6px 9px; font-size: 12px; outline: none; width: 100%;
  transition: border-color var(--transition), box-shadow var(--transition), background var(--transition);
  font-family: inherit;
}
.write-input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-dim); background: var(--surface); }
.write-input::placeholder { color: var(--text-muted); }
.write-textarea { resize: vertical; min-height: 100px; line-height: 1.6; }
.write-select { cursor: pointer; }

.write-type-pills { display: flex; gap: 6px; flex-wrap: wrap; }
.write-type-pill {
  padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: 600;
  border: 1px solid var(--border); background: var(--surface-panel);
  color: var(--text-muted); cursor: pointer;
  transition: background var(--transition), color var(--transition), border-color var(--transition), box-shadow var(--transition);
}
.write-type-pill:hover { border-color: var(--border-hover); color: var(--text-primary); box-shadow: 0 0 0 3px var(--accent-dim); }
.write-type-pill.active.feedback { background: var(--green-dim); color: var(--green); border-color: var(--green-border); }
.write-type-pill.active.project  { background: var(--blue-dim);   color: var(--blue);   border-color: var(--blue-border); }
.write-type-pill.active.user     { background: var(--purple-dim); color: var(--purple); border-color: var(--purple-border); }
.write-type-pill.active.reference { background: var(--orange-dim); color: var(--orange); border-color: var(--orange-border); }

.write-extra-toggle {
  display: inline-flex; align-items: center; gap: 5px;
  background: none; border: none; cursor: pointer;
  font-size: 11px; color: var(--text-muted); padding: 0;
  transition: color var(--transition);
}
.write-extra-toggle:hover { color: var(--text-secondary); }
.write-extra-chevron { transition: transform var(--transition); flex-shrink: 0; }
.write-extra-chevron.open { transform: rotate(180deg); }
.write-extra-fields { display: flex; flex-direction: column; gap: 10px; margin-top: 8px; }
.write-collapsible { display: flex; flex-direction: column; }

.write-footer {
  display: flex; align-items: center; gap: 8px;
  padding: 12px 16px; border-top: 1px solid var(--border-subtle);
  flex-shrink: 0;
}
.write-target-hint {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 11px; color: var(--text-muted); margin-right: auto;
  max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

/* ── New button ── */
.btn-new {
  display: inline-flex; align-items: center; gap: 5px;
  background: linear-gradient(135deg, var(--accent), var(--accent-strong)); color: #fff;
  border: none; border-radius: var(--radius-sm);
  padding: 5px 12px; font-size: 12px; font-weight: 500; cursor: pointer;
  transition: opacity var(--transition), box-shadow var(--transition), transform var(--transition);
  box-shadow: 0 0 18px -8px var(--glow);
  white-space: nowrap;
}
.btn-new:hover { opacity: 0.9; box-shadow: 0 0 22px -6px var(--glow); transform: translateY(-1px); }
.btn-new:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

/* ── Toolbar action buttons (Export / Import) ── */
.btn-toolbar-action {
  display: inline-flex; align-items: center; gap: 5px;
  background: var(--surface-panel); color: var(--text-secondary);
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  padding: 5px 10px; font-size: 12px; cursor: pointer;
  transition: background var(--transition), color var(--transition), border-color var(--transition), box-shadow var(--transition);
  white-space: nowrap;
}
.btn-toolbar-action:hover { background: var(--surface-2); color: var(--accent); border-color: var(--border-hover); box-shadow: 0 0 0 3px var(--accent-dim); }
.btn-toolbar-action:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.toolbar-sep { width: 1px; height: 16px; background: var(--border); flex-shrink: 0; }

/* ── Checkbox column ── */
.col-check { width: 36px; text-align: center; padding: 4px 6px; }
.row-check { width: 14px; height: 14px; cursor: pointer; accent-color: var(--accent); opacity: 0; transition: opacity 0.1s; }
tr:hover .row-check,
tr.selected .row-check { opacity: 1; }
th.col-check:hover .row-check,
th.col-check.has-selection .row-check { opacity: 1; }

/* ── Selected row ── */
tbody tr.selected td { background: var(--row-active); }
tbody tr.selected td.col-hits,
tbody tr.selected td.col-updated,
tbody tr.selected td.col-actions { background: var(--row-active); }
tbody tr.selected:hover td { background: var(--row-hover); }
tbody tr.selected:hover td.col-hits,
tbody tr.selected:hover td.col-updated,
tbody tr.selected:hover td.col-actions { background: var(--row-hover); }

/* ── Bulk action bar ── */
.bulk-bar {
  position: fixed; bottom: 40px; left: 50%; transform: translateX(-50%);
  display: flex; align-items: center; gap: 8px;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-lg); padding: 8px 16px;
  box-shadow: 0 18px 46px var(--shadow), 0 0 32px -18px var(--glow);
  z-index: 900; white-space: nowrap;
  backdrop-filter: blur(14px);
}
.bulk-enter-active, .bulk-leave-active { transition: opacity 150ms ease, transform 150ms ease; }
.bulk-enter-from { opacity: 0; transform: translateX(-50%) translateY(12px); }
.bulk-leave-to  { opacity: 0; transform: translateX(-50%) translateY(12px); }
.bulk-count { font-size: 12px; font-weight: 600; color: var(--text-primary); }
.bulk-clear {
  display: flex; align-items: center; justify-content: center;
  width: 18px; height: 18px; background: none; border: none;
  color: var(--text-muted); cursor: pointer; font-size: 14px; border-radius: 3px;
  transition: background var(--transition), color var(--transition);
}
.bulk-clear:hover { background: var(--surface-2); color: var(--text-primary); }
.bulk-sep { color: var(--border); font-size: 16px; }
.bulk-btn {
  background: var(--surface-2); color: var(--text-secondary);
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  padding: 4px 12px; font-size: 12px; cursor: pointer;
  transition: background var(--transition), color var(--transition);
}
.bulk-btn:hover:not(:disabled) { background: var(--bg); color: var(--text-primary); }
.bulk-btn:disabled { opacity: 0.4; cursor: default; }
.bulk-btn-danger:hover:not(:disabled) { background: var(--red-dim); color: var(--red); border-color: var(--red); }
.bulk-confirm-text { font-size: 12px; color: var(--text-secondary); }
.bulk-move-select {
  background: var(--surface); color: var(--text-primary);
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  padding: 4px 8px; font-size: 12px; cursor: pointer; max-width: 160px;
}

/* ── Login modal ── */
.login-overlay { background: var(--bg); }
.login-modal {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 36px 32px 28px;
  width: 360px;
  max-width: 90vw;
  display: flex; flex-direction: column; gap: 16px;
  box-shadow: 0 8px 32px var(--shadow);
}
.login-logo { display: flex; align-items: center; gap: 10px; }
.login-title { font-family: 'Orbitron', sans-serif; font-weight: 700; font-size: 15px; color: var(--text-primary); letter-spacing: 0.02em; }
.login-subtitle { font-size: 12px; color: var(--text-secondary); margin: 0; }
.login-form { display: flex; flex-direction: column; gap: 10px; }
.login-input {
  background: var(--surface-2); color: var(--text-primary);
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  padding: 9px 12px; font-size: 13px; font-family: 'JetBrains Mono', monospace;
  outline: none; width: 100%;
  transition: border-color var(--transition);
}
.login-input:focus { border-color: var(--accent); }
.login-error { font-size: 12px; color: var(--red); }
.login-btn {
  background: var(--accent); color: #fff;
  border: none; border-radius: var(--radius-sm);
  padding: 9px 16px; font-size: 13px; cursor: pointer;
  display: flex; align-items: center; justify-content: center; gap: 6px;
  transition: opacity var(--transition);
}
.login-btn:hover:not(:disabled) { opacity: 0.88; }
.login-btn:disabled { opacity: 0.4; cursor: default; }
.login-actions { display: flex; gap: 8px; }
.login-actions .login-btn { flex: 1; }
.login-skip {
  background: transparent; color: var(--text-secondary);
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  padding: 9px 14px; font-size: 12px; cursor: pointer;
  transition: background var(--transition), color var(--transition);
  white-space: nowrap;
}
.login-skip:hover:not(:disabled) { background: var(--surface-2); color: var(--text-primary); }
.login-skip:disabled { opacity: 0.4; cursor: default; }
.btn-logout { color: var(--text-muted); }
.btn-logout:hover { color: var(--red) !important; }

/* ── Import progress ── */
.import-progress-bar {
  width: 100%; height: 4px; background: var(--border);
  border-radius: 2px; overflow: hidden; margin-top: 8px;
}
.import-progress-fill {
  height: 100%; background: var(--accent); border-radius: 2px;
  transition: width 100ms linear;
}

/* ── Admin page ── */
.admin-modal {
  width: min(900px, 96vw);
  max-width: min(900px, 96vw);
  /* 不设 max-height，让弹窗自然撑开，无需滚动条 */
  display: flex; flex-direction: column;
}
.admin-modal-body {
  overflow: visible; padding: 0;
}
.admin-section {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  box-shadow: 0 2px 16px var(--shadow);
}
.admin-section-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px; border-bottom: 1px solid var(--border-subtle);
  background: var(--surface-panel);
}
.admin-section-title {
  display: flex; align-items: center; gap: 7px;
  font-family: ui-monospace, monospace; font-size: 12px; font-weight: 700;
  color: var(--text-primary); letter-spacing: 0.06em; text-transform: uppercase;
}
.admin-create-form {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 16px; border-bottom: 1px solid var(--border-subtle);
  background: var(--bg-secondary);
}
.admin-select, .admin-input {
  background: var(--surface-2); color: var(--text-primary);
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  padding: 6px 10px; font-size: 12px; outline: none;
  transition: border-color var(--transition);
}
.admin-select:focus, .admin-input:focus { border-color: var(--accent); }
.admin-input { flex: 1; }
.admin-create-btn { padding: 6px 14px; font-size: 12px; }
.admin-new-token-banner {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  padding: 10px 16px; border-bottom: 1px solid var(--border-subtle);
  background: var(--green-dim); border-left: 3px solid var(--green);
}
.admin-new-token-label { font-size: 11px; color: var(--text-muted); white-space: nowrap; }
.admin-new-token-value {
  font-family: ui-monospace, monospace; font-size: 12px;
  background: var(--surface); border: 1px solid var(--border);
  padding: 3px 8px; border-radius: var(--radius-sm);
  color: var(--text-primary); word-break: break-all;
}
.admin-dismiss { padding: 4px 10px; font-size: 11px; margin-left: auto; }
.admin-table {
  width: 100%; border-collapse: collapse; font-size: 12px;
  table-layout: fixed;
}
.admin-table th {
  padding: 8px 14px; text-align: left;
  font-size: 10px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--text-muted); border-bottom: 1px solid var(--border-subtle);
  background: var(--surface-panel);
}
.admin-table td {
  padding: 10px 14px; border-bottom: 1px solid var(--border-subtle);
  color: var(--text-primary); vertical-align: middle;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.admin-table tr:last-child td { border-bottom: none; }
.admin-table tr:hover td { background: var(--row-hover); }
/* 各列固定比例，防止撑宽 */
.admin-table th:nth-child(1), .admin-table td:nth-child(1) { width: 110px; }
.admin-table th:nth-child(2), .admin-table td:nth-child(2) { width: auto; }
.admin-table th:nth-child(3), .admin-table td:nth-child(3) { width: 120px; white-space: nowrap; }
.admin-table th:nth-child(4), .admin-table td:nth-child(4) { width: 80px; }
.admin-table th:nth-child(5), .admin-table td:nth-child(5) { width: 90px; }
.admin-table th:nth-child(6), .admin-table td:nth-child(6) { width: 180px; white-space: nowrap; }
.admin-row-disabled td { opacity: 0.55; }
.admin-kind-badge {
  display: inline-block; padding: 2px 8px; border-radius: 20px;
  font-size: 10px; font-weight: 700; letter-spacing: 0.04em;
  font-family: ui-monospace, monospace;
}
.admin-kind-ui  { background: var(--blue-dim); color: var(--blue); border: 1px solid var(--blue-border); }
.admin-kind-mcp { background: var(--green-dim); color: var(--green); border: 1px solid var(--green-border); }
.admin-name-cell { max-width: 380px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; word-break: break-all; }
.admin-toggle {
  position: relative; display: inline-flex; align-items: center;
  width: 32px; height: 18px; border: none; border-radius: 18px;
  cursor: pointer; transition: background 0.2s; flex-shrink: 0;
  vertical-align: middle;
}
.admin-toggle-on  { background: var(--green); }
.admin-toggle-off { background: var(--border); }
.admin-toggle-knob {
  position: absolute; width: 12px; height: 12px; border-radius: 50%;
  background: #fff; transition: transform 0.2s; top: 3px; left: 3px;
  pointer-events: none;
}
.admin-toggle-on .admin-toggle-knob  { transform: translateX(14px); }
.admin-toggle-off .admin-toggle-knob { transform: translateX(0); }
.admin-status-text { margin-left: 7px; font-size: 11px; color: var(--text-muted); vertical-align: middle; }
.admin-date { color: var(--text-muted); font-size: 11px; white-space: nowrap; }
.admin-actions-cell { white-space: nowrap; }
.admin-reset,
.admin-revoke { display: inline-flex; align-items: center; gap: 4px; font-size: 11px; padding: 4px 10px; opacity: 1; }
.btn-token-revoke {
  background: none; cursor: pointer;
  border: 1px solid rgba(207,34,46,0.3); border-radius: var(--radius-sm);
  color: var(--red);
  transition: background var(--transition), border-color var(--transition);
}
.btn-token-revoke:hover { background: var(--red-dim); border-color: rgba(207,34,46,0.55); }
[data-theme="dark"] .btn-token-revoke { border-color: rgba(248,81,73,0.25); }
[data-theme="dark"] .btn-token-revoke:hover { border-color: rgba(248,81,73,0.45); }
.admin-empty { padding: 24px; text-align: center; color: var(--text-muted); font-size: 13px; }
.btn-admin { text-decoration: none; display: inline-flex; align-items: center; justify-content: center; }

</style>
