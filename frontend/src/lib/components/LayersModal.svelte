<script lang="ts">
  import { layersState, activeSidebarTab } from '../stores';

  import {
    X,
    Eye,
    EyeOff,
    Layers,
    Sliders
  } from 'lucide-svelte';


  // =========================================================
  // CLOSE
  // =========================================================

  function closePanel() {
    $activeSidebarTab = 'chat';
  }


  // =========================================================
  // VISIBILITY
  // =========================================================

  function toggleVisibility(id: string) {

    layersState.update(layers =>
      layers.map(layer =>
        layer.id === id
          ? {
              ...layer,
              visible: !layer.visible
            }
          : layer
      )
    );
  }


  // =========================================================
  // OPACITY
  // =========================================================

  function updateOpacity(
    id: string,
    val: number
  ) {

    layersState.update(layers =>
      layers.map(layer =>
        layer.id === id
          ? {
              ...layer,
              opacity: val
            }
          : layer
      )
    );
  }
</script>


<div class="layers-drawer">


  <!-- =====================================================
       HEADER
       ===================================================== -->

  <div class="drawer-header">

    <div class="title-row">

      <div class="title-icon">

        <Layers
          size={15}
          strokeWidth={1.7}
        />

      </div>


      <div class="title-content">

        <h3 class="drawer-title">
          Geospatial Layers
        </h3>

        <span class="drawer-subtitle">
          Map & analysis overlays
        </span>

      </div>

    </div>


    <button
      class="close-btn"
      on:click={closePanel}
      title="Close layers"
      aria-label="Close layers"
    >

      <X
        size={16}
        strokeWidth={1.8}
      />

    </button>

  </div>


  <!-- =====================================================
       CONTENT
       ===================================================== -->

  <div class="drawer-content">


    <!-- =================================================
         SATELLITE BASEMAPS
         ================================================= -->

    <div class="layer-section">

      <div class="section-heading-row">

        <span class="section-heading">
          SATELLITE BASEMAPS
        </span>

        <span class="section-line"></span>

      </div>


      <div class="layers-list">

        {#each $layersState.filter(l => l.category === 'satellite') as layer}

          <div
            class="layer-item"
            class:active={layer.visible}
          >

            <div class="layer-top-row">


              <!-- Visibility -->

              <button
                class="vis-toggle"
                class:visible={layer.visible}
                on:click={() => toggleVisibility(layer.id)}
                title={
                  layer.visible
                    ? 'Hide layer'
                    : 'Show layer'
                }
                aria-label={
                  layer.visible
                    ? `Hide ${layer.name}`
                    : `Show ${layer.name}`
                }
              >

                {#if layer.visible}

                  <Eye
                    size={15}
                    strokeWidth={1.7}
                  />

                {:else}

                  <EyeOff
                    size={15}
                    strokeWidth={1.7}
                  />

                {/if}

              </button>


              <!-- Information -->

              <div class="layer-info">

                <span class="layer-name">
                  {layer.name}
                </span>

                <span class="layer-desc">
                  {layer.description}
                </span>

              </div>

            </div>


            <!-- Opacity -->

            {#if layer.visible}

              <div class="opacity-control">

                <Sliders
                  size={11}
                  strokeWidth={1.6}
                  class="slider-icon"
                />


                <input
                  type="range"
                  min="0.1"
                  max="1.0"
                  step="0.05"
                  value={layer.opacity}
                  on:input={(e) =>
                    updateOpacity(
                      layer.id,
                      parseFloat(
                        e.currentTarget.value
                      )
                    )
                  }
                  class="opacity-slider"
                  aria-label={`${layer.name} opacity`}
                />


                <span class="opacity-val">
                  {Math.round(layer.opacity * 100)}%
                </span>

              </div>

            {/if}

          </div>

        {/each}

      </div>

    </div>


    <!-- =================================================
         ANALYSIS OVERLAYS
         ================================================= -->

    <div class="layer-section">

      <div class="section-heading-row">

        <span class="section-heading">
          ANALYSIS & VECTOR OVERLAYS
        </span>

        <span class="section-line"></span>

      </div>


      <div class="layers-list">

        {#each $layersState.filter(l => l.category === 'analysis') as layer}

          <div
            class="layer-item"
            class:active={layer.visible}
          >

            <div class="layer-top-row">

              <button
                class="vis-toggle"
                class:visible={layer.visible}
                on:click={() => toggleVisibility(layer.id)}
                title={
                  layer.visible
                    ? 'Hide layer'
                    : 'Show layer'
                }
                aria-label={
                  layer.visible
                    ? `Hide ${layer.name}`
                    : `Show ${layer.name}`
                }
              >

                {#if layer.visible}

                  <Eye
                    size={15}
                    strokeWidth={1.7}
                  />

                {:else}

                  <EyeOff
                    size={15}
                    strokeWidth={1.7}
                  />

                {/if}

              </button>


              <div class="layer-info">

                <span class="layer-name">
                  {layer.name}
                </span>

                <span class="layer-desc">
                  {layer.description}
                </span>

              </div>

            </div>


            {#if layer.visible}

              <div class="opacity-control">

                <Sliders
                  size={11}
                  strokeWidth={1.6}
                  class="slider-icon"
                />


                <input
                  type="range"
                  min="0.1"
                  max="1.0"
                  step="0.05"
                  value={layer.opacity}
                  on:input={(e) =>
                    updateOpacity(
                      layer.id,
                      parseFloat(
                        e.currentTarget.value
                      )
                    )
                  }
                  class="opacity-slider"
                  aria-label={`${layer.name} opacity`}
                />


                <span class="opacity-val">
                  {Math.round(layer.opacity * 100)}%
                </span>

              </div>

            {/if}

          </div>

        {/each}

      </div>

    </div>


    <!-- =================================================
         SCIENTIFIC TOPOGRAPHY
         ================================================= -->

    <div class="layer-section">

      <div class="section-heading-row">

        <span class="section-heading">
          SCIENTIFIC TOPOGRAPHY
        </span>

        <span class="section-line"></span>

      </div>


      <div class="layers-list">

        {#each $layersState.filter(l => l.category === 'scientific') as layer}

          <div
            class="layer-item"
            class:active={layer.visible}
          >

            <div class="layer-top-row">

              <button
                class="vis-toggle"
                class:visible={layer.visible}
                on:click={() => toggleVisibility(layer.id)}
                title={
                  layer.visible
                    ? 'Hide layer'
                    : 'Show layer'
                }
                aria-label={
                  layer.visible
                    ? `Hide ${layer.name}`
                    : `Show ${layer.name}`
                }
              >

                {#if layer.visible}

                  <Eye
                    size={15}
                    strokeWidth={1.7}
                  />

                {:else}

                  <EyeOff
                    size={15}
                    strokeWidth={1.7}
                  />

                {/if}

              </button>


              <div class="layer-info">

                <span class="layer-name">
                  {layer.name}
                </span>

                <span class="layer-desc">
                  {layer.description}
                </span>

              </div>

            </div>


            {#if layer.visible}

              <div class="opacity-control">

                <Sliders
                  size={11}
                  strokeWidth={1.6}
                  class="slider-icon"
                />


                <input
                  type="range"
                  min="0.1"
                  max="1.0"
                  step="0.05"
                  value={layer.opacity}
                  on:input={(e) =>
                    updateOpacity(
                      layer.id,
                      parseFloat(
                        e.currentTarget.value
                      )
                    )
                  }
                  class="opacity-slider"
                  aria-label={`${layer.name} opacity`}
                />


                <span class="opacity-val">
                  {Math.round(layer.opacity * 100)}%
                </span>

              </div>

            {/if}

          </div>

        {/each}

      </div>

    </div>

  </div>

</div>


<style>

  /* =========================================================
     DRAWER
     ========================================================= */

  .layers-drawer {

    width:
      300px;

    height:
      100%;

    flex-shrink:
      0;

    position:
      relative;

    display:
      flex;

    flex-direction:
      column;

    overflow:
      hidden;

    background:
      #070707;

    border-right:
      1px solid
      rgba(255,255,255,0.09);

    color:
      #ffffff;

    z-index:
      35;

    font-family:
      Inter,
      "SF Pro Display",
      "SF Pro Text",
      -apple-system,
      BlinkMacSystemFont,
      "Helvetica Neue",
      Arial,
      sans-serif;

    box-shadow:
      8px 0 25px
      rgba(0,0,0,0.18);
  }


  /* =========================================================
     HEADER
     ========================================================= */

  .drawer-header {

    height:
      64px;

    flex-shrink:
      0;

    display:
      flex;

    align-items:
      center;

    justify-content:
      space-between;

    padding:
      0 15px;

    background:
      rgba(255,255,255,0.018);

    border-bottom:
      1px solid
      rgba(255,255,255,0.075);
  }


  .title-row {

    min-width:
      0;

    display:
      flex;

    align-items:
      center;

    gap:
      9px;
  }


  /* =========================================================
     TITLE ICON
     ========================================================= */

  .title-icon {

    width:
      30px;

    height:
      30px;

    flex-shrink:
      0;

    display:
      flex;

    align-items:
      center;

    justify-content:
      center;

    border-radius:
      8px;

    background:
      rgba(255,255,255,0.055);

    border:
      1px solid
      rgba(255,255,255,0.10);

    color:
      rgba(255,255,255,0.82);

    box-shadow:
      inset 0 1px 0
      rgba(255,255,255,0.045);
  }


  .title-content {

    min-width:
      0;

    display:
      flex;

    flex-direction:
      column;

    gap:
      2px;
  }


  .drawer-title {

    margin:
      0;

    font-size:
      12.5px;

    line-height:
      1.2;

    font-weight:
      650;

    letter-spacing:
      -0.015em;

    color:
      #ffffff;
  }


  .drawer-subtitle {

    font-size:
      9px;

    line-height:
      1.2;

    color:
      rgba(255,255,255,0.32);
  }


  /* =========================================================
     CLOSE
     ========================================================= */

  .close-btn {

    width:
      30px;

    height:
      30px;

    flex-shrink:
      0;

    display:
      flex;

    align-items:
      center;

    justify-content:
      center;

    border-radius:
      8px;

    border:
      1px solid
      transparent;

    background:
      transparent;

    color:
      rgba(255,255,255,0.34);

    cursor:
      pointer;

    transition:
      all 0.15s ease;
  }


  .close-btn:hover {

    color:
      #ffffff;

    background:
      rgba(255,255,255,0.06);

    border-color:
      rgba(255,255,255,0.09);
  }


  /* =========================================================
     CONTENT
     ========================================================= */

  .drawer-content {

    flex:
      1;

    min-height:
      0;

    overflow-y:
      auto;

    padding:
      17px 13px 20px;

    display:
      flex;

    flex-direction:
      column;

    gap:
      24px;
  }


  .drawer-content::-webkit-scrollbar {

    width:
      4px;
  }


  .drawer-content::-webkit-scrollbar-track {

    background:
      transparent;
  }


  .drawer-content::-webkit-scrollbar-thumb {

    background:
      rgba(255,255,255,0.12);

    border-radius:
      10px;
  }


  /* =========================================================
     SECTION
     ========================================================= */

  .layer-section {

    display:
      flex;

    flex-direction:
      column;

    gap:
      9px;
  }


  .section-heading-row {

    display:
      flex;

    align-items:
      center;

    gap:
      8px;

    padding:
      0 3px;
  }


  .section-heading {

    flex-shrink:
      0;

    font-size:
      8.5px;

    line-height:
      1;

    font-weight:
      700;

    letter-spacing:
      0.11em;

    color:
      rgba(255,255,255,0.32);
  }


  .section-line {

    flex:
      1;

    height:
      1px;

    background:
      rgba(255,255,255,0.06);
  }


  /* =========================================================
     LIST
     ========================================================= */

  .layers-list {

    display:
      flex;

    flex-direction:
      column;

    gap:
      5px;
  }


  /* =========================================================
     LAYER ITEM
     ========================================================= */

  .layer-item {

    position:
      relative;

    display:
      flex;

    flex-direction:
      column;

    gap:
      8px;

    padding:
      10px;

    border-radius:
      9px;

    background:
      rgba(255,255,255,0.018);

    border:
      1px solid
      rgba(255,255,255,0.055);

    transition:
      background 0.15s ease,
      border-color 0.15s ease;
  }


  .layer-item:hover {

    background:
      rgba(255,255,255,0.035);

    border-color:
      rgba(255,255,255,0.09);
  }


  /* =========================================================
     ACTIVE LAYER
     ========================================================= */

  .layer-item.active {

    background:
      rgba(255,255,255,0.045);

    border-color:
      rgba(255,255,255,0.13);

    box-shadow:
      inset 0 1px 0
      rgba(255,255,255,0.035);
  }


  /* =========================================================
     TOP ROW
     ========================================================= */

  .layer-top-row {

    display:
      flex;

    align-items:
      flex-start;

    gap:
      9px;
  }


  /* =========================================================
     VISIBILITY BUTTON
     ========================================================= */

  .vis-toggle {

    width:
      28px;

    height:
      28px;

    flex-shrink:
      0;

    display:
      flex;

    align-items:
      center;

    justify-content:
      center;

    margin-top:
      -1px;

    padding:
      0;

    border-radius:
      7px;

    background:
      rgba(255,255,255,0.025);

    border:
      1px solid
      rgba(255,255,255,0.065);

    color:
      rgba(255,255,255,0.24);

    cursor:
      pointer;

    transition:
      all 0.15s ease;
  }


  .vis-toggle:hover {

    color:
      rgba(255,255,255,0.80);

    background:
      rgba(255,255,255,0.065);

    border-color:
      rgba(255,255,255,0.12);
  }


  .vis-toggle.visible {

    color:
      #ffffff;

    background:
      rgba(255,255,255,0.085);

    border-color:
      rgba(255,255,255,0.14);
  }


  /* =========================================================
     LAYER INFO
     ========================================================= */

  .layer-info {

    min-width:
      0;

    flex:
      1;

    display:
      flex;

    flex-direction:
      column;

    gap:
      3px;

    padding-top:
      1px;
  }


  .layer-name {

    overflow:
      hidden;

    text-overflow:
      ellipsis;

    white-space:
      nowrap;

    font-size:
      11.5px;

    line-height:
      1.3;

    font-weight:
      600;

    color:
      rgba(255,255,255,0.78);
  }


  .layer-item.active
  .layer-name {

    color:
      #ffffff;
  }


  .layer-desc {

    overflow:
      hidden;

    text-overflow:
      ellipsis;

    white-space:
      nowrap;

    font-size:
      9.5px;

    line-height:
      1.35;

    color:
      rgba(255,255,255,0.28);
  }


  /* =========================================================
     OPACITY
     ========================================================= */

  .opacity-control {

    display:
      flex;

    align-items:
      center;

    gap:
      7px;

    padding-top:
      8px;

    border-top:
      1px solid
      rgba(255,255,255,0.055);
  }


  .slider-icon {

    flex-shrink:
      0;

    color:
      rgba(255,255,255,0.30);
  }


  .opacity-slider {

    flex:
      1;

    min-width:
      0;

    height:
      3px;

    appearance:
      none;

    -webkit-appearance:
      none;

    background:
      rgba(255,255,255,0.14);

    border-radius:
      10px;

    outline:
      none;

    cursor:
      pointer;
  }


  .opacity-slider::-webkit-slider-thumb {

    appearance:
      none;

    -webkit-appearance:
      none;

    width:
      12px;

    height:
      12px;

    border-radius:
      50%;

    background:
      #ffffff;

    border:
      2px solid
      #080808;

    box-shadow:
      0 0 0 1px
      rgba(255,255,255,0.25);

    cursor:
      pointer;
  }


  .opacity-slider::-moz-range-thumb {

    width:
      12px;

    height:
      12px;

    border-radius:
      50%;

    background:
      #ffffff;

    border:
      2px solid
      #080808;

    box-shadow:
      0 0 0 1px
      rgba(255,255,255,0.25);

    cursor:
      pointer;
  }


  .opacity-slider:focus-visible {

    outline:
      1px solid
      rgba(255,255,255,0.45);

    outline-offset:
      3px;
  }


  .opacity-val {

    width:
      32px;

    flex-shrink:
      0;

    text-align:
      right;

    font-family:
      var(--font-mono, "SF Mono", monospace);

    font-size:
      8.5px;

    font-variant-numeric:
      tabular-nums;

    color:
      rgba(255,255,255,0.38);
  }


  /* =========================================================
     FOCUS
     ========================================================= */

  .close-btn:focus-visible,
  .vis-toggle:focus-visible {

    outline:
      1px solid
      rgba(255,255,255,0.5);

    outline-offset:
      2px;
  }


  /* =========================================================
     RESPONSIVE
     ========================================================= */

  @media (max-width: 700px) {

    .layers-drawer {

      width:
        min(300px, 86vw);
    }
  }


  @media (max-height: 700px) {

    .drawer-content {

      gap:
        18px;

      padding-top:
        13px;
    }


    .layer-item {

      padding:
        8px;
    }


    .layer-section {

      gap:
        7px;
    }
  }

</style>