<script lang="ts">
  import { showAuditTraceModal, currentResult } from '../stores';
  import {
    X,
    CheckCircle2,
    Clock,
    Cpu,
    Database,
    Activity,
    Server
  } from 'lucide-svelte';

  function closeModal() {
    $showAuditTraceModal = false;
  }
</script>

{#if $showAuditTraceModal}

  <div
    class="modal-backdrop"
    on:click={closeModal}
    role="button"
    tabindex="0"
    aria-label="Close audit trace"
  >

    <div
      class="modal-card"
      on:click|stopPropagation
      role="region"
      tabindex="-1"
    >

      <!-- =====================================================
           HEADER
           ===================================================== -->

      <div class="modal-header">

        <div class="header-title-row">

          <div class="title-icon">
            <Activity
              size={15}
              strokeWidth={1.7}
            />
          </div>

          <div class="title-content">
            <div class="modal-kicker">
              EXECUTION / PROVENANCE
            </div>

            <h2 class="modal-title">
              Execution Audit Trace
            </h2>
          </div>

        </div>


        <button
          class="close-btn"
          on:click={closeModal}
          aria-label="Close"
        >
          <X
            size={16}
            strokeWidth={1.6}
          />
        </button>

      </div>


      <!-- =====================================================
           METADATA
           ===================================================== -->

      <div class="modal-meta-strip">


        <div class="meta-item">

          <Server
            size={12}
            strokeWidth={1.5}
          />

          <div class="meta-content">

            <span class="meta-label">
              PIPELINE
            </span>

            <span class="meta-value">
              {$currentResult?.provenance.pipeline || 'ATS / LangGraph'}
            </span>

          </div>

        </div>


        <div class="meta-divider"></div>


        <div class="meta-item">

          <Cpu
            size={12}
            strokeWidth={1.5}
          />

          <div class="meta-content">

            <span class="meta-label">
              MODEL
            </span>

            <span class="meta-value">
              {$currentResult?.provenance.model_name || 'Prithvi-EO-2.0'}
            </span>

          </div>

        </div>


        <div class="meta-divider"></div>


        <div class="meta-item">

          <Database
            size={12}
            strokeWidth={1.5}
          />

          <div class="meta-content">

            <span class="meta-label">
              SOURCE
            </span>

            <span class="source-pill">
              {$currentResult?.provenance.source === 'worker'
                ? 'SATELLITE WORKER'
                : 'SATELLITE ARCHIVE'}
            </span>

          </div>

        </div>

      </div>


      <!-- =====================================================
           TRACE
           ===================================================== -->

      <div class="trace-steps-container">

        {#if ($currentResult?.audit_trace || []).length === 0}

          <div class="empty-trace">

            <div class="empty-icon">
              <Activity
                size={17}
                strokeWidth={1.5}
              />
            </div>

            <span>
              No execution trace available.
            </span>

          </div>

        {:else}

          {#each ($currentResult?.audit_trace || []) as stage, idx}

            <div class="trace-step-item">


              <!-- TIMELINE -->

              <div class="step-indicator">

                <div class="step-circle completed">

                  <CheckCircle2
                    size={17}
                    strokeWidth={1.6}
                  />

                </div>


                {#if idx < ($currentResult?.audit_trace.length || 0) - 1}

                  <div class="step-line"></div>

                {/if}

              </div>


              <!-- CONTENT -->

              <div class="step-content">


                <div class="step-header">

                  <div class="step-title-group">

                    <span class="step-number">
                      {String(idx + 1).padStart(2, '0')}
                    </span>

                    <span class="step-name">
                      {stage.name}
                    </span>

                  </div>


                  <span class="step-duration">

                    <Clock
                      size={10}
                      strokeWidth={1.6}
                    />

                    {stage.duration_ms} ms

                  </span>

                </div>


                <div class="step-details">

                  {stage.details ||
                    'Successfully verified and completed.'}

                </div>


                <div class="step-status">

                  <span class="status-pill completed">
                    COMPLETED
                  </span>

                  <span class="step-time">
                    {stage.timestamp?.split('T')[1]?.slice(0, 8) || ''}
                  </span>

                </div>

              </div>

            </div>

          {/each}

        {/if}

      </div>


      <!-- =====================================================
           FOOTER
           ===================================================== -->

      <div class="modal-footer">

        <div class="latency-block">

          <span class="latency-label">
            TOTAL LATENCY
          </span>

          <span class="total-latency">
            {(
              $currentResult?.audit_trace?.reduce(
                (a, b) => a + b.duration_ms,
                0
              ) || 360
            )} ms
          </span>

        </div>


        <button
          class="done-btn"
          on:click={closeModal}
        >
          Close Trace
        </button>

      </div>

    </div>

  </div>

{/if}


<style>

  /* =========================================================
     BACKDROP
     ========================================================= */

  .modal-backdrop {

    position:
      fixed;

    inset:
      0;

    z-index:
      100;

    display:
      flex;

    align-items:
      center;

    justify-content:
      center;

    padding:
      20px;

    background:
      rgba(0,0,0,0.76);

    backdrop-filter:
      blur(16px);

    -webkit-backdrop-filter:
      blur(16px);
  }


  /* =========================================================
     MODAL
     ========================================================= */

  .modal-card {

    width:
      min(100%, 610px);

    max-height:
      min(720px, calc(100vh - 40px));

    display:
      flex;

    flex-direction:
      column;

    overflow:
      hidden;

    border-radius:
      13px;

    background:
      linear-gradient(
        145deg,
        rgba(17,17,17,0.98),
        rgba(7,7,7,0.98)
      );

    border:
      1px solid
      rgba(255,255,255,0.105);

    box-shadow:
      0 30px 80px
      rgba(0,0,0,0.62),

      inset 0 1px 0
      rgba(255,255,255,0.045);
  }


  /* =========================================================
     HEADER
     ========================================================= */

  .modal-header {

    display:
      flex;

    align-items:
      center;

    justify-content:
      space-between;

    padding:
      17px 20px;

    border-bottom:
      1px solid
      rgba(255,255,255,0.065);
  }


  .header-title-row {

    display:
      flex;

    align-items:
      center;

    gap:
      10px;
  }


  .title-icon {

    width:
      31px;

    height:
      31px;

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
      rgba(255,255,255,0.085);

    color:
      rgba(255,255,255,0.68);

    box-shadow:
      inset 0 1px 0
      rgba(255,255,255,0.035);
  }


  .title-content {

    display:
      flex;

    flex-direction:
      column;

    gap:
      2px;
  }


  .modal-kicker {

    font-family:
      var(--font-mono, monospace);

    font-size:
      7px;

    font-weight:
      650;

    letter-spacing:
      0.14em;

    color:
      rgba(255,255,255,0.25);
  }


  .modal-title {

    margin:
      0;

    font-size:
      15px;

    line-height:
      1.2;

    font-weight:
      620;

    letter-spacing:
      -0.015em;

    color:
      rgba(255,255,255,0.90);
  }


  .close-btn {

    width:
      30px;

    height:
      30px;

    padding:
      0;

    display:
      flex;

    align-items:
      center;

    justify-content:
      center;

    border-radius:
      7px;

    border:
      1px solid
      transparent;

    background:
      transparent;

    color:
      rgba(255,255,255,0.32);

    cursor:
      pointer;

    transition:
      all 0.15s ease;
  }


  .close-btn:hover {

    color:
      #ffffff;

    background:
      rgba(255,255,255,0.065);

    border-color:
      rgba(255,255,255,0.08);
  }


  /* =========================================================
     META STRIP
     ========================================================= */

  .modal-meta-strip {

    display:
      flex;

    align-items:
      center;

    padding:
      11px 20px;

    gap:
      14px;

    background:
      rgba(255,255,255,0.018);

    border-bottom:
      1px solid
      rgba(255,255,255,0.055);
  }


  .meta-item {

    min-width:
      0;

    display:
      flex;

    align-items:
      center;

    gap:
      7px;

    color:
      rgba(255,255,255,0.30);
  }


  .meta-content {

    min-width:
      0;

    display:
      flex;

    align-items:
      center;

    gap:
      6px;
  }


  .meta-label {

    font-size:
      7px;

    font-weight:
      700;

    letter-spacing:
      0.10em;

    color:
      rgba(255,255,255,0.20);
  }


  .meta-value {

    max-width:
      170px;

    overflow:
      hidden;

    text-overflow:
      ellipsis;

    white-space:
      nowrap;

    font-family:
      var(--font-mono, monospace);

    font-size:
      7.5px;

    color:
      rgba(255,255,255,0.48);
  }


  .meta-divider {

    width:
      1px;

    height:
      18px;

    flex-shrink:
      0;

    background:
      rgba(255,255,255,0.07);
  }


  .source-pill {

    padding:
      3px 5px;

    border-radius:
      4px;

    background:
      rgba(255,255,255,0.065);

    border:
      1px solid
      rgba(255,255,255,0.08);

    color:
      rgba(255,255,255,0.55);

    font-family:
      var(--font-mono, monospace);

    font-size:
      6.5px;

    font-weight:
      650;

    letter-spacing:
      0.03em;
  }


  /* =========================================================
     TRACE CONTAINER
     ========================================================= */

  .trace-steps-container {

    flex:
      1;

    min-height:
      0;

    padding:
      22px 20px 8px;

    max-height:
      470px;

    overflow-y:
      auto;

    scrollbar-width:
      thin;

    scrollbar-color:
      rgba(255,255,255,0.12)
      transparent;
  }


  .trace-steps-container::-webkit-scrollbar {

    width:
      4px;
  }


  .trace-steps-container::-webkit-scrollbar-track {

    background:
      transparent;
  }


  .trace-steps-container::-webkit-scrollbar-thumb {

    background:
      rgba(255,255,255,0.12);

    border-radius:
      10px;
  }


  /* =========================================================
     TRACE STEP
     ========================================================= */

  .trace-step-item {

    position:
      relative;

    display:
      flex;

    gap:
      12px;
  }


  .step-indicator {

    width:
      22px;

    flex-shrink:
      0;

    display:
      flex;

    flex-direction:
      column;

    align-items:
      center;
  }


  .step-circle {

    width:
      21px;

    height:
      21px;

    display:
      flex;

    align-items:
      center;

    justify-content:
      center;

    z-index:
      2;

    border-radius:
      50%;

    color:
      rgba(255,255,255,0.72);

    background:
      #0b0b0b;

    box-shadow:
      0 0 0 4px
      rgba(255,255,255,0.018);
  }


  .step-circle.completed {

    color:
      #ffffff;
  }


  .step-line {

    width:
      1px;

    flex:
      1;

    min-height:
      26px;

    margin:
      2px 0;

    background:
      linear-gradient(
        to bottom,
        rgba(255,255,255,0.20),
        rgba(255,255,255,0.045)
      );
  }


  /* =========================================================
     STEP CONTENT
     ========================================================= */

  .step-content {

    flex:
      1;

    min-width:
      0;

    padding:
      0 0 21px;
  }


  .step-header {

    display:
      flex;

    align-items:
      center;

    justify-content:
      space-between;

    gap:
      12px;

    margin-bottom:
      5px;
  }


  .step-title-group {

    min-width:
      0;

    display:
      flex;

    align-items:
      center;

    gap:
      7px;
  }


  .step-number {

    font-family:
      var(--font-mono, monospace);

    font-size:
      7px;

    color:
      rgba(255,255,255,0.18);
  }


  .step-name {

    overflow:
      hidden;

    text-overflow:
      ellipsis;

    white-space:
      nowrap;

    font-size:
      11.5px;

    font-weight:
      650;

    letter-spacing:
      -0.005em;

    color:
      rgba(255,255,255,0.78);
  }


  .step-duration {

    flex-shrink:
      0;

    display:
      flex;

    align-items:
      center;

    gap:
      4px;

    font-family:
      var(--font-mono, monospace);

    font-size:
      7.5px;

    color:
      rgba(255,255,255,0.28);
  }


  .step-details {

    max-width:
      490px;

    margin-bottom:
      7px;

    font-size:
      9.5px;

    line-height:
      1.55;

    color:
      rgba(255,255,255,0.34);
  }


  .step-status {

    display:
      flex;

    align-items:
      center;

    gap:
      8px;
  }


  .status-pill {

    display:
      inline-flex;

    align-items:
      center;

    padding:
      3px 5px;

    border-radius:
      4px;

    font-family:
      var(--font-mono, monospace);

    font-size:
      6.5px;

    font-weight:
      700;

    letter-spacing:
      0.08em;
  }


  .status-pill.completed {

    background:
      rgba(255,255,255,0.07);

    border:
      1px solid
      rgba(255,255,255,0.10);

    color:
      rgba(255,255,255,0.58);
  }


  .step-time {

    font-family:
      var(--font-mono, monospace);

    font-size:
      7.5px;

    color:
      rgba(255,255,255,0.18);
  }


  /* =========================================================
     EMPTY TRACE
     ========================================================= */

  .empty-trace {

    min-height:
      220px;

    display:
      flex;

    flex-direction:
      column;

    align-items:
      center;

    justify-content:
      center;

    gap:
      10px;

    color:
      rgba(255,255,255,0.24);

    font-size:
      10px;
  }


  .empty-icon {

    width:
      40px;

    height:
      40px;

    display:
      flex;

    align-items:
      center;

    justify-content:
      center;

    border-radius:
      10px;

    background:
      rgba(255,255,255,0.035);

    border:
      1px solid
      rgba(255,255,255,0.065);
  }


  /* =========================================================
     FOOTER
     ========================================================= */

  .modal-footer {

    display:
      flex;

    align-items:
      center;

    justify-content:
      space-between;

    padding:
      13px 20px;

    background:
      rgba(255,255,255,0.018);

    border-top:
      1px solid
      rgba(255,255,255,0.065);
  }


  .latency-block {

    display:
      flex;

    flex-direction:
      column;

    gap:
      2px;
  }


  .latency-label {

    font-size:
      6.5px;

    font-weight:
      700;

    letter-spacing:
      0.12em;

    color:
      rgba(255,255,255,0.19);
  }


  .total-latency {

    font-family:
      var(--font-mono, monospace);

    font-size:
      10px;

    color:
      rgba(255,255,255,0.56);
  }


  .done-btn {

    padding:
      7px 13px;

    border-radius:
      6px;

    background:
      rgba(255,255,255,0.92);

    border:
      1px solid
      rgba(255,255,255,0.95);

    color:
      #050505;

    font-family:
      inherit;

    font-size:
      9px;

    font-weight:
      650;

    cursor:
      pointer;

    transition:
      all 0.15s ease;
  }


  .done-btn:hover {

    background:
      #ffffff;

    transform:
      translateY(-1px);

    box-shadow:
      0 5px 16px
      rgba(255,255,255,0.10);
  }


  /* =========================================================
     RESPONSIVE
     ========================================================= */

  @media (max-width: 650px) {

    .modal-backdrop {

      padding:
        10px;
    }


    .modal-card {

      max-height:
        calc(100vh - 20px);

      border-radius:
        11px;
    }


    .modal-meta-strip {

      flex-direction:
        column;

      align-items:
        flex-start;

      gap:
        9px;
    }


    .meta-divider {

      display:
        none;
    }


    .meta-item {

      width:
        100%;
    }


    .meta-content {

      justify-content:
        space-between;

      width:
        100%;
    }


    .meta-value {

      max-width:
        55%;
    }


    .step-header {

      align-items:
        flex-start;

      flex-direction:
        column;

      gap:
        4px;
    }


    .step-duration {

      margin-left:
        0;
    }


    .modal-footer {

      padding:
        12px 16px;
    }

  }

</style>