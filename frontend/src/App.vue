<template>
  <div class="app">
    <header class="app-header">
      <div class="logo">
        <svg width="18" height="18" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect width="32" height="32" rx="7" fill="#6366f1"/>
          <path d="M16 6 C13 6 11 7.5 10.5 9.5 C9 9.2 7 10 6.5 12 C5 12.5 4 14 4.5 16 C4 17.5 4.5 19.5 6 20.5 C6.5 22.5 8 24 10 24 C11 25.5 13 26 15 25.5 L15 22 C13 22 11.5 21 11 19.5 C9.5 19.5 8.5 18.5 8.5 17 C7.5 16.5 7 15.5 7.5 14.5 C7.2 13.5 8 12.5 9 12.5 C9.2 11 10.5 10 12 10.5 C12.5 9 14 8 16 8 Z" fill="#e0e7ff"/>
          <path d="M16 6 C19 6 21 7.5 21.5 9.5 C23 9.2 25 10 25.5 12 C27 12.5 28 14 27.5 16 C28 17.5 27.5 19.5 26 20.5 C25.5 22.5 24 24 22 24 C21 25.5 19 26 17 25.5 L17 22 C19 22 20.5 21 21 19.5 C22.5 19.5 23.5 18.5 23.5 17 C24.5 16.5 25 15.5 24.5 14.5 C24.8 13.5 24 12.5 23 12.5 C22.8 11 21.5 10 20 10.5 C19.5 9 18 8 16 8 Z" fill="#e0e7ff"/>
          <line x1="16" y1="8" x2="16" y2="25.5" stroke="#6366f1" stroke-width="1" opacity="0.6"/>
          <path d="M10 14 Q12 15.5 10.5 17" stroke="#818cf8" stroke-width="1" fill="none" stroke-linecap="round"/>
          <path d="M9.5 17.5 Q11.5 18.5 11 20" stroke="#818cf8" stroke-width="1" fill="none" stroke-linecap="round"/>
          <path d="M22 14 Q20 15.5 21.5 17" stroke="#818cf8" stroke-width="1" fill="none" stroke-linecap="round"/>
          <path d="M22.5 17.5 Q20.5 18.5 21 20" stroke="#818cf8" stroke-width="1" fill="none" stroke-linecap="round"/>
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
      <div class="filter-group">
        <span class="filter-label">{{ t('Project') }}</span>
        <div class="pill-group">
          <button :class="['pill', selectedProject === '' ? 'pill-active' : '']" @click="selectedProject = ''; load()">{{ t('All') }}</button>
          <button v-for="p in projects" :key="p.id"
            :class="['pill', selectedProject === p.slug ? 'pill-active' : '']"
            @click="selectedProject = p.slug; load()"
            :title="p.slug">
            {{ p.display_name || p.slug }}
            <span class="pill-count">{{ p.memory_count }}</span>
          </button>
        </div>
      </div>
      <div class="filter-group">
        <span class="filter-label">{{ t('Type') }}</span>
        <div class="pill-group">
          <button :class="['pill', selectedType === '' ? 'pill-active' : '']" @click="selectedType = ''; load()">{{ t('All') }}</button>
          <button v-for="tp in ['user','feedback','project','reference']" :key="tp"
            :class="['pill', selectedType === tp ? 'pill-active' : '']"
            @click="selectedType = tp; load()">{{ tp }}</button>
        </div>
      </div>
      <div class="toolbar-right">
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
        <button class="btn-ctx-preview" @click="openContextPreview" :title="t('Context preview')">
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <circle cx="6" cy="6" r="4.5" stroke="currentColor" stroke-width="1.2"/>
            <line x1="6" y1="4" x2="6" y2="6.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
            <circle cx="6" cy="8.2" r="0.65" fill="currentColor"/>
          </svg>
          {{ t('Context preview') }}
        </button>
      </div>
    </div>

    <div class="table-wrap">
      <table>
        <colgroup>
          <col style="width:90px">
          <col style="width:80px">
          <col style="width:160px">
          <col>
          <col style="width:64px">
          <col style="width:140px">
          <col style="width:80px">
        </colgroup>
        <thead>
          <tr>
            <th class="type-col">{{ t('Type') }}</th>
            <th>{{ t('Project') }}</th>
            <th>{{ t('Name') }}</th>
            <th>{{ t('Description') }}</th>
            <th class="sortable" @click="toggleSort('hits')">
              {{ t('Hits') }} <span class="sort-icon" v-if="sortBy === 'hits'">{{ sortDesc ? '↓' : '↑' }}</span>
            </th>
            <th class="sortable" @click="toggleSort('time')">
              {{ t('Updated') }} <span class="sort-icon" v-if="sortBy === 'time'">{{ sortDesc ? '↓' : '↑' }}</span>
            </th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <template v-for="m in paged" :key="m.id">
            <tr @click="toggle(m.id)" :class="['type-' + m.type, { active: expanded === m.id }]">
              <td class="type-col"><span :class="['tag', m.type]">{{ m.type }}</span></td>
              <td class="project-cell" @mouseenter="showTip($event, projectMap[m.project_id] || '—')" @mouseleave="hideTip">
                <span v-if="projectMap[m.project_id]" :class="['project-badge', projectColorClass(m.project_id)]">{{ projectAbbr(m.project_id) }}</span>
                <span v-else class="hit-zero">—</span>
              </td>
              <td class="name" @mouseenter="showTip($event, m.name)" @mouseleave="hideTip">{{ m.name }}</td>
              <td><div class="desc" @mouseenter="showTip($event, m.description)" @mouseleave="hideTip">{{ m.description }}</div></td>
              <td class="hit" :class="{ 'hit-active': m.hit_count > 0 }">
                <span v-if="m.hit_count > 0" class="hit-pill">{{ m.hit_count }}</span>
                <span v-else class="hit-zero">—</span>
              </td>
              <td class="date"><span :title="fmtDate(m.updated_at)">{{ relTime(m.updated_at) }}</span></td>
              <td>
                <div class="row-actions">
                  <button class="btn-edit-quick" @click.stop="openEdit(m)" :title="t('Edit')" :aria-label="t('Edit')">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                    </svg>
                  </button>
                  <button class="btn-del" @click.stop="del(m)" :title="t('Delete')" :aria-label="t('Delete')">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                      <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
                    </svg>
                  </button>
                  <svg class="row-chevron" :class="{open: expanded === m.id}" width="12" height="12" viewBox="0 0 12 12" fill="none">
                    <path d="M2.5 4.5L6 8L9.5 4.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </div>
              </td>
            </tr>
            <tr v-if="expanded === m.id" class="detail-row">
              <td colspan="7">
                <div class="detail">
                  <div class="content-block">
                    <div class="block-label">{{ t('Content') }}</div>
                    <div class="md-body" v-html="md(m.content)"></div>
                  </div>
                  <div v-if="m.why" class="content-block">
                    <div class="block-label">{{ t('Why') }}</div>
                    <div class="md-body" v-html="md(m.why)"></div>
                  </div>
                  <div v-if="m.how_to_apply" class="content-block">
                    <div class="block-label">{{ t('How to Apply') }}</div>
                    <div class="md-body" v-html="md(m.how_to_apply)"></div>
                  </div>
                  <div class="meta-row">
                    <span class="meta-item">
                      {{ t('ID:') }}
                      <code class="copyable" @click.stop="copy(m.id)" :title="t('Click to copy')">{{ m.id }}</code>
                      <span class="copy-hint" v-if="copied === m.id">{{ t('Copied') }}</span>
                    </span>
                    <span class="meta-sep">·</span>
                    <span class="meta-item">
                      {{ t('Project:') }} <code class="copyable" @click.stop="copy(m.project_id)" :title="t('Click to copy')">{{ m.project_id }}</code>
                      <span class="copy-hint" v-if="copied === m.project_id">{{ t('Copied') }}</span>
                    </span>
                    <span class="meta-sep">·</span>
                    <span class="meta-item">{{ t('Hits') }} <strong>{{ m.hit_count }}</strong></span>
                    <template v-if="m.last_hit_at">
                      <span class="meta-sep">·</span>
                      <span class="meta-item">{{ t('Last hit') }} {{ fmtDateTime(m.last_hit_at) }}</span>
                    </template>
                  </div>
                  <div class="move-row" @click.stop>
                    <span class="block-label">{{ t('Move to project') }}</span>
                    <select class="move-select" v-model="moveTarget[m.id]">
                      <option value="">{{ t('— Select project —') }}</option>
                      <option v-for="p in projects" :key="p.id" :value="p.slug">{{ p.display_name || p.slug }} ({{ p.memory_count }})</option>
                    </select>
                    <button class="btn-move" :disabled="!moveTarget[m.id] || isMoving[m.id]" @click.stop="moveMemory(m)">
                      {{ isMoving[m.id] ? t('Moving…') : t('Move') }}
                    </button>
                    <span class="copy-hint" v-if="moved === m.id">{{ t('Moved ✓') }}</span>
                    <span class="save-hint err" v-if="moveError[m.id]">{{ moveError[m.id] }}</span>
                  </div>
                  <div class="action-row" @click.stop>
                    <button class="btn-edit" @click.stop="openEdit(m)">{{ t('Edit') }}</button>
                  </div>
                </div>
              </td>
            </tr>
          </template>
          <tr v-if="paged.length === 0">
            <td colspan="7" class="empty">
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
    <div v-if="settingsOpen" class="modal-overlay">
      <div class="modal">
        <div class="modal-header">
          <span class="modal-title">{{ t('Settings') }}</span>
          <button class="modal-close" @click="settingsOpen = false">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <line x1="1" y1="1" x2="11" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              <line x1="11" y1="1" x2="1" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div class="settings-group">
            <div class="settings-group-title">{{ t('Extraction Model') }}</div>
            <label class="field-row">
              <span class="field-label" @mouseenter="showTip($event, t('OpenAI-compatible API base URL'))" @mouseleave="hideTip">{{ t('Base URL') }}</span>
              <input v-model="form.extraction_base_url" class="field-input" :placeholder="t('https://api.openai.com/v1')" />
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
              <input v-model="form.search_top_k" class="field-input" placeholder="8" />
            </label>
            <label class="field-row">
              <span class="field-label" @mouseenter="showTip($event, t('Cosine similarity threshold (0–1) above which an existing memory is considered a duplicate on save'))" @mouseleave="hideTip">{{ t('Dup threshold') }}</span>
              <input v-model="form.dup_threshold" class="field-input" placeholder="0.92" />
            </label>
            <label class="field-row">
              <span class="field-label" @mouseenter="showTip($event, t('PostgreSQL asyncpg connection string — requires service restart'))" @mouseleave="hideTip">{{ t('DB DSN') }}</span>
              <input v-model="form.db_dsn" class="field-input" :placeholder="t('postgresql+asyncpg://… (restart required)')" />
            </label>
            <label class="field-row">
              <span class="field-label" @mouseenter="showTip($event, t('HTTP port the service listens on — requires service restart'))" @mouseleave="hideTip">{{ t('HTTP port') }}</span>
              <input v-model="form.http_port" class="field-input" :placeholder="t('8765 (restart required)')" />
            </label>
          </div>
          <div class="settings-group">
            <div class="settings-group-title">{{ t('Embed Model') }}</div>
            <label class="field-row">
              <span class="field-label" @mouseenter="showTip($event, t('FastEmbed model name used to generate memory vectors'))" @mouseleave="hideTip">{{ t('Model name') }}</span>
              <input v-model="form.embed_model" class="field-input" placeholder="BAAI/bge-small-zh-v1.5" />
            </label>
            <label class="field-row">
              <span class="field-label" @mouseenter="showTip($event, t('Vector dimension — must match the chosen embed model'))" @mouseleave="hideTip">{{ t('Dimensions') }}</span>
              <input v-model="form.embed_dim" class="field-input" placeholder="512" />
            </label>
          </div>
        </div>
        <div class="modal-footer">
          <span :class="['save-hint', saveHint.startsWith('Error') ? 'err' : 'ok']" v-if="saveHint">{{ saveHint }}</span>
          <button class="btn-cancel" @click="settingsOpen = false">{{ t('Cancel') }}</button>
          <button class="btn-save" @click="saveSettings" :disabled="isSaving">{{ isSaving ? t('Saving…') : t('Save') }}</button>
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
    <div v-if="editTarget" class="modal-overlay">
      <div class="modal modal-edit">
        <div class="modal-header">
          <span class="modal-title">{{ t('Edit Memory') }}</span>
          <button class="modal-close" @click="editTarget = null">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <line x1="1" y1="1" x2="11" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              <line x1="11" y1="1" x2="1" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div class="field-row"><label class="field-label">{{ t('Name') }}</label><input class="field-input" v-model="editForm.name" /></div>
          <div class="field-row"><label class="field-label">{{ t('Description') }}</label><textarea class="field-input" v-model="editForm.description" rows="2" /></div>
          <div class="field-row"><label class="field-label">{{ t('Content') }}</label><textarea class="field-input" v-model="editForm.content" rows="6" /></div>
          <div class="field-row"><label class="field-label">{{ t('Why') }}</label><input class="field-input" v-model="editForm.why" /></div>
          <div class="field-row"><label class="field-label">{{ t('How to apply') }}</label><input class="field-input" v-model="editForm.how_to_apply" /></div>
          <div class="field-row field-row-inline">
            <label class="field-label">{{ t('Importance') }}</label>
            <select class="field-input field-select-sm" v-model.number="editForm.importance">
              <option v-for="n in [1,2,3,4,5]" :key="n" :value="n">{{ n }}</option>
            </select>
          </div>
          <p v-if="editError" class="save-hint err">{{ editError }}</p>
        </div>
        <div class="modal-footer">
          <button class="btn-cancel" @click="editTarget = null">{{ t('Cancel') }}</button>
          <button class="btn-save" :disabled="isEditSaving" @click="saveEdit">{{ isEditSaving ? t('Saving…') : t('Save') }}</button>
        </div>
      </div>
    </div>
    <div v-if="ctxPreviewOpen" class="modal-overlay">
      <div class="modal modal-lg">
        <div class="modal-header">
          <span class="modal-title">{{ t('Context preview') }}</span>
          <button class="modal-close" @click="ctxPreviewOpen = false">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <line x1="1" y1="1" x2="11" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              <line x1="11" y1="1" x2="1" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div class="ctx-preview-controls">
            <select class="field-input ctx-project-select" v-model="ctxPreviewSlug" @change="loadContextPreview">
              <option value="">{{ t('— Select project —') }}</option>
              <option v-for="p in projects" :key="p.id" :value="p.slug">
                {{ p.display_name || p.slug }}
              </option>
            </select>
          </div>
          <div v-if="!ctxPreviewSlug" class="empty-state" style="padding:32px 0">{{ t('Select a project to preview its injected context.') }}</div>
          <div v-else-if="ctxPreviewLoading" class="empty-state">{{ t('Loading…') }}</div>
          <pre v-else class="ctx-preview-pre">{{ ctxPreviewMd }}</pre>
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
const memories = ref([])
const stats = ref(null)
const selectedProject = ref('')
const selectedType = ref('')
const searchText = ref('')
const expanded = ref(null)
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
    const [mems, st] = await Promise.all([
      fetch(`${BASE}/memories?${params}`).then(r => r.json()),
      fetch(`${BASE}/stats${selectedProject.value ? '?project_slug=' + selectedProject.value : ''}`).then(r => r.json())
    ])
    memories.value = mems
    stats.value = st
  } finally {
    isLoading.value = false
  }
}

const deleteTarget = ref(null)
const isDeleting = ref(false)
function del(m) { deleteTarget.value = m }
async function confirmDelete() {
  if (!deleteTarget.value) return
  isDeleting.value = true
  try {
    await fetch(`${BASE}/memories/${deleteTarget.value.id}`, { method: 'DELETE' })
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
    const r = await fetch(`${BASE}/memories/${m.id}/move?project_slug=${encodeURIComponent(slug)}`, { method: 'PATCH' })
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
    const r = await fetch(`${BASE}/memories/${editTarget.value.id}`, {
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

const ctxPreviewOpen = ref(false)
const ctxPreviewSlug = ref('')
const ctxPreviewMd = ref('')
const ctxPreviewLoading = ref(false)
function openContextPreview() {
  ctxPreviewOpen.value = true
  ctxPreviewSlug.value = selectedProject.value || ''
  ctxPreviewMd.value = ''
  if (ctxPreviewSlug.value) loadContextPreview()
}
async function loadContextPreview() {
  const slug = ctxPreviewSlug.value
  if (!slug) return
  ctxPreviewLoading.value = true
  ctxPreviewMd.value = ''
  try {
    const r = await fetch(`${BASE}/context-preview?project_slug=${encodeURIComponent(slug)}`)
    if (!r.ok) { ctxPreviewMd.value = '(error loading context)'; return }
    const data = await r.json()
    ctxPreviewMd.value = data.markdown || '*(no memories would be injected for this project)*'
  } finally {
    ctxPreviewLoading.value = false
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

function toggleSort(col) {
  if (sortBy.value === col) { sortDesc.value = !sortDesc.value } else { sortBy.value = col; sortDesc.value = true }
  page.value = 1
  load()
}
function toggle(id) { expanded.value = expanded.value === id ? null : id }
function resetFilters() {
  selectedProject.value = ''
  selectedType.value = ''
  searchText.value = ''
  load()
}
const serverTz = ref(null)       // IANA name if available
const serverOffsetMin = ref(null) // fallback: UTC offset in minutes

function _fmt(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (serverTz.value) {
    try {
      const parts = new Intl.DateTimeFormat('sv', {
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
        hour12: false, timeZone: serverTz.value,
      }).formatToParts(d)
      const get = t => parts.find(p => p.type === t)?.value ?? ''
      return `${get('year')}-${get('month')}-${get('day')} ${get('hour')}:${get('minute')}:${get('second')}`
    } catch { /* fall through */ }
  }
  // offset_minutes fallback (works when IANA name not available, e.g. Windows)
  const off = serverOffsetMin.value
  if (off != null) {
    const shifted = new Date(d.getTime() + off * 60000 - d.getTimezoneOffset() * 60000)
    const pad = n => String(n).padStart(2, '0')
    return `${shifted.getFullYear()}-${pad(shifted.getMonth()+1)}-${pad(shifted.getDate())} ` +
           `${pad(shifted.getHours())}:${pad(shifted.getMinutes())}:${pad(shifted.getSeconds())}`
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

const isDark = ref(localStorage.getItem('mo-theme') === 'dark')

// ── Settings modal ──
const settingsOpen = ref(false)
const isSaving = ref(false)
const saveHint = ref('')
const availableModels = ref([])
const isFetchingModels = ref(false)
const modelDropOpen = ref(false)
const modelHighlight = ref(-1)
const form = ref({ extraction_base_url: '', extraction_model: '', extraction_api_key: '', embed_model: '', embed_dim: '', hook_cooldown_sec: '', hook_min_turns: '', hook_budget_tokens: '', search_top_k: '', dup_threshold: '', db_dsn: '', http_port: '' })

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
    const models = await fetch(`${BASE}/models?${params}`, { headers }).then(r => r.ok ? r.json() : [])
    availableModels.value = models
    if (models.length) modelDropOpen.value = true
  } finally {
    isFetchingModels.value = false
  }
}

const KEY_SENTINEL = '__keep__'

async function openSettings() {
  const data = await fetch(`${BASE}/settings`).then(r => r.json())
  form.value = { ...data, extraction_api_key: data.extraction_api_key === '***' ? KEY_SENTINEL : (data.extraction_api_key || '') }
  availableModels.value = []
  modelDropOpen.value = false
  modelHighlight.value = -1
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
    const r = await fetch(`${BASE}/settings`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
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

onMounted(async () => {
  applyTheme()
  const tzInfo = await fetch(`${BASE}/timezone`).then(r => r.json()).catch(() => null)
  if (tzInfo?.iana) serverTz.value = tzInfo.iana
  if (tzInfo?.offset_minutes != null) serverOffsetMin.value = tzInfo.offset_minutes
  projects.value = await fetch(`${BASE}/projects?hide_empty=true`).then(r => r.json())
  await load()
})
</script>

<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

/* ── Shared tokens (layout, radii, timing) ── */
:root {
  --radius-sm: 5px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --transition: 150ms ease;
}

/* ── Light theme (default) ── */
:root,
[data-theme="light"] {
  --bg:             #f6f8fa;
  --surface:        #ffffff;
  --surface-2:      #f0f2f5;
  --border:         #d0d7de;
  --border-subtle:  #e4e8ec;
  --border-hover:   #adb5bd;
  --text-primary:   #1f2328;
  --text-secondary: #57606a;
  --text-muted:     #8c959f;
  --accent:         #0969da;
  --accent-dim:     rgba(9,105,218,0.1);
  --green:          #1a7f37;
  --green-dim:      rgba(26,127,55,0.1);
  --green-border:   rgba(26,127,55,0.2);
  --blue:           #0969da;
  --blue-dim:       rgba(9,105,218,0.1);
  --blue-border:    rgba(9,105,218,0.2);
  --purple:         #8250df;
  --purple-dim:     rgba(130,80,223,0.1);
  --purple-border:  rgba(130,80,223,0.2);
  --orange:         #9a6700;
  --orange-dim:     rgba(154,103,0,0.1);
  --orange-border:  rgba(154,103,0,0.2);
  --red:            #cf222e;
  --red-dim:        rgba(207,34,46,0.1);
  --shadow:         rgba(0,0,0,0.12);
}

/* ── Dark theme ── */
[data-theme="dark"] {
  --bg:             #0d1117;
  --surface:        #161b22;
  --surface-2:      #1c2128;
  --border:         #30363d;
  --border-subtle:  #21262d;
  --border-hover:   #484f58;
  --text-primary:   #e6edf3;
  --text-secondary: #8b949e;
  --text-muted:     #6e7681;
  --accent:         #58a6ff;
  --accent-dim:     rgba(88,166,255,0.12);
  --green:          #3fb950;
  --green-dim:      rgba(63,185,80,0.15);
  --green-border:   rgba(63,185,80,0.25);
  --blue:           #58a6ff;
  --blue-dim:       rgba(88,166,255,0.15);
  --blue-border:    rgba(88,166,255,0.25);
  --purple:         #bc8cff;
  --purple-dim:     rgba(188,140,255,0.15);
  --purple-border:  rgba(188,140,255,0.25);
  --orange:         #d29922;
  --orange-dim:     rgba(210,153,34,0.15);
  --orange-border:  rgba(210,153,34,0.25);
  --red:            #f85149;
  --red-dim:        rgba(248,81,73,0.15);
  --shadow:         rgba(0,0,0,0.5);
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  background: var(--bg);
  color: var(--text-primary);
  font-size: 13px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}

.app {
  width: 100%;
  max-width: 1600px;
  margin: 0 auto;
  padding: 14px 20px 60px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* ── Header ── */
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-subtle);
}

.logo { display: flex; align-items: center; gap: 8px; }
.header-spacer { flex: 1; }
.stat-sep { color: var(--text-muted); }
h1 { font-size: 14px; font-weight: 600; color: var(--text-primary); letter-spacing: -0.01em; }

.stats-row { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; }
.stat-total { font-size: 11px; color: var(--text-muted); margin-right: 2px; }

.badge {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 1px 6px 1px 5px; border-radius: 20px;
  font-size: 10px; font-weight: 500; border: 1px solid transparent;
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
  background: var(--surface); color: var(--text-secondary);
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  cursor: pointer; transition: background var(--transition), color var(--transition);
}
.btn-theme:hover { background: var(--surface-2); color: var(--text-primary); }
.btn-theme:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

.btn-refresh {
  display: inline-flex; align-items: center; gap: 6px;
  background: var(--surface); color: var(--text-secondary);
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  padding: 6px 12px; font-size: 12px; cursor: pointer;
  transition: background var(--transition), color var(--transition), border-color var(--transition);
  white-space: nowrap;
}
.btn-refresh:hover { background: var(--surface-2); color: var(--text-primary); }
.btn-refresh:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

@keyframes spin { to { transform: rotate(360deg); } }
.spinning { animation: spin 0.7s linear infinite; }

/* ── Toolbar ── */
.toolbar {
  display: flex; flex-direction: column;
  gap: 8px; padding-bottom: 4px;
}

.filter-group {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}
.filter-label {
  font-size: 11px; color: var(--text-muted); font-weight: 500;
  min-width: 44px; flex-shrink: 0; text-align: right;
}
.pill-group { display: flex; gap: 4px; flex-wrap: wrap; }
.pill {
  background: var(--surface); color: var(--text-secondary);
  border: 1px solid var(--border); border-radius: 20px;
  padding: 3px 10px; font-size: 11px; cursor: pointer; font-weight: 500;
  transition: background var(--transition), color var(--transition), border-color var(--transition);
  display: flex; align-items: center; gap: 4px;
}
.pill:hover { border-color: var(--accent); color: var(--accent); }
.pill-active {
  background: var(--accent-dim); color: var(--accent);
  border-color: var(--accent);
}
.pill-count {
  background: var(--bg-secondary); border-radius: 10px;
  padding: 0 5px; font-size: 10px; color: var(--text-muted);
}
.pill-active .pill-count { background: var(--accent-dim); color: var(--accent); }

.toolbar-right {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}

.search-wrap {
  display: flex; align-items: center; gap: 8px;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-sm); padding: 5px 10px;
  min-width: 160px; max-width: 240px;
  transition: border-color var(--transition);
}
.search-wrap:focus-within { border-color: var(--accent); }
.search-input {
  background: none; border: none; outline: none;
  color: var(--text-primary); font-size: 12px; width: 100%;
}
.search-input::placeholder { color: var(--text-muted); }

.ctx-preview-controls { margin-bottom: 12px; }
.ctx-project-select { min-width: 240px; }

/* ── Table ── */
.toolbar { padding-bottom: 12px; border-bottom: 1px solid var(--border-subtle); margin-bottom: 4px; }
.table-wrap {
  border: 1px solid var(--border); border-radius: var(--radius-lg);
  overflow: hidden; overflow-x: auto;
}

table { width: 100%; border-collapse: collapse; table-layout: fixed; }

thead { position: sticky; top: 0; z-index: 2; background: var(--surface); box-shadow: 0 1px 0 var(--border), 0 4px 14px -4px var(--shadow); }
th {
  padding: 8px 12px; text-align: left;
  color: var(--text-muted); font-weight: 500; font-size: 11px;
  text-transform: uppercase; letter-spacing: 0.04em;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}

tbody tr {
  transition: background var(--transition);
  cursor: pointer;
}
tbody tr:not(.detail-row):hover td { background: var(--surface); }
tbody tr.active td { background: var(--accent-dim) !important; }
tbody tr.active:hover td { background: var(--accent-dim) !important; }

td {
  padding: 7px 12px;
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

.project-cell { max-width: 80px; }
.type-col { }
.name {
  font-weight: 500; max-width: 180px; color: var(--text-primary);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.desc {
  color: var(--text-secondary); max-width: 320px;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
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
  transition: width 300ms ease;
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
}
.hit-zero { color: var(--text-muted); }

.date { color: var(--text-muted); white-space: nowrap; font-size: 12px; font-variant-numeric: tabular-nums; }

.sortable { cursor: pointer; user-select: none; }
.sortable:hover { color: var(--text-secondary); }
.sort-icon { display: inline-block; margin-left: 3px; color: var(--accent); }

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

/* Detail row */
.detail-row td {
  background: var(--surface-2) !important;
  cursor: default;
  padding: 0;
  border-bottom: 1px solid var(--border);
}
.detail {
  padding: 16px 14px;
  display: flex; flex-direction: column; gap: 14px;
  animation: detail-in 180ms ease-out;
}
@keyframes detail-in {
  from { opacity: 0; transform: translateY(-5px); }
  to   { opacity: 1; transform: translateY(0); }
}
.content-block { display: flex; flex-direction: column; gap: 6px; }

.block-label {
  font-size: 10px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.06em; color: var(--text-muted);
}

pre {
  white-space: pre-wrap; word-break: break-word;
  color: var(--text-primary); font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', ui-monospace, monospace;
  font-size: 12px; line-height: 1.6;
  background: var(--bg); padding: 10px 12px;
  border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);
}

.md-body {
  color: var(--text-secondary); font-size: 13px; line-height: 1.7;
  background: var(--bg); padding: 10px 12px;
  border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);
}
.md-body p { margin: 0 0 8px; }
.md-body p:last-child { margin-bottom: 0; }
.md-body h1,.md-body h2,.md-body h3 { color: var(--text-primary); font-weight: 600; margin: 12px 0 6px; }
.md-body h1 { font-size: 15px; } .md-body h2 { font-size: 14px; } .md-body h3 { font-size: 13px; }
.md-body ul { list-style-type: disc; padding-left: 20px; margin: 6px 0 10px; }
.md-body ol { list-style-type: decimal; padding-left: 20px; margin: 6px 0 10px; }
.md-body ul ul { list-style-type: circle; margin: 2px 0 2px; }
.md-body ul ul ul { list-style-type: square; }
.md-body li { margin: 3px 0; line-height: 1.6; display: list-item; }
.md-body code { background: var(--surface-2); border: 1px solid var(--border); padding: 1px 5px; border-radius: 3px; font-family: ui-monospace, monospace; font-size: 12px; color: var(--accent); }
.md-body pre { background: var(--bg); border: 1px solid var(--border); border-radius: 5px; padding: 10px 12px; overflow-x: auto; margin: 8px 0; }
.md-body pre code { background: none; border: none; padding: 0; color: var(--text-primary); }
.md-body blockquote { border-left: 3px solid var(--border); padding-left: 10px; color: var(--text-muted); margin: 6px 0; }
.md-body strong { color: var(--text-primary); font-weight: 600; }
.md-body a { color: var(--accent); text-decoration: none; }
.md-body a:hover { text-decoration: underline; }
.md-body hr { border: none; border-top: 1px solid var(--border); margin: 10px 0; }

.meta-row {
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
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
  padding: 48px 20px; color: var(--text-muted); font-size: 13px;
}

/* Move row */
.move-row {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding-top: 4px; border-top: 1px solid var(--border-subtle); margin-top: 4px;
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
  background: none; color: var(--text-muted);
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
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--border-hover); }
* { scrollbar-width: thin; scrollbar-color: var(--border) transparent; }

body { margin: 0; }
html, body { overflow-x: hidden; }

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
  background: rgba(0,0,0,0.45);
  display: flex; align-items: center; justify-content: center;
  animation: overlay-in 150ms ease;
}
.modal {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-lg); width: 440px; max-width: 95vw;
  box-shadow: 0 20px 60px var(--shadow);
  display: flex; flex-direction: column;
  animation: modal-in 200ms cubic-bezier(0.16, 1, 0.3, 1);
}
.modal-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 16px 12px; border-bottom: 1px solid var(--border-subtle);
}
.modal-title { font-size: 14px; font-weight: 600; color: var(--text-primary); }
.modal-close {
  display: flex; align-items: center; justify-content: center;
  width: 22px; height: 22px; background: none; border: none;
  color: var(--text-muted); cursor: pointer; border-radius: 4px;
  transition: background var(--transition), color var(--transition);
}
.modal-close:hover { background: var(--red-dim); color: var(--red); }
.modal-body { padding: 16px; display: flex; flex-direction: column; gap: 16px; overflow-y: auto; max-height: calc(90vh - 120px); }
.settings-group { display: flex; flex-direction: column; gap: 10px; }
.settings-group-title {
  font-size: 10px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.06em; color: var(--text-muted);
}
.field-row { display: flex; align-items: center; gap: 10px; }
.field-label { font-size: 12px; color: var(--text-secondary); width: 80px; flex-shrink: 0; cursor: help; }
.field-input {
  flex: 1; background: var(--bg); color: var(--text-primary);
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  padding: 6px 9px; font-size: 12px; outline: none;
  transition: border-color var(--transition);
}
.field-input:focus { border-color: var(--accent); }
.field-input::placeholder { color: var(--text-muted); }
.modal-footer {
  display: flex; align-items: center; justify-content: flex-end; gap: 8px;
  padding: 12px 16px; border-top: 1px solid var(--border-subtle);
}
.save-hint { font-size: 12px; margin-right: auto; }
.save-hint.ok { color: var(--green); }
.save-hint.err { color: var(--red); }
.btn-cancel {
  background: none; color: var(--text-secondary);
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  padding: 5px 14px; font-size: 12px; cursor: pointer;
  transition: background var(--transition);
}
.btn-cancel:hover { background: var(--surface-2); }
.btn-save {
  background: var(--accent); color: #fff;
  border: none; border-radius: var(--radius-sm);
  padding: 5px 16px; font-size: 12px; cursor: pointer; font-weight: 500;
  transition: opacity var(--transition);
}
.btn-save:hover:not(:disabled) { opacity: 0.85; }
.btn-save:disabled { opacity: 0.45; cursor: default; }

.modal-sm { width: 360px; }
.modal-edit { width: 560px; }
.modal-lg { width: 700px; }
.field-row-inline { align-items: center; flex-direction: row; gap: 12px; }
.field-select-sm { width: 80px !important; }
.action-row { display: flex; gap: 8px; margin-top: 8px; }
.btn-edit {
  background: var(--bg-secondary); color: var(--text-secondary);
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  padding: 4px 14px; font-size: 11px; cursor: pointer; font-weight: 500;
  transition: background var(--transition), color var(--transition);
}
.btn-edit:hover { background: var(--accent-dim); color: var(--accent); border-color: var(--accent); }
.btn-ctx-preview {
  display: flex; align-items: center; gap: 5px;
  background: transparent; color: var(--text-muted);
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  padding: 4px 10px; font-size: 11px; cursor: pointer; font-weight: 500;
  transition: background var(--transition), color var(--transition);
}
.btn-ctx-preview:hover { background: var(--accent-dim); color: var(--accent); border-color: var(--accent); }
.ctx-preview-pre {
  white-space: pre-wrap; font-family: monospace; font-size: 12px; line-height: 1.6;
  color: var(--text-primary); max-height: 60vh; overflow-y: auto;
  background: var(--bg-secondary); border-radius: var(--radius); padding: 16px;
  border: 1px solid var(--border); margin: 0;
}
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

/* ── Row actions + chevron ── */
.row-actions {
  display: flex; align-items: center; justify-content: flex-end; gap: 4px;
}
.row-chevron {
  flex-shrink: 0; color: var(--text-muted);
  transition: transform var(--transition), opacity var(--transition);
  opacity: 0;
}
tr:hover .row-chevron,
tr.active .row-chevron { opacity: 1; }
.row-chevron.open { transform: rotate(180deg); }

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
  box-shadow: 0 8px 24px var(--shadow);
  max-height: 200px; overflow-y: auto;
  padding: 4px;
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
.combobox-check {
  width: 14px; height: 14px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  color: var(--accent);
}
</style>
