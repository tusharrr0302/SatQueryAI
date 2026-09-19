<script lang="ts">
  import { createEventDispatcher } from 'svelte';

  import {
    Sprout,
    Flame,
    Building2,
    TreePine,
    Droplet,
    ArrowRight,
  } from 'lucide-svelte';

  const dispatch = createEventDispatcher<{
    launchQuery: string;
  }>();

  const useCases = [
    {
      id: 'urban',
      title: 'Urban Planning & Sprawl',
      category: 'Metropolitan Development',
      icon: Building2,
      query: 'Show me how Delhi changed over the last 10 years',
      dataset: 'Sentinel-2 • Sentinel-1 SAR',
      model: 'Prithvi-EO-2.0',
      analysis: 'Bi-Temporal Change Detection',
      vis: '3D Surface & Change Map',
      description:
        'Longitudinal urban boundary tracking, impervious surface index calculation, and infrastructure corridor sprawl modeling.'
    },
    {
      id: 'veg',
      title: 'Vegetation Health & Phenology',
      category: 'Ecology & Urban Greenspace',
      icon: Sprout,
      query:
        'Show me the vegetation change in Delhi over the last 1 year using Sentinel-2 data.',
      dataset: 'Sentinel-2 • 10m Multispectral',
      model: 'Prithvi-EO-2.0',
      analysis: 'Vegetation Index • NDVI',
      vis: '3D Surface & NDVI Ramp',
      description:
        'Canopy density monitoring, chlorophyll reflectance mapping, and seasonal green cover regeneration analytics.'
    },
    {
      id: 'forestry',
      title: 'Forest Canopy & Deforestation',
      category: 'Conservation Intelligence',
      icon: TreePine,
      query: 'Show deforestation in the Amazon',
      dataset: 'Sentinel-1 SAR • Sentinel-2',
      model: 'TerraFM',
      analysis: 'Multisensor Disturbance Detection',
      vis: 'Forest Loss Map & Time Series',
      description:
        'Cloud-penetrating SAR backscatter combined with optical red-edge information to detect forest disturbance and clearings.'
    },
    {
      id: 'disaster',
      title: 'Disaster Management & Flash Floods',
      category: 'Emergency Response',
      icon: Flame,
      query: 'Show flood extent in Derna from September 2023',
      dataset: 'Sentinel-1 SAR • Sentinel-2',
      model: 'TerraFM',
      analysis: 'Flood Inundation & Sedimentation',
      vis: 'Inundation Contours & Polygon Map',
      description:
        'Rapid all-weather damage assessment, sediment plume tracking, and spatial mapping of affected areas.'
    },
    {
      id: 'agri',
      title: 'Agricultural Crop Analytics',
      category: 'Food Security',
      icon: Sprout,
      query: 'Analyze crop health in Punjab',
      dataset: 'Sentinel-2 L2A',
      model: 'Prithvi-EO-2.0',
      analysis: 'Phenology & Biomass Forecasting',
      vis: 'Crop Index & Biomass Matrix',
      description:
        'Multi-temporal crop emergence evaluation, yield estimation, moisture stress tracking, and harvest timing analysis.'
    },
    {
      id: 'water',
      title: 'Water Resources & Reservoirs',
      category: 'Hydrological Modeling',
      icon: Droplet,
      query: 'Detect water bodies and surface area in Delhi',
      dataset: 'Sentinel-2 • Landsat-9',
      model: 'CLOSP',
      analysis: 'Surface Water Delineation',
      vis: 'Water Boundary & Time Series',
      description:
        'Wetland depletion tracking, reservoir monitoring, and seasonal surface-water extent analysis.'
    }
  ];

  function launchCase(query: string) {
    dispatch('launchQuery', query);
  }
</script>


<div class="use-cases-page">


  <!-- =====================================================
       BACKGROUND
       ===================================================== -->

  <div class="background-grid"></div>

  <div class="background-glow"></div>


  <!-- =====================================================
       PAGE CONTENT
       ===================================================== -->

  <div class="page-content">


    <!-- ===================================================
         HEADER
         =================================================== -->

    <section class="page-header">

      <div class="header-eyebrow">

        <span class="eyebrow-line"></span>

        <span>OPERATIONAL CAPABILITIES</span>

        <span class="eyebrow-line"></span>

      </div>


      <h1 class="page-title">
        Remote Sensing
        <span>Intelligence Applications</span>
      </h1>


      <p class="page-desc">
        Explore how natural-language questions can be transformed
        into satellite data selections, Earth observation models,
        scientific analysis, and visual geospatial outputs.
      </p>


      <div class="header-meta">

        <span>06 APPLICATIONS</span>

        <span class="meta-dot"></span>

        <span>EARTH OBSERVATION</span>

        <span class="meta-dot"></span>

        <span>AGENTIC TOOL SYSTEM</span>

      </div>

    </section>


    <!-- ===================================================
         CASE GRID
         =================================================== -->

    <section class="cases-grid">

      {#each useCases as item, index}

        <article class="case-card">


          <!-- Card number -->

          <div class="card-number">
            {String(index + 1).padStart(2, '0')}
          </div>


          <!-- Top -->

          <div class="case-top">

            <div class="case-icon-box">

              <svelte:component
                this={item.icon}
                size={21}
                strokeWidth={1.35}
              />

            </div>


            <div class="case-heading">

              <span class="case-category">
                {item.category}
              </span>

              <h2 class="case-title">
                {item.title}
              </h2>

            </div>

          </div>


          <!-- Description -->

          <p class="case-description">
            {item.description}
          </p>


          <!-- =================================================
               QUERY
               ================================================= -->

          <div class="query-section">

            <div class="section-label">
              NATURAL LANGUAGE QUERY
            </div>

            <div class="query-box">

              <span class="query-mark">“</span>

              <span class="query-text">
                {item.query}
              </span>

            </div>

          </div>


          <!-- =================================================
               PIPELINE
               ================================================= -->

          <div class="pipeline">

            <div class="pipeline-header">

              <span>
                ANALYSIS PIPELINE
              </span>

              <span class="pipeline-status">
                READY
              </span>

            </div>


            <div class="pipeline-grid">


              <!-- Dataset -->

              <div class="pipeline-item">

                <span class="pipeline-label">
                  DATASET
                </span>

                <span class="pipeline-value">
                  {item.dataset}
                </span>

              </div>


              <!-- Model -->

              <div class="pipeline-item">

                <span class="pipeline-label">
                  MODEL
                </span>

                <span class="pipeline-value">
                  {item.model}
                </span>

              </div>


              <!-- Analysis -->

              <div class="pipeline-item">

                <span class="pipeline-label">
                  ANALYSIS
                </span>

                <span class="pipeline-value">
                  {item.analysis}
                </span>

              </div>


              <!-- Visualization -->

              <div class="pipeline-item">

                <span class="pipeline-label">
                  VISUALIZATION
                </span>

                <span class="pipeline-value">
                  {item.vis}
                </span>

              </div>

            </div>

          </div>


          <!-- =================================================
               ACTION
               ================================================= -->

          <button
            class="launch-btn"
            on:click={() => launchCase(item.query)}
          >

            <span>
              Run Investigation
            </span>

            <span class="launch-icon">
              <ArrowRight
                size={15}
                strokeWidth={1.5}
              />
            </span>

          </button>


        </article>

      {/each}

    </section>


    <!-- =====================================================
         FOOTER
         ===================================================== -->

    <div class="page-footer">

      <div class="footer-line"></div>

      <span>
        SATQUERY / EARTH OBSERVATION INTELLIGENCE
      </span>

      <span>
        06 USE CASES
      </span>

    </div>

  </div>

</div>


<style>

  /* =========================================================
     ROOT
     ========================================================= */

  .use-cases-page {

    /*
     * Reserve the fixed navbar area so the page begins below it.
     */

    height: calc(100vh - var(--navbar-total-height));

    min-height: 0;

    width: 100%;

    position: relative;

    overflow-y: auto;

    overflow-x: hidden;

    box-sizing: border-box;

    background:
      #050505;

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

    scrollbar-width: thin;

    scrollbar-color:
      rgba(255,255,255,0.12)
      transparent;
  }


  .use-cases-page::-webkit-scrollbar {

    width: 5px;
  }


  .use-cases-page::-webkit-scrollbar-track {

    background:
      transparent;
  }


  .use-cases-page::-webkit-scrollbar-thumb {

    background:
      rgba(255,255,255,0.12);

    border-radius:
      999px;
  }


  /* =========================================================
     BACKGROUND
     ========================================================= */

  .background-grid {

    position: fixed;

    inset: var(--navbar-total-height) 0 0 0;

    pointer-events: none;

    opacity: 0.18;

    background-image:
      linear-gradient(
        rgba(255,255,255,0.025) 1px,
        transparent 1px
      ),
      linear-gradient(
        90deg,
        rgba(255,255,255,0.025) 1px,
        transparent 1px
      );

    background-size:
      80px 80px;

    mask-image:
      linear-gradient(
        to bottom,
        black,
        transparent 80%
      );

    -webkit-mask-image:
      linear-gradient(
        to bottom,
        black,
        transparent 80%
      );
  }


  .background-glow {

    position: fixed;

    width: 700px;

    height: 500px;

    top: var(--navbar-total-height);

    left: 50%;

    transform:
      translateX(-50%);

    pointer-events: none;

    background:
      radial-gradient(
        ellipse,
        rgba(255,255,255,0.045),
        transparent 68%
      );

    filter:
      blur(30px);

    opacity:
      0.7;
  }


  /* =========================================================
     CONTENT
     ========================================================= */

  .page-content {

    position: relative;

    z-index: 2;

    width: 100%;

    max-width: 1440px;

    margin: 0 auto;

    box-sizing: border-box;

    padding:
      54px
      48px
      40px;
  }


  /* =========================================================
     HEADER
     ========================================================= */

  .page-header {

    max-width:
      900px;

    margin-bottom:
      48px;
  }


  .header-eyebrow {

    display: flex;

    align-items: center;

    gap: 12px;

    margin-bottom:
      18px;

    color:
      rgba(255,255,255,0.38);

    font-size:
      9px;

    font-weight:
      600;

    letter-spacing:
      0.22em;

    text-transform:
      uppercase;
  }


  .eyebrow-line {

    width: 28px;

    height: 1px;

    background:
      rgba(255,255,255,0.24);
  }


  .page-title {

    margin: 0;

    max-width:
      850px;

    font-size:
      clamp(38px, 5vw, 64px);

    line-height:
      0.98;

    font-weight:
      350;

    letter-spacing:
      -0.055em;

    color:
      #ffffff;
  }


  .page-title span {

    display: block;

    color:
      rgba(255,255,255,0.32);

    font-weight:
      300;
  }


  .page-desc {

    max-width:
      690px;

    margin:
      22px 0 0;

    color:
      rgba(255,255,255,0.42);

    font-size:
      13px;

    line-height:
      1.75;

    font-weight:
      400;

    letter-spacing:
      -0.005em;
  }


  .header-meta {

    display: flex;

    align-items: center;

    flex-wrap: wrap;

    gap: 10px;

    margin-top:
      24px;

    color:
      rgba(255,255,255,0.24);

    font-family:
      var(--font-mono, monospace);

    font-size:
      8px;

    letter-spacing:
      0.12em;
  }


  .meta-dot {

    width: 3px;

    height: 3px;

    border-radius:
      50%;

    background:
      rgba(255,255,255,0.25);
  }


  /* =========================================================
     GRID
     ========================================================= */

  .cases-grid {

    display: grid;

    grid-template-columns:
      repeat(2, minmax(0, 1fr));

    gap:
      18px;
  }


  /* =========================================================
     CARD
     ========================================================= */

  .case-card {

    position: relative;

    min-width: 0;

    display: flex;

    flex-direction: column;

    padding:
      24px;

    border-radius:
      16px;

    background:
      linear-gradient(
        145deg,
        rgba(255,255,255,0.055),
        rgba(255,255,255,0.018)
      );

    border:
      1px solid
      rgba(255,255,255,0.095);

    box-shadow:
      inset 0 1px 0
      rgba(255,255,255,0.065),

      inset 0 -1px 0
      rgba(255,255,255,0.018),

      0 20px 60px
      rgba(0,0,0,0.25);

    backdrop-filter:
      blur(22px)
      saturate(115%);

    -webkit-backdrop-filter:
      blur(22px)
      saturate(115%);

    overflow:
      hidden;

    transition:
      transform 0.25s ease,
      border-color 0.25s ease,
      background 0.25s ease,
      box-shadow 0.25s ease;
  }


  /* Top glass reflection */

  .case-card::before {

    content: "";

    position: absolute;

    top: 0;

    left: 8%;

    right: 8%;

    height: 1px;

    background:
      linear-gradient(
        90deg,
        transparent,
        rgba(255,255,255,0.16),
        transparent
      );

    pointer-events:
      none;
  }


  /* Hover */

  .case-card:hover {

    transform:
      translateY(-4px);

    border-color:
      rgba(255,255,255,0.17);

    background:
      linear-gradient(
        145deg,
        rgba(255,255,255,0.072),
        rgba(255,255,255,0.022)
      );

    box-shadow:
      inset 0 1px 0
      rgba(255,255,255,0.075),

      0 28px 70px
      rgba(0,0,0,0.42);
  }


  /* =========================================================
     CARD NUMBER
     ========================================================= */

  .card-number {

    position: absolute;

    top: 20px;

    right: 23px;

    color:
      rgba(255,255,255,0.12);

    font-family:
      var(--font-mono, monospace);

    font-size:
      9px;

    letter-spacing:
      0.08em;
  }


  /* =========================================================
     CARD TOP
     ========================================================= */

  .case-top {

    display: flex;

    align-items: center;

    gap: 14px;

    padding-right:
      40px;
  }


  .case-icon-box {

    width: 44px;

    height: 44px;

    flex-shrink: 0;

    display: flex;

    align-items: center;

    justify-content: center;

    border-radius:
      11px;

    color:
      rgba(255,255,255,0.78);

    background:
      rgba(255,255,255,0.045);

    border:
      1px solid
      rgba(255,255,255,0.11);

    box-shadow:
      inset 0 1px 0
      rgba(255,255,255,0.075);
  }


  .case-heading {

    min-width:
      0;

    display: flex;

    flex-direction: column;

    gap: 4px;
  }


  .case-category {

    color:
      rgba(255,255,255,0.31);

    font-size:
      8px;

    font-weight:
      600;

    letter-spacing:
      0.15em;

    text-transform:
      uppercase;

    white-space:
      nowrap;

    overflow:
      hidden;

    text-overflow:
      ellipsis;
  }


  .case-title {

    margin: 0;

    color:
      rgba(255,255,255,0.91);

    font-size:
      17px;

    line-height:
      1.2;

    font-weight:
      500;

    letter-spacing:
      -0.025em;
  }


  /* =========================================================
     DESCRIPTION
     ========================================================= */

  .case-description {

    margin:
      22px 0 0;

    min-height:
      62px;

    color:
      rgba(255,255,255,0.40);

    font-size:
      11.5px;

    line-height:
      1.65;

    letter-spacing:
      -0.002em;
  }


  /* =========================================================
     QUERY
     ========================================================= */

  .query-section {

    margin-top:
      20px;
  }


  .section-label {

    margin-bottom:
      7px;

    color:
      rgba(255,255,255,0.24);

    font-family:
      var(--font-mono, monospace);

    font-size:
      7px;

    font-weight:
      500;

    letter-spacing:
      0.13em;
  }


  .query-box {

    position: relative;

    min-height:
      47px;

    display: flex;

    align-items: flex-start;

    gap: 7px;

    padding:
      11px 13px;

    box-sizing:
      border-box;

    border-radius:
      9px;

    background:
      rgba(0,0,0,0.28);

    border:
      1px solid
      rgba(255,255,255,0.065);

    box-shadow:
      inset 0 1px 0
      rgba(255,255,255,0.025);
  }


  .query-mark {

    color:
      rgba(255,255,255,0.25);

    font-family:
      Georgia,
      serif;

    font-size:
      19px;

    line-height:
      13px;
  }


  .query-text {

    color:
      rgba(255,255,255,0.64);

    font-size:
      10.5px;

    line-height:
      1.5;

    font-style:
      italic;
  }


  /* =========================================================
     PIPELINE
     ========================================================= */

  .pipeline {

    margin-top:
      16px;

    border:
      1px solid
      rgba(255,255,255,0.065);

    border-radius:
      10px;

    overflow:
      hidden;

    background:
      rgba(0,0,0,0.18);
  }


  .pipeline-header {

    height:
      29px;

    padding:
      0 11px;

    display:
      flex;

    align-items:
      center;

    justify-content:
      space-between;

    border-bottom:
      1px solid
      rgba(255,255,255,0.055);

    color:
      rgba(255,255,255,0.25);

    font-family:
      var(--font-mono, monospace);

    font-size:
      7px;

    font-weight:
      500;

    letter-spacing:
      0.12em;
  }


  .pipeline-status {

    color:
      rgba(255,255,255,0.43);
  }


  .pipeline-grid {

    display:
      grid;

    grid-template-columns:
      1fr 1fr;
  }


  .pipeline-item {

    min-width:
      0;

    min-height:
      59px;

    padding:
      10px 11px;

    display:
      flex;

    flex-direction:
      column;

    justify-content:
      center;

    gap:
      4px;

    border-bottom:
      1px solid
      rgba(255,255,255,0.045);
  }


  .pipeline-item:nth-child(odd) {

    border-right:
      1px solid
      rgba(255,255,255,0.045);
  }


  .pipeline-item:nth-child(3),
  .pipeline-item:nth-child(4) {

    border-bottom:
      none;
  }


  .pipeline-label {

    color:
      rgba(255,255,255,0.22);

    font-size:
      7px;

    font-weight:
      600;

    letter-spacing:
      0.11em;

    text-transform:
      uppercase;
  }


  .pipeline-value {

    color:
      rgba(255,255,255,0.57);

    font-family:
      var(--font-mono, monospace);

    font-size:
      9px;

    line-height:
      1.35;

    white-space:
      nowrap;

    overflow:
      hidden;

    text-overflow:
      ellipsis;
  }


  /* =========================================================
     BUTTON
     ========================================================= */

  .launch-btn {

    width:
      100%;

    height:
      40px;

    margin-top:
      16px;

    display:
      flex;

    align-items:
      center;

    justify-content:
      space-between;

    padding:
      0 10px 0 14px;

    border-radius:
      9px;

    border:
      1px solid
      rgba(255,255,255,0.105);

    background:
      rgba(255,255,255,0.035);

    color:
      rgba(255,255,255,0.68);

    font-family:
      inherit;

    font-size:
      10.5px;

    font-weight:
      500;

    letter-spacing:
      -0.005em;

    cursor:
      pointer;

    box-shadow:
      inset 0 1px 0
      rgba(255,255,255,0.045);

    transition:
      all 0.2s ease;
  }


  .launch-btn:hover {

    color:
      #050505;

    background:
      rgba(255,255,255,0.92);

    border-color:
      rgba(255,255,255,0.92);

    box-shadow:
      0 8px 25px
      rgba(0,0,0,0.35);

    transform:
      translateY(-1px);
  }


  .launch-icon {

    width:
      27px;

    height:
      27px;

    display:
      flex;

    align-items:
      center;

    justify-content:
      center;

    border-radius:
      7px;

    background:
      rgba(255,255,255,0.06);

    transition:
      background 0.2s ease,
      transform 0.2s ease;
  }


  .launch-btn:hover .launch-icon {

    background:
      rgba(0,0,0,0.10);

    transform:
      translateX(2px);
  }


  /* =========================================================
     FOOTER
     ========================================================= */

  .page-footer {

    display:
      flex;

    align-items:
      center;

    justify-content:
      space-between;

    gap:
      20px;

    margin-top:
      38px;

    padding-top:
      16px;

    border-top:
      1px solid
      rgba(255,255,255,0.055);

    color:
      rgba(255,255,255,0.19);

    font-family:
      var(--font-mono, monospace);

    font-size:
      7px;

    letter-spacing:
      0.13em;
  }


  .footer-line {

    flex:
      1;

    height:
      1px;

    background:
      linear-gradient(
        90deg,
        rgba(255,255,255,0.08),
        transparent
      );
  }


  /* =========================================================
     RESPONSIVE — TABLET
     ========================================================= */

  @media (max-width: 900px) {

    .page-content {

      padding:
        42px 28px 32px;
    }


    .cases-grid {

      grid-template-columns:
        1fr;
    }


    .page-title {

      font-size:
        48px;
    }

  }


  /* =========================================================
     RESPONSIVE — MOBILE
     ========================================================= */

  @media (max-width: 600px) {

    .use-cases-page {

      height:
        calc(100vh - 60px);
    }


    .page-content {

      padding:
        30px 16px 28px;
    }


    .page-header {

      margin-bottom:
        32px;
    }


    .header-eyebrow {

      font-size:
        7px;

      letter-spacing:
        0.16em;
    }


    .page-title {

      font-size:
        38px;

      line-height:
        1;
    }


    .page-desc {

      font-size:
        12px;

      line-height:
        1.65;
    }


    .header-meta {

      font-size:
        7px;

      gap:
        7px;
    }


    .case-card {

      padding:
        19px;
    }


    .case-title {

      font-size:
        15px;
    }


    .case-description {

      min-height:
        auto;

      font-size:
        11px;
    }


    .pipeline-value {

      font-size:
        8px;
    }


    .page-footer {

      flex-wrap:
        wrap;

      font-size:
        6px;
    }

  }

</style>