<script lang="ts">
  import { currentResult } from '../stores';
  import EChartRenderer from './EChartRenderer.svelte';

  import {
    Layers,
    Calendar,
    Info,
    Box,
    Activity
  } from 'lucide-svelte';


  // =========================================================
  // BACKEND VISUALIZATIONS
  // =========================================================

  $: visualizations =
    $currentResult?.visualizations || [];

  $: hasVisualizations =
    visualizations.length > 0;


  // =========================================================
  // VIEW STATE
  // =========================================================

  let selectedVisIndex = 0;

  let viewDimension:
    '2d' | '3d' = '2d';


  $: if (
    selectedVisIndex >= visualizations.length
  ) {
    selectedVisIndex = 0;
  }


  $: currentVis =
    visualizations[selectedVisIndex] || null;


  // =========================================================
  // HEADER DATA
  // =========================================================

  $: title =
    currentVis?.title ||
    (
      $currentResult?.aoi?.name
        ? `${$currentResult.aoi.name} Analysis`
        : 'Earth Observation'
    );


  $: subTitle =
    currentVis?.sub_title ||
    (
      $currentResult?.provenance?.model_name
        ? `${$currentResult.provenance.model_name} • Remote Sensing`
        : 'Geospatial Intelligence'
    );


  $: dateRange =
    $currentResult?.provenance?.acquisition_dates ||
    '';
</script>


<div class="scientific-panel">

  <!-- =====================================================
       PANEL HEADER
       ===================================================== -->

  <div class="panel-header">

    <div class="header-left">

      <div class="title-row">

        <div class="title-icon">
          <Layers
            size={13}
            strokeWidth={1.7}
          />
        </div>

        <span class="panel-title">
          {title}
        </span>


        {#if currentVis}

          <span class="type-badge">
            {(currentVis.type || 'chart').toUpperCase()}
          </span>

        {/if}

      </div>


      <span class="panel-sub">
        {subTitle}
      </span>

    </div>


    <!-- =================================================
         HEADER CONTROLS
         ================================================= -->

    <div class="header-controls">


      <!-- 2D / 3D -->

      {#if hasVisualizations}

        <div class="dim-toggle-group">

          <button
            class="dim-btn"
            class:active={viewDimension === '2d'}
            on:click={() => (viewDimension = '2d')}
            title="2D Analytical Chart"
          >

            <Activity
              size={11}
              strokeWidth={1.8}
            />

            <span>
              2D
            </span>

          </button>


          <button
            class="dim-btn"
            class:active={viewDimension === '3d'}
            on:click={() => (viewDimension = '3d')}
            title="3D Topographic / Mesh Surface"
          >

            <Box
              size={11}
              strokeWidth={1.8}
            />

            <span>
              3D
            </span>

          </button>

        </div>

      {/if}


      <!-- VISUALIZATION TABS -->

      {#if visualizations.length > 1}

        <div class="vis-tabs">

          {#each visualizations as v, idx}

            <button
              class="vis-tab-btn"
              class:active={selectedVisIndex === idx}
              on:click={() => (selectedVisIndex = idx)}
            >

              {v.title || `Vis ${idx + 1}`}

            </button>

          {/each}

        </div>

      {/if}


      <!-- DATE -->

      {#if dateRange}

        <div class="date-badge">

          <Calendar
            size={11}
            strokeWidth={1.7}
          />

          <span>
            {dateRange}
          </span>

        </div>

      {/if}

    </div>

  </div>


  <!-- =====================================================
       VISUALIZATION CANVAS
       ===================================================== -->

  <div class="vis-canvas-container">

    {#if hasVisualizations && currentVis}


      <!-- =================================================
           3D VIEW
           ================================================= -->

      {#if viewDimension === '3d'}

        <div class="renderer-frame">

          <EChartRenderer
            type="3d_surface"
            title={currentVis.title}
            subTitle={currentVis.sub_title}
            data={currentVis.data}
          />

        </div>


      <!-- =================================================
           CESIUM VIEW
           ================================================= -->

      {:else if currentVis.renderer === 'cesium'}

        <div class="cesium-vis-status-card">

          <div class="cesium-card-badge">

            <span class="pulse-dot"></span>

            <span>
              ACTIVE 3D GEOSPATIAL LAYER
            </span>

          </div>


          <h4 class="cesium-card-title">
            {currentVis.title}
          </h4>


          <p class="cesium-card-desc">
            {currentVis.description ||
              'Spatial vector and raster overlay rendered directly on the Cesium 3D Globe above.'}
          </p>


          {#if currentVis.legend}

            <div class="cesium-legend-strip">

              <span class="legend-lbl">
                {currentVis.legend.title || 'Layer Metric'}
              </span>

              <span class="legend-separator">
                /
              </span>

              <span class="legend-val">

                {currentVis.layer?.metric?.value ||
                  currentVis.legend.unit ||
                  'Active'}

              </span>

            </div>

          {/if}


          <button
            class="switch-3d-btn"
            on:click={() => (viewDimension = '3d')}
          >

            <Box
              size={12}
              strokeWidth={1.7}
            />

            <span>
              Switch to 3D Mesh Surface
            </span>

          </button>

        </div>


      <!-- =================================================
           NORMAL 2D CHART
           ================================================= -->

      {:else}

        <div class="renderer-frame">

          <EChartRenderer
            type={currentVis.type}
            title=""
            subTitle=""
            data={currentVis.data}
            xAxis={currentVis.xAxis}
            yAxis={currentVis.yAxis}
            series={currentVis.series}
            visualMap={currentVis.visualMap}
          />

        </div>

      {/if}


    <!-- ===================================================
         EMPTY STATE
         =================================================== -->

    {:else}

      <div class="no-chart-placeholder">

        <div class="placeholder-icon-wrap">

          <Info
            size={20}
            strokeWidth={1.6}
            class="info-icon"
          />

        </div>


        <div class="placeholder-text">

          <span class="placeholder-title">
            Earth Observation Planning & Synthesis
          </span>


          <span class="placeholder-desc">
            No quantitative satellite telemetry or numerical
            chart is required for this inquiry. Refer to the
            specialist foundation model recommendations and
            sensor configuration on the right.
          </span>

        </div>

      </div>

    {/if}

  </div>

</div>


<style>

  /* =========================================================
     PANEL
     ========================================================= */

  .scientific-panel {

    width: 100%;
    height: 100%;

    display: flex;
    flex-direction: column;

    position: relative;

    overflow: hidden;

    padding: 12px 14px;

    background:
      linear-gradient(
        145deg,
        rgba(18,18,18,0.96),
        rgba(5,5,5,0.985)
      );

    border:
      1px solid
      rgba(255,255,255,0.09);

    border-radius: 13px;

    color: #ffffff;

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
      inset 0 1px 0
      rgba(255,255,255,0.035),
      0 10px 30px
      rgba(0,0,0,0.18);
  }


  /* subtle glass highlight */

  .scientific-panel::before {

    content: "";

    position: absolute;

    top: 0;
    left: 12%;
    right: 12%;

    height: 1px;

    background:
      linear-gradient(
        90deg,
        transparent,
        rgba(255,255,255,0.16),
        transparent
      );

    pointer-events: none;
  }


  /* =========================================================
     HEADER
     ========================================================= */

  .panel-header {

    display: flex;

    align-items: center;
    justify-content: space-between;

    gap: 16px;

    margin-bottom: 7px;

    padding-bottom: 9px;

    border-bottom:
      1px solid
      rgba(255,255,255,0.065);

    flex-shrink: 0;
  }


  .header-left {

    min-width: 0;

    max-width: 42%;

    display: flex;

    flex-direction: column;

    gap: 3px;
  }


  .title-row {

    min-width: 0;

    display: flex;

    align-items: center;

    gap: 7px;
  }


  /* =========================================================
     TITLE ICON
     ========================================================= */

  .title-icon {

    width: 25px;
    height: 25px;

    flex-shrink: 0;

    display: flex;

    align-items: center;
    justify-content: center;

    border-radius: 7px;

    color:
      rgba(255,255,255,0.78);

    background:
      rgba(255,255,255,0.055);

    border:
      1px solid
      rgba(255,255,255,0.09);

    box-shadow:
      inset 0 1px 0
      rgba(255,255,255,0.045);
  }


  /* =========================================================
     TITLE
     ========================================================= */

  .panel-title {

    min-width: 0;

    overflow: hidden;

    text-overflow: ellipsis;

    white-space: nowrap;

    font-size: 13px;

    line-height: 1.2;

    font-weight: 620;

    letter-spacing:
      -0.015em;

    color:
      rgba(255,255,255,0.92);
  }


  /* =========================================================
     TYPE BADGE
     ========================================================= */

  .type-badge {

    flex-shrink: 0;

    padding:
      2px 5px;

    border-radius: 4px;

    background:
      rgba(255,255,255,0.065);

    border:
      1px solid
      rgba(255,255,255,0.11);

    color:
      rgba(255,255,255,0.52);

    font-size: 8px;

    font-weight: 700;

    letter-spacing:
      0.55px;

    white-space: nowrap;
  }


  .panel-sub {

    overflow: hidden;

    text-overflow: ellipsis;

    white-space: nowrap;

    font-size: 9.5px;

    color:
      rgba(255,255,255,0.36);
  }


  /* =========================================================
     HEADER CONTROLS
     ========================================================= */

  .header-controls {

    display: flex;

    align-items: center;

    justify-content: flex-end;

    gap: 7px;

    flex-shrink: 0;

    min-width: 0;
  }


  /* =========================================================
     2D / 3D TOGGLE
     ========================================================= */

  .dim-toggle-group {

    display: flex;

    align-items: center;

    gap: 2px;

    padding: 2px;

    border-radius: 7px;

    background:
      rgba(255,255,255,0.035);

    border:
      1px solid
      rgba(255,255,255,0.09);
  }


  .dim-btn {

    height: 25px;

    display: flex;

    align-items: center;

    gap: 4px;

    padding:
      0 8px;

    border-radius: 5px;

    border:
      1px solid transparent;

    background:
      transparent;

    color:
      rgba(255,255,255,0.38);

    font-family:
      inherit;

    font-size: 9px;

    font-weight: 500;

    cursor: pointer;

    transition:
      all 0.16s ease;
  }


  .dim-btn:hover {

    color:
      rgba(255,255,255,0.82);

    background:
      rgba(255,255,255,0.045);
  }


  .dim-btn.active {

    color:
      #050505;

    background:
      #ffffff;

    border-color:
      rgba(255,255,255,0.9);

    font-weight:
      650;

    box-shadow:
      0 2px 7px
      rgba(0,0,0,0.35);
  }


  /* =========================================================
     VISUALIZATION TABS
     ========================================================= */

  .vis-tabs {

    max-width: 230px;

    display: flex;

    align-items: center;

    overflow-x: auto;

    gap: 2px;

    padding: 2px;

    border-radius: 7px;

    background:
      rgba(255,255,255,0.035);

    border:
      1px solid
      rgba(255,255,255,0.08);
  }


  .vis-tabs::-webkit-scrollbar {

    display: none;
  }


  .vis-tab-btn {

    flex-shrink: 0;

    min-height: 24px;

    padding:
      0 8px;

    border-radius: 5px;

    border:
      1px solid transparent;

    background:
      transparent;

    color:
      rgba(255,255,255,0.36);

    font-family:
      inherit;

    font-size: 9px;

    font-weight: 500;

    cursor: pointer;

    transition:
      all 0.16s ease;

    white-space: nowrap;
  }


  .vis-tab-btn:hover {

    color:
      rgba(255,255,255,0.78);

    background:
      rgba(255,255,255,0.045);
  }


  .vis-tab-btn.active {

    color:
      #050505;

    background:
      #ffffff;

    border-color:
      #ffffff;

    font-weight:
      650;
  }


  /* =========================================================
     DATE BADGE
     ========================================================= */

  .date-badge {

    height: 25px;

    display: flex;

    align-items: center;

    gap: 5px;

    padding:
      0 8px;

    border-radius: 7px;

    background:
      rgba(255,255,255,0.035);

    border:
      1px solid
      rgba(255,255,255,0.08);

    color:
      rgba(255,255,255,0.42);

    font-family:
      var(--font-mono, "SF Mono", monospace);

    font-size: 8.5px;

    white-space: nowrap;
  }


  .date-badge :global(svg) {

    color:
      rgba(255,255,255,0.62);
  }


  /* =========================================================
     CANVAS
     ========================================================= */

  .vis-canvas-container {

    flex: 1;

    width: 100%;

    min-height: 180px;

    position: relative;

    overflow: hidden;
  }


  .renderer-frame {

    width: 100%;
    height: 100%;

    min-height: 180px;

    position: relative;

    overflow: hidden;

    border-radius: 9px;

    background:
      rgba(0,0,0,0.18);

    border:
      1px solid
      rgba(255,255,255,0.045);
  }


  /* =========================================================
     EMPTY STATE
     ========================================================= */

  .no-chart-placeholder {

    width: 100%;
    height: 100%;

    display: flex;

    align-items: center;
    justify-content: center;

    gap: 14px;

    padding: 24px;

    border-radius: 10px;

    background:
      linear-gradient(
        145deg,
        rgba(255,255,255,0.025),
        rgba(255,255,255,0.012)
      );

    border:
      1px dashed
      rgba(255,255,255,0.10);
  }


  .placeholder-icon-wrap {

    width: 42px;
    height: 42px;

    flex-shrink: 0;

    display: flex;

    align-items: center;
    justify-content: center;

    border-radius: 11px;

    background:
      rgba(255,255,255,0.045);

    border:
      1px solid
      rgba(255,255,255,0.09);

    box-shadow:
      inset 0 1px 0
      rgba(255,255,255,0.045);
  }


  :global(.info-icon) {

    color:
      rgba(255,255,255,0.72);
  }


  .placeholder-text {

    display: flex;

    flex-direction: column;

    gap: 5px;

    max-width: 430px;
  }


  .placeholder-title {

    font-size: 12px;

    font-weight: 600;

    color:
      rgba(255,255,255,0.78);
  }


  .placeholder-desc {

    font-size: 10.5px;

    line-height: 1.5;

    color:
      rgba(255,255,255,0.30);
  }


  /* =========================================================
     CESIUM STATUS
     ========================================================= */

  .cesium-vis-status-card {

    width: 100%;
    height: 100%;

    display: flex;

    flex-direction: column;

    align-items: center;
    justify-content: center;

    text-align: center;

    padding: 24px;

    border-radius: 10px;

    background:
      radial-gradient(
        circle at 50% 30%,
        rgba(255,255,255,0.045),
        transparent 68%
      );

    border:
      1px dashed
      rgba(255,255,255,0.12);
  }


  /* =========================================================
     CESIUM BADGE
     ========================================================= */

  .cesium-card-badge {

    display: inline-flex;

    align-items: center;

    gap: 7px;

    margin-bottom: 9px;

    padding:
      4px 9px;

    border-radius: 12px;

    background:
      rgba(255,255,255,0.055);

    border:
      1px solid
      rgba(255,255,255,0.10);

    color:
      rgba(255,255,255,0.56);

    font-size: 8.5px;

    font-weight: 700;

    letter-spacing:
      0.08em;
  }


  /* =========================================================
     PULSE
     ========================================================= */

  .pulse-dot {

    width: 6px;
    height: 6px;

    flex-shrink: 0;

    border-radius: 50%;

    background:
      #ffffff;

    box-shadow:
      0 0 7px
      rgba(255,255,255,0.45);

    animation:
      pulse 2s infinite;
  }


  @keyframes pulse {

    0% {
      transform: scale(0.9);
      opacity: 0.55;
    }

    50% {
      transform: scale(1.2);
      opacity: 1;
    }

    100% {
      transform: scale(0.9);
      opacity: 0.55;
    }
  }


  /* =========================================================
     CESIUM TITLE
     ========================================================= */

  .cesium-card-title {

    margin:
      0 0 7px;

    font-size:
      14px;

    line-height:
      1.25;

    font-weight:
      620;

    color:
      #ffffff;

    letter-spacing:
      -0.015em;
  }


  .cesium-card-desc {

    max-width:
      440px;

    margin:
      0 0 13px;

    font-size:
      10.5px;

    line-height:
      1.5;

    color:
      rgba(255,255,255,0.38);
  }


  /* =========================================================
     LEGEND
     ========================================================= */

  .cesium-legend-strip {

    display: inline-flex;

    align-items: center;

    gap: 8px;

    padding:
      5px 10px;

    border-radius:
      7px;

    background:
      rgba(255,255,255,0.04);

    border:
      1px solid
      rgba(255,255,255,0.09);

    font-size:
      9.5px;
  }


  .legend-lbl {

    color:
      rgba(255,255,255,0.32);
  }


  .legend-separator {

    color:
      rgba(255,255,255,0.18);
  }


  .legend-val {

    color:
      #ffffff;

    font-weight:
      600;
  }


  /* =========================================================
     SWITCH TO 3D
     ========================================================= */

  .switch-3d-btn {

    display: inline-flex;

    align-items: center;

    gap: 6px;

    margin-top: 11px;

    padding:
      7px 13px;

    border-radius: 7px;

    background:
      rgba(255,255,255,0.07);

    border:
      1px solid
      rgba(255,255,255,0.13);

    color:
      rgba(255,255,255,0.78);

    font-family:
      inherit;

    font-size:
      9.5px;

    font-weight:
      600;

    cursor:
      pointer;

    transition:
      all 0.16s ease;
  }


  .switch-3d-btn:hover {

    background:
      #ffffff;

    border-color:
      #ffffff;

    color:
      #050505;

    transform:
      translateY(-1px);

    box-shadow:
      0 5px 16px
      rgba(0,0,0,0.35);
  }


  /* =========================================================
     FOCUS
     ========================================================= */

  .dim-btn:focus-visible,
  .vis-tab-btn:focus-visible,
  .switch-3d-btn:focus-visible {

    outline:
      1px solid
      rgba(255,255,255,0.5);

    outline-offset:
      2px;
  }


  /* =========================================================
     RESPONSIVE
     ========================================================= */

  @media (max-width: 900px) {

    .header-left {

      max-width:
        35%;
    }

    .vis-tabs {

      max-width:
        180px;
    }
  }


  @media (max-width: 700px) {

    .panel-header {

      align-items:
        flex-start;

      flex-direction:
        column;
    }


    .header-left {

      width:
        100%;

      max-width:
        100%;
    }


    .header-controls {

      width:
        100%;

      justify-content:
        flex-start;

      flex-wrap:
        wrap;
    }
  }

</style>