<script lang="ts">
  import {
    Terminal,
    BookOpen,
    Layers,
    Cpu,
    Database,
    Network,
    ShieldCheck,
    Check
  } from 'lucide-svelte';


  let activeSection = 'overview';


  const sections = [
    {
      id: 'overview',
      title: 'System Overview'
    },
    {
      id: 'architecture',
      title: 'ATS Architecture'
    },
    {
      id: 'models',
      title: 'EO Foundation Models'
    },
    {
      id: 'datasets',
      title: 'Ingested Datasets'
    },
    {
      id: 'visualizations',
      title: '3D Scientific Engine'
    },
    {
      id: 'api',
      title: 'REST & WebSocket API'
    },
    {
      id: 'mock-worker',
      title: 'Mock & Worker Fallback'
    },
    {
      id: 'audit',
      title: 'Audit Trace & Provenance'
    }
  ];


  const sectionIcons = {
    overview: BookOpen,
    architecture: Network,
    models: Cpu,
    datasets: Database,
    visualizations: Layers,
    api: Terminal,
    'mock-worker': ShieldCheck,
    audit: Check
  };
</script>


<div class="docs-container">


  <!-- =====================================================
       LEFT NAVIGATION
       ===================================================== -->

  <aside class="docs-nav">


    <div class="nav-header">

      <div class="nav-header-icon">
        <BookOpen
          size={14}
          strokeWidth={1.7}
        />
      </div>

      <div>
        <div class="nav-title">
          DOCUMENTATION
        </div>

        <div class="nav-subtitle">
          SatQuery AI
        </div>
      </div>

    </div>


    <div class="nav-divider"></div>


    <div class="nav-section-label">
      SYSTEM
    </div>


    <div class="nav-links">

      {#each sections as sec}

        {@const Icon =
          sectionIcons[
            sec.id as keyof typeof sectionIcons
          ]}


        <button
          class="nav-link"
          class:active={
            activeSection === sec.id
          }
          on:click={() =>
            (activeSection = sec.id)
          }
        >

          <span class="nav-link-icon">

            <Icon
              size={14}
              strokeWidth={
                activeSection === sec.id
                  ? 1.9
                  : 1.6
              }
            />

          </span>


          <span class="nav-link-text">
            {sec.title}
          </span>


          {#if activeSection === sec.id}

            <span class="active-marker"></span>

          {/if}

        </button>

      {/each}

    </div>


    <div class="nav-footer">

      <div class="footer-line"></div>

      <div class="footer-status">

        <span class="status-dot"></span>

        <span>
          SYSTEM DOCUMENTATION
        </span>

      </div>

      <span class="footer-version">
        v1.0
      </span>

    </div>

  </aside>


  <!-- =====================================================
       MAIN DOCUMENTATION
       ===================================================== -->

  <main class="docs-content">


    <!-- ===================================================
         OVERVIEW
         =================================================== -->

    {#if activeSection === 'overview'}

      <section class="doc-sec">

        <div class="section-kicker">
          01 / OVERVIEW
        </div>

        <h1>
          SatQuery AI
          <span>— Technical Overview</span>
        </h1>

        <p class="lead">
          SatQuery AI is an interactive Earth-observation
          intelligence workstation that enables users to
          converse with multi-sensor, multi-temporal
          satellite data through validated natural-language
          queries.
        </p>


        <div class="content-divider"></div>


        <h3>
          Core Tenet:
          <span>Specialized AI, Not Generic Chatbots</span>
        </h3>


        <p>
          General-purpose LLMs lack spatial coordinate
          reference systems, spectral band understanding,
          and bi-temporal differencing capability.
          SatQuery AI pairs an Agentic Tool System (ATS)
          powered by LangGraph with specialized remote
          sensing foundation models:
        </p>


        <ul class="feature-list">

          <li>
            <strong>Prithvi-EO-2.0</strong>
            <span>
              (IBM/NASA): 300M parameter temporal ViT for
              multispectral changes & phenology.
            </span>
          </li>

          <li>
            <strong>GeoChat-7B</strong>
            <span>
              (MBZUAI): Grounded VLM for single-image
              conversational VQA and localization.
            </span>
          </li>

          <li>
            <strong>TerraFM</strong>
            <span>
              Multisensor optical + synthetic aperture radar
              (SAR) feature fusion.
            </span>
          </li>

          <li>
            <strong>CLOSP</strong>
            <span>
              Cross-modal optical-SAR semantic alignment
              and text-image retrieval.
            </span>
          </li>

        </ul>

      </section>


    <!-- ===================================================
         ARCHITECTURE
         =================================================== -->

    {:else if activeSection === 'architecture'}

      <section class="doc-sec">

        <div class="section-kicker">
          02 / ARCHITECTURE
        </div>

        <h1>
          Agentic Tool System
          <span>(ATS) Architecture</span>
        </h1>

        <p class="lead">
          The core orchestration principle of SatQuery AI:
        </p>


        <div class="principle-card">

          <span class="quote-mark">
            “
          </span>

          <div>
            <strong>
              GPT-OSS decides WHAT should happen;
            </strong>

            <br />

            <span>
              FastAPI decides HOW it happens.
            </span>
          </div>

        </div>


        <div class="architecture-flow">

          <div class="flow-node primary">
            USER QUERY
          </div>

          <div class="flow-arrow">↓</div>

          <div class="flow-node">
            Groq / GPT-OSS 120B
            <small>
              Intent Analyzer
            </small>
          </div>

          <div class="flow-arrow">↓</div>

          <div class="flow-node">
            Standardized
            AnalysisRequest
            <small>
              Typed Schema
            </small>
          </div>

          <div class="flow-arrow">↓</div>

          <div class="flow-node">
            FastAPI Validation
            <small>
              RequestValidator
            </small>
          </div>

          <div class="flow-arrow">↓</div>

          <div class="flow-node">
            Tool Calling /
            Tool Execution
          </div>

          <div class="flow-arrow">↓</div>

          <div class="flow-node">
            EO Specialist Worker
            <small>
              Prithvi / GeoChat / Mock
            </small>
          </div>

          <div class="flow-arrow">↓</div>

          <div class="flow-node">
            Normalized Result
            Contract
          </div>

          <div class="flow-arrow">↓</div>

          <div class="flow-node final">
            Cesium 3D Globe +
            3D NDVI Mesh +
            Audit Trace
          </div>

        </div>


        <p>
          The system strictly forbids the LLM from executing
          arbitrary Python, generating SQL, or modifying
          CesiumJS camera parameters directly. Execution is
          strictly governed by typed Pydantic contracts.
        </p>

      </section>


    <!-- ===================================================
         MODELS
         =================================================== -->

    {:else if activeSection === 'models'}

      <section class="doc-sec">

        <div class="section-kicker">
          03 / MODEL REGISTRY
        </div>

        <h1>
          EO Foundation Model
          <span>Registry</span>
        </h1>

        <p class="lead">
          SatQuery AI uses a closed model registry ensuring
          audited provenance across all analytical outputs.
        </p>


        <div class="table-wrap">

          <table>

            <thead>

              <tr>

                <th>
                  MODEL ID
                </th>

                <th>
                  NAME
                </th>

                <th>
                  SENSORS
                </th>

                <th>
                  PRIMARY CAPABILITIES
                </th>

              </tr>

            </thead>


            <tbody>

              <tr>

                <td>
                  <code>
                    prithvi-eo-2.0
                  </code>
                </td>

                <td>
                  <strong>
                    Prithvi-EO-2.0
                  </strong>
                </td>

                <td>
                  Sentinel-2, HLS
                </td>

                <td>
                  Decadal change, NDVI vegetation,
                  crop yield dynamics
                </td>

              </tr>


              <tr>

                <td>
                  <code>
                    geochat-7b
                  </code>
                </td>

                <td>
                  <strong>
                    GeoChat-7B
                  </strong>
                </td>

                <td>
                  Optical VHR
                </td>

                <td>
                  Single-image VQA, scene captioning,
                  visual grounding
                </td>

              </tr>


              <tr>

                <td>
                  <code>
                    terrafm
                  </code>
                </td>

                <td>
                  <strong>
                    TerraFM
                  </strong>
                </td>

                <td>
                  Sentinel-1 SAR + Optical
                </td>

                <td>
                  Flood inundation, built-up extraction,
                  all-weather tracking
                </td>

              </tr>


              <tr>

                <td>
                  <code>
                    closp
                  </code>
                </td>

                <td>
                  <strong>
                    CLOSP
                  </strong>
                </td>

                <td>
                  SAR + Optical
                </td>

                <td>
                  Cross-modal retrieval, semantic
                  representation alignment
                </td>

              </tr>

            </tbody>

          </table>

        </div>

      </section>


    <!-- ===================================================
         DATASETS
         =================================================== -->

    {:else if activeSection === 'datasets'}

      <section class="doc-sec">

        <div class="section-kicker">
          04 / DATA CATALOG
        </div>

        <h1>
          Supported
          <span>Datasets</span>
        </h1>

        <p class="lead">
          The platform natively supports seven
          planetary-scale observational datasets.
        </p>


        <div class="dataset-grid">

          <div class="dataset-card">
            <span class="dataset-number">01</span>
            <strong>Sentinel-2</strong>
            <span class="dataset-org">
              COPERNICUS
            </span>
            <p>
              13 multispectral bands at 10m/20m resolution
              with 5-day global revisit.
            </p>
          </div>


          <div class="dataset-card">
            <span class="dataset-number">02</span>
            <strong>Sentinel-1</strong>
            <span class="dataset-org">
              COPERNICUS
            </span>
            <p>
              C-band active SAR (VV+VH) for cloud-penetrating
              night/day observation.
            </p>
          </div>


          <div class="dataset-card">
            <span class="dataset-number">03</span>
            <strong>Landsat 8/9</strong>
            <span class="dataset-org">
              USGS / NASA
            </span>
            <p>
              30m multispectral + thermal record for
              retrospective analysis.
            </p>
          </div>


          <div class="dataset-card">
            <span class="dataset-number">04</span>
            <strong>PlanetScope</strong>
            <span class="dataset-org">
              PLANET LABS
            </span>
            <p>
              3m high-cadence daily global coverage.
            </p>
          </div>


          <div class="dataset-card">
            <span class="dataset-number">05</span>
            <strong>Copernicus DEM</strong>
            <span class="dataset-org">
              COPERNICUS
            </span>
            <p>
              Global 30m Digital Elevation Model for
              hydrological and slope modeling.
            </p>
          </div>


          <div class="dataset-card">
            <span class="dataset-number">06</span>
            <strong>Cartosat-2/3</strong>
            <span class="dataset-org">
              ISRO
            </span>
            <p>
              Sub-meter cartographic and urban
              infrastructure mapping.
            </p>
          </div>


          <div class="dataset-card">
            <span class="dataset-number">07</span>
            <strong>RISAT-1A</strong>
            <span class="dataset-org">
              ISRO
            </span>
            <p>
              Polarimetric radar imaging for monsoon
              agriculture and flood mapping.
            </p>
          </div>

        </div>

      </section>


    <!-- ===================================================
         VISUALIZATIONS
         =================================================== -->

    {:else if activeSection === 'visualizations'}

      <section class="doc-sec">

        <div class="section-kicker">
          05 / VISUALIZATION
        </div>

        <h1>
          3D Scientific
          <span>Visualization Engine</span>
        </h1>

        <p class="lead">
          Visualization is driven deterministically by
          backend result data through typed
          <code>VisualizationSpec</code>.
        </p>


        <div class="visual-list">

          <div class="visual-item">

            <div class="visual-index">
              01
            </div>

            <div>

              <strong>
                CesiumJS Globe Canvas
              </strong>

              <p>
                High-performance 3D virtual globe with
                camera fly-to, pins, and AOI boundary
                vectors.
              </p>

            </div>

          </div>


          <div class="visual-item">

            <div class="visual-index">
              02
            </div>

            <div>

              <strong>
                3D Isometric Surface Plot
              </strong>

              <p>
                Interactive canvas visualizing continuous
                matrix indices such as NDVI, DSM elevation,
                and heat index.
              </p>

            </div>

          </div>


          <div class="visual-item">

            <div class="visual-index">
              03
            </div>

            <div>

              <strong>
                Bi-Temporal Comparison Cards
              </strong>

              <p>
                Side-by-side satellite before/after cards
                with sensor metadata.
              </p>

            </div>

          </div>


          <div class="visual-item">

            <div class="visual-index">
              04
            </div>

            <div>

              <strong>
                Timelapse Scrubber
              </strong>

              <p>
                Longitudinal playback across decadal
                time slices (2016 → 2026).
              </p>

            </div>

          </div>

        </div>

      </section>


    <!-- ===================================================
         API
         =================================================== -->

    {:else if activeSection === 'api'}

      <section class="doc-sec">

        <div class="section-kicker">
          06 / API
        </div>

        <h1>
          REST &
          <span>WebSocket API</span>
        </h1>

        <p class="lead">
          FastAPI provides both REST endpoints and
          real-time WebSocket telemetry.
        </p>


        <div class="endpoint-list">

          <div class="endpoint-row">
            <code>POST</code>
            <span>/api/chat</span>
            <small>Submit remote sensing query</small>
          </div>

          <div class="endpoint-row">
            <code>POST</code>
            <span>/api/agent/plan</span>
            <small>Generate ATS execution plan</small>
          </div>

          <div class="endpoint-row">
            <code>POST</code>
            <span>/api/agent/execute</span>
            <small>Execute remote sensing pipeline</small>
          </div>

          <div class="endpoint-row">
            <code>GET</code>
            <span>/api/datasets</span>
            <small>Retrieve observational catalog</small>
          </div>

          <div class="endpoint-row">
            <code>GET</code>
            <span>/api/models</span>
            <small>Retrieve registered EO models</small>
          </div>

          <div class="endpoint-row">
            <code>GET</code>
            <span>/api/aoi</span>
            <small>List saved Areas of Interest</small>
          </div>

          <div class="endpoint-row">
            <code>POST</code>
            <span>/api/aoi</span>
            <small>Create custom AOI polygon</small>
          </div>

          <div class="endpoint-row">
            <code>GET</code>
            <span>/api/investigations</span>
            <small>List saved investigations</small>
          </div>

          <div class="endpoint-row">
            <code>POST</code>
            <span>/api/investigations</span>
            <small>Save active investigation</small>
          </div>

          <div class="endpoint-row websocket">
            <code>WS</code>
            <span>/ws/chat</span>
            <small>
              Real-time telemetry & execution streaming
            </small>
          </div>

        </div>

      </section>


    <!-- ===================================================
         MOCK / WORKER
         =================================================== -->

    {:else if activeSection === 'mock-worker'}

      <section class="doc-sec">

        <div class="section-kicker">
          07 / EXECUTION
        </div>

        <h1>
          Mock & Worker
          <span>Fallback Architecture</span>
        </h1>

        <p class="lead">
          The application supports dual execution modes
          configured via environment variables.
        </p>


        <div class="terminal-window">

          <div class="terminal-header">

            <div class="terminal-dots">
              <span></span>
              <span></span>
              <span></span>
            </div>

            <span>
              .env
            </span>

          </div>


          <pre><span class="comment"># Run with deterministic local scientific data</span>
MODEL_MODE=mock

<span class="comment"># Run with remote external Prithvi worker</span>
MODEL_MODE=worker
PRITHVI_WORKER_URL=https://xxxx.ngrok-free.app
ALLOW_MOCK_FALLBACK=true</pre>

        </div>


        <p>
          When in worker mode, if the remote worker
          endpoint is unreachable or times out, the system
          transparently activates mock fallback with
          <code>source="mock"</code> and
          <code>fallback=true</code>, visibly logged in
          the audit trace without disrupting the user
          experience.
        </p>

      </section>


    <!-- ===================================================
         AUDIT
         =================================================== -->

    {:else if activeSection === 'audit'}

      <section class="doc-sec">

        <div class="section-kicker">
          08 / PROVENANCE
        </div>

        <h1>
          Audit Trail &
          <span>Scientific Provenance</span>
        </h1>

        <p class="lead">
          Every response returned by SatQuery AI contains
          an auditable 6-stage execution trace.
        </p>


        <div class="audit-timeline">

          <div class="audit-step">

            <div class="audit-marker">
              01
            </div>

            <div class="audit-content">

              <strong>
                UNDERSTANDING REQUEST
              </strong>

              <p>
                Parsing spatial boundaries, temporal scope,
                and task taxonomy.
              </p>

            </div>

          </div>


          <div class="audit-step">

            <div class="audit-marker">
              02
            </div>

            <div class="audit-content">

              <strong>
                SELECTING DATA
              </strong>

              <p>
                Resolving sensor bands, cloud tolerance,
                and acquisition dates.
              </p>

            </div>

          </div>


          <div class="audit-step">

            <div class="audit-marker">
              03
            </div>

            <div class="audit-content">

              <strong>
                SELECTING MODEL
              </strong>

              <p>
                Binding specialized foundation model
                from registry.
              </p>

            </div>

          </div>


          <div class="audit-step">

            <div class="audit-marker">
              04
            </div>

            <div class="audit-content">

              <strong>
                RUNNING ANALYSIS
              </strong>

              <p>
                Executing feature extraction, differencing,
                or segmentation.
              </p>

            </div>

          </div>


          <div class="audit-step">

            <div class="audit-marker">
              05
            </div>

            <div class="audit-content">

              <strong>
                GENERATING VISUALIZATION
              </strong>

              <p>
                Constructing 3D surface matrix and
                comparison assets.
              </p>

            </div>

          </div>


          <div class="audit-step final">

            <div class="audit-marker">
              06
            </div>

            <div class="audit-content">

              <strong>
                COMPLETE
              </strong>

              <p>
                Compiling final normalized result and
                confidence metrics.
              </p>

            </div>

          </div>

        </div>

      </section>

    {/if}

  </main>

</div>


<style>

  /* =========================================================
     GLOBAL
     ========================================================= */

  .docs-container {

    width:
      100%;

    height:
      calc(100vh - 60px);

    min-height:
      0;

    display:
      flex;

    overflow:
      hidden;

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
  }


  /* =========================================================
     LEFT NAV
     ========================================================= */

  .docs-nav {

    width:
      245px;

    height:
      100%;

    flex-shrink:
      0;

    box-sizing:
      border-box;

    display:
      flex;

    flex-direction:
      column;

    padding:
      18px 12px;

    background:
      rgba(255,255,255,0.018);

    border-right:
      1px solid
      rgba(255,255,255,0.075);
  }


  .nav-header {

    display:
      flex;

    align-items:
      center;

    gap:
      9px;

    padding:
      4px 5px 13px;
  }


  .nav-header-icon {

    width:
      29px;

    height:
      29px;

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
      rgba(255,255,255,0.09);

    color:
      rgba(255,255,255,0.72);
  }


  .nav-title {

    font-size:
      9px;

    font-weight:
      700;

    letter-spacing:
      0.14em;

    color:
      rgba(255,255,255,0.65);
  }


  .nav-subtitle {

    margin-top:
      2px;

    font-size:
      8px;

    color:
      rgba(255,255,255,0.25);
  }


  .nav-divider {

    height:
      1px;

    background:
      rgba(255,255,255,0.065);

    margin:
      0 5px 17px;
  }


  .nav-section-label {

    padding:
      0 9px 7px;

    font-size:
      8px;

    font-weight:
      700;

    letter-spacing:
      0.13em;

    color:
      rgba(255,255,255,0.22);
  }


  .nav-links {

    display:
      flex;

    flex-direction:
      column;

    gap:
      2px;
  }


  .nav-link {

    position:
      relative;

    width:
      100%;

    min-height:
      36px;

    display:
      flex;

    align-items:
      center;

    gap:
      9px;

    padding:
      0 9px;

    border-radius:
      7px;

    border:
      1px solid
      transparent;

    background:
      transparent;

    color:
      rgba(255,255,255,0.38);

    text-align:
      left;

    cursor:
      pointer;

    font-family:
      inherit;

    font-size:
      10.5px;

    transition:
      all 0.15s ease;
  }


  .nav-link:hover {

    color:
      rgba(255,255,255,0.82);

    background:
      rgba(255,255,255,0.035);
  }


  .nav-link.active {

    color:
      #ffffff;

    background:
      rgba(255,255,255,0.065);

    border-color:
      rgba(255,255,255,0.09);

    box-shadow:
      inset 0 1px 0
      rgba(255,255,255,0.025);
  }


  .nav-link-icon {

    width:
      24px;

    height:
      24px;

    display:
      flex;

    align-items:
      center;

    justify-content:
      center;

    flex-shrink:
      0;

    border-radius:
      6px;

    color:
      rgba(255,255,255,0.28);

    transition:
      all 0.15s ease;
  }


  .nav-link.active
  .nav-link-icon {

    color:
      #ffffff;

    background:
      rgba(255,255,255,0.075);
  }


  .nav-link-text {

    flex:
      1;
  }


  .active-marker {

    width:
      2px;

    height:
      14px;

    border-radius:
      3px;

    background:
      #ffffff;

    box-shadow:
      0 0 8px
      rgba(255,255,255,0.35);
  }


  /* =========================================================
     NAV FOOTER
     ========================================================= */

  .nav-footer {

    margin-top:
      auto;

    padding:
      0 6px;
  }


  .footer-line {

    height:
      1px;

    background:
      rgba(255,255,255,0.06);

    margin-bottom:
      11px;
  }


  .footer-status {

    display:
      flex;

    align-items:
      center;

    gap:
      6px;

    font-size:
      7.5px;

    letter-spacing:
      0.08em;

    color:
      rgba(255,255,255,0.20);
  }


  .status-dot {

    width:
      5px;

    height:
      5px;

    border-radius:
      50%;

    background:
      rgba(255,255,255,0.55);

    box-shadow:
      0 0 7px
      rgba(255,255,255,0.30);
  }


  .footer-version {

    display:
      block;

    margin-top:
      5px;

    font-family:
      var(--font-mono, monospace);

    font-size:
      7.5px;

    color:
      rgba(255,255,255,0.14);
  }


  /* =========================================================
     CONTENT
     ========================================================= */

  .docs-content {

    flex:
      1;

    min-width:
      0;

    height:
      100%;

    overflow-y:
      auto;

    box-sizing:
      border-box;

    padding:
      54px clamp(30px, 6vw, 90px) 90px;
    
    scrollbar-width:
      thin;

    scrollbar-color:
      rgba(255,255,255,0.12)
      transparent;
  }


  .docs-content::-webkit-scrollbar {

    width:
      5px;
  }


  .docs-content::-webkit-scrollbar-track {

    background:
      transparent;
  }


  .docs-content::-webkit-scrollbar-thumb {

    background:
      rgba(255,255,255,0.12);

    border-radius:
      10px;
  }


  /* =========================================================
     SECTION
     ========================================================= */

  .doc-sec {

    width:
      100%;

    max-width:
      900px;

    display:
      flex;

    flex-direction:
      column;

    gap:
      16px;
  }


  .section-kicker {

    margin-bottom:
      -4px;

    font-family:
      var(--font-mono, monospace);

    font-size:
      8.5px;

    letter-spacing:
      0.14em;

    color:
      rgba(255,255,255,0.27);
  }


  h1 {

    margin:
      0;

    font-size:
      clamp(28px, 3vw, 39px);

    line-height:
      1.08;

    letter-spacing:
      -0.045em;

    font-weight:
      650;

    color:
      #ffffff;
  }


  h1 span {

    color:
      rgba(255,255,255,0.40);

    font-weight:
      450;
  }


  h3 {

    margin:
      8px 0 0;

    font-size:
      15px;

    line-height:
      1.3;

    font-weight:
      650;

    color:
      #ffffff;
  }


  h3 span {

    color:
      rgba(255,255,255,0.42);

    font-weight:
      450;
  }


  p {

    margin:
      0;

    max-width:
      760px;

    font-size:
      12.5px;

    line-height:
      1.75;

    color:
      rgba(255,255,255,0.43);
  }


  p.lead {

    max-width:
      700px;

    font-size:
      14px;

    line-height:
      1.7;

    color:
      rgba(255,255,255,0.67);
  }


  .content-divider {

    width:
      100%;

    height:
      1px;

    margin:
      9px 0 3px;

    background:
      rgba(255,255,255,0.07);
  }


  /* =========================================================
     LIST
     ========================================================= */

  .feature-list {

    margin:
      4px 0 0;

    padding:
      0;

    list-style:
      none;

    display:
      flex;

    flex-direction:
      column;

    gap:
      5px;
  }


  .feature-list li {

    position:
      relative;

    display:
      flex;

    gap:
      5px;

    padding:
      9px 11px;

    border-radius:
      7px;

    background:
      rgba(255,255,255,0.022);

    border:
      1px solid
      rgba(255,255,255,0.055);

    font-size:
      11.5px;

    line-height:
      1.55;

    color:
      rgba(255,255,255,0.40);
  }


  .feature-list li::before {

    content:
      "";

    width:
      3px;

    height:
      3px;

    flex-shrink:
      0;

    margin-top:
      7px;

    border-radius:
      50%;

    background:
      rgba(255,255,255,0.55);
  }


  .feature-list strong {

    color:
      rgba(255,255,255,0.82);
  }


  /* =========================================================
     ARCHITECTURE
     ========================================================= */

  .principle-card {

    display:
      flex;

    align-items:
      flex-start;

    gap:
      13px;

    padding:
      15px 17px;

    margin:
      3px 0 6px;

    border-radius:
      9px;

    background:
      rgba(255,255,255,0.035);

    border:
      1px solid
      rgba(255,255,255,0.09);

    box-shadow:
      inset 0 1px 0
      rgba(255,255,255,0.035);
  }


  .quote-mark {

    font-size:
      28px;

    line-height:
      0.8;

    color:
      rgba(255,255,255,0.24);
  }


  .principle-card strong {

    color:
      #ffffff;

    font-size:
      12.5px;
  }


  .principle-card span {

    color:
      rgba(255,255,255,0.48);

    font-size:
      12.5px;
  }


  .architecture-flow {

    display:
      flex;

    flex-direction:
      column;

    align-items:
      center;

    margin:
      5px 0 5px;

    padding:
      18px;

    border:
      1px solid
      rgba(255,255,255,0.065);

    border-radius:
      10px;

    background:
      rgba(255,255,255,0.018);
  }


  .flow-node {

    width:
      min(100%, 430px);

    box-sizing:
      border-box;

    padding:
      10px 14px;

    text-align:
      center;

    border-radius:
      7px;

    background:
      rgba(255,255,255,0.035);

    border:
      1px solid
      rgba(255,255,255,0.09);

    color:
      rgba(255,255,255,0.70);

    font-family:
      var(--font-mono, monospace);

    font-size:
      9.5px;

    line-height:
      1.35;
  }


  .flow-node.primary,
  .flow-node.final {

    background:
      rgba(255,255,255,0.08);

    border-color:
      rgba(255,255,255,0.17);

    color:
      #ffffff;
  }


  .flow-node small {

    display:
      block;

    margin-top:
      3px;

    font-size:
      7.5px;

    color:
      rgba(255,255,255,0.28);
  }


  .flow-arrow {

    height:
      22px;

    display:
      flex;

    align-items:
      center;

    color:
      rgba(255,255,255,0.25);

    font-family:
      var(--font-mono, monospace);

    font-size:
      11px;
  }


  /* =========================================================
     TABLE
     ========================================================= */

  .table-wrap {

    width:
      100%;

    overflow-x:
      auto;

    margin-top:
      7px;

    border:
      1px solid
      rgba(255,255,255,0.075);

    border-radius:
      9px;

    background:
      rgba(255,255,255,0.018);
  }


  table {

    width:
      100%;

    border-collapse:
      collapse;

    min-width:
      720px;

    font-size:
      10.5px;
  }


  th {

    padding:
      11px 13px;

    text-align:
      left;

    background:
      rgba(255,255,255,0.045);

    border-bottom:
      1px solid
      rgba(255,255,255,0.08);

    color:
      rgba(255,255,255,0.37);

    font-size:
      8px;

    letter-spacing:
      0.08em;

    font-weight:
      700;
  }


  td {

    padding:
      12px 13px;

    border-bottom:
      1px solid
      rgba(255,255,255,0.045);

    color:
      rgba(255,255,255,0.40);

    line-height:
      1.45;
  }


  tr:last-child td {

    border-bottom:
      0;
  }


  td strong {

    color:
      rgba(255,255,255,0.80);
  }


  /* =========================================================
     CODE
     ========================================================= */

  code {

    padding:
      2px 5px;

    border-radius:
      4px;

    background:
      rgba(255,255,255,0.055);

    color:
      rgba(255,255,255,0.74);

    font-family:
      var(--font-mono, "SF Mono", monospace);

    font-size:
      9.5px;
  }


  /* =========================================================
     DATASET GRID
     ========================================================= */

  .dataset-grid {

    display:
      grid;

    grid-template-columns:
      repeat(2, minmax(0, 1fr));

    gap:
      7px;

    margin-top:
      6px;
  }


  .dataset-card {

    position:
      relative;

    display:
      flex;

    flex-direction:
      column;

    min-height:
      125px;

    padding:
      14px;

    box-sizing:
      border-box;

    border-radius:
      9px;

    background:
      rgba(255,255,255,0.022);

    border:
      1px solid
      rgba(255,255,255,0.065);

    overflow:
      hidden;

    transition:
      all 0.15s ease;
  }


  .dataset-card:hover {

    background:
      rgba(255,255,255,0.042);

    border-color:
      rgba(255,255,255,0.12);
  }


  .dataset-number {

    position:
      absolute;

    top:
      12px;

    right:
      13px;

    font-family:
      var(--font-mono, monospace);

    font-size:
      8px;

    color:
      rgba(255,255,255,0.18);
  }


  .dataset-card strong {

    font-size:
      12.5px;

    font-weight:
      650;

    color:
      rgba(255,255,255,0.85);
  }


  .dataset-org {

    margin-top:
      3px;

    font-family:
      var(--font-mono, monospace);

    font-size:
      7px;

    letter-spacing:
      0.1em;

    color:
      rgba(255,255,255,0.24);
  }


  .dataset-card p {

    margin-top:
      auto;

    padding-top:
      10px;

    font-size:
      9.5px;

    line-height:
      1.5;

    color:
      rgba(255,255,255,0.35);
  }


  /* =========================================================
     VISUALIZATION LIST
     ========================================================= */

  .visual-list {

    display:
      flex;

    flex-direction:
      column;

    gap:
      5px;

    margin-top:
      7px;
  }


  .visual-item {

    display:
      grid;

    grid-template-columns:
      40px 1fr;

    gap:
      13px;

    padding:
      14px;

    border-radius:
      8px;

    background:
      rgba(255,255,255,0.022);

    border:
      1px solid
      rgba(255,255,255,0.06);
  }


  .visual-index {

    font-family:
      var(--font-mono, monospace);

    font-size:
      9px;

    color:
      rgba(255,255,255,0.23);
  }


  .visual-item strong {

    font-size:
      12px;

    color:
      rgba(255,255,255,0.82);
  }


  .visual-item p {

    margin-top:
      4px;

    font-size:
      10.5px;

    line-height:
      1.55;
  }


  /* =========================================================
     API
     ========================================================= */

  .endpoint-list {

    margin-top:
      7px;

    border:
      1px solid
      rgba(255,255,255,0.065);

    border-radius:
      9px;

    overflow:
      hidden;
  }


  .endpoint-row {

    display:
      grid;

    grid-template-columns:
      42px minmax(180px, 1fr) 1.4fr;

    align-items:
      center;

    gap:
      10px;

    min-height:
      39px;

    padding:
      0 12px;

    border-bottom:
      1px solid
      rgba(255,255,255,0.045);

    background:
      rgba(255,255,255,0.018);
  }


  .endpoint-row:last-child {

    border-bottom:
      0;
  }


  .endpoint-row:hover {

    background:
      rgba(255,255,255,0.035);
  }


  .endpoint-row code {

    padding:
      0;

    background:
      transparent;

    font-size:
      8px;

    font-weight:
      700;

    color:
      rgba(255,255,255,0.45);
  }


  .endpoint-row span {

    font-family:
      var(--font-mono, monospace);

    font-size:
      9px;

    color:
      rgba(255,255,255,0.70);
  }


  .endpoint-row small {

    font-size:
      9px;

    color:
      rgba(255,255,255,0.28);
  }


  .endpoint-row.websocket {

    background:
      rgba(255,255,255,0.04);
  }


  /* =========================================================
     TERMINAL
     ========================================================= */

  .terminal-window {

    margin-top:
      7px;

    overflow:
      hidden;

    border-radius:
      9px;

    border:
      1px solid
      rgba(255,255,255,0.09);

    background:
      #020202;

    box-shadow:
      0 15px 35px
      rgba(0,0,0,0.35);
  }


  .terminal-header {

    height:
      32px;

    display:
      flex;

    align-items:
      center;

    gap:
      10px;

    padding:
      0 12px;

    background:
      rgba(255,255,255,0.035);

    border-bottom:
      1px solid
      rgba(255,255,255,0.065);

    font-family:
      var(--font-mono, monospace);

    font-size:
      8px;

    color:
      rgba(255,255,255,0.27);
  }


  .terminal-dots {

    display:
      flex;

    gap:
      4px;
  }


  .terminal-dots span {

    width:
      5px;

    height:
      5px;

    border-radius:
      50%;

    background:
      rgba(255,255,255,0.18);
  }


  pre {

    margin:
      0;

    padding:
      18px;

    overflow-x:
      auto;

    font-family:
      var(--font-mono, "SF Mono", monospace);

    font-size:
      10px;

    line-height:
      1.8;

    color:
      rgba(255,255,255,0.72);
  }


  .comment {

    color:
      rgba(255,255,255,0.22);
  }


  /* =========================================================
     AUDIT
     ========================================================= */

  .audit-timeline {

    position:
      relative;

    display:
      flex;

    flex-direction:
      column;

    margin-top:
      8px;
  }


  .audit-timeline::before {

    content:
      "";

    position:
      absolute;

    left:
      15px;

    top:
      17px;

    bottom:
      17px;

    width:
      1px;

    background:
      rgba(255,255,255,0.09);
  }


  .audit-step {

    position:
      relative;

    display:
      grid;

    grid-template-columns:
      32px 1fr;

    gap:
      13px;

    padding:
      9px 0;
  }


  .audit-marker {

    position:
      relative;

    z-index:
      1;

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
      50%;

    background:
      #080808;

    border:
      1px solid
      rgba(255,255,255,0.15);

    font-family:
      var(--font-mono, monospace);

    font-size:
      7px;

    color:
      rgba(255,255,255,0.45);
  }


  .audit-step.final
  .audit-marker {

    background:
      #ffffff;

    color:
      #000000;

    border-color:
      #ffffff;
  }


  .audit-content {

    padding:
      2px 0 8px;
  }


  .audit-content strong {

    font-size:
      10.5px;

    letter-spacing:
      0.025em;

    color:
      rgba(255,255,255,0.78);
  }


  .audit-content p {

    margin-top:
      3px;

    font-size:
      10px;

    line-height:
      1.5;

    color:
      rgba(255,255,255,0.32);
  }


  /* =========================================================
     RESPONSIVE
     ========================================================= */

  @media (max-width: 900px) {

    .docs-nav {

      width:
        205px;
    }

    .docs-content {

      padding:
        40px 30px 70px;
    }

    .dataset-grid {

      grid-template-columns:
        1fr;
    }

  }


  @media (max-width: 680px) {

    .docs-container {

      height:
        calc(100vh - 60px);
    }


    .docs-nav {

      width:
        58px;

      padding:
        14px 7px;
    }


    .nav-header {

      justify-content:
        center;

      padding:
        3px 0 12px;
    }


    .nav-header > div:last-child,
    .nav-section-label,
    .nav-link-text,
    .nav-footer {

      display:
        none;
    }


    .nav-divider {

      margin:
        0 4px 10px;
    }


    .nav-link {

      justify-content:
        center;

      padding:
        0;
    }


    .nav-link-icon {

      width:
        29px;

      height:
        29px;
    }


    .active-marker {

      position:
        absolute;

      right:
        2px;
    }


    .docs-content {

      padding:
        30px 18px 60px;
    }


    h1 {

      font-size:
        27px;
    }


    .endpoint-row {

      grid-template-columns:
        38px 1fr;

      padding:
        8px 10px;

      gap:
        7px;
    }


    .endpoint-row small {

      grid-column:
        2;
    }

  }

</style>