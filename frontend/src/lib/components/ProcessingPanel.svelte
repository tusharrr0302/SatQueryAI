<script lang="ts">
  import {
    CheckCircle2,
    Paperclip,
    ArrowUp
  } from 'lucide-svelte';

  export let query: string = '';
  export let progressStep: number = 4;
  export let errorMessage: string = '';
  export let onStartOver: (() => void) | undefined = undefined;


  const steps = [
    {
      id: 1,
      title: 'Understanding request',
      subtitle: 'Identifying location, time range and analysis type',
      time: '2.1s',
    },
    {
      id: 2,
      title: 'Selecting data',
      subtitle: 'Sentinel-2 imagery (2014 - 2024)',
      time: '1.8s',
    },
    {
      id: 3,
      title: 'Selecting model',
      subtitle: 'Prithvi-EO-2.0 (temporal change analysis)',
      time: '1.2s',
    },
    {
      id: 4,
      title: 'Running analysis',
      subtitle: 'Processing satellite imagery...',
      time: '...',
    },
    {
      id: 5,
      title: 'Generating visualization',
      subtitle: 'Preparing maps and charts',
      time: '',
    },
    {
      id: 6,
      title: 'Finalizing results',
      subtitle: 'Almost complete...',
      time: '',
    },
  ];
</script>


<div class="processing-panel-wrapper">


  <!-- =====================================================
       CONVERSATION
       ===================================================== -->

  <div class="processing-content">


    <!-- =================================================
         USER QUERY
         ================================================= -->

    <div class="user-bubble-row">

      <div class="user-bubble">

        <span class="bubble-text">
          {query}
        </span>

        <span class="bubble-time">
          10:24 AM
        </span>

      </div>


      <div class="user-avatar">
        TK
      </div>

    </div>


    <!-- =================================================
         ASSISTANT PROCESSING
         ================================================= -->

    <div class="assistant-card">


      <!-- HEADER -->

      <div class="card-header">

        <div class="satquery-icon">

          <img
            src="/satquery_logo.png"
            alt="SatQuery AI"
            class="satquery-logo-img"
          />

        </div>


        <div class="title-col">

          <div class="agent-name">
            SatQuery <span>AI</span>
          </div>

          <div class="agent-status">
            Analyzing your request...
          </div>

        </div>

      </div>


      <!-- =================================================
           ERROR
           ================================================= -->

      {#if errorMessage}

        <div
          class="error-box"
          role="alert"
        >

          <div class="error-heading">
            Analysis could not be completed
          </div>

          <span class="error-message">
            {errorMessage}
          </span>


          {#if onStartOver}

            <button
              class="retry-btn"
              on:click={onStartOver}
            >
              Start over
            </button>

          {/if}

        </div>

      {/if}


      <!-- =================================================
           EXECUTION STEPS
           ================================================= -->

      <div class="steps-checklist">

        {#each steps as step}

          <div
            class="step-row"
            class:completed={step.id < progressStep}
            class:active={step.id === progressStep}
            class:pending={step.id > progressStep}
          >


            <!-- STEP ICON -->

            <div class="step-icon">

              {#if step.id < progressStep}

                <CheckCircle2
                  size={16}
                  strokeWidth={1.8}
                  class="check-done"
                />

              {:else if step.id === progressStep}

                <div class="pulsing-spinner"></div>

              {:else}

                <div class="circle-pending"></div>

              {/if}

            </div>


            <!-- STEP DETAILS -->

            <div class="step-details">

              <span class="step-title">
                {step.title}
              </span>

              <span class="step-subtitle">
                {step.subtitle}
              </span>

            </div>


            <!-- TIME -->

            {#if step.time}

              <span class="step-time">
                {step.time}
              </span>

            {/if}

          </div>

        {/each}

      </div>

    </div>

  </div>


  <!-- =====================================================
       BOTTOM INPUT
       ===================================================== -->

  <div class="input-container">

    <div class="input-bar">


      <button
        class="attach-btn"
        title="Attach file"
        disabled
      >

        <Paperclip
          size={17}
          strokeWidth={1.7}
        />

      </button>


      <input
        type="text"
        placeholder="Ask anything about Earth..."
        disabled
        class="chat-input"
      />


      <button
        class="send-btn"
        disabled
      >

        <ArrowUp
          size={17}
          strokeWidth={1.8}
        />

      </button>

    </div>

  </div>

</div>


<style>

  /* =========================================================
     MAIN PANEL
     ========================================================= */

  .processing-panel-wrapper {

    width: 100%;
    height: 100%;

    min-height: 0;

    display: flex;
    flex-direction: column;

    overflow: hidden;

    background:
      linear-gradient(
        145deg,
        rgba(16,16,16,0.97),
        rgba(4,4,4,0.99)
      );

    border:
      1px solid
      rgba(255,255,255,0.085);

    border-radius:
      14px;

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

    box-shadow:
      inset 0 1px 0
      rgba(255,255,255,0.035);
  }


  /* =========================================================
     CONVERSATION
     ========================================================= */

  .processing-content {

    flex: 1;

    min-height: 0;

    overflow-y: auto;

    padding:
      24px 26px 28px;

    display:
      flex;

    flex-direction:
      column;

    gap:
      18px;
  }


  .processing-content::-webkit-scrollbar {

    width:
      4px;
  }


  .processing-content::-webkit-scrollbar-track {

    background:
      transparent;
  }


  .processing-content::-webkit-scrollbar-thumb {

    background:
      rgba(255,255,255,0.12);

    border-radius:
      10px;
  }


  /* =========================================================
     USER MESSAGE
     ========================================================= */

  .user-bubble-row {

    display:
      flex;

    align-items:
      flex-start;

    justify-content:
      flex-end;

    gap:
      9px;
  }


  .user-bubble {

    max-width:
      min(72%, 620px);

    display:
      flex;

    flex-direction:
      column;

    gap:
      5px;

    padding:
      11px 15px;

    border-radius:
      13px 5px 13px 13px;

    background:
      rgba(255,255,255,0.065);

    border:
      1px solid
      rgba(255,255,255,0.10);

    box-shadow:
      inset 0 1px 0
      rgba(255,255,255,0.025);
  }


  .bubble-text {

    font-size:
      13px;

    line-height:
      1.45;

    color:
      rgba(255,255,255,0.86);
  }


  .bubble-time {

    font-size:
      9px;

    font-family:
      var(--font-mono, "SF Mono", monospace);

    color:
      rgba(255,255,255,0.28);

    text-align:
      right;
  }


  /* =========================================================
     USER AVATAR
     ========================================================= */

  .user-avatar {

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
      50%;

    background:
      #171717;

    border:
      1px solid
      rgba(255,255,255,0.13);

    color:
      rgba(255,255,255,0.72);

    font-size:
      9px;

    font-weight:
      650;

    letter-spacing:
      -0.02em;

    box-shadow:
      inset 0 1px 0
      rgba(255,255,255,0.045);
  }


  /* =========================================================
     ASSISTANT CARD
     ========================================================= */

  .assistant-card {

    width:
      min(100%, 760px);

    background:
      rgba(255,255,255,0.028);

    border:
      1px solid
      rgba(255,255,255,0.085);

    border-radius:
      12px;

    padding:
      17px 18px 18px;

    display:
      flex;

    flex-direction:
      column;

    gap:
      17px;

    box-shadow:
      inset 0 1px 0
      rgba(255,255,255,0.025);
  }


  /* =========================================================
     ASSISTANT HEADER
     ========================================================= */

  .card-header {

    display:
      flex;

    align-items:
      center;

    gap:
      10px;

    padding-bottom:
      13px;

    border-bottom:
      1px solid
      rgba(255,255,255,0.055);
  }


  .satquery-icon {

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

    border-radius:
      8px;

    background:
      rgba(255,255,255,0.055);

    border:
      1px solid
      rgba(255,255,255,0.10);

    box-shadow:
      inset 0 1px 0
      rgba(255,255,255,0.045);
  }


  .satquery-logo-img {

    width:
      20px;

    height:
      20px;

    object-fit:
      contain;

    display:
      block;

    filter:
      grayscale(1);
  }


  .title-col {

    display:
      flex;

    flex-direction:
      column;

    gap:
      2px;
  }


  .agent-name {

    font-size:
      13px;

    line-height:
      1.2;

    font-weight:
      650;

    letter-spacing:
      -0.015em;

    color:
      #ffffff;
  }


  .agent-name span {

    color:
      rgba(255,255,255,0.52);

    font-weight:
      500;
  }


  .agent-status {

    font-size:
      10px;

    color:
      rgba(255,255,255,0.34);
  }


  /* =========================================================
     ERROR
     ========================================================= */

  .error-box {

    display:
      flex;

    flex-direction:
      column;

    gap:
      5px;

    padding:
      12px 13px;

    border-radius:
      9px;

    background:
      rgba(255,255,255,0.035);

    border:
      1px solid
      rgba(255,255,255,0.16);

    color:
      rgba(255,255,255,0.75);

    font-size:
      11px;

    line-height:
      1.45;
  }


  .error-heading {

    color:
      #ffffff;

    font-size:
      11px;

    font-weight:
      650;
  }


  .error-message {

    color:
      rgba(255,255,255,0.40);
  }


  .retry-btn {

    align-self:
      flex-start;

    margin-top:
      5px;

    padding:
      6px 11px;

    border-radius:
      6px;

    background:
      rgba(255,255,255,0.075);

    border:
      1px solid
      rgba(255,255,255,0.13);

    color:
      rgba(255,255,255,0.76);

    font-family:
      inherit;

    font-size:
      10px;

    font-weight:
      600;

    cursor:
      pointer;

    transition:
      all 0.15s ease;
  }


  .retry-btn:hover {

    background:
      #ffffff;

    border-color:
      #ffffff;

    color:
      #050505;
  }


  /* =========================================================
     CHECKLIST
     ========================================================= */

  .steps-checklist {

    display:
      flex;

    flex-direction:
      column;

    gap:
      3px;

    padding:
      1px 0;
  }


  .step-row {

    min-height:
      50px;

    display:
      flex;

    align-items:
      center;

    gap:
      11px;

    padding:
      7px 9px;

    border-radius:
      8px;

    transition:
      background 0.18s ease;
  }


  /* =========================================================
     STEP ACTIVE
     ========================================================= */

  .step-row.active {

    background:
      rgba(255,255,255,0.055);

    border:
      1px solid
      rgba(255,255,255,0.07);

    padding:
      6px 8px;
  }


  /* =========================================================
     STEP ICON
     ========================================================= */

  .step-icon {

    width:
      20px;

    height:
      20px;

    flex-shrink:
      0;

    display:
      flex;

    align-items:
      center;

    justify-content:
      center;
  }


  .check-done {

    color:
      rgba(255,255,255,0.82);
  }


  /* =========================================================
     ACTIVE SPINNER
     ========================================================= */

  .pulsing-spinner {

    width:
      14px;

    height:
      14px;

    border:
      1.8px solid
      rgba(255,255,255,0.16);

    border-top-color:
      #ffffff;

    border-radius:
      50%;

    animation:
      spin 0.8s linear infinite;
  }


  @keyframes spin {

    to {
      transform:
        rotate(360deg);
    }
  }


  /* =========================================================
     PENDING CIRCLE
     ========================================================= */

  .circle-pending {

    width:
      11px;

    height:
      11px;

    border:
      1px solid
      rgba(255,255,255,0.17);

    border-radius:
      50%;
  }


  /* =========================================================
     STEP TEXT
     ========================================================= */

  .step-details {

    flex:
      1;

    min-width:
      0;

    display:
      flex;

    flex-direction:
      column;

    gap:
      2px;
  }


  .step-title {

    overflow:
      hidden;

    text-overflow:
      ellipsis;

    white-space:
      nowrap;

    font-size:
      11.5px;

    line-height:
      1.25;

    font-weight:
      600;

    color:
      rgba(255,255,255,0.78);
  }


  .step-subtitle {

    overflow:
      hidden;

    text-overflow:
      ellipsis;

    white-space:
      nowrap;

    font-size:
      9.5px;

    line-height:
      1.3;

    color:
      rgba(255,255,255,0.29);
  }


  /* COMPLETED */

  .step-row.completed
  .step-title {

    color:
      rgba(255,255,255,0.70);
  }


  .step-row.completed
  .step-subtitle {

    color:
      rgba(255,255,255,0.26);
  }


  /* ACTIVE */

  .step-row.active
  .step-title {

    color:
      #ffffff;
  }


  .step-row.active
  .step-subtitle {

    color:
      rgba(255,255,255,0.42);
  }


  /* PENDING */

  .step-row.pending
  .step-title {

    color:
      rgba(255,255,255,0.25);
  }


  .step-row.pending
  .step-subtitle {

    color:
      rgba(255,255,255,0.16);
  }


  /* =========================================================
     TIME
     ========================================================= */

  .step-time {

    flex-shrink:
      0;

    min-width:
      28px;

    text-align:
      right;

    font-size:
      9px;

    font-family:
      var(--font-mono, "SF Mono", monospace);

    font-variant-numeric:
      tabular-nums;

    color:
      rgba(255,255,255,0.30);
  }


  .step-row.active
  .step-time {

    color:
      rgba(255,255,255,0.62);
  }


  /* =========================================================
     INPUT AREA
     ========================================================= */

  .input-container {

    flex-shrink:
      0;

    padding:
      13px 18px 15px;

    background:
      rgba(0,0,0,0.24);

    border-top:
      1px solid
      rgba(255,255,255,0.06);
  }


  .input-bar {

    height:
      46px;

    display:
      flex;

    align-items:
      center;

    gap:
      5px;

    padding:
      5px 6px 5px 10px;

    border-radius:
      13px;

    background:
      rgba(255,255,255,0.035);

    border:
      1px solid
      rgba(255,255,255,0.095);

    box-shadow:
      inset 0 1px 0
      rgba(255,255,255,0.025);
  }


  /* =========================================================
     ATTACH
     ========================================================= */

  .attach-btn {

    width:
      32px;

    height:
      32px;

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
      transparent;

    border:
      none;

    color:
      rgba(255,255,255,0.25);

    cursor:
      not-allowed;
  }


  /* =========================================================
     INPUT
     ========================================================= */

  .chat-input {

    flex:
      1;

    min-width:
      0;

    height:
      34px;

    padding:
      0 8px;

    background:
      transparent;

    border:
      none;

    outline:
      none;

    color:
      #ffffff;

    font-family:
      inherit;

    font-size:
      11.5px;
  }


  .chat-input::placeholder {

    color:
      rgba(255,255,255,0.24);
  }


  /* =========================================================
     SEND
     ========================================================= */

  .send-btn {

    width:
      34px;

    height:
      34px;

    flex-shrink:
      0;

    display:
      flex;

    align-items:
      center;

    justify-content:
      center;

    border-radius:
      9px;

    background:
      rgba(255,255,255,0.08);

    border:
      1px solid
      rgba(255,255,255,0.09);

    color:
      rgba(255,255,255,0.22);

    opacity:
      1;

    cursor:
      not-allowed;
  }


  /* =========================================================
     RESPONSIVE
     ========================================================= */

  @media (max-width: 700px) {

    .processing-content {

      padding:
        18px 16px 20px;
    }


    .user-bubble {

      max-width:
        82%;
    }


    .assistant-card {

      width:
        100%;

      padding:
        15px;
    }


    .input-container {

      padding:
        10px 12px 12px;
    }
  }


  @media (max-height: 700px) {

    .processing-content {

      padding:
        16px 20px 18px;

      gap:
        14px;
    }


    .assistant-card {

      gap:
        13px;

      padding:
        14px 16px;
    }


    .step-row {

      min-height:
        43px;
    }


    .input-bar {

      height:
        42px;
    }
  }

</style>