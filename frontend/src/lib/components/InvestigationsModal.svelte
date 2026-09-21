<script lang="ts">
  import { onMount } from 'svelte';
  import {
    activeSidebarTab,
    currentResult,
    globeLocation,
  } from '../stores';
  import { fetchInvestigations as apiFetch, saveInvestigation as apiSave } from '../api';
  import { X, Shield, Plus, ArrowUpRight, Trash2, Calendar, BookmarkCheck } from 'lucide-svelte';

  let investigations: any[] = [];
  let isSaving = false;
  let newName = '';

  onMount(async () => {
    loadList();
  });

  async function loadList() {
    try {
      const data = await apiFetch();
      investigations = data.investigations || [];
    } catch (err) {
      console.warn('Could not load investigations');
    }
  }

  async function handleSaveCurrent() {
    if (!newName.trim() || !$currentResult) return;
    isSaving = true;
    try {
      await apiSave({
        name: newName.trim(),
        query: $currentResult.query,
        location: $currentResult.aoi.name,
        aoi: $currentResult.aoi,
        analysis_type: $currentResult.analysis_type,
        visualization_type: $currentResult.visualization?.type || 'static_map',
        summary: $currentResult.key_finding,
        confidence: $currentResult.confidence,
      });
      newName = '';
      await loadList();
    } catch (err) {
      console.warn('Save failed:', err);
    } finally {
      isSaving = false;
    }
  }

  function restoreInvestigation(inv: any) {
    if (inv.aoi) {
      globeLocation.update(g => ({
        ...g,
        latitude: inv.aoi.center.latitude,
        longitude: inv.aoi.center.longitude,
        name: inv.aoi.name,
        area_km2: inv.aoi.area_km2,
        polygon: inv.aoi.polygon || g.polygon,
        flyTrigger: g.flyTrigger + 1
      }));
    }
    $activeSidebarTab = 'chat';
  }

  function closePanel() {
    $activeSidebarTab = 'chat';
  }
</script>

<div class="inv-drawer">
  <div class="drawer-header">
    <div class="title-row">
      <Shield size={17} class="accent-icon" />
      <h3 class="drawer-title">Saved Investigations</h3>
    </div>
    <button class="close-btn" on:click={closePanel}>
      <X size={16} />
    </button>
  </div>

  <div class="drawer-content">
    <!-- Save Active Result Box -->
    {#if $currentResult}
      <div class="save-box">
        <span class="box-label">SAVE CURRENT ANALYSIS</span>
        <div class="save-input-row">
          <input
            type="text"
            bind:value={newName}
            placeholder="Investigation title (e.g. Delhi Decadal)..."
            class="name-input"
          />
          <button
            class="save-action-btn"
            on:click={handleSaveCurrent}
            disabled={!newName.trim() || isSaving}
          >
            <Plus size={14} />
            <span>Save</span>
          </button>
        </div>
      </div>
    {/if}

    <!-- Investigations List -->
    <div class="list-section">
      <span class="section-heading">SAVED SESSIONS ({investigations.length})</span>

      {#if investigations.length === 0}
        <div class="empty-state">
          <span>No saved investigations yet. Run a query and click save to preserve session state.</span>
        </div>
      {:else}
        <div class="cards-list">
          {#each investigations as inv}
            <div class="inv-card">
              <div class="card-header">
                <span class="inv-name">{inv.name}</span>
                <span class="inv-type">{inv.analysis_type}</span>
              </div>
              <div class="inv-query">"{inv.query}"</div>
              <div class="inv-meta">
                <span>{inv.location}</span>
                <span class="conf">{(inv.confidence * 100).toFixed(0)}% Conf</span>
              </div>
              <button class="restore-btn" on:click={() => restoreInvestigation(inv)}>
                <span>Restore Session</span>
                <ArrowUpRight size={13} />
              </button>
            </div>
          {/each}
        </div>
      {/if}
    </div>
  </div>
</div>

<style>
  .inv-drawer {
    width: 330px;
    height: 100%;
    background: #090e18;
    border-right: 1px solid rgba(255, 255, 255, 0.08);
    display: flex;
    flex-direction: column;
    z-index: 35;
    flex-shrink: 0;
  }

  .drawer-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 18px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }

  .title-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  :global(.accent-icon) {
    color: #f8fafc;
  }

  .drawer-title {
    font-size: 14px;
    font-weight: 700;
    color: #ffffff;
  }

  .close-btn {
    color: #94a3b8;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 4px;
  }

  .drawer-content {
    flex: 1;
    overflow-y: auto;
    padding: 18px;
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  .save-box {
    background: rgba(16, 24, 38, 0.7);
    border: 1px solid rgba(16, 185, 129, 0.2);
    border-radius: 10px;
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .box-label {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
    color: #e2e8f0;
  }

  .save-input-row {
    display: flex;
    gap: 8px;
  }

  .name-input {
    flex: 1;
    background: rgba(0, 0, 0, 0.3);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
    color: #ffffff;
  }

  .save-action-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    background: #f8fafc;
    color: #030712;
    font-size: 11.5px;
    font-weight: 600;
    padding: 6px 12px;
    border-radius: 6px;
  }

  .save-action-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .section-heading {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
    color: #64748b;
    margin-bottom: 8px;
    display: block;
  }

  .empty-state {
    font-size: 12px;
    color: #64748b;
    line-height: 1.5;
    padding: 12px 0;
  }

  .cards-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .inv-card {
    background: rgba(16, 24, 38, 0.5);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 10px;
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .inv-name {
    font-size: 13px;
    font-weight: 600;
    color: #ffffff;
  }

  .inv-type {
    font-size: 10px;
    font-family: var(--font-mono);
    color: #e2e8f0;
  }

  .inv-query {
    font-size: 11.5px;
    color: #94a3b8;
    font-style: italic;
  }

  .inv-meta {
    display: flex;
    justify-content: space-between;
    font-size: 10.5px;
    color: #64748b;
    font-family: var(--font-mono);
  }

  .conf {
    color: #f8fafc;
  }

  .restore-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    padding: 6px;
    font-size: 11px;
    font-weight: 500;
    color: #e2e8f0;
    transition: all 0.15s ease;
  }

  .restore-btn:hover {
    background: rgba(255, 255, 255, 0.08);
    border-color: rgba(255, 255, 255, 0.16);
    color: #ffffff;
  }
</style>
