<script lang="ts">
  import { onDestroy } from 'svelte';
  import { timelineState } from '../stores';
  import {
    Play,
    Pause,
    SkipBack,
    SkipForward,
    Clock
  } from 'lucide-svelte';

  let timerInterval: ReturnType<typeof setInterval> | null = null;


  // =========================================================
  // PLAYBACK
  // =========================================================

  function togglePlay() {
    $timelineState.isPlaying =
      !$timelineState.isPlaying;

    if ($timelineState.isPlaying) {
      startPlayback();
    } else {
      stopPlayback();
    }
  }


  function startPlayback() {

    stopPlayback();

    if (!$timelineState.years.length) {
      return;
    }

    timerInterval = setInterval(() => {

      const idx =
        $timelineState.years.indexOf(
          $timelineState.activeYear
        );

      const nextIdx =
        (idx + 1) %
        $timelineState.years.length;

      $timelineState.activeYear =
        $timelineState.years[nextIdx];

    }, 1800);
  }


  function stopPlayback() {

    if (timerInterval) {

      clearInterval(timerInterval);

      timerInterval = null;
    }
  }


  // =========================================================
  // PREVIOUS
  // =========================================================

  function stepPrev() {

    stopPlayback();

    $timelineState.isPlaying = false;

    if (!$timelineState.years.length) {
      return;
    }

    const idx =
      $timelineState.years.indexOf(
        $timelineState.activeYear
      );

    const prevIdx =
      idx > 0
        ? idx - 1
        : $timelineState.years.length - 1;

    $timelineState.activeYear =
      $timelineState.years[prevIdx];
  }


  // =========================================================
  // NEXT
  // =========================================================

  function stepNext() {

    stopPlayback();

    $timelineState.isPlaying = false;

    if (!$timelineState.years.length) {
      return;
    }

    const idx =
      $timelineState.years.indexOf(
        $timelineState.activeYear
      );

    const nextIdx =
      (idx + 1) %
      $timelineState.years.length;

    $timelineState.activeYear =
      $timelineState.years[nextIdx];
  }


  // =========================================================
  // YEAR SELECTION
  // =========================================================

  function selectYear(yr: string) {

    stopPlayback();

    $timelineState.isPlaying = false;

    $timelineState.activeYear = yr;
  }


  // =========================================================
  // CLEANUP
  // =========================================================

  onDestroy(() => {
    stopPlayback();
  });
</script>


<div class="timeline-bar-wrapper">


  <!-- =====================================================
       PLAYBACK CONTROLS
       ===================================================== -->

  <div class="timeline-controls">

    <button
      class="ctrl-btn"
      on:click={stepPrev}
      title="Previous year"
      aria-label="Previous year"
    >
      <SkipBack
        size={13}
        strokeWidth={1.8}
      />
    </button>


    <button
      class="play-btn"
      class:playing={$timelineState.isPlaying}
      on:click={togglePlay}
      title={
        $timelineState.isPlaying
          ? 'Pause timelapse'
          : 'Play timelapse'
      }
      aria-label={
        $timelineState.isPlaying
          ? 'Pause timelapse'
          : 'Play timelapse'
      }
    >

      {#if $timelineState.isPlaying}

        <Pause
          size={13}
          strokeWidth={1.9}
        />

      {:else}

        <Play
          size={13}
          strokeWidth={1.9}
        />

      {/if}

    </button>


    <button
      class="ctrl-btn"
      on:click={stepNext}
      title="Next year"
      aria-label="Next year"
    >
      <SkipForward
        size={13}
        strokeWidth={1.8}
      />
    </button>

  </div>


  <!-- =====================================================
       DIVIDER
       ===================================================== -->

  <div class="control-divider"></div>


  <!-- =====================================================
       TIMELINE
       ===================================================== -->

  <div class="timeline-track">

    {#if $timelineState.years.length}

      <!-- Timeline line -->

      <div class="timeline-line"></div>


      {#each $timelineState.years as yr, i}

        <button
          class="year-tick"
          class:active={
            $timelineState.activeYear === yr
          }
          on:click={() => selectYear(yr)}
          title={`View ${yr}`}
          aria-label={`View ${yr}`}
        >

          <span class="tick-dot"></span>

          <span class="tick-label">
            {yr}
          </span>

        </button>

      {/each}

    {:else}

      <span class="empty-timeline">
        No timeline data
      </span>

    {/if}

  </div>


  <!-- =====================================================
       ACTIVE YEAR
       ===================================================== -->

  <div class="timeline-info">

    <Clock
      size={12}
      strokeWidth={1.7}
      class="clock-icon"
    />

    <div class="active-year-content">

      <span class="active-year-label">
        YEAR
      </span>

      <span class="active-badge">
        {$timelineState.activeYear || '—'}
      </span>

    </div>

  </div>

</div>


<style>

  /* =========================================================
     MAIN TIMELINE
     ========================================================= */

  .timeline-bar-wrapper {

    width:
      fit-content;

    max-width:
      calc(100vw - 32px);

    min-height:
      48px;

    display:
      flex;

    align-items:
      center;

    gap:
      11px;

    padding:
      5px 8px;

    box-sizing:
      border-box;

    background:
      rgba(8,8,8,0.92);

    border:
      1px solid
      rgba(255,255,255,0.11);

    border-radius:
      12px;

    backdrop-filter:
      blur(16px);

    -webkit-backdrop-filter:
      blur(16px);

    box-shadow:
      0 8px 28px
      rgba(0,0,0,0.38),

      inset 0 1px 0
      rgba(255,255,255,0.045);

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
  }


  /* =========================================================
     PLAYBACK CONTROLS
     ========================================================= */

  .timeline-controls {

    display:
      flex;

    align-items:
      center;

    gap:
      2px;

    flex-shrink:
      0;
  }


  .ctrl-btn {

    width:
      28px;

    height:
      28px;

    display:
      flex;

    align-items:
      center;

    justify-content:
      center;

    border:
      1px solid
      transparent;

    border-radius:
      7px;

    background:
      transparent;

    color:
      rgba(255,255,255,0.40);

    cursor:
      pointer;

    transition:
      all 0.15s ease;
  }


  .ctrl-btn:hover {

    color:
      #ffffff;

    background:
      rgba(255,255,255,0.065);

    border-color:
      rgba(255,255,255,0.08);
  }


  /* =========================================================
     PLAY BUTTON
     ========================================================= */

  .play-btn {

    width:
      30px;

    height:
      30px;

    display:
      flex;

    align-items:
      center;

    justify-content:
      center;

    border:
      1px solid
      rgba(255,255,255,0.18);

    border-radius:
      8px;

    background:
      #ffffff;

    color:
      #050505;

    cursor:
      pointer;

    box-shadow:
      0 2px 8px
      rgba(0,0,0,0.3);

    transition:
      all 0.15s ease;
  }


  .play-btn:hover {

    background:
      #e8e8e8;

    transform:
      translateY(-1px);

    box-shadow:
      0 4px 12px
      rgba(0,0,0,0.4);
  }


  .play-btn.playing {

    background:
      #d9d9d9;
  }


  .play-btn:active {

    transform:
      translateY(0);
  }


  /* =========================================================
     DIVIDER
     ========================================================= */

  .control-divider {

    width:
      1px;

    height:
      24px;

    flex-shrink:
      0;

    background:
      rgba(255,255,255,0.10);
  }


  /* =========================================================
     TIMELINE TRACK
     ========================================================= */

  .timeline-track {

    position:
      relative;

    display:
      flex;

    align-items:
      flex-start;

    gap:
      0;

    padding:
      0 7px;

    min-width:
      220px;

    max-width:
      560px;

    overflow-x:
      auto;

    scrollbar-width:
      none;
  }


  .timeline-track::-webkit-scrollbar {

    display:
      none;
  }


  /* =========================================================
     TIMELINE LINE
     ========================================================= */

  .timeline-line {

    position:
      absolute;

    left:
      12px;

    right:
      12px;

    top:
      7px;

    height:
      1px;

    background:
      rgba(255,255,255,0.13);

    pointer-events:
      none;
  }


  /* =========================================================
     YEAR
     ========================================================= */

  .year-tick {

    position:
      relative;

    z-index:
      1;

    width:
      48px;

    min-width:
      48px;

    height:
      38px;

    display:
      flex;

    flex-direction:
      column;

    align-items:
      center;

    gap:
      5px;

    padding:
      0;

    border:
      none;

    background:
      transparent;

    color:
      rgba(255,255,255,0.30);

    cursor:
      pointer;

    font-family:
      inherit;

    transition:
      color 0.15s ease;
  }


  /* =========================================================
     DOT
     ========================================================= */

  .tick-dot {

    width:
      7px;

    height:
      7px;

    flex-shrink:
      0;

    margin-top:
      4px;

    border-radius:
      50%;

    background:
      #252525;

    border:
      1px solid
      rgba(255,255,255,0.20);

    box-shadow:
      0 0 0 2px
      #080808;

    transition:
      all 0.18s ease;
  }


  /* =========================================================
     YEAR LABEL
     ========================================================= */

  .tick-label {

    font-family:
      var(--font-mono, "SF Mono", monospace);

    font-size:
      9px;

    line-height:
      1;

    font-weight:
      500;

    color:
      rgba(255,255,255,0.30);

    white-space:
      nowrap;

    transition:
      color 0.15s ease,
      font-weight 0.15s ease;
  }


  /* =========================================================
     HOVER
     ========================================================= */

  .year-tick:hover {

    color:
      rgba(255,255,255,0.72);
  }


  .year-tick:hover .tick-dot {

    background:
      rgba(255,255,255,0.48);

    border-color:
      rgba(255,255,255,0.48);

    transform:
      scale(1.12);
  }


  .year-tick:hover .tick-label {

    color:
      rgba(255,255,255,0.70);
  }


  /* =========================================================
     ACTIVE YEAR
     ========================================================= */

  .year-tick.active {

    color:
      #ffffff;
  }


  .year-tick.active .tick-dot {

    width:
      9px;

    height:
      9px;

    margin-top:
      3px;

    background:
      #ffffff;

    border:
      2px solid
      #080808;

    box-shadow:
      0 0 0 1px
      rgba(255,255,255,0.75),

      0 0 10px
      rgba(255,255,255,0.18);

    transform:
      scale(1);
  }


  .year-tick.active .tick-label {

    color:
      #ffffff;

    font-weight:
      700;
  }


  /* =========================================================
     ACTIVE YEAR INFO
     ========================================================= */

  .timeline-info {

    min-width:
      58px;

    display:
      flex;

    align-items:
      center;

    gap:
      7px;

    padding:
      0 7px 0 11px;

    border-left:
      1px solid
      rgba(255,255,255,0.10);

    flex-shrink:
      0;
  }


  .clock-icon {

    color:
      rgba(255,255,255,0.40);
  }


  .active-year-content {

    display:
      flex;

    flex-direction:
      column;

    gap:
      2px;
  }


  .active-year-label {

    font-size:
      7px;

    line-height:
      1;

    font-weight:
      650;

    letter-spacing:
      0.12em;

    color:
      rgba(255,255,255,0.28);
  }


  .active-badge {

    font-family:
      var(--font-mono, "SF Mono", monospace);

    font-size:
      11px;

    line-height:
      1;

    font-weight:
      700;

    color:
      #ffffff;

    font-variant-numeric:
      tabular-nums;
  }


  /* =========================================================
     EMPTY
     ========================================================= */

  .empty-timeline {

    display:
      flex;

    align-items:
      center;

    height:
      38px;

    padding:
      0 10px;

    font-size:
      9px;

    color:
      rgba(255,255,255,0.25);
  }


  /* =========================================================
     FOCUS
     ========================================================= */

  .ctrl-btn:focus-visible,
  .play-btn:focus-visible,
  .year-tick:focus-visible {

    outline:
      1px solid
      rgba(255,255,255,0.55);

    outline-offset:
      2px;
  }


  /* =========================================================
     RESPONSIVE
     ========================================================= */

  @media (max-width: 700px) {

    .timeline-bar-wrapper {

      max-width:
        calc(100vw - 20px);

      gap:
        7px;

      padding:
        4px 6px;
    }


    .timeline-track {

      min-width:
        150px;

      max-width:
        300px;
    }


    .timeline-info {

      padding-left:
        7px;
    }
  }


  @media (max-width: 480px) {

    .timeline-track {

      min-width:
        120px;

      max-width:
        200px;
    }


    .timeline-info {

      min-width:
        45px;
    }


    .active-year-label {

      display:
        none;
    }
  }

</style>