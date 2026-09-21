<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { Search, ArrowUp } from 'lucide-svelte';

  export let isAnalyzing: boolean = false;

  const dispatch = createEventDispatcher<{
    submitQuery: string;
  }>();

  let queryText = '';

  const sampleQueries = [
    'Show deforestation in the Amazon',
    'Compare urban growth in Delhi',
    'Analyze crop health in Punjab',
    'Detect flooding in this region'
  ];

  function handleSubmit() {
    if (!queryText.trim() || isAnalyzing) return;

    dispatch('submitQuery', queryText.trim());
  }

  function handleSample(q: string) {
    if (isAnalyzing) return;

    queryText = q;
    dispatch('submitQuery', q);
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }
</script>


<div class="landing-hero-overlay">

  <!-- =====================================================
       50% BLACK LAYER
       ===================================================== -->

  <div class="black-layer"></div>


  <!-- =====================================================
       SUBTLE GLASS VERTICAL STRUCTURE
       ===================================================== -->

  <div class="glass-architecture" aria-hidden="true">

    <div class="glass-column column-1"></div>
    <div class="glass-column column-2"></div>
    <div class="glass-column column-3"></div>
    <div class="glass-column column-4"></div>
    <div class="glass-column column-5"></div>
    <div class="glass-column column-6"></div>

  </div>


  <!-- =====================================================
       HERO
       ===================================================== -->

  <main class="hero-content">

    <!-- Eyebrow -->

    <div class="eyebrow">

      <span class="eyebrow-line"></span>

      <span class="eyebrow-text">
        EARTH OBSERVATION
      </span>

      <span class="eyebrow-line"></span>

    </div>


    <!-- Main heading -->

    <h1 class="headline">

      <span class="headline-primary">
        ASK EARTH
      </span>

      <br />

      <span class="headline-secondary">
        ANYTHING.
      </span>

    </h1>


    <!-- Description -->

    <p class="description">
      Explore Earth through satellite imagery,
      <br class="desktop-break" />
      vision-language models, and intelligent geospatial analysis.
    </p>


    <!-- =====================================================
         QUERY
         ===================================================== -->

    <div class="query-section">

      <div class="query-box">

        <div class="query-left">

          <Search
            size={18}
            strokeWidth={1.5}
            class="search-icon"
          />

          <input
            type="text"
            bind:value={queryText}
            on:keydown={handleKeydown}
            placeholder="Ask anything about Earth..."
            disabled={isAnalyzing}
            class="query-input"
          />

        </div>


        <button
          class="submit-btn"
          on:click={handleSubmit}
          disabled={isAnalyzing || !queryText.trim()}
          aria-label="Submit query"
        >

          {#if isAnalyzing}

            <div class="spinner"></div>

          {:else}

            <ArrowUp
              size={18}
              strokeWidth={1.5}
            />

          {/if}

        </button>

      </div>


      <!-- Examples -->

      <div class="examples">

        <span class="examples-label">
          TRY
        </span>

        {#each sampleQueries as sample, i}

          <button
            class="example"
            on:click={() => handleSample(sample)}
            disabled={isAnalyzing}
          >
            {sample}
          </button>

          {#if i < sampleQueries.length - 1}
            <span class="separator">·</span>
          {/if}

        {/each}

      </div>

    </div>

  </main>


  <!-- =====================================================
       BOTTOM STATUS
       ===================================================== -->

  <div class="bottom-left">

    <div class="system-line"></div>

    <div class="system-info">

      <span>CESIUM</span>

      <span>•</span>

      <span>EARTH OBSERVATION</span>

    </div>

  </div>


  <div class="bottom-right">

    <span>REAL-TIME</span>

    <span class="status-dot"></span>

  </div>

</div>


<style>

  /* =====================================================
     ROOT
     ===================================================== */

  .landing-hero-overlay {

    position: absolute;

    inset: 0;

    z-index: 10;

    display: flex;

    align-items: center;

    justify-content: center;

    overflow: hidden;

    pointer-events: none;

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

    animation: fadeIn 0.7s ease-out;
  }


  @keyframes fadeIn {

    from {
      opacity: 0;
    }

    to {
      opacity: 1;
    }

  }


  /* =====================================================
     50% BLACK OVERLAY
     ===================================================== */

  .black-layer {

    position: absolute;

    inset: 0;

    background: rgba(0, 0, 0, 0.50);

    pointer-events: none;

    z-index: -1;
  }


  /* =====================================================
     EXTRA VIGNETTE
     ===================================================== */

  .landing-hero-overlay::before {

    content: "";

    position: absolute;

    inset: 0;

    pointer-events: none;

    background:
      radial-gradient(
        ellipse at 50% 48%,
        transparent 18%,
        rgba(0, 0, 0, 0.12) 50%,
        rgba(0, 0, 0, 0.55) 100%
      );

    z-index: -1;
  }


  .landing-hero-overlay::after {

    content: "";

    position: absolute;

    inset: 0;

    pointer-events: none;

    background:
      linear-gradient(
        180deg,
        rgba(0, 0, 0, 0.30) 0%,
        transparent 22%,
        transparent 55%,
        rgba(0, 0, 0, 0.72) 100%
      );

    z-index: -1;
  }


  /* =====================================================
     GLASS ARCHITECTURE
     ===================================================== */

  .glass-architecture {

    position: absolute;

    inset: 0;

    display: flex;

    justify-content: center;

    pointer-events: none;

    opacity: 0.65;

    z-index: -2;
  }


  .glass-column {

    position: relative;

    width: 110px;

    height: 100%;

    border-left:
      1px solid
      rgba(255, 255, 255, 0.035);

    border-right:
      1px solid
      rgba(255, 255, 255, 0.025);

    background:
      linear-gradient(
        180deg,
        rgba(255, 255, 255, 0.045),
        rgba(255, 255, 255, 0.008) 50%,
        rgba(255, 255, 255, 0.025)
      );

    backdrop-filter: blur(2px);
  }


  .glass-column::after {

    content: "";

    position: absolute;

    inset: 0;

    background:
      linear-gradient(
        90deg,
        transparent,
        rgba(255, 255, 255, 0.025),
        transparent
      );
  }


  .column-1 {
    transform: translateY(7%);
    opacity: 0.35;
  }

  .column-2 {
    transform: translateY(-3%);
    opacity: 0.55;
  }

  .column-3 {
    transform: translateY(4%);
    opacity: 0.8;
  }

  .column-4 {
    transform: translateY(-2%);
    opacity: 0.65;
  }

  .column-5 {
    transform: translateY(6%);
    opacity: 0.4;
  }

  .column-6 {
    transform: translateY(-4%);
    opacity: 0.25;
  }


  /* =====================================================
     HERO POSITION
     ===================================================== */

  .hero-content {

    position: relative;

    width: min(900px, calc(100% - 40px));

    display: flex;

    flex-direction: column;

    align-items: center;

    text-align: center;

    pointer-events: auto;

    /*
      Move content slightly upward.

      This leaves the lower portion
      visually dominated by Earth.
    */

    transform: translateY(-7%);
  }


  /* =====================================================
     EYEBROW
     ===================================================== */

  .eyebrow {

    display: flex;

    align-items: center;

    gap: 13px;

    margin-bottom: 22px;

    color:
      rgba(255, 255, 255, 0.50);

    font-size: 9px;

    font-weight: 500;

    letter-spacing: 4px;

    text-transform: uppercase;
  }


  .eyebrow-line {

    width: 25px;

    height: 1px;

    background:
      linear-gradient(
        90deg,
        transparent,
        rgba(255, 255, 255, 0.40)
      );
  }


  .eyebrow-line:last-child {

    background:
      linear-gradient(
        90deg,
        rgba(255, 255, 255, 0.40),
        transparent
      );
  }


  /* =====================================================
     HEADLINE
     ===================================================== */

  .headline {

    margin: 0;

    padding: 0;

    font-family:
      Inter,
      "SF Pro Display",
      -apple-system,
      BlinkMacSystemFont,
      "Helvetica Neue",
      Arial,
      sans-serif;

    font-size:
      clamp(58px, 7.2vw, 100px);

    line-height: 0.88;

    font-weight: 300;

    letter-spacing: -0.075em;

    text-transform: uppercase;

    white-space: nowrap;

    text-shadow:
      0 4px 30px rgba(0, 0, 0, 0.95),
      0 12px 80px rgba(0, 0, 0, 0.70);
  }


  .headline-primary {

    color: #ffffff;

    font-weight: 400;
  }


  .headline-secondary {

    color:
      rgba(255, 255, 255, 0.38);

    font-weight: 300;
  }


  /* =====================================================
     DESCRIPTION
     ===================================================== */

  .description {

    margin:
      27px
      0
      32px;

    max-width: 550px;

    color:
      rgba(255, 255, 255, 0.53);

    font-size: 13px;

    line-height: 1.7;

    font-weight: 400;

    letter-spacing: -0.012em;

    text-shadow:
      0 2px 18px rgba(0, 0, 0, 0.95);
  }


  /* =====================================================
     QUERY SECTION
     ===================================================== */

  .query-section {

    width:
      min(650px, 100%);

    display: flex;

    flex-direction: column;

    align-items: center;

    gap: 13px;
  }


  /* =====================================================
     QUERY BOX
     ===================================================== */

  .query-box {

    position: relative;

    width: 100%;

    height: 60px;

    display: flex;

    align-items: center;

    justify-content: space-between;

    padding:
      5px
      6px
      5px
      21px;

    border-radius: 999px;

    background:
      linear-gradient(
        180deg,
        rgba(255, 255, 255, 0.075),
        rgba(255, 255, 255, 0.018)
      ),
      rgba(0, 0, 0, 0.62);

    border:
      1px solid
      rgba(255, 255, 255, 0.19);

    backdrop-filter:
      blur(28px)
      saturate(110%);

    -webkit-backdrop-filter:
      blur(28px)
      saturate(110%);

    box-shadow:
      inset 0 1px 0
        rgba(255, 255, 255, 0.10),

      inset 0 -1px 0
        rgba(255, 255, 255, 0.02),

      0 22px 70px
        rgba(0, 0, 0, 0.70);
  }


  .query-box::before {

    content: "";

    position: absolute;

    top: 0;

    left: 8%;

    width: 84%;

    height: 1px;

    background:
      linear-gradient(
        90deg,
        transparent,
        rgba(255, 255, 255, 0.16),
        transparent
      );
  }


  .query-box:focus-within {

    border-color:
      rgba(255, 255, 255, 0.30);

    box-shadow:
      inset 0 1px 0
        rgba(255, 255, 255, 0.13),

      0 25px 80px
        rgba(0, 0, 0, 0.80);
  }


  .query-left {

    flex: 1;

    min-width: 0;

    display: flex;

    align-items: center;
  }


  /* =====================================================
     SEARCH
     ===================================================== */

  :global(.search-icon) {

    flex-shrink: 0;

    margin-right: 12px;

    color:
      rgba(255, 255, 255, 0.42);
  }


  /* =====================================================
     INPUT
     ===================================================== */

  .query-input {

    width: 100%;

    min-width: 0;

    padding: 0;

    border: none;

    outline: none;

    background: transparent;

    color: #ffffff;

    font-family:
      Inter,
      "SF Pro Text",
      -apple-system,
      BlinkMacSystemFont,
      "Helvetica Neue",
      Arial,
      sans-serif;

    font-size: 13px;

    font-weight: 400;

    letter-spacing: -0.01em;
  }


  .query-input::placeholder {

    color:
      rgba(255, 255, 255, 0.40);
  }


  .query-input:disabled {

    opacity: 0.5;
  }


  /* =====================================================
     SUBMIT
     ===================================================== */

  .submit-btn {

    width: 48px;

    height: 48px;

    flex-shrink: 0;

    display: flex;

    align-items: center;

    justify-content: center;

    padding: 0;

    border-radius: 50%;

    border:
      1px solid
      rgba(255, 255, 255, 0.20);

    background:
      rgba(255, 255, 255, 0.92);

    color: #050505;

    cursor: pointer;

    box-shadow:
      0 2px 12px
      rgba(0, 0, 0, 0.40);

    transition:
      transform 0.2s ease,
      background 0.2s ease,
      opacity 0.2s ease;
  }


  .submit-btn:hover:not(:disabled) {

    transform: scale(1.05);

    background: #ffffff;
  }


  .submit-btn:active:not(:disabled) {

    transform: scale(0.95);
  }


  .submit-btn:disabled {

    opacity: 0.24;

    cursor: default;
  }


  /* =====================================================
     SPINNER
     ===================================================== */

  .spinner {

    width: 16px;

    height: 16px;

    border:
      1.5px solid
      rgba(0, 0, 0, 0.20);

    border-top-color: #000000;

    border-radius: 50%;

    animation:
      spin 0.75s linear infinite;
  }


  @keyframes spin {

    to {
      transform: rotate(360deg);
    }

  }


  /* =====================================================
     EXAMPLES
     ===================================================== */

  .examples {

    display: flex;

    align-items: center;

    justify-content: center;

    flex-wrap: wrap;

    gap: 7px;

    max-width: 680px;

    color:
      rgba(255, 255, 255, 0.27);

    font-size: 10px;
  }


  .examples-label {

    color:
      rgba(255, 255, 255, 0.22);

    font-size: 8px;

    font-weight: 600;

    letter-spacing: 2px;
  }


  .example {

    padding: 0;

    border: none;

    background: transparent;

    color:
      rgba(255, 255, 255, 0.35);

    font-family: inherit;

    font-size: 10px;

    cursor: pointer;

    transition:
      color 0.2s ease;
  }


  .example:hover:not(:disabled) {

    color:
      rgba(255, 255, 255, 0.82);
  }


  .example:disabled {

    cursor: default;
  }


  .separator {

    color:
      rgba(255, 255, 255, 0.15);
  }


  /* =====================================================
     BOTTOM LEFT
     ===================================================== */

  .bottom-left {

    position: absolute;

    left: 28px;

    bottom: 25px;

    display: flex;

    align-items: center;

    gap: 10px;

    pointer-events: none;
  }


  .system-line {

    width: 25px;

    height: 1px;

    background:
      rgba(255, 255, 255, 0.28);
  }


  .system-info {

    display: flex;

    align-items: center;

    gap: 7px;

    color:
      rgba(255, 255, 255, 0.25);

    font-size: 8px;

    font-weight: 500;

    letter-spacing: 1.6px;
  }


  /* =====================================================
     BOTTOM RIGHT
     ===================================================== */

  .bottom-right {

    position: absolute;

    right: 28px;

    bottom: 25px;

    display: flex;

    align-items: center;

    gap: 8px;

    color:
      rgba(255, 255, 255, 0.25);

    font-size: 8px;

    font-weight: 500;

    letter-spacing: 1.6px;

    pointer-events: none;
  }


  .status-dot {

    width: 5px;

    height: 5px;

    border-radius: 50%;

    background:
      rgba(255, 255, 255, 0.70);

    box-shadow:
      0 0 8px
      rgba(255, 255, 255, 0.50);
  }


  /* =====================================================
     TABLET
     ===================================================== */

  @media (max-width: 800px) {

    .hero-content {

      transform:
        translateY(-5%);
    }


    .headline {

      font-size:
        clamp(48px, 10vw, 72px);
    }


    .description {

      font-size: 12px;
    }


    .glass-column {

      width: 75px;
    }

  }


  /* =====================================================
     MOBILE
     ===================================================== */

  @media (max-width: 600px) {

    .hero-content {

      width:
        calc(100% - 30px);

      transform:
        translateY(-4%);
    }


    .headline {

      font-size: 43px;

      letter-spacing:
        -0.065em;
    }


    .description {

      font-size: 11px;

      margin-bottom: 25px;
    }


    .desktop-break {

      display: none;
    }


    .query-box {

      height: 55px;

      padding-left: 16px;
    }


    .submit-btn {

      width: 43px;

      height: 43px;
    }


    .examples {

      display: none;
    }


    .bottom-left {

      left: 15px;

      bottom: 15px;
    }


    .bottom-right {

      right: 15px;

      bottom: 15px;
    }

  }


  /* =====================================================
     SMALL MOBILE
     ===================================================== */

  @media (max-width: 430px) {

    .headline {

      font-size: 37px;
    }


    .eyebrow {

      font-size: 8px;

      letter-spacing: 2.2px;
    }


    .bottom-left,
    .bottom-right {

      display: none;
    }

  }

</style>