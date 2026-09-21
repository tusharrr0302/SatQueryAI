<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { Maximize2, Crosshair, Columns, Sparkles, Satellite, Cloud, Ruler, Database, AlertTriangle, ImageOff, Layers } from 'lucide-svelte';
  import type { EvidenceItem } from '../stores';

  export let item: EvidenceItem;
  export let badge: string = 'OBSERVATION';
  export let isBaseline: boolean = false;
  export let hasComparePartner: boolean = false;

  const dispatch = createEventDispatcher<{
    focusGlobe: { item: EvidenceItem };
    expand: { item: EvidenceItem };
    compare: { item: EvidenceItem };
    openLayer: { item: EvidenceItem };
  }>();

  $: isAvailable = item.available !== false && Boolean(item.image_url);

  function resolveUrl(url?: string | null): string {
    if (!url) return '';
    if (/^https?:\/\//.test(url)) return url;
    return `${window.location.origin}${url.startsWith('/') ? url : `/${url}`}`;
  }

  function handleFocus() {
    if (isAvailable) {
      dispatch('focusGlobe', { item });
    }
  }

  function handleExpand() {
    if (isAvailable) {
      dispatch('expand', { item });
    }
  }

  function handleCompare() {
    if (isAvailable) {
      dispatch('compare', { item });
    }
  }

  function handleOpenLayer() {
    if (isAvailable) {
      dispatch('openLayer', { item });
    }
  }
</script>

<div class="evidence-card" class:baseline={isBaseline} class:unavailable={!isAvailable}>
  <!-- Card Header -->
  <div class="card-header">
    <div class="header-left">
      <span class="badge" class:badge-current={!isBaseline && isAvailable} class:badge-baseline={isBaseline && isAvailable} class:badge-unavail={!isAvailable}>
        {#if isAvailable}
          <Satellite size={11} />
        {:else}
          <AlertTriangle size={11} />
        {/if}
        {isAvailable ? badge : 'UNAVAILABLE'}
      </span>
      <h4 class="card-title">{item.title}</h4>
    </div>

    {#if isAvailable}
      <div class="header-actions">
        <button class="action-btn" on:click={handleFocus} title="Focus AOI on 3D globe">
          <Crosshair size={12} />
          <span>Focus on globe</span>
        </button>

        <button class="action-btn" on:click={handleOpenLayer} title="Open and overlay as layer on Cesium globe">
          <Layers size={12} />
          <span>Open Layer</span>
        </button>

        {#if hasComparePartner}
          <button class="action-btn" on:click={handleCompare} title="Compare pre-event and current observations">
            <Columns size={12} />
            <span>Compare</span>
          </button>
        {/if}

        <button class="action-btn icon-only" on:click={handleExpand} title="Expand high-res preview">
          <Maximize2 size={12} />
        </button>
      </div>
    {/if}
  </div>

  {#if isAvailable && item.image_url}
    <!-- Large Satellite Image Container -->
    <div class="image-viewport" on:click={handleExpand} role="button" tabindex="0" on:keydown={(e) => e.key === 'Enter' && handleExpand()}>
      <img
        src={resolveUrl(item.image_url)}
        alt={item.title}
        class="evidence-img"
        loading="lazy"
      />
      <div class="image-overlay">
        <span class="overlay-hint">
          <Maximize2 size={13} />
          Click to inspect full resolution
        </span>
      </div>
    </div>
  {:else}
    <!-- Honest Unavailable Notice (Zero Synthetic Imagery) -->
    <div class="image-unavailable">
      <div class="unavail-icon-box">
        <ImageOff size={22} class="unavail-icon" />
      </div>
      <div class="unavail-body">
        <span class="unavail-title">Satellite observation unavailable</span>
        <p class="unavail-desc">{item.error_message || item.message || 'The observation could not be retrieved or rendered from verified remote sensing providers.'}</p>
      </div>
    </div>
  {/if}

  <!-- Metadata Strip -->
  <div class="metadata-strip">
    <div class="meta-item">
      <span class="meta-val">{item.acquisition_date}</span>
    </div>
    <span class="meta-dot">·</span>
    <div class="meta-item">
      <span class="meta-val">{item.sensor || 'Sentinel-2 MSI'}</span>
    </div>
    {#if item.processing_level}
      <span class="meta-dot">·</span>
      <div class="meta-item">
        <span class="meta-val">{item.processing_level}</span>
      </div>
    {/if}
    {#if isAvailable}
      <span class="meta-dot">·</span>
      <div class="meta-item">
        <Ruler size={11} class="meta-icon" />
        <span class="meta-val">{item.resolution_m || 10} m</span>
      </div>
      <span class="meta-dot">·</span>
      <div class="meta-item">
        <Cloud size={11} class="meta-icon" />
        <span class="meta-val">{item.cloud_cover != null ? `${item.cloud_cover}% cloud` : '0% cloud'}</span>
      </div>
    {/if}
    {#if item.rendering}
      <span class="meta-dot">·</span>
      <div class="meta-item">
        <span class="meta-val uppercase">{item.rendering.replace(/_/g, ' ')}</span>
      </div>
    {/if}
    {#if item.coverage_type}
      <span class="meta-dot">·</span>
      <div class="meta-item">
        <span class="meta-val uppercase">{item.coverage_type}</span>
      </div>
    {/if}
    <span class="meta-dot">·</span>
    <div class="meta-item source-tag">
      <Database size={11} class="meta-icon" />
      <span class="meta-val uppercase">{item.source || 'Copernicus'}</span>
    </div>
  </div>

  {#if item.baseline_role === 'temporal_baseline'}
    <div class="baseline-note-row">
      <AlertTriangle size={11} class="note-icon" />
      <span>Earlier temporal baseline selected prior to the observation window (unconfirmed flood event date).</span>
    </div>
  {/if}
</div>

<style>
  .evidence-card {
    background: rgba(18, 22, 34, 0.75);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    overflow: hidden;
    margin: 12px 0;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
    backdrop-filter: blur(12px);
    transition: border-color 0.2s ease, transform 0.2s ease;
  }

  .evidence-card:hover {
    border-color: rgba(56, 189, 248, 0.28);
  }

  .evidence-card.baseline {
    border-left: 3px solid #f59e0b;
  }

  .evidence-card:not(.baseline) {
    border-left: 3px solid #38bdf8;
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 14px;
    background: rgba(255, 255, 255, 0.02);
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    gap: 12px;
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
  }

  .badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.04em;
    padding: 2px 7px;
    border-radius: 4px;
    text-transform: uppercase;
  }

  .badge-current {
    background: rgba(56, 189, 248, 0.15);
    color: #38bdf8;
    border: 1px solid rgba(56, 189, 248, 0.3);
  }

  .badge-baseline {
    background: rgba(245, 158, 11, 0.15);
    color: #fbbf24;
    border: 1px solid rgba(245, 158, 11, 0.3);
  }

  .badge-unavail {
    background: rgba(239, 68, 68, 0.15);
    color: #f87171;
    border: 1px solid rgba(239, 68, 68, 0.3);
  }

  .evidence-card.unavailable {
    border-left: 3px solid #ef4444;
  }

  .image-unavailable {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 24px 18px;
    background: rgba(15, 20, 30, 0.6);
    border-top: 1px dashed rgba(239, 68, 68, 0.2);
    border-bottom: 1px dashed rgba(239, 68, 68, 0.2);
  }

  .unavail-icon-box {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 44px;
    height: 44px;
    border-radius: 8px;
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.25);
    flex-shrink: 0;
  }

  .unavail-icon {
    color: #f87171;
  }

  .unavail-body {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;
  }

  .unavail-title {
    font-size: 13px;
    font-weight: 600;
    color: #f87171;
  }

  .unavail-desc {
    margin: 0;
    font-size: 12px;
    color: #94a3b8;
    line-height: 1.45;
  }

  .card-title {
    margin: 0;
    font-size: 13px;
    font-weight: 600;
    color: #f1f5f9;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
  }

  .action-btn {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #cbd5e1;
    font-size: 11px;
    padding: 4px 8px;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.18s ease;
  }

  .action-btn:hover {
    background: rgba(56, 189, 248, 0.15);
    border-color: rgba(56, 189, 248, 0.4);
    color: #38bdf8;
  }

  .action-btn.icon-only {
    padding: 5px;
  }

  .image-viewport {
    position: relative;
    width: 100%;
    min-height: 240px;
    max-height: 380px;
    background: #090d16;
    overflow: hidden;
    cursor: pointer;
  }

  .evidence-img {
    width: 100%;
    height: 100%;
    max-height: 380px;
    object-fit: cover;
    display: block;
    transition: transform 0.3s ease;
  }

  .image-viewport:hover .evidence-img {
    transform: scale(1.015);
  }

  .image-overlay {
    position: absolute;
    inset: 0;
    background: linear-gradient(to top, rgba(0, 0, 0, 0.6) 0%, transparent 40%);
    display: flex;
    align-items: flex-end;
    justify-content: flex-end;
    padding: 10px 14px;
    opacity: 0;
    transition: opacity 0.2s ease;
  }

  .image-viewport:hover .image-overlay {
    opacity: 1;
  }

  .overlay-hint {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    color: #f1f5f9;
    background: rgba(0, 0, 0, 0.65);
    padding: 4px 8px;
    border-radius: 4px;
    border: 1px solid rgba(255, 255, 255, 0.12);
  }

  .metadata-strip {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
    padding: 8px 14px;
    background: rgba(10, 14, 24, 0.6);
    border-top: 1px solid rgba(255, 255, 255, 0.05);
    font-size: 11px;
    color: #94a3b8;
  }

  .meta-item {
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }

  .meta-icon {
    opacity: 0.7;
  }

  .meta-val {
    color: #e2e8f0;
    font-weight: 500;
  }

  .meta-dot {
    color: #475569;
  }

  .uppercase {
    text-transform: uppercase;
    font-size: 10px;
    letter-spacing: 0.03em;
  }

  .source-tag {
    color: #38bdf8;
  }

  .baseline-note-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 7px 14px;
    background: rgba(245, 158, 11, 0.08);
    border-top: 1px solid rgba(245, 158, 11, 0.2);
    font-size: 11px;
    color: #fbbf24;
    line-height: 1.4;
  }

  :global(.note-icon) {
    flex-shrink: 0;
    color: #f59e0b;
  }
</style>
