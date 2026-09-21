<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import {
    Columns,
    Layers,
    Crosshair,
    Maximize2,
    Calendar,
    Cloud,
    Ruler,
    Satellite,
    Sliders,
    SplitSquareVertical,
    Activity,
  } from 'lucide-svelte';
  import type { EvidenceItem } from '../stores';

  export let beforeItem: EvidenceItem;
  export let currentItem: EvidenceItem;
  export let differenceItem: EvidenceItem | null = null;

  const dispatch = createEventDispatcher<{
    focusGlobe: { item: EvidenceItem };
    syncCesium: { mode: 'before' | 'current' | 'difference' };
    expand: { url: string; label: string };
  }>();

  type CompareMode = 'swipe' | 'side-by-side' | 'difference';
  let mode: CompareMode = 'swipe';

  let sliderPos: number = 50; // percentage from 0 to 100
  let isDragging: boolean = false;
  let containerRef: HTMLDivElement | null = null;

  function resolveUrl(url?: string | null): string {
    if (!url) return '';
    if (/^https?:\/\//.test(url)) return url;
    return `${window.location.origin}${url.startsWith('/') ? url : `/${url}`}`;
  }

  function handlePointerDown(e: PointerEvent) {
    isDragging = true;
    updateSlider(e);
  }

  function handlePointerMove(e: PointerEvent) {
    if (!isDragging) return;
    updateSlider(e);
  }

  function handlePointerUp() {
    isDragging = false;
  }

  function updateSlider(e: PointerEvent) {
    if (!containerRef) return;
    const rect = containerRef.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const pct = Math.max(0, Math.min(100, (x / rect.width) * 100));
    sliderPos = Math.round(pct * 10) / 10;
  }

  function handleSyncCesium(target: 'before' | 'current' | 'difference') {
    dispatch('syncCesium', { mode: target });
  }
</script>

<svelte:window on:pointermove={handlePointerMove} on:pointerup={handlePointerUp} />

<div class="comparison-card">
  <!-- Top Bar: Title & Mode Switcher -->
  <div class="comp-topbar">
    <div class="comp-title-area">
      <div class="icon-bubble">
        <SplitSquareVertical size={14} class="comp-icon" />
      </div>
      <div>
        <h4 class="comp-heading">Before vs. Current Optical Observation</h4>
        <span class="comp-subheading">
          {beforeItem.acquisition_date} &rarr; {currentItem.acquisition_date} · {beforeItem.aoi_name || 'Himalayan Target Area'}
        </span>
      </div>
    </div>

    <!-- Mode Selector Tabs -->
    <div class="mode-tabs">
      <button
        class="mode-tab-btn"
        class:active={mode === 'swipe'}
        on:click={() => (mode = 'swipe')}
        title="Interactive draggable comparison divider"
      >
        <Sliders size={12} />
        <span>Swipe Divider</span>
      </button>

      <button
        class="mode-tab-btn"
        class:active={mode === 'side-by-side'}
        on:click={() => (mode = 'side-by-side')}
        title="Side-by-side synchronized view"
      >
        <Columns size={12} />
        <span>Side-by-Side</span>
      </button>

      {#if differenceItem && differenceItem.available && differenceItem.image_url}
        <button
          class="mode-tab-btn diff-btn"
          class:active={mode === 'difference'}
          on:click={() => (mode = 'difference')}
          title="Analytical difference / change layer"
        >
          <Activity size={12} />
          <span>Difference</span>
        </button>
      {/if}
    </div>
  </div>

  <!-- Synchronized Metadata Pill Row -->
  <div class="metadata-comparison-row">
    <div class="meta-side before-meta">
      <span class="meta-tag before-tag">BEFORE (PRE-EVENT)</span>
      <span class="meta-date">{beforeItem.acquisition_date}</span>
      <span class="meta-sep">·</span>
      <span class="meta-spec">{beforeItem.sensor}</span>
      <span class="meta-sep">·</span>
      <span class="meta-spec">{beforeItem.resolution_m}m</span>
      <span class="meta-sep">·</span>
      <span class="meta-spec">{beforeItem.cloud_cover != null ? `${beforeItem.cloud_cover}% cloud` : '0% cloud'}</span>
      <button
        class="cesium-sync-btn"
        on:click={() => handleSyncCesium('before')}
        title="Show pre-event layer on 3D Cesium globe"
      >
        <Crosshair size={11} />
        <span>Sync Cesium</span>
      </button>
    </div>

    <div class="meta-side current-meta">
      <span class="meta-tag current-tag">CURRENT OBSERVATION</span>
      <span class="meta-date">{currentItem.acquisition_date}</span>
      <span class="meta-sep">·</span>
      <span class="meta-spec">{currentItem.sensor}</span>
      <span class="meta-sep">·</span>
      <span class="meta-spec">{currentItem.resolution_m}m</span>
      <span class="meta-sep">·</span>
      <span class="meta-spec">{currentItem.cloud_cover != null ? `${currentItem.cloud_cover}% cloud` : '0% cloud'}</span>
      <button
        class="cesium-sync-btn"
        on:click={() => handleSyncCesium('current')}
        title="Show current layer on 3D Cesium globe"
      >
        <Crosshair size={11} />
        <span>Sync Cesium</span>
      </button>
    </div>
  </div>

  <!-- Viewport Area -->
  {#if mode === 'swipe'}
    <!-- Draggable Split Swipe Divider -->
    <div
      class="swipe-viewport"
      bind:this={containerRef}
      on:pointerdown={handlePointerDown}
      role="region"
      aria-label="Interactive image comparison slider"
    >
      <!-- Base Layer: Current Observation -->
      <img
        src={resolveUrl(currentItem.image_url)}
        alt="Current observation"
        class="comp-img base-img"
        draggable="false"
      />
      <div class="img-badge current-badge-float">
        Current ({currentItem.acquisition_date})
      </div>

      <!-- Overlaid Layer: Before-Event Baseline (clipped to sliderPos) -->
      <div class="clip-container" style={`clip-path: inset(0 ${100 - sliderPos}% 0 0);`}>
        <img
          src={resolveUrl(beforeItem.image_url)}
          alt="Before-event baseline"
          class="comp-img overlay-img"
          draggable="false"
        />
        <div class="img-badge before-badge-float">
          Before ({beforeItem.acquisition_date})
        </div>
      </div>

      <!-- Draggable Divider Line & Handle -->
      <div class="divider-line" style={`left: ${sliderPos}%;`}>
        <div class="divider-handle">
          <span class="handle-arrow">&larr;</span>
          <span class="handle-bar"></span>
          <span class="handle-arrow">&rarr;</span>
        </div>
      </div>

      <!-- Interaction Instruction Hint -->
      <div class="drag-hint">
        <span>Drag divider to inspect changes</span>
      </div>
    </div>
  {:else if mode === 'side-by-side'}
    <!-- Side-by-Side Dual Viewport -->
    <div class="side-by-side-grid">
      <div class="side-panel">
        <div class="panel-header">
          <span class="panel-badge before-tag">BEFORE</span>
          <span class="panel-date">{beforeItem.acquisition_date}</span>
        </div>
        <div class="panel-img-box">
          <img
            src={resolveUrl(beforeItem.image_url)}
            alt="Before baseline"
            class="comp-img"
          />
        </div>
      </div>

      <div class="side-panel">
        <div class="panel-header">
          <span class="panel-badge current-tag">CURRENT</span>
          <span class="panel-date">{currentItem.acquisition_date}</span>
        </div>
        <div class="panel-img-box">
          <img
            src={resolveUrl(currentItem.image_url)}
            alt="Current observation"
            class="comp-img"
          />
        </div>
      </div>
    </div>
  {:else if mode === 'difference' && differenceItem && differenceItem.image_url}
    <!-- Analytical Difference Viewport -->
    <div class="difference-viewport">
      <img
        src={resolveUrl(differenceItem.image_url)}
        alt="Surface difference analysis"
        class="comp-img"
      />
      <div class="diff-overlay-info">
        <span class="diff-badge">DIFFERENCE OVERLAY</span>
        <p class="diff-note">
          Pixel-level reflectance difference between {beforeItem.acquisition_date} and {currentItem.acquisition_date}.
        </p>
      </div>
    </div>
  {/if}
</div>

<style>
  .comparison-card {
    background: rgba(15, 19, 32, 0.85);
    border: 1px solid rgba(56, 178, 172, 0.25);
    border-radius: 12px;
    overflow: hidden;
    margin: 14px 0;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.45);
    backdrop-filter: blur(14px);
  }

  .comp-topbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(20, 26, 44, 0.6);
    flex-wrap: wrap;
    gap: 10px;
  }

  .comp-title-area {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .icon-bubble {
    width: 28px;
    height: 28px;
    border-radius: 6px;
    background: rgba(56, 178, 172, 0.15);
    display: flex;
    align-items: center;
    justify-content: center;
  }

  :global(.comp-icon) {
    color: #38b2ac;
  }

  .comp-heading {
    margin: 0;
    font-size: 0.88rem;
    font-weight: 600;
    color: #f1f5f9;
    letter-spacing: -0.01em;
  }

  .comp-subheading {
    font-size: 0.73rem;
    color: #94a3b8;
  }

  .mode-tabs {
    display: flex;
    background: rgba(10, 14, 24, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 6px;
    padding: 2px;
    gap: 2px;
  }

  .mode-tab-btn {
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 4px 10px;
    font-size: 0.72rem;
    font-weight: 500;
    color: #94a3b8;
    background: transparent;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .mode-tab-btn:hover {
    color: #e2e8f0;
  }

  .mode-tab-btn.active {
    background: rgba(56, 178, 172, 0.2);
    color: #38b2ac;
    font-weight: 600;
  }

  .metadata-comparison-row {
    display: flex;
    justify-content: space-between;
    padding: 8px 16px;
    background: rgba(12, 16, 28, 0.5);
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    font-size: 0.72rem;
    color: #cbd5e1;
    flex-wrap: wrap;
    gap: 8px;
  }

  .meta-side {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .meta-tag {
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    padding: 2px 6px;
    border-radius: 4px;
  }

  .before-tag {
    background: rgba(234, 179, 8, 0.15);
    color: #facc15;
    border: 1px solid rgba(234, 179, 8, 0.3);
  }

  .current-tag {
    background: rgba(56, 178, 172, 0.15);
    color: #38b2ac;
    border: 1px solid rgba(56, 178, 172, 0.3);
  }

  .meta-date {
    font-weight: 600;
    color: #f8fafc;
  }

  .meta-sep {
    color: #64748b;
  }

  .meta-spec {
    color: #94a3b8;
  }

  .cesium-sync-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 2px 8px;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 4px;
    color: #94a3b8;
    font-size: 0.68rem;
    cursor: pointer;
    margin-left: 6px;
    transition: all 0.15s ease;
  }

  .cesium-sync-btn:hover {
    background: rgba(56, 178, 172, 0.15);
    color: #38b2ac;
    border-color: rgba(56, 178, 172, 0.3);
  }

  /* Swipe Viewport */
  .swipe-viewport {
    position: relative;
    width: 100%;
    height: 380px;
    overflow: hidden;
    cursor: ew-resize;
    user-select: none;
    background: #020617;
  }

  .comp-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
    user-select: none;
    pointer-events: none;
  }

  .clip-container {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    overflow: hidden;
  }

  .divider-line {
    position: absolute;
    top: 0;
    bottom: 0;
    width: 2px;
    background: #38b2ac;
    box-shadow: 0 0 10px rgba(56, 178, 172, 0.8);
    transform: translateX(-50%);
    pointer-events: none;
  }

  .divider-handle {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 38px;
    height: 38px;
    border-radius: 50%;
    background: #0f172a;
    border: 2px solid #38b2ac;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 2px;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.6);
    color: #38b2ac;
    font-size: 0.72rem;
    font-weight: bold;
  }

  .handle-bar {
    width: 1px;
    height: 14px;
    background: rgba(255, 255, 255, 0.3);
  }

  .img-badge {
    position: absolute;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.02em;
    pointer-events: none;
    backdrop-filter: blur(8px);
    z-index: 5;
  }

  .before-badge-float {
    top: 12px;
    left: 12px;
    background: rgba(20, 26, 44, 0.85);
    border: 1px solid rgba(234, 179, 8, 0.4);
    color: #facc15;
  }

  .current-badge-float {
    top: 12px;
    right: 12px;
    background: rgba(20, 26, 44, 0.85);
    border: 1px solid rgba(56, 178, 172, 0.4);
    color: #38b2ac;
  }

  .drag-hint {
    position: absolute;
    bottom: 10px;
    left: 50%;
    transform: translateX(-50%);
    padding: 3px 10px;
    background: rgba(10, 14, 24, 0.75);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    font-size: 0.68rem;
    color: #94a3b8;
    pointer-events: none;
  }

  /* Side by Side Grid */
  .side-by-side-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    padding: 12px;
  }

  .side-panel {
    background: rgba(10, 14, 24, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 8px;
    overflow: hidden;
  }

  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 10px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  }

  .panel-badge {
    font-size: 0.65rem;
    font-weight: bold;
    padding: 2px 6px;
    border-radius: 4px;
  }

  .panel-date {
    font-size: 0.72rem;
    color: #94a3b8;
  }

  .panel-img-box {
    height: 240px;
  }

  /* Difference Viewport */
  .difference-viewport {
    position: relative;
    height: 340px;
    background: #020617;
  }

  .diff-overlay-info {
    position: absolute;
    bottom: 14px;
    left: 14px;
    right: 14px;
    padding: 10px 14px;
    background: rgba(10, 14, 24, 0.85);
    border: 1px solid rgba(56, 178, 172, 0.3);
    border-radius: 6px;
    backdrop-filter: blur(8px);
  }

  .diff-badge {
    font-size: 0.65rem;
    font-weight: 700;
    color: #38b2ac;
    background: rgba(56, 178, 172, 0.15);
    padding: 2px 6px;
    border-radius: 4px;
  }

  .diff-note {
    margin: 4px 0 0 0;
    font-size: 0.73rem;
    color: #cbd5e1;
  }

  @media (max-width: 640px) {
    .side-by-side-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
