<script lang="ts">
  import {
    activeDataLayers,
    currentGlobeSkin,
    flyToLayerTrigger,
    activeSidebarTab,
    type DataLayerSpec,
  } from '../stores';
  import { getAvailableSkins, type GlobeSkin } from '../services/globeSkinRegistry';
  import {
    X,
    Eye,
    EyeOff,
    Layers,
    Sliders,
    Crosshair,
    Trash2,
    Sparkles,
    Globe2,
    Compass,
    Check,
    Info,
  } from 'lucide-svelte';

  const skins: GlobeSkin[] = getAvailableSkins();

  function closePanel() {
    $activeSidebarTab = 'chat';
  }

  function setSkin(skinId: string) {
    $currentGlobeSkin = skinId;
  }

  function toggleLayerVisibility(layerId: string) {
    activeDataLayers.update((layers) =>
      layers.map((l) =>
        l.layer_id === layerId
          ? { ...l, visible: l.visible === false ? true : false }
          : l
      )
    );
  }

  function updateLayerOpacity(layerId: string, opacity: number) {
    activeDataLayers.update((layers) =>
      layers.map((l) =>
        l.layer_id === layerId
          ? { ...l, style: { ...l.style, opacity } }
          : l
      )
    );
  }

  function focusLayer(layerId: string) {
    flyToLayerTrigger.set({ layerId, timestamp: Date.now() });
  }

  function removeLayer(layerId: string) {
    activeDataLayers.update((layers) =>
      layers.filter((l) => l.layer_id !== layerId)
    );
  }

  function clearAllLayers() {
    activeDataLayers.set([]);
  }

  function formatBounds(bounds?: number[]): string {
    if (!bounds || bounds.length !== 4) return '';
    const [w, s, e, n] = bounds;
    return `${s.toFixed(2)}°N, ${w.toFixed(2)}°E to ${n.toFixed(2)}°N, ${e.toFixed(2)}°E`;
  }

  function getTypeBadgeColor(type: string): string {
    switch (type.toLowerCase()) {
      case 'geojson':
        return '#38bdf8';
      case 'raster':
        return '#a78bfa';
      case 'bbox':
        return '#34d399';
      case 'heatmap':
        return '#fb923c';
      case 'marker':
        return '#f472b6';
      default:
        return '#94a3b8';
    }
  }

  function getSourceBadgeLabel(source?: string): { label: string; bg: string; color: string } {
    const s = source?.toLowerCase() || 'mock';
    if (s.includes('planetary') || s === 'live') {
      return { label: 'LIVE SATELLITE', bg: 'rgba(56, 189, 248, 0.12)', color: '#38bdf8' };
    }
    if (s === 'user_data') {
      return { label: 'USER RASTER', bg: 'rgba(167, 139, 250, 0.12)', color: '#c084fc' };
    }
    return { label: 'BENCHMARK', bg: 'rgba(255, 255, 255, 0.08)', color: 'rgba(255, 255, 255, 0.65)' };
  }
</script>

<aside class="layers-drawer" aria-label="Geospatial Layers Drawer">
  <!-- Header -->
  <header class="drawer-header">
    <div class="title-row">
      <div class="title-icon">
        <Layers size={16} strokeWidth={2} />
      </div>
      <div class="title-content">
        <h3 class="drawer-title">Geospatial Layers</h3>
        <span class="drawer-subtitle">Globe skins & analytical overlays</span>
      </div>
    </div>

    <button
      class="close-btn"
      on:click={closePanel}
      title="Close layers panel"
      aria-label="Close layers panel"
    >
      <X size={16} strokeWidth={1.8} />
    </button>
  </header>

  <!-- Scrollable Content -->
  <div class="drawer-content">
    <!-- =========================================================
         SECTION 1: GLOBE SKIN / BASEMAP SYSTEM (PHASE 8)
         ========================================================= -->
    <section class="layer-section">
      <div class="section-heading-row">
        <div class="heading-with-icon">
          <Globe2 size={12} class="section-icon" />
          <span class="section-heading">GLOBE SKIN / BASEMAP</span>
        </div>
        <span class="section-badge">Base index 0</span>
      </div>

      <p class="section-description">
        Modifies base Earth presentation without reloading or altering analytical data layers.
      </p>

      <div class="skins-grid">
        {#each skins as skin}
          {@const isSelected = $currentGlobeSkin === skin.id}
          <button
            class="skin-card"
            class:active={isSelected}
            on:click={() => setSkin(skin.id)}
            title={skin.description}
          >
            <div class="skin-header">
              <span
                class="skin-swatch"
                style="background: {skin.previewColor};"
              ></span>
              <span class="skin-name">{skin.name}</span>
              {#if isSelected}
                <span class="active-check">
                  <Check size={11} strokeWidth={2.5} />
                </span>
              {/if}
            </div>
            <span class="skin-desc">{skin.description}</span>
          </button>
        {/each}
      </div>
    </section>

    <!-- =========================================================
         SECTION 2: DYNAMIC ACTIVE DATA LAYERS (PHASE 7)
         ========================================================= -->
    <section class="layer-section">
      <div class="section-heading-row">
        <div class="heading-with-icon">
          <Sparkles size={12} class="section-icon" />
          <span class="section-heading">ACTIVE ANALYSIS LAYERS</span>
        </div>
        <div class="heading-actions">
          <span class="count-badge">{$activeDataLayers.length}</span>
          {#if $activeDataLayers.length > 0}
            <button
              class="clear-all-btn"
              on:click={clearAllLayers}
              title="Remove all active analysis layers"
            >
              <Trash2 size={11} />
              <span>Clear</span>
            </button>
          {/if}
        </div>
      </div>

      <!-- EMPTY STATE -->
      {#if $activeDataLayers.length === 0}
        <div class="empty-layers-card">
          <div class="empty-icon-box">
            <Compass size={22} strokeWidth={1.5} />
          </div>
          <h4 class="empty-title">No Active Analysis Layers</h4>
          <p class="empty-desc">
            Submit a remote-sensing query (e.g., <em>"Analyze flood extent in Derna"</em> or <em>"Vegetation loss in Uttarakhand"</em>) to generate multi-spectral spatial layers.
          </p>
          <div class="empty-hint">
            <Info size={12} />
            <span>Layers clamp to 3D terrain with real-time opacity controls.</span>
          </div>
        </div>
      {:else}
        <!-- DYNAMIC LAYERS LIST -->
        <div class="layers-list">
          {#each $activeDataLayers as layer (layer.layer_id)}
            {@const isVisible = layer.visible !== false}
            {@const opacity = layer.style?.opacity ?? 1.0}
            {@const typeColor = getTypeBadgeColor(layer.type)}
            {@const srcBadge = getSourceBadgeLabel(layer.provenance?.source)}

            <div class="layer-item" class:dimmed={!isVisible}>
              <!-- Header Row -->
              <div class="layer-top-row">
                <button
                  class="vis-toggle"
                  class:visible={isVisible}
                  on:click={() => toggleLayerVisibility(layer.layer_id)}
                  title={isVisible ? 'Hide layer' : 'Show layer'}
                  aria-label={isVisible ? `Hide ${layer.title}` : `Show ${layer.title}`}
                >
                  {#if isVisible}
                    <Eye size={14} strokeWidth={1.8} />
                  {:else}
                    <EyeOff size={14} strokeWidth={1.8} />
                  {/if}
                </button>

                <div class="layer-info">
                  <div class="layer-title-line">
                    <span class="layer-title" title={layer.title}>{layer.title}</span>
                  </div>
                  <div class="layer-badges">
                    <span
                      class="layer-badge type-badge"
                      style="color: {typeColor}; border-color: {typeColor}33; background: {typeColor}15;"
                    >
                      {layer.type.toUpperCase()}
                    </span>
                    <span
                      class="layer-badge src-badge"
                      style="color: {srcBadge.color}; background: {srcBadge.bg};"
                    >
                      {srcBadge.label}
                    </span>
                  </div>
                </div>

                <!-- Focus / Recenter Button -->
                <button
                  class="focus-btn"
                  on:click={() => focusLayer(layer.layer_id)}
                  title="Fly camera to layer extent"
                  aria-label="Fly camera to layer extent"
                >
                  <Crosshair size={13} strokeWidth={1.8} />
                </button>
              </div>

              <!-- Description -->
              {#if layer.description}
                <p class="layer-description-text">{layer.description}</p>
              {/if}

              <!-- Spatial Bounds indicator -->
              {#if layer.spatial?.bounds && layer.spatial.bounds.length === 4}
                <div class="layer-extent-row">
                  <span class="extent-label">EXTENT:</span>
                  <span class="extent-val">{formatBounds(layer.spatial.bounds)}</span>
                </div>
              {/if}

              <!-- Opacity Slider -->
              {#if isVisible}
                <div class="opacity-control">
                  <Sliders size={11} strokeWidth={1.6} class="slider-icon" />
                  <input
                    type="range"
                    min="0.05"
                    max="1.0"
                    step="0.05"
                    value={opacity}
                    on:input={(e) =>
                      updateLayerOpacity(layer.layer_id, parseFloat(e.currentTarget.value))
                    }
                    class="opacity-slider"
                    aria-label={`${layer.title} opacity`}
                  />
                  <span class="opacity-val">{Math.round(opacity * 100)}%</span>
                </div>
              {/if}

              <!-- Legend Preview -->
              {#if isVisible && layer.legend}
                <div class="legend-box">
                  <div class="legend-header">
                    <span class="legend-title">{layer.legend.title || 'Layer Legend'}</span>
                    {#if layer.legend.unit}
                      <span class="legend-unit">({layer.legend.unit})</span>
                    {/if}
                  </div>

                  {#if layer.legend.items && layer.legend.items.length > 0}
                    <!-- Categorical Legend -->
                    <div class="legend-items-list">
                      {#each layer.legend.items as item}
                        <div class="legend-item-pill">
                          <span
                            class="legend-color-dot"
                            style="background: {item.color};"
                          ></span>
                          <span class="legend-item-lbl">{item.label}</span>
                          {#if item.value}
                            <span class="legend-item-val">{item.value}</span>
                          {/if}
                        </div>
                      {/each}
                    </div>
                  {:else if layer.legend.min !== undefined && layer.legend.max !== undefined}
                    <!-- Continuous Spectrum Legend -->
                    <div class="continuous-legend">
                      <div class="spectrum-bar"></div>
                      <div class="spectrum-labels">
                        <span>{layer.legend.min}</span>
                        <span>{layer.legend.max}</span>
                      </div>
                    </div>
                  {/if}
                </div>
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    </section>
  </div>
</aside>

<style>
  /* DRAWER CONTAINER */
  .layers-drawer {
    width: 320px;
    height: 100%;
    flex-shrink: 0;
    position: relative;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    background: #080a0f;
    border-right: 1px solid rgba(255, 255, 255, 0.08);
    color: #ffffff;
    z-index: 35;
    font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    box-shadow: 12px 0 32px rgba(0, 0, 0, 0.45);
  }

  /* HEADER */
  .drawer-header {
    height: 60px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 16px;
    background: rgba(255, 255, 255, 0.015);
    border-bottom: 1px solid rgba(255, 255, 255, 0.07);
  }

  .title-row {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .title-icon {
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 8px;
    background: rgba(56, 189, 248, 0.1);
    border: 1px solid rgba(56, 189, 248, 0.22);
    color: #38bdf8;
  }

  .title-content {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .drawer-title {
    margin: 0;
    font-size: 13px;
    font-weight: 650;
    letter-spacing: -0.01em;
    color: #ffffff;
  }

  .drawer-subtitle {
    font-size: 9.5px;
    color: rgba(255, 255, 255, 0.42);
  }

  .close-btn {
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 6px;
    border: 1px solid transparent;
    background: transparent;
    color: rgba(255, 255, 255, 0.4);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .close-btn:hover {
    color: #ffffff;
    background: rgba(255, 255, 255, 0.08);
    border-color: rgba(255, 255, 255, 0.12);
  }

  /* DRAWER CONTENT */
  .drawer-content {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding: 16px 14px 24px;
    display: flex;
    flex-direction: column;
    gap: 24px;
  }

  .drawer-content::-webkit-scrollbar {
    width: 4px;
  }

  .drawer-content::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.14);
    border-radius: 4px;
  }

  /* SECTION */
  .layer-section {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .section-heading-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 2px;
  }

  .heading-with-icon {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  :global(.section-icon) {
    color: #38bdf8;
  }

  .section-heading {
    font-size: 9.5px;
    font-weight: 700;
    letter-spacing: 0.09em;
    color: rgba(255, 255, 255, 0.65);
  }

  .section-badge {
    font-size: 8.5px;
    font-family: monospace;
    padding: 2px 6px;
    border-radius: 4px;
    background: rgba(255, 255, 255, 0.05);
    color: rgba(255, 255, 255, 0.4);
    border: 1px solid rgba(255, 255, 255, 0.06);
  }

  .heading-actions {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .count-badge {
    font-size: 9px;
    font-weight: 600;
    padding: 1px 6px;
    border-radius: 10px;
    background: rgba(56, 189, 248, 0.14);
    color: #38bdf8;
    border: 1px solid rgba(56, 189, 248, 0.25);
  }

  .clear-all-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 9.5px;
    padding: 2px 7px;
    border-radius: 4px;
    background: rgba(239, 68, 68, 0.08);
    border: 1px solid rgba(239, 68, 68, 0.2);
    color: #f87171;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .clear-all-btn:hover {
    background: rgba(239, 68, 68, 0.18);
    color: #fca5a5;
  }

  .section-description {
    margin: 0;
    font-size: 9.5px;
    line-height: 1.4;
    color: rgba(255, 255, 255, 0.38);
  }

  /* SKINS GRID */
  .skins-grid {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .skin-card {
    text-align: left;
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 9px 11px;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.06);
    color: #ffffff;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .skin-card:hover {
    background: rgba(255, 255, 255, 0.05);
    border-color: rgba(255, 255, 255, 0.12);
  }

  .skin-card.active {
    background: rgba(56, 189, 248, 0.08);
    border-color: rgba(56, 189, 248, 0.35);
    box-shadow: 0 0 16px rgba(56, 189, 248, 0.08);
  }

  .skin-header {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .skin-swatch {
    width: 12px;
    height: 12px;
    border-radius: 3px;
    border: 1px solid rgba(255, 255, 255, 0.25);
    flex-shrink: 0;
  }

  .skin-name {
    flex: 1;
    font-size: 11.5px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.9);
  }

  .skin-card.active .skin-name {
    color: #ffffff;
  }

  .active-check {
    color: #38bdf8;
    display: flex;
  }

  .skin-desc {
    font-size: 9px;
    line-height: 1.35;
    color: rgba(255, 255, 255, 0.35);
  }

  /* EMPTY STATE */
  .empty-layers-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    padding: 24px 16px;
    border-radius: 10px;
    background: rgba(255, 255, 255, 0.015);
    border: 1px dashed rgba(255, 255, 255, 0.1);
    gap: 8px;
  }

  .empty-icon-box {
    width: 44px;
    height: 44px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(255, 255, 255, 0.03);
    color: rgba(255, 255, 255, 0.3);
    margin-bottom: 4px;
  }

  .empty-title {
    margin: 0;
    font-size: 12px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.7);
  }

  .empty-desc {
    margin: 0;
    font-size: 9.5px;
    line-height: 1.45;
    color: rgba(255, 255, 255, 0.35);
  }

  .empty-desc em {
    color: rgba(255, 255, 255, 0.6);
    font-style: normal;
  }

  .empty-hint {
    margin-top: 6px;
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 9px;
    color: rgba(56, 189, 248, 0.7);
  }

  /* ACTIVE LAYERS LIST */
  .layers-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .layer-item {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 11px;
    border-radius: 9px;
    background: rgba(255, 255, 255, 0.025);
    border: 1px solid rgba(255, 255, 255, 0.08);
    transition: all 0.15s ease;
  }

  .layer-item:hover {
    background: rgba(255, 255, 255, 0.045);
    border-color: rgba(255, 255, 255, 0.14);
  }

  .layer-item.dimmed {
    opacity: 0.55;
    background: rgba(255, 255, 255, 0.01);
  }

  .layer-top-row {
    display: flex;
    align-items: flex-start;
    gap: 8px;
  }

  .vis-toggle {
    width: 26px;
    height: 26px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 6px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: rgba(255, 255, 255, 0.35);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .vis-toggle:hover {
    color: #ffffff;
    background: rgba(255, 255, 255, 0.1);
  }

  .vis-toggle.visible {
    color: #38bdf8;
    background: rgba(56, 189, 248, 0.12);
    border-color: rgba(56, 189, 248, 0.3);
  }

  .layer-info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  .layer-title-line {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .layer-title {
    font-size: 11.5px;
    font-weight: 600;
    color: #ffffff;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .layer-badges {
    display: flex;
    align-items: center;
    gap: 4px;
    flex-wrap: wrap;
  }

  .layer-badge {
    font-size: 8px;
    font-weight: 650;
    letter-spacing: 0.04em;
    padding: 1px 5px;
    border-radius: 3px;
    border: 1px solid transparent;
  }

  .focus-btn {
    width: 26px;
    height: 26px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 6px;
    background: transparent;
    border: 1px solid transparent;
    color: rgba(255, 255, 255, 0.4);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .focus-btn:hover {
    color: #38bdf8;
    background: rgba(56, 189, 248, 0.1);
    border-color: rgba(56, 189, 248, 0.25);
  }

  .layer-description-text {
    margin: 0;
    font-size: 9.5px;
    line-height: 1.35;
    color: rgba(255, 255, 255, 0.45);
  }

  .layer-extent-row {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 8.5px;
    color: rgba(255, 255, 255, 0.35);
    font-family: monospace;
  }

  .extent-label {
    font-weight: 700;
    color: rgba(255, 255, 255, 0.25);
  }

  .opacity-control {
    display: flex;
    align-items: center;
    gap: 7px;
    padding-top: 6px;
    border-top: 1px solid rgba(255, 255, 255, 0.05);
  }

  :global(.slider-icon) {
    color: rgba(255, 255, 255, 0.3);
  }

  .opacity-slider {
    flex: 1;
    height: 3px;
    appearance: none;
    -webkit-appearance: none;
    background: rgba(255, 255, 255, 0.12);
    border-radius: 4px;
    outline: none;
    cursor: pointer;
  }

  .opacity-slider::-webkit-slider-thumb {
    appearance: none;
    -webkit-appearance: none;
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: #38bdf8;
    box-shadow: 0 0 6px rgba(56, 189, 248, 0.6);
    cursor: pointer;
  }

  .opacity-val {
    width: 30px;
    text-align: right;
    font-size: 9px;
    font-family: monospace;
    color: rgba(255, 255, 255, 0.5);
  }

  /* LEGEND */
  .legend-box {
    margin-top: 4px;
    padding: 8px 9px;
    border-radius: 6px;
    background: rgba(0, 0, 0, 0.35);
    border: 1px solid rgba(255, 255, 255, 0.05);
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .legend-header {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .legend-title {
    font-size: 9px;
    font-weight: 650;
    color: rgba(255, 255, 255, 0.6);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .legend-unit {
    font-size: 8.5px;
    color: rgba(255, 255, 255, 0.35);
  }

  .legend-items-list {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
  }

  .legend-item-pill {
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 2px 6px;
    border-radius: 4px;
    background: rgba(255, 255, 255, 0.04);
    font-size: 8.5px;
    color: rgba(255, 255, 255, 0.7);
  }

  .legend-color-dot {
    width: 8px;
    height: 8px;
    border-radius: 2px;
    flex-shrink: 0;
  }

  .legend-item-val {
    color: rgba(255, 255, 255, 0.4);
    font-family: monospace;
    font-size: 8px;
  }

  .continuous-legend {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  .spectrum-bar {
    height: 6px;
    border-radius: 3px;
    background: linear-gradient(to right, #38bdf8, #34d399, #facc15, #ef4444);
  }

  .spectrum-labels {
    display: flex;
    justify-content: space-between;
    font-size: 8px;
    font-family: monospace;
    color: rgba(255, 255, 255, 0.4);
  }
</style>