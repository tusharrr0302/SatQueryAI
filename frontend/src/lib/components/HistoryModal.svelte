<script lang="ts">
  import { onMount, createEventDispatcher } from 'svelte';

  import {
    activeSidebarTab,
    conversationId,
    messages,
    currentResult,
    globeLocation,
    appViewState,
    type ChatMessage,
  } from '../stores';

  import { fetchConversations } from '../api';

  import {
    Clock,
    X,
    ArrowUpRight,
    Database,
    Cpu,
    MapPin,
    Activity
  } from 'lucide-svelte';


  const dispatch = createEventDispatcher<{
    selectConversation: any;
  }>();


  let conversations: any[] = [];
  let isLoading = true;


  // =========================================================
  // FALLBACK CONVERSATIONS
  // =========================================================

  const fallbackConversations = [
    {
      id: 'conv_delhi_decadal',
      title: 'Delhi Urban Growth',
      query: 'Show me how Delhi changed over the last 10 years',
      last_active: '2026-09-15T10:00:00Z',
      model_name: 'Prithvi-EO-2.0',
      dataset_ids: ['Sentinel-2', 'Sentinel-1'],
      aoi_name: 'Delhi, India',
      lat: 28.6139,
      lon: 77.2090,
      metric_badge: '+134.2 km² (21.4%)',
    },
    {
      id: 'conv_amazon',
      title: 'Amazon Deforestation',
      query: 'Show me deforestation in the Amazon',
      last_active: '2026-09-15T09:30:00Z',
      model_name: 'TerraFM',
      dataset_ids: ['Sentinel-1', 'Sentinel-2'],
      aoi_name: 'Amazon Basin, Brazil',
      lat: -3.4653,
      lon: -62.2159,
      metric_badge: '-312.4 km² loss',
    },
    {
      id: 'conv_punjab',
      title: 'Punjab Crop Health',
      query: 'Analyze crop health in Punjab',
      last_active: '2026-09-15T09:00:00Z',
      model_name: 'Prithvi-EO-2.0',
      dataset_ids: ['Sentinel-2'],
      aoi_name: 'Punjab Agricultural Belt',
      lat: 31.1471,
      lon: 75.3412,
      metric_badge: 'Peak NDVI 0.74',
    },
    {
      id: 'conv_derna',
      title: 'Derna Flood Analysis',
      query: 'Show the flooding caused by Storm Daniel in Derna',
      last_active: '2026-09-15T08:30:00Z',
      model_name: 'TerraFM',
      dataset_ids: ['Sentinel-1'],
      aoi_name: 'Derna, Libya',
      lat: 32.7667,
      lon: 22.6367,
      metric_badge: '4.6 km² inundated',
    },
    {
      id: 'conv_delhi_veg',
      title: 'Delhi Vegetation',
      query: 'Show me the vegetation change in Delhi over the last year',
      last_active: '2026-09-15T08:00:00Z',
      model_name: 'Prithvi-EO-2.0',
      dataset_ids: ['Sentinel-2'],
      aoi_name: 'Delhi, India',
      lat: 28.6139,
      lon: 77.2090,
      metric_badge: '+0.14 NDVI gain',
    },
  ];


  // =========================================================
  // LOAD HISTORY
  // =========================================================

  onMount(async () => {

    try {

      const res = await fetchConversations();

      if (
        res &&
        res.conversations &&
        res.conversations.length
      ) {

        conversations =
          res.conversations;

      } else {

        conversations =
          fallbackConversations;
      }

    } catch (e) {

      console.warn(
        'Using fallback history items:',
        e
      );

      conversations =
        fallbackConversations;

    } finally {

      isLoading = false;
    }
  });


  // =========================================================
  // CLOSE
  // =========================================================

  function closeDrawer() {

    $activeSidebarTab =
      'chat';
  }


  // =========================================================
  // SELECT CONVERSATION
  // =========================================================

  function handleSelect(conv: any) {

    $conversationId =
      conv.id;


    if (conv.last_result) {

      $currentResult =
        conv.last_result;
    }


    // Restore existing messages

    if (
      conv.messages &&
      conv.messages.length
    ) {

      $messages =
        conv.messages;

    } else {

      // Reconstruct clean message thread

      $messages = [
        {
          id:
            `msg_${conv.id}_u`,

          role:
            'user',

          content:
            conv.query ||
            conv.title,

          timestamp:
            conv.last_active ||
            new Date().toISOString(),
        },

        {
          id:
            `msg_${conv.id}_a`,

          role:
            'assistant',

          content:
            conv.last_result?.key_finding ||
            `${conv.title} analysis loaded.`,

          result:
            conv.last_result,

          timestamp:
            conv.last_active ||
            new Date().toISOString(),
        }
      ];
    }


    // =====================================================
    // RESTORE GLOBE CAMERA
    // =====================================================

    const lat =
      conv.last_result?.aoi?.center?.latitude ??
      conv.lat ??
      28.6139;

    const lon =
      conv.last_result?.aoi?.center?.longitude ??
      conv.lon ??
      77.2090;

    const name =
      conv.last_result?.aoi?.name ??
      conv.aoi_name ??
      'Target AOI';

    const area =
      conv.last_result?.aoi?.area_km2 ??
      1500;

    const polygon =
      conv.last_result?.aoi?.polygon ??
      [];


    globeLocation.update((g) => ({

      ...g,

      latitude:
        lat,

      longitude:
        lon,

      name:
        name,

      area_km2:
        area,

      polygon:
        polygon,

      flyTrigger:
        g.flyTrigger + 1,

    }));


    // =====================================================
    // SWITCH BACK TO ANALYSIS
    // =====================================================

    $appViewState =
      'analysis';

    $activeSidebarTab =
      'chat';


    dispatch(
      'selectConversation',
      conv
    );
  }


  // =========================================================
  // DATE
  // =========================================================

  function formatDate(iso: string) {

    if (!iso) {
      return 'Recent';
    }


    try {

      const d =
        new Date(iso);

      return d.toLocaleDateString(
        'en-US',
        {
          month: 'short',
          day: 'numeric',
          hour: '2-digit',
          minute: '2-digit'
        }
      );

    } catch {

      return 'Recent';
    }
  }
</script>


<!-- =========================================================
     HISTORY OVERLAY
     ========================================================= -->

<div
  class="history-backdrop"
  on:click={closeDrawer}
  role="button"
  tabindex="0"
>


  <!-- =======================================================
       DRAWER
       ======================================================= -->

  <div
    class="history-drawer"
    on:click|stopPropagation
    role="region"
    tabindex="-1"
  >


    <!-- =====================================================
         HEADER
         ===================================================== -->

    <div class="drawer-header">

      <div class="header-left">


        <div class="header-icon">

          <Clock
            size={16}
            strokeWidth={1.7}
          />

        </div>


        <div class="header-titles">

          <h2 class="drawer-title">
            Investigation History
          </h2>

          <span class="drawer-sub">
            Saved Earth observation queries
          </span>

        </div>

      </div>


      <button
        class="close-btn"
        on:click={closeDrawer}
        title="Close history"
        aria-label="Close history"
      >

        <X
          size={16}
          strokeWidth={1.8}
        />

      </button>

    </div>


    <!-- =====================================================
         BODY
         ===================================================== -->

    <div class="drawer-body">


      <!-- LOADING -->

      {#if isLoading}

        <div class="loading-state">

          <div class="spinner"></div>

          <span>
            Loading historical queries...
          </span>

        </div>


      <!-- EMPTY -->

      {:else if conversations.length === 0}

        <div class="empty-state">

          <div class="empty-icon">

            <Clock
              size={24}
              strokeWidth={1.5}
            />

          </div>

          <p>
            No recorded investigations yet
          </p>

        </div>


      <!-- RESULTS -->

      {:else}

        <div class="conv-list">

          {#each conversations as conv (conv.id)}

            {@const res = conv.last_result}

            {@const model =
              res?.provenance?.model_name ||
              conv.model_name ||
              'Prithvi-EO-2.0'}

            {@const datasets =
              res?.provenance?.dataset_ids ||
              conv.dataset_ids ||
              ['Sentinel-2']}

            {@const aoi =
              res?.aoi?.name ||
              conv.aoi_name ||
              'Global'}

            {@const metric =
              conv.metric_badge ||
              (
                res?.metrics?.[0]
                  ? `${res.metrics[0].label}: ${res.metrics[0].value}`
                  : null
              )}


            <!-- =================================================
                 CONVERSATION CARD
                 ================================================= -->

            <button
              class="conv-card"
              on:click={() => handleSelect(conv)}
              aria-label={`Open ${conv.title}`}
            >


              <!-- CARD HEADER -->

              <div class="card-top">

                <span class="conv-title">
                  {conv.title}
                </span>

                <span class="conv-time">
                  {formatDate(
                    conv.last_active ||
                    conv.created_at
                  )}
                </span>

              </div>


              <!-- QUERY -->

              <p class="conv-query">
                "{conv.query ||
                  conv.messages?.[0]?.content ||
                  conv.title}"
              </p>


              <!-- =================================================
                   METADATA
                   ================================================= -->

              <div class="card-meta">


                <div class="meta-tag">

                  <MapPin
                    size={10}
                    strokeWidth={1.7}
                  />

                  <span>
                    {aoi.split(',')[0]}
                  </span>

                </div>


                <div class="meta-tag">

                  <Cpu
                    size={10}
                    strokeWidth={1.7}
                  />

                  <span>
                    {model}
                  </span>

                </div>


                <div class="meta-tag">

                  <Database
                    size={10}
                    strokeWidth={1.7}
                  />

                  <span>
                    {Array.isArray(datasets)
                      ? datasets.join(' + ')
                      : datasets}
                  </span>

                </div>

              </div>


              <!-- =================================================
                   FOOTER
                   ================================================= -->

              {#if metric}

                <div class="card-footer">


                  <div class="metric-pill">

                    <Activity
                      size={10}
                      strokeWidth={1.7}
                    />

                    <span>
                      {metric}
                    </span>

                  </div>


                  <div class="open-link">

                    <span>
                      Reopen
                    </span>

                    <ArrowUpRight
                      size={12}
                      strokeWidth={1.7}
                    />

                  </div>

                </div>

              {/if}

            </button>

          {/each}

        </div>

      {/if}

    </div>

  </div>

</div>


<style>

  /* =========================================================
     OVERLAY
     ========================================================= */

  .history-backdrop {

    position:
      fixed;

    inset:
      0;

    z-index:
      90;

    display:
      flex;

    justify-content:
      flex-start;

    background:
      rgba(0,0,0,0.72);

    backdrop-filter:
      blur(7px);

    -webkit-backdrop-filter:
      blur(7px);

    animation:
      fadeIn 0.18s ease-out;
  }


  @keyframes fadeIn {

    from {
      opacity:
        0;
    }

    to {
      opacity:
        1;
    }
  }


  /* =========================================================
     DRAWER
     ========================================================= */

  .history-drawer {

    width:
      430px;

    max-width:
      90vw;

    height:
      100%;

    box-sizing:
      border-box;

    display:
      flex;

    flex-direction:
      column;

    background:
      #070707;

    border-right:
      1px solid
      rgba(255,255,255,0.10);

    box-shadow:
      14px 0 40px
      rgba(0,0,0,0.55);

    animation:
      slideIn 0.24s
      cubic-bezier(
        0.16,
        1,
        0.3,
        1
      );

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


  @keyframes slideIn {

    from {
      transform:
        translateX(-100%);
    }

    to {
      transform:
        translateX(0);
    }
  }


  /* =========================================================
     HEADER
     ========================================================= */

  .drawer-header {

    height:
      68px;

    flex-shrink:
      0;

    display:
      flex;

    align-items:
      center;

    justify-content:
      space-between;

    padding:
      0 17px;

    background:
      rgba(255,255,255,0.018);

    border-bottom:
      1px solid
      rgba(255,255,255,0.075);
  }


  .header-left {

    min-width:
      0;

    display:
      flex;

    align-items:
      center;

    gap:
      10px;
  }


  /* =========================================================
     HEADER ICON
     ========================================================= */

  .header-icon {

    width:
      31px;

    height:
      31px;

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
      rgba(255,255,255,0.11);

    color:
      rgba(255,255,255,0.80);

    box-shadow:
      inset 0 1px 0
      rgba(255,255,255,0.045);
  }


  .header-titles {

    min-width:
      0;

    display:
      flex;

    flex-direction:
      column;

    gap:
      3px;
  }


  .drawer-title {

    margin:
      0;

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


  .drawer-sub {

    font-size:
      9.5px;

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

    padding:
      0;

    border-radius:
      8px;

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
      rgba(255,255,255,0.06);

    border-color:
      rgba(255,255,255,0.09);
  }


  /* =========================================================
     BODY
     ========================================================= */

  .drawer-body {

    flex:
      1;

    min-height:
      0;

    overflow-y:
      auto;

    padding:
      15px;

    scrollbar-width:
      thin;

    scrollbar-color:
      rgba(255,255,255,0.12)
      transparent;
  }


  .drawer-body::-webkit-scrollbar {

    width:
      4px;
  }


  .drawer-body::-webkit-scrollbar-track {

    background:
      transparent;
  }


  .drawer-body::-webkit-scrollbar-thumb {

    background:
      rgba(255,255,255,0.12);

    border-radius:
      10px;
  }


  /* =========================================================
     LIST
     ========================================================= */

  .conv-list {

    display:
      flex;

    flex-direction:
      column;

    gap:
      6px;
  }


  /* =========================================================
     CONVERSATION CARD
     ========================================================= */

  .conv-card {

    width:
      100%;

    box-sizing:
      border-box;

    display:
      flex;

    flex-direction:
      column;

    gap:
      9px;

    padding:
      13px 13px 12px;

    text-align:
      left;

    border-radius:
      10px;

    background:
      rgba(255,255,255,0.022);

    border:
      1px solid
      rgba(255,255,255,0.065);

    color:
      #ffffff;

    cursor:
      pointer;

    font-family:
      inherit;

    box-shadow:
      inset 0 1px 0
      rgba(255,255,255,0.018);

    transition:
      background 0.16s ease,
      border-color 0.16s ease,
      transform 0.16s ease,
      box-shadow 0.16s ease;
  }


  .conv-card:hover {

    background:
      rgba(255,255,255,0.045);

    border-color:
      rgba(255,255,255,0.14);

    transform:
      translateY(-1px);

    box-shadow:
      inset 0 1px 0
      rgba(255,255,255,0.035),

      0 6px 18px
      rgba(0,0,0,0.20);
  }


  .conv-card:active {

    transform:
      translateY(0);
  }


  /* =========================================================
     CARD TOP
     ========================================================= */

  .card-top {

    display:
      flex;

    align-items:
      center;

    justify-content:
      space-between;

    gap:
      12px;
  }


  .conv-title {

    min-width:
      0;

    overflow:
      hidden;

    text-overflow:
      ellipsis;

    white-space:
      nowrap;

    font-size:
      12.5px;

    line-height:
      1.25;

    font-weight:
      650;

    color:
      rgba(255,255,255,0.90);
  }


  .conv-time {

    flex-shrink:
      0;

    font-family:
      var(--font-mono, "SF Mono", monospace);

    font-size:
      8.5px;

    color:
      rgba(255,255,255,0.27);

    white-space:
      nowrap;
  }


  /* =========================================================
     QUERY
     ========================================================= */

  .conv-query {

    margin:
      0;

    display:
      -webkit-box;

    -webkit-line-clamp:
      2;

    -webkit-box-orient:
      vertical;

    overflow:
      hidden;

    font-size:
      10.5px;

    line-height:
      1.45;

    color:
      rgba(255,255,255,0.38);
  }


  /* =========================================================
     METADATA
     ========================================================= */

  .card-meta {

    display:
      flex;

    align-items:
      center;

    gap:
      5px;

    flex-wrap:
      wrap;

    padding-top:
      1px;
  }


  .meta-tag {

    max-width:
      100%;

    display:
      inline-flex;

    align-items:
      center;

    gap:
      4px;

    padding:
      4px 6px;

    border-radius:
      5px;

    background:
      rgba(255,255,255,0.035);

    border:
      1px solid
      rgba(255,255,255,0.055);

    color:
      rgba(255,255,255,0.43);

    font-size:
      8.5px;

    line-height:
      1;

    white-space:
      nowrap;
  }


  .meta-tag svg {

    flex-shrink:
      0;

    color:
      rgba(255,255,255,0.35);
  }


  .meta-tag span {

    overflow:
      hidden;

    text-overflow:
      ellipsis;

    max-width:
      150px;
  }


  /* =========================================================
     CARD FOOTER
     ========================================================= */

  .card-footer {

    display:
      flex;

    align-items:
      center;

    justify-content:
      space-between;

    gap:
      10px;

    padding-top:
      9px;

    border-top:
      1px solid
      rgba(255,255,255,0.055);
  }


  /* =========================================================
     METRIC
     ========================================================= */

  .metric-pill {

    min-width:
      0;

    display:
      inline-flex;

    align-items:
      center;

    gap:
      5px;

    padding:
      4px 7px;

    border-radius:
      5px;

    background:
      rgba(255,255,255,0.055);

    border:
      1px solid
      rgba(255,255,255,0.08);

    color:
      rgba(255,255,255,0.72);

    font-size:
      9px;

    font-weight:
      600;

    white-space:
      nowrap;
  }


  .metric-pill svg {

    color:
      rgba(255,255,255,0.48);

    flex-shrink:
      0;
  }


  /* =========================================================
     REOPEN
     ========================================================= */

  .open-link {

    display:
      flex;

    align-items:
      center;

    gap:
      3px;

    flex-shrink:
      0;

    color:
      rgba(255,255,255,0.30);

    font-size:
      9.5px;

    font-weight:
      550;

    transition:
      color 0.15s ease;
  }


  .conv-card:hover
  .open-link {

    color:
      rgba(255,255,255,0.82);
  }


  /* =========================================================
     LOADING / EMPTY
     ========================================================= */

  .loading-state,
  .empty-state {

    height:
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
      rgba(255,255,255,0.28);

    font-size:
      10.5px;

    text-align:
      center;
  }


  .empty-state p {

    margin:
      0;
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
      rgba(255,255,255,0.035);

    border:
      1px solid
      rgba(255,255,255,0.07);

    color:
      rgba(255,255,255,0.28);
  }


  /* =========================================================
     SPINNER
     ========================================================= */

  .spinner {

    width:
      18px;

    height:
      18px;

    border:
      1.8px solid
      rgba(255,255,255,0.12);

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
     FOCUS
     ========================================================= */

  .conv-card:focus-visible,
  .close-btn:focus-visible {

    outline:
      1px solid
      rgba(255,255,255,0.55);

    outline-offset:
      2px;
  }


  /* =========================================================
     MOBILE
     ========================================================= */

  @media (max-width: 600px) {

    .history-drawer {

      width:
        min(430px, 92vw);

      max-width:
        92vw;
    }


    .drawer-header {

      padding:
        0 14px;
    }


    .drawer-body {

      padding:
        12px;
    }
  }


  /* =========================================================
     SHORT SCREENS
     ========================================================= */

  @media (max-height: 700px) {

    .drawer-header {

      height:
        60px;
    }


    .drawer-body {

      padding:
        11px 13px;
    }


    .conv-card {

      padding:
        10px 11px;
    }


    .conv-list {

      gap:
        5px;
    }
  }

</style>