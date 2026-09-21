<script lang="ts">
  import { onMount, createEventDispatcher } from 'svelte';
  import { Plus, Database, Layers, CheckCircle2, Circle, AlertCircle, MessageSquare, Trash2, ArrowRight, Activity, Globe } from 'lucide-svelte';
  import { activeAsset, userAssets, activeSidebarTab } from '../stores';
  import { fetchDataAssets, deleteDataAsset } from '../api';
  import { pickSatelliteFile, uploadSatelliteFile } from '../services/fileService';
  import { resolveBackendUrl } from '../config';

  const dispatch = createEventDispatcher<{
    selectAsset: any;
    askQuery: string;
  }>();

  let isUploading = false;
  let uploadStatus = '';
  let errorMessage = '';

  onMount(async () => {
    await loadAssets();
  });

  async function loadAssets() {
    try {
      const assets = await fetchDataAssets();
      $userAssets = assets;
      if (assets.length > 0 && !$activeAsset) {
        $activeAsset = assets[0];
      }
    } catch (err) {
      console.warn('Could not load assets:', err);
    }
  }

  async function handleAddData() {
    errorMessage = '';
    try {
      const selected = await pickSatelliteFile();
      if (!selected) return;

      isUploading = true;
      uploadStatus = 'Reading file metadata...';

      const result = await uploadSatelliteFile(selected, (msg) => {
        uploadStatus = msg;
      });

      await loadAssets();
      // Set active asset to the newly uploaded one
      const found = $userAssets.find((a) => a.asset_id === result.asset_id);
      if (found) {
        $activeAsset = found;
        dispatch('selectAsset', found);
      }
    } catch (err: any) {
      console.error('Failed to add data:', err);
      errorMessage = err.message || 'Failed to inspect satellite image.';
    } finally {
      isUploading = false;
      uploadStatus = '';
    }
  }

  async function handleDelete(assetId: string) {
    try {
      await deleteDataAsset(assetId);
      $userAssets = $userAssets.filter((a) => a.asset_id !== assetId);
      if ($activeAsset?.asset_id === assetId) {
        $activeAsset = $userAssets.length > 0 ? $userAssets[0] : null;
      }
    } catch (err: any) {
      errorMessage = err.message || 'Failed to delete asset.';
    }
  }

  function handleSelect(asset: any) {
    $activeAsset = asset;
    dispatch('selectAsset', asset);
  }

  function startChatWithDataset() {
    $activeSidebarTab = 'chat';
    dispatch('askQuery', 'What is this image?');
  }

  function sendQuickQuestion(question: string) {
    $activeSidebarTab = 'chat';
    dispatch('askQuery', question);
  }
</script>

<div class="data-workspace-panel">
  <!-- Header -->
  <div class="panel-header">
    <div class="header-title-row">
      <div class="header-icon">
        <Database size={16} strokeWidth={1.8} />
      </div>
      <div>
        <h2 class="panel-title">Your Data</h2>
        <span class="panel-subtitle">Earth observation raster assets & profiles</span>
      </div>
    </div>
    <button class="add-data-btn" on:click={handleAddData} disabled={isUploading}>
      <Plus size={14} />
      <span>Add Data</span>
    </button>
  </div>

  {#if errorMessage}
    <div class="error-banner">
      <AlertCircle size={14} />
      <span>{errorMessage}</span>
    </div>
  {/if}

  {#if isUploading}
    <div class="uploading-banner">
      <div class="spinner"></div>
      <span>{uploadStatus || 'Processing satellite telemetry...'}</span>
    </div>
  {/if}

  <div class="panel-body">
    {#if $userAssets.length === 0 && !isUploading}
      <!-- Empty State -->
      <div class="empty-state">
        <div class="empty-icon-wrap">
          <Layers size={32} strokeWidth={1.4} />
        </div>
        <h3>No Datasets Connected</h3>
        <p>
          Import local GeoTIFF, TIFF, or multispectral satellite images to analyze
          spectral bands, vegetation indices, or inspect properties with ATS.
        </p>
        <button class="empty-add-btn" on:click={handleAddData}>
          <Plus size={15} />
          <span>Choose Satellite Data</span>
        </button>
      </div>
    {:else}
      <!-- Workspace Split: Asset List & Active Asset Card -->
      <div class="data-content-grid">
        <!-- Asset Selector Strip -->
        <div class="asset-selector-list">
          <span class="list-label">CONNECTED ASSETS ({$userAssets.length})</span>
          <div class="asset-items">
            {#each $userAssets as asset}
              <div
                class="asset-item-card"
                class:active={$activeAsset?.asset_id === asset.asset_id}
                on:click={() => handleSelect(asset)}
                on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && handleSelect(asset)}
                role="button"
                tabindex="0"
              >
                <div class="asset-thumb">
                  {#if asset.thumbnail_url}
                    <img src={resolveBackendUrl(asset.thumbnail_url)} alt={asset.filename} />
                  {:else}
                    <Layers size={16} />
                  {/if}
                </div>
                <div class="asset-item-info">
                  <span class="asset-item-name">{asset.filename}</span>
                  <div class="asset-item-meta">
                    <span>{asset.profile.dimensions.bands} bands</span>
                    <span>•</span>
                    <span>{asset.profile.modality || 'optical'}</span>
                  </div>
                </div>
                <button
                  class="item-delete-btn"
                  on:click|stopPropagation={() => handleDelete(asset.asset_id)}
                  title="Remove asset"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            {/each}
          </div>
        </div>

        <!-- Active Asset Details Card -->
        {#if $activeAsset}
          {@const p = $activeAsset.profile}
          <div class="active-profile-card">
            <div class="profile-card-header">
              <div class="profile-title-block">
                <span class="profile-format-tag">{p.format}</span>
                <span class="profile-filename">{$activeAsset.filename}</span>
              </div>
              <button class="chat-dataset-btn" on:click={startChatWithDataset}>
                <MessageSquare size={13} />
                <span>Chat with this Data</span>
                <ArrowRight size={13} />
              </button>
            </div>

            <!-- Properties Metric Grid -->
            <div class="spec-metrics-grid">
              <div class="spec-box">
                <span class="spec-lbl">MODALITY</span>
                <span class="spec-val uppercase">{p.modality || 'Multispectral'}</span>
              </div>
              <div class="spec-box">
                <span class="spec-lbl">BANDS</span>
                <span class="spec-val">{p.dimensions.bands} bands</span>
              </div>
              <div class="spec-box">
                <span class="spec-lbl">RASTER SIZE</span>
                <span class="spec-val">{p.dimensions.width && p.dimensions.height ? `${p.dimensions.width}×${p.dimensions.height}` : 'Variable'}</span>
              </div>
              <div class="spec-box">
                <span class="spec-lbl">RESOLUTION</span>
                <span class="spec-val">
                  {p.resolution ? `${p.resolution[0]}m` : 'Uncalibrated'}
                </span>
              </div>
              <div class="spec-box">
                <span class="spec-lbl">CRS</span>
                <span class="spec-val">{p.crs || 'Unprojected'}</span>
              </div>
              <div class="spec-box full-col">
                <span class="spec-lbl">SENSOR / PLATFORM</span>
                <span class="spec-val" class:unverified={!p.sensor}>
                  {p.sensor ? `${p.sensor} (${p.platform})` : 'Unknown — not verified in metadata'}
                </span>
              </div>
            </div>

            <!-- Analysis Capabilities Checklist -->
            <div class="analyses-section">
              <span class="section-kicker">AVAILABLE ANALYSIS</span>
              <div class="analyses-list">
                {#each p.possible_analyses as item}
                  <div class="analysis-item-row available">
                    <CheckCircle2 size={14} class="check-icon" />
                    <span>{item}</span>
                  </div>
                {/each}
                <div class="analysis-item-row pending">
                  <Circle size={14} class="circle-icon" />
                  <div class="pending-desc">
                    <span>Change detection</span>
                    <span class="pending-sub">Requires second temporal image of matching AOI</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Limitations Section -->
            {#if p.limitations && p.limitations.length > 0}
              <div class="limitations-section">
                <span class="section-kicker">DATA LIMITATIONS</span>
                <ul class="limitations-list">
                  {#each p.limitations as lim}
                    <li>{lim}</li>
                  {/each}
                </ul>
              </div>
            {/if}

            <!-- Quick Questions Bar -->
            <div class="quick-questions-section">
              <span class="section-kicker">ASK ABOUT THIS DATA</span>
              <div class="quick-chips-row">
                <button
                  class="quick-chip"
                  on:click={() => sendQuickQuestion('What is this image?')}
                >
                  "What is this image?"
                </button>
                {#if p.dimensions.bands >= 8}
                  <button
                    class="quick-chip"
                    on:click={() => sendQuickQuestion('What does Band 8 represent?')}
                  >
                    "What does Band 8 represent?"
                  </button>
                {/if}
                <button
                  class="quick-chip"
                  on:click={() => sendQuickQuestion('Show vegetation.')}
                >
                  "Show vegetation"
                </button>
              </div>
            </div>
          </div>
        {/if}
      </div>
    {/if}
  </div>
</div>

<style>
  .data-workspace-panel {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    background: #050507;
    color: #fff;
    overflow: hidden;
    position: relative;
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.08);
  }

  .panel-header {
    height: 56px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 18px;
    background: rgba(255, 255, 255, 0.025);
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    flex-shrink: 0;
  }

  .header-title-row {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .header-icon {
    width: 32px;
    height: 32px;
    border-radius: 8px;
    background: rgba(59, 130, 246, 0.15);
    color: #60a5fa;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .panel-title {
    font-size: 13.5px;
    font-weight: 600;
    letter-spacing: -0.01em;
    margin: 0;
  }

  .panel-subtitle {
    font-size: 10.5px;
    color: rgba(255, 255, 255, 0.45);
  }

  .add-data-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 7px 14px;
    background: #2563eb;
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 8px;
    color: #fff;
    font-size: 11.5px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .add-data-btn:hover:not(:disabled) {
    background: #1d4ed8;
    transform: translateY(-1px);
  }

  .add-data-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .error-banner {
    background: rgba(239, 68, 68, 0.15);
    border-bottom: 1px solid rgba(239, 68, 68, 0.3);
    color: #fca5a5;
    padding: 8px 18px;
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 11.5px;
  }

  .uploading-banner {
    background: rgba(59, 130, 246, 0.12);
    border-bottom: 1px solid rgba(59, 130, 246, 0.25);
    color: #93c5fd;
    padding: 8px 18px;
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 11.5px;
  }

  .spinner {
    width: 14px;
    height: 14px;
    border: 2px solid rgba(147, 197, 253, 0.3);
    border-top-color: #93c5fd;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .panel-body {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
  }

  .empty-state {
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 40px 20px;
    color: rgba(255, 255, 255, 0.45);
  }

  .empty-icon-wrap {
    width: 64px;
    height: 64px;
    border-radius: 16px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    display: flex;
    align-items: center;
    justify-content: center;
    color: rgba(255, 255, 255, 0.3);
    margin-bottom: 16px;
  }

  .empty-state h3 {
    font-size: 15px;
    font-weight: 600;
    color: #fff;
    margin: 0 0 8px 0;
  }

  .empty-state p {
    font-size: 12px;
    max-width: 380px;
    line-height: 1.5;
    margin: 0 0 20px 0;
  }

  .empty-add-btn {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 9px 18px;
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 8px;
    color: #fff;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .empty-add-btn:hover {
    background: rgba(255, 255, 255, 0.14);
  }

  .data-content-grid {
    display: grid;
    grid-template-columns: 280px 1fr;
    gap: 16px;
    height: 100%;
  }

  .asset-selector-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    border-right: 1px solid rgba(255, 255, 255, 0.06);
    padding-right: 14px;
    overflow-y: auto;
  }

  .list-label {
    font-size: 9px;
    font-weight: 700;
    color: rgba(255, 255, 255, 0.4);
    letter-spacing: 0.06em;
  }

  .asset-items {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .asset-item-card {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 10px;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .asset-item-card:hover {
    background: rgba(255, 255, 255, 0.06);
    border-color: rgba(255, 255, 255, 0.12);
  }

  .asset-item-card.active {
    background: rgba(59, 130, 246, 0.15);
    border-color: rgba(59, 130, 246, 0.4);
  }

  .asset-thumb {
    width: 32px;
    height: 32px;
    border-radius: 6px;
    background: rgba(0, 0, 0, 0.5);
    border: 1px solid rgba(255, 255, 255, 0.1);
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .asset-thumb img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .asset-item-info {
    flex: 1;
    min-width: 0;
  }

  .asset-item-name {
    font-size: 11px;
    font-weight: 500;
    color: #fff;
    display: block;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .asset-item-meta {
    display: flex;
    gap: 4px;
    font-size: 9.5px;
    color: rgba(255, 255, 255, 0.4);
  }

  .item-delete-btn {
    background: transparent;
    border: none;
    color: rgba(255, 255, 255, 0.25);
    cursor: pointer;
    padding: 4px;
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .item-delete-btn:hover {
    color: #f87171;
    background: rgba(239, 68, 68, 0.1);
  }

  .active-profile-card {
    display: flex;
    flex-direction: column;
    gap: 16px;
    overflow-y: auto;
    padding-right: 6px;
  }

  .profile-card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-bottom: 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }

  .profile-title-block {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .profile-format-tag {
    padding: 2px 7px;
    background: rgba(59, 130, 246, 0.2);
    border: 1px solid rgba(59, 130, 246, 0.4);
    border-radius: 4px;
    color: #93c5fd;
    font-size: 9.5px;
    font-weight: 600;
  }

  .profile-filename {
    font-size: 14px;
    font-weight: 600;
    color: #fff;
  }

  .chat-dataset-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 6px;
    color: #fff;
    font-size: 11px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .chat-dataset-btn:hover {
    background: rgba(59, 130, 246, 0.25);
    border-color: rgba(59, 130, 246, 0.5);
    color: #93c5fd;
  }

  .spec-metrics-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
  }

  .spec-box {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 8px;
    padding: 8px 12px;
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  .spec-box.full-col {
    grid-column: span 4;
  }

  .spec-lbl {
    font-size: 9px;
    font-weight: 700;
    color: rgba(255, 255, 255, 0.4);
    letter-spacing: 0.05em;
  }

  .spec-val {
    font-size: 12px;
    font-weight: 600;
    color: #fff;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", sans-serif;
  }

  .spec-val.unverified {
    color: #fbbf24;
  }

  .section-kicker {
    font-size: 9px;
    font-weight: 700;
    color: rgba(255, 255, 255, 0.4);
    letter-spacing: 0.06em;
    display: block;
    margin-bottom: 8px;
  }

  .analyses-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .analysis-item-row {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    padding: 6px 10px;
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 6px;
    font-size: 11.5px;
  }

  .analysis-item-row.available {
    color: rgba(255, 255, 255, 0.88);
  }

  .analysis-item-row.pending {
    color: rgba(255, 255, 255, 0.45);
  }

  :global(.check-icon) {
    color: #34d399;
    flex-shrink: 0;
    margin-top: 1px;
  }

  :global(.circle-icon) {
    color: rgba(255, 255, 255, 0.3);
    flex-shrink: 0;
    margin-top: 1px;
  }

  .pending-desc {
    display: flex;
    flex-direction: column;
    gap: 1px;
  }

  .pending-sub {
    font-size: 9.5px;
    color: rgba(255, 255, 255, 0.35);
  }

  .limitations-list {
    margin: 0;
    padding-left: 18px;
    font-size: 11px;
    color: rgba(255, 255, 255, 0.5);
    line-height: 1.5;
  }

  .quick-chips-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .quick-chip {
    padding: 5px 11px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    color: rgba(255, 255, 255, 0.8);
    font-size: 11px;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .quick-chip:hover {
    background: rgba(59, 130, 246, 0.2);
    border-color: rgba(59, 130, 246, 0.4);
    color: #93c5fd;
  }
</style>
