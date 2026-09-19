<script lang="ts">
  import { ZoomIn, ZoomOut, Maximize2, RotateCcw, Layers, Eye } from 'lucide-svelte';
  import { resolveBackendUrl } from '../config';

  export let title: string = 'Raster View';
  export let imageUrl: string = '';
  export let bands: any[] = [];
  export let activeBandIndex: number | null = null;

  let zoom = 1.0;
  let panX = 0;
  let panY = 0;
  let isDragging = false;
  let startX = 0;
  let startY = 0;

  function handleZoomIn() {
    zoom = Math.min(zoom * 1.25, 5.0);
  }

  function handleZoomOut() {
    zoom = Math.max(zoom / 1.25, 0.4);
  }

  function handleReset() {
    zoom = 1.0;
    panX = 0;
    panY = 0;
  }

  function handleMouseDown(e: MouseEvent) {
    isDragging = true;
    startX = e.clientX - panX;
    startY = e.clientY - panY;
  }

  function handleMouseMove(e: MouseEvent) {
    if (!isDragging) return;
    panX = e.clientX - startX;
    panY = e.clientY - startY;
  }

  function handleMouseUp() {
    isDragging = false;
  }
</script>

<div class="raster-viewer-card">
  <div class="raster-toolbar">
    <div class="toolbar-left">
      <Layers size={14} class="toolbar-icon" />
      <span class="toolbar-title">{title}</span>
    </div>
    <div class="toolbar-controls">
      <button class="tool-btn" on:click={handleZoomOut} title="Zoom Out"><ZoomOut size={13} /></button>
      <span class="zoom-level">{Math.round(zoom * 100)}%</span>
      <button class="tool-btn" on:click={handleZoomIn} title="Zoom In"><ZoomIn size={13} /></button>
      <button class="tool-btn" on:click={handleReset} title="Reset View"><RotateCcw size={13} /></button>
    </div>
  </div>

  <div
    class="raster-viewport"
    on:mousedown={handleMouseDown}
    on:mousemove={handleMouseMove}
    on:mouseup={handleMouseUp}
    on:mouseleave={handleMouseUp}
    role="region"
    aria-label="Interactive Raster Viewport"
  >
    {#if imageUrl}
      <div
        class="raster-canvas-wrapper"
        style="transform: translate({panX}px, {panY}px) scale({zoom}); cursor: {isDragging ? 'grabbing' : 'grab'};"
      >
        <img
          src={resolveBackendUrl(imageUrl)}
          alt={title}
          class="raster-image"
          draggable="false"
        />
      </div>
    {:else}
      <div class="empty-raster">
        <Eye size={28} strokeWidth={1.5} />
        <span>No raster preview generated yet</span>
      </div>
    {/if}

    <!-- Band Inspector Chip Tray if bands available -->
    {#if bands && bands.length > 0}
      <div class="bands-overlay-tray">
        <span class="tray-label">BANDS ({bands.length})</span>
        <div class="bands-chips-scroll">
          {#each bands as b}
            <div
              class="band-chip"
              class:selected={activeBandIndex === b.index}
              title="{b.description || b.name}: min={b.min}, max={b.max}, mean={b.mean}"
            >
              <span class="band-id">{b.name}</span>
              {#if b.wavelength_um}
                <span class="band-wl">{b.wavelength_um}µm</span>
              {/if}
            </div>
          {/each}
        </div>
      </div>
    {/if}
  </div>
</div>

<style>
  .raster-viewer-card {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    background: #09090b;
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    overflow: hidden;
    position: relative;
  }

  .raster-toolbar {
    height: 38px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 12px;
    background: rgba(255, 255, 255, 0.03);
    border-bottom: 1px solid rgba(255, 255, 255, 0.07);
    user-select: none;
  }

  .toolbar-left {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .toolbar-title {
    font-size: 11px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.85);
    letter-spacing: 0.02em;
    text-transform: uppercase;
  }

  .toolbar-controls {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .tool-btn {
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    color: rgba(255, 255, 255, 0.75);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .tool-btn:hover {
    background: rgba(255, 255, 255, 0.12);
    color: #fff;
  }

  .zoom-level {
    font-size: 10px;
    font-family: monospace;
    color: rgba(255, 255, 255, 0.5);
    min-width: 32px;
    text-align: center;
  }

  .raster-viewport {
    flex: 1;
    position: relative;
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
    background: radial-gradient(circle at 50% 50%, #121216 0%, #060608 100%);
  }

  .raster-canvas-wrapper {
    transition: transform 0.05s ease-out;
    transform-origin: center center;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .raster-image {
    max-width: 85%;
    max-height: 85%;
    object-fit: contain;
    border-radius: 6px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.8), 0 0 0 1px rgba(255, 255, 255, 0.1);
  }

  .empty-raster {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    color: rgba(255, 255, 255, 0.3);
    font-size: 12px;
  }

  .bands-overlay-tray {
    position: absolute;
    bottom: 10px;
    left: 10px;
    right: 10px;
    background: rgba(10, 10, 14, 0.88);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    padding: 6px 10px;
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .tray-label {
    font-size: 9px;
    font-weight: 700;
    color: rgba(255, 255, 255, 0.4);
    letter-spacing: 0.05em;
    flex-shrink: 0;
  }

  .bands-chips-scroll {
    display: flex;
    align-items: center;
    gap: 6px;
    overflow-x: auto;
    scrollbar-width: none;
  }

  .band-chip {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 3px 7px;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 4px;
    font-size: 10px;
    color: rgba(255, 255, 255, 0.8);
    white-space: nowrap;
    cursor: default;
  }

  .band-chip.selected {
    background: rgba(59, 130, 246, 0.25);
    border-color: rgba(59, 130, 246, 0.6);
    color: #93c5fd;
  }

  .band-id {
    font-weight: 600;
  }

  .band-wl {
    color: rgba(255, 255, 255, 0.4);
    font-size: 8.5px;
  }
</style>
