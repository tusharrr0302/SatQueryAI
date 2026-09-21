<script lang="ts">
  import { onMount } from 'svelte';
  import { fetchDatasets } from '../api';

  import {
    Search,
    Satellite,
    Database,
    Calendar,
    Eye,
    Activity,
    Check
  } from 'lucide-svelte';


  let datasets: any[] = [];
  let searchQuery = '';
  let selectedFilter = 'all';


  onMount(async () => {
    try {
      const data = await fetchDatasets();
      datasets = data.datasets || [];
    } catch (err) {
      console.warn(
        'Could not fetch datasets, using catalog fallback'
      );
    }
  });


  $: filteredDatasets = datasets.filter((d) => {

    const query =
      searchQuery.toLowerCase().trim();

    const matchesSearch =
      !query ||
      d.name?.toLowerCase().includes(query) ||
      d.provider?.toLowerCase().includes(query) ||
      d.modality?.toLowerCase().includes(query);


    if (
      selectedFilter === 'optical'
    ) {
      return (
        matchesSearch &&
        d.modality
          ?.toLowerCase()
          .includes('optical')
      );
    }


    if (
      selectedFilter === 'sar'
    ) {
      return (
        matchesSearch &&
        d.modality
          ?.toLowerCase()
          .includes('sar')
      );
    }


    if (
      selectedFilter === 'elevation'
    ) {
      return (
        matchesSearch &&
        d.modality
          ?.toLowerCase()
          .includes('elevation')
      );
    }


    return matchesSearch;
  });
</script>


<div class="datasets-page">


  <!-- =====================================================
       HEADER
       ===================================================== -->

  <header class="page-header">


    <div class="header-top">

      <div class="header-icon">

        <Satellite
          size={17}
          strokeWidth={1.5}
        />

      </div>


      <div class="eyebrow">
        OBSERVATIONAL CATALOG
      </div>

    </div>


    <h1 class="page-title">
      Satellite Datasets
      <span>& Missions</span>
    </h1>


    <p class="page-desc">
      Comprehensive registry of Earth observation
      optical, SAR, multispectral, and digital elevation
      missions integrated into SatQuery AI's
      agentic ingestion engine.
    </p>


    <!-- ===================================================
         CONTROLS
         =================================================== -->

    <div class="controls-row">


      <!-- SEARCH -->

      <div class="search-box">

        <Search
          size={15}
          strokeWidth={1.6}
          class="search-icon"
        />

        <input
          type="text"
          bind:value={searchQuery}
          placeholder="Search mission, provider, or sensor..."
          class="search-input"
        />

        {#if searchQuery}

          <button
            class="clear-search"
            on:click={() => (searchQuery = '')}
            aria-label="Clear search"
          >
            ×
          </button>

        {/if}

      </div>


      <!-- FILTERS -->

      <div class="filter-pills">


        <button
          class="pill"
          class:active={
            selectedFilter === 'all'
          }
          on:click={() =>
            (selectedFilter = 'all')
          }
        >
          All
          <span>
            {datasets.length}
          </span>
        </button>


        <button
          class="pill"
          class:active={
            selectedFilter === 'optical'
          }
          on:click={() =>
            (selectedFilter = 'optical')
          }
        >
          Optical
        </button>


        <button
          class="pill"
          class:active={
            selectedFilter === 'sar'
          }
          on:click={() =>
            (selectedFilter = 'sar')
          }
        >
          Radar / SAR
        </button>


        <button
          class="pill"
          class:active={
            selectedFilter === 'elevation'
          }
          on:click={() =>
            (selectedFilter = 'elevation')
          }
        >
          Topography
        </button>

      </div>

    </div>


    <!-- RESULT COUNT -->

    {#if !searchQuery && selectedFilter === 'all'}

      <div class="catalog-status">

        <span class="status-dot"></span>

        <span>
          {datasets.length}
          {datasets.length === 1
            ? ' dataset'
            : ' datasets'}
          available
        </span>

      </div>

    {:else}

      <div class="catalog-status">

        <span class="status-dot"></span>

        <span>
          {filteredDatasets.length}
          results
        </span>

      </div>

    {/if}

  </header>


  <!-- =====================================================
       DATASET GRID
       ===================================================== -->

  <div class="datasets-grid">


    {#if filteredDatasets.length === 0}

      <div class="empty-state">

        <div class="empty-icon">

          <Database
            size={23}
            strokeWidth={1.4}
          />

        </div>

        <h3>
          No datasets found
        </h3>

        <p>
          Try a different mission name, provider,
          or modality.
        </p>

      </div>


    {:else}

      {#each filteredDatasets as ds, index}

        <article class="dataset-card">


          <!-- =================================================
               CARD HEADER
               ================================================= -->

          <div class="card-top">


            <div class="card-index">
              {String(index + 1).padStart(2, '0')}
            </div>


            <div class="badge-row">

              <span class="provider-badge">
                {ds.provider || 'Copernicus'}
              </span>

              <span class="res-badge">
                {ds.spatial_resolution || '10m'}
              </span>

            </div>


            <h3 class="ds-name">
              {ds.name}
            </h3>


            <p class="ds-desc">
              {ds.description || 'No description available.'}
            </p>

          </div>


          <!-- =================================================
               SPECIFICATION MATRIX
               ================================================= -->

          <div class="spec-matrix">


            <div class="spec-item">

              <div class="spec-icon">

                <Activity
                  size={12}
                  strokeWidth={1.5}
                />

              </div>

              <div class="spec-content">

                <span class="spec-label">
                  MODALITY
                </span>

                <span class="spec-val">
                  {ds.modality || '—'}
                </span>

              </div>

            </div>


            <div class="spec-divider"></div>


            <div class="spec-item">

              <div class="spec-icon">

                <Calendar
                  size={12}
                  strokeWidth={1.5}
                />

              </div>

              <div class="spec-content">

                <span class="spec-label">
                  TEMPORAL COVERAGE
                </span>

                <span class="spec-val">
                  {ds.temporal_coverage || '—'}
                </span>

              </div>

            </div>

          </div>


          <!-- =================================================
               CAPABILITIES
               ================================================= -->

          <div class="capabilities-section">


            <div class="section-heading-row">

              <span class="section-label">
                KEY CAPABILITIES
              </span>

              <span class="cap-count">
                {(ds.capabilities || ds.tasks || []).length}
              </span>

            </div>


            <div class="caps-tags">

              {#if (ds.capabilities || ds.tasks || []).length}

                {#each (ds.capabilities || ds.tasks || []) as cap}

                  <span class="cap-tag">

                    <Check
                      size={10}
                      strokeWidth={2}
                    />

                    {cap}

                  </span>

                {/each}

              {:else}

                <span class="no-capabilities">
                  No capability metadata
                </span>

              {/if}

            </div>

          </div>


          <!-- =================================================
               CARD FOOTER
               ================================================= -->

          <div class="card-footer">

            <span class="catalog-label">
              SATQUERY CATALOG
            </span>

            <span class="inspect-label">

              <Eye
                size={11}
                strokeWidth={1.6}
              />

              Integrated

            </span>

          </div>


        </article>

      {/each}

    {/if}

  </div>

</div>


<style>

  /* =========================================================
     PAGE
     ========================================================= */

  .datasets-page {

    width:
      100%;

    height:
      calc(100vh - 60px);

    min-height:
      0;

    box-sizing:
      border-box;

    overflow-y:
      auto;

    overflow-x:
      hidden;

    padding:
      42px clamp(24px, 5vw, 72px) 70px;

    background:
      #050505;

    color:
      #ffffff;

    font-family:
      Inter,
      "SF Pro Display",
      "SF Pro Text",
      -apple-system,
      BlinkMacSystemFont,
      "Helvetica Neue",
      Arial,
      sans-serif;

    scrollbar-width:
      thin;

    scrollbar-color:
      rgba(255,255,255,0.12)
      transparent;
  }


  .datasets-page::-webkit-scrollbar {
    width:
      5px;
  }


  .datasets-page::-webkit-scrollbar-track {
    background:
      transparent;
  }


  .datasets-page::-webkit-scrollbar-thumb {

    background:
      rgba(255,255,255,0.12);

    border-radius:
      10px;
  }


  /* =========================================================
     HEADER
     ========================================================= */

  .page-header {

    width:
      100%;

    max-width:
      1040px;

    margin:
      0 auto 30px;

    display:
      flex;

    flex-direction:
      column;
  }


  .header-top {

    display:
      flex;

    align-items:
      center;

    gap:
      9px;

    margin-bottom:
      12px;
  }


  .header-icon {

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
      rgba(255,255,255,0.055);

    border:
      1px solid
      rgba(255,255,255,0.10);

    color:
      rgba(255,255,255,0.70);

    box-shadow:
      inset 0 1px 0
      rgba(255,255,255,0.04);
  }


  .eyebrow {

    font-size:
      8.5px;

    font-weight:
      700;

    letter-spacing:
      0.16em;

    color:
      rgba(255,255,255,0.34);
  }


  .page-title {

    margin:
      0;

    font-size:
      clamp(30px, 3.4vw, 43px);

    line-height:
      1.05;

    letter-spacing:
      -0.045em;

    font-weight:
      650;

    color:
      #ffffff;
  }


  .page-title span {

    color:
      rgba(255,255,255,0.36);

    font-weight:
      420;
  }


  .page-desc {

    max-width:
      700px;

    margin:
      13px 0 0;

    font-size:
      12px;

    line-height:
      1.7;

    color:
      rgba(255,255,255,0.40);
  }


  /* =========================================================
     CONTROLS
     ========================================================= */

  .controls-row {

    display:
      flex;

    align-items:
      center;

    gap:
      8px;

    flex-wrap:
      wrap;

    margin-top:
      22px;
  }


  .search-box {

    width:
      330px;

    height:
      37px;

    box-sizing:
      border-box;

    display:
      flex;

    align-items:
      center;

    gap:
      8px;

    padding:
      0 11px;

    border-radius:
      8px;

    background:
      rgba(255,255,255,0.035);

    border:
      1px solid
      rgba(255,255,255,0.085);

    box-shadow:
      inset 0 1px 0
      rgba(255,255,255,0.025);

    transition:
      border-color 0.15s ease,
      background 0.15s ease;
  }


  .search-box:focus-within {

    background:
      rgba(255,255,255,0.045);

    border-color:
      rgba(255,255,255,0.20);
  }


  :global(.search-icon) {

    flex-shrink:
      0;

    color:
      rgba(255,255,255,0.28);
  }


  .search-input {

    min-width:
      0;

    flex:
      1;

    border:
      0;

    outline:
      0;

    background:
      transparent;

    color:
      #ffffff;

    font-family:
      inherit;

    font-size:
      10.5px;
  }


  .search-input::placeholder {

    color:
      rgba(255,255,255,0.23);
  }


  .clear-search {

    width:
      20px;

    height:
      20px;

    padding:
      0;

    display:
      flex;

    align-items:
      center;

    justify-content:
      center;

    border-radius:
      5px;

    background:
      rgba(255,255,255,0.06);

    color:
      rgba(255,255,255,0.45);

    font-size:
      15px;

    line-height:
      1;

    cursor:
      pointer;
  }


  .filter-pills {

    display:
      flex;

    align-items:
      center;

    gap:
      5px;

    flex-wrap:
      wrap;
  }


  .pill {

    height:
      34px;

    padding:
      0 11px;

    display:
      inline-flex;

    align-items:
      center;

    gap:
      5px;

    border-radius:
      7px;

    border:
      1px solid
      rgba(255,255,255,0.07);

    background:
      rgba(255,255,255,0.025);

    color:
      rgba(255,255,255,0.36);

    font-family:
      inherit;

    font-size:
      9.5px;

    cursor:
      pointer;

    transition:
      all 0.15s ease;
  }


  .pill:hover {

    background:
      rgba(255,255,255,0.055);

    color:
      rgba(255,255,255,0.75);

    border-color:
      rgba(255,255,255,0.12);
  }


  .pill span {

    color:
      rgba(255,255,255,0.22);

    font-family:
      var(--font-mono, monospace);

    font-size:
      8px;
  }


  .pill.active {

    background:
      rgba(255,255,255,0.09);

    border-color:
      rgba(255,255,255,0.16);

    color:
      #ffffff;

    font-weight:
      600;

    box-shadow:
      inset 0 1px 0
      rgba(255,255,255,0.035);
  }


  .pill.active span {

    color:
      rgba(255,255,255,0.58);
  }


  /* =========================================================
     STATUS
     ========================================================= */

  .catalog-status {

    display:
      flex;

    align-items:
      center;

    gap:
      6px;

    margin-top:
      12px;

    font-family:
      var(--font-mono, monospace);

    font-size:
      8px;

    color:
      rgba(255,255,255,0.22);
  }


  .status-dot {

    width:
      4px;

    height:
      4px;

    border-radius:
      50%;

    background:
      rgba(255,255,255,0.60);

    box-shadow:
      0 0 7px
      rgba(255,255,255,0.25);
  }


  /* =========================================================
     GRID
     ========================================================= */

  .datasets-grid {

    width:
      100%;

    max-width:
      1040px;

    margin:
      0 auto;

    display:
      grid;

    grid-template-columns:
      repeat(
        auto-fit,
        minmax(300px, 1fr)
      );

    gap:
      9px;
  }


  /* =========================================================
     DATASET CARD
     ========================================================= */

  .dataset-card {

    position:
      relative;

    min-width:
      0;

    min-height:
      285px;

    box-sizing:
      border-box;

    display:
      flex;

    flex-direction:
      column;

    padding:
      16px;

    border-radius:
      10px;

    background:
      linear-gradient(
        145deg,
        rgba(255,255,255,0.045),
        rgba(255,255,255,0.018)
      );

    border:
      1px solid
      rgba(255,255,255,0.075);

    box-shadow:
      inset 0 1px 0
      rgba(255,255,255,0.025);

    overflow:
      hidden;

    transition:
      transform 0.18s ease,
      border-color 0.18s ease,
      background 0.18s ease,
      box-shadow 0.18s ease;
  }


  .dataset-card::before {

    content:
      "";

    position:
      absolute;

    top:
      0;

    left:
      0;

    right:
      0;

    height:
      1px;

    background:
      linear-gradient(
        90deg,
        transparent,
        rgba(255,255,255,0.16),
        transparent
      );

    opacity:
      0.45;
  }


  .dataset-card:hover {

    transform:
      translateY(-2px);

    background:
      linear-gradient(
        145deg,
        rgba(255,255,255,0.06),
        rgba(255,255,255,0.025)
      );

    border-color:
      rgba(255,255,255,0.15);

    box-shadow:
      inset 0 1px 0
      rgba(255,255,255,0.04),

      0 12px 28px
      rgba(0,0,0,0.28);
  }


  /* =========================================================
     CARD TOP
     ========================================================= */

  .card-top {

    position:
      relative;

    display:
      flex;

    flex-direction:
      column;

    gap:
      7px;
  }


  .card-index {

    position:
      absolute;

    right:
      0;

    top:
      0;

    font-family:
      var(--font-mono, monospace);

    font-size:
      8px;

    color:
      rgba(255,255,255,0.15);
  }


  .badge-row {

    display:
      flex;

    align-items:
      center;

    gap:
      5px;

    padding-right:
      25px;
  }


  .provider-badge {

    display:
      inline-flex;

    align-items:
      center;

    padding:
      4px 6px;

    border-radius:
      4px;

    background:
      rgba(255,255,255,0.07);

    border:
      1px solid
      rgba(255,255,255,0.08);

    color:
      rgba(255,255,255,0.60);

    font-size:
      7.5px;

    font-weight:
      650;

    letter-spacing:
      0.04em;

    text-transform:
      uppercase;
  }


  .res-badge {

    padding:
      4px 6px;

    border-radius:
      4px;

    color:
      rgba(255,255,255,0.28);

    background:
      rgba(255,255,255,0.025);

    border:
      1px solid
      rgba(255,255,255,0.055);

    font-family:
      var(--font-mono, monospace);

    font-size:
      7.5px;
  }


  .ds-name {

    margin:
      4px 0 0;

    padding-right:
      30px;

    font-size:
      17px;

    line-height:
      1.2;

    font-weight:
      650;

    letter-spacing:
      -0.025em;

    color:
      rgba(255,255,255,0.90);
  }


  .ds-desc {

    margin:
      0;

    min-height:
      48px;

    font-size:
      10px;

    line-height:
      1.6;

    color:
      rgba(255,255,255,0.33);
  }


  /* =========================================================
     SPEC MATRIX
     ========================================================= */

  .spec-matrix {

    margin-top:
      14px;

    padding:
      9px;

    display:
      flex;

    flex-direction:
      column;

    gap:
      8px;

    border-radius:
      7px;

    background:
      rgba(0,0,0,0.22);

    border:
      1px solid
      rgba(255,255,255,0.055);
  }


  .spec-item {

    display:
      flex;

    align-items:
      center;

    gap:
      8px;

    min-width:
      0;
  }


  .spec-icon {

    width:
      23px;

    height:
      23px;

    flex-shrink:
      0;

    display:
      flex;

    align-items:
      center;

    justify-content:
      center;

    border-radius:
      5px;

    background:
      rgba(255,255,255,0.045);

    color:
      rgba(255,255,255,0.30);
  }


  .spec-content {

    min-width:
      0;

    flex:
      1;

    display:
      flex;

    flex-direction:
      column;

    gap:
      2px;
  }


  .spec-label {

    font-size:
      7px;

    font-weight:
      700;

    letter-spacing:
      0.10em;

    color:
      rgba(255,255,255,0.20);
  }


  .spec-val {

    overflow:
      hidden;

    text-overflow:
      ellipsis;

    white-space:
      nowrap;

    font-family:
      var(--font-mono, monospace);

    font-size:
      8.5px;

    color:
      rgba(255,255,255,0.60);
  }


  .spec-divider {

    height:
      1px;

    background:
      rgba(255,255,255,0.045);
  }


  /* =========================================================
     CAPABILITIES
     ========================================================= */

  .capabilities-section {

    margin-top:
      14px;

    display:
      flex;

    flex-direction:
      column;

    gap:
      7px;
  }


  .section-heading-row {

    display:
      flex;

    align-items:
      center;

    justify-content:
      space-between;
  }


  .section-label {

    font-size:
      7.5px;

    font-weight:
      700;

    letter-spacing:
      0.12em;

    color:
      rgba(255,255,255,0.22);
  }


  .cap-count {

    font-family:
      var(--font-mono, monospace);

    font-size:
      7px;

    color:
      rgba(255,255,255,0.18);
  }


  .caps-tags {

    display:
      flex;

    flex-wrap:
      wrap;

    gap:
      4px;
  }


  .cap-tag {

    display:
      inline-flex;

    align-items:
      center;

    gap:
      4px;

    padding:
      4px 6px;

    border-radius:
      4px;

    background:
      rgba(255,255,255,0.035);

    border:
      1px solid
      rgba(255,255,255,0.06);

    color:
      rgba(255,255,255,0.43);

    font-size:
      8px;

    line-height:
      1.25;

    transition:
      all 0.15s ease;
  }


  .cap-tag:hover {

    background:
      rgba(255,255,255,0.065);

    color:
      rgba(255,255,255,0.72);

    border-color:
      rgba(255,255,255,0.11);
  }


  .cap-tag :global(svg) {

    color:
      rgba(255,255,255,0.42);

    flex-shrink:
      0;
  }


  .no-capabilities {

    font-size:
      8.5px;

    color:
      rgba(255,255,255,0.18);
  }


  /* =========================================================
     CARD FOOTER
     ========================================================= */

  .card-footer {

    margin-top:
      auto;

    padding-top:
      12px;

    display:
      flex;

    align-items:
      center;

    justify-content:
      space-between;

    border-top:
      1px solid
      rgba(255,255,255,0.05);
  }


  .catalog-label {

    font-family:
      var(--font-mono, monospace);

    font-size:
      6.5px;

    letter-spacing:
      0.10em;

    color:
      rgba(255,255,255,0.16);
  }


  .inspect-label {

    display:
      flex;

    align-items:
      center;

    gap:
      4px;

    font-size:
      7.5px;

    color:
      rgba(255,255,255,0.25);
  }


  /* =========================================================
     EMPTY
     ========================================================= */

  .empty-state {

    grid-column:
      1 / -1;

    min-height:
      300px;

    display:
      flex;

    flex-direction:
      column;

    align-items:
      center;

    justify-content:
      center;

    text-align:
      center;

    border:
      1px solid
      rgba(255,255,255,0.065);

    border-radius:
      10px;

    background:
      rgba(255,255,255,0.018);
  }


  .empty-icon {

    width:
      48px;

    height:
      48px;

    display:
      flex;

    align-items:
      center;

    justify-content:
      center;

    border-radius:
      12px;

    background:
      rgba(255,255,255,0.04);

    border:
      1px solid
      rgba(255,255,255,0.08);

    color:
      rgba(255,255,255,0.28);

    margin-bottom:
      12px;
  }


  .empty-state h3 {

    margin:
      0;

    font-size:
      13px;

    font-weight:
      600;

    color:
      rgba(255,255,255,0.70);
  }


  .empty-state p {

    margin:
      5px 0 0;

    font-size:
      9.5px;

    color:
      rgba(255,255,255,0.25);
  }


  /* =========================================================
     RESPONSIVE
     ========================================================= */

  @media (max-width: 900px) {

    .datasets-page {

      padding:
        34px 24px 60px;
    }


    .search-box {

      width:
        100%;
    }


    .controls-row {

      align-items:
        stretch;
    }

  }


  @media (max-width: 600px) {

    .datasets-page {

      padding:
        25px 14px 50px;
    }


    .page-title {

      font-size:
        29px;
    }


    .page-desc {

      font-size:
        10.5px;
    }


    .filter-pills {

      width:
        100%;
    }


    .pill {

      flex:
        1;
    }


    .datasets-grid {

      grid-template-columns:
        1fr;
    }


    .dataset-card {

      min-height:
        270px;
    }

  }

</style>