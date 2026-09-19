<script lang="ts">
  import { onMount } from 'svelte';
  import {
    activeNav,
    activeSidebarTab,
    isLandingPage,
    appViewState,
    type ViewState,
    messages,
    currentResult,
    isAnalyzing,
    globeLocation,
    conversationId,
  } from './lib/stores';
  import { sendChatQuery, initWebSocket } from './lib/api';

  // Components
  import Navbar from './lib/components/Navbar.svelte';
  import Sidebar from './lib/components/Sidebar.svelte';
  import HeroLanding from './lib/components/HeroLanding.svelte';
  import CesiumGlobe from './lib/components/CesiumGlobe.svelte';
  import ProcessingPanel from './lib/components/ProcessingPanel.svelte';
  import ScientificVisPanel from './lib/components/ScientificVisPanel.svelte';
  import ChatPanel from './lib/components/ChatPanel.svelte';
  import LayersModal from './lib/components/LayersModal.svelte';
  import InvestigationsModal from './lib/components/InvestigationsModal.svelte';
  import AuditTraceModal from './lib/components/AuditTraceModal.svelte';
  import SettingsModal from './lib/components/SettingsModal.svelte';
  import DatasetsPage from './lib/components/DatasetsPage.svelte';
  import UseCasesPage from './lib/components/UseCasesPage.svelte';
  import DocsPage from './lib/components/DocsPage.svelte';
  import HistoryModal from './lib/components/HistoryModal.svelte';
  import { Crosshair } from 'lucide-svelte';

  let viewState: ViewState = 'landing';
  let submittedQuery = '';
  let currentProcessingStep = 1;
  let processingError = '';
  let cesiumGlobeComponent: any;

  // Keep stores synchronized
  $: $appViewState = viewState;
  $: $isLandingPage = viewState === 'landing';

  onMount(() => {
    // Initialize WebSocket for live backend telemetry
    initWebSocket((event, data) => {
      console.log('WS Event received:', event, data);
      if (event === 'planning') {
        currentProcessingStep = 1;
      } else if (event === 'aoi_resolving') {
        currentProcessingStep = 1;
        if (data?.name) {
          globeLocation.update((g) => ({ ...g, name: `Resolving ${data.name}...` }));
        }
      } else if (event === 'analysis_started') {
        currentProcessingStep = 3;
      } else if (event === 'imagery_started') {
        currentProcessingStep = 4;
      } else if (event === 'scenario_matched' || event === 'gpt_started') {
        currentProcessingStep = 2;
      } else if (event === 'tool_started') {
        currentProcessingStep = 3;
      } else if (event === 'globe_action') {
        currentProcessingStep = 4;
        if (data.latitude && data.longitude) {
          globeLocation.update((g) => ({
            ...g,
            latitude: data.latitude,
            longitude: data.longitude,
            name: data.name || g.name,
            flyTrigger: g.flyTrigger + 1,
          }));
        }
      } else if (event === 'visualization_created') {
        currentProcessingStep = 5;
      } else if (event === 'completed') {
        currentProcessingStep = 6;
      }
    });
  });

  async function handleLandingQuery(query: string) {
    submittedQuery = query;
    viewState = 'processing';
    $isAnalyzing = true;
    currentProcessingStep = 1;
    processingError = '';
    globeLocation.update((g) => ({ ...g, latitude: 0, longitude: 0, name: 'Resolving AOI...', area_km2: 0, bbox: [], polygon: [], flyTrigger: g.flyTrigger + 1 }));
    $activeNav = 'home';
    $activeSidebarTab = 'chat';

    try {
      // Execute real backend query (coordinates driven dynamically from backend response)
      const res = await sendChatQuery(query, $conversationId);

      currentProcessingStep = 6;

      if (res.result) {
        $currentResult = res.result;
        $messages = [res.user_message, res.assistant_message];
        $conversationId = res.conversation_id;
        localStorage.setItem('sq_conv_id', res.conversation_id);

        if (res.globe_action) {
          globeLocation.update((g) => ({
            ...g,
            latitude: res.globe_action.latitude,
            longitude: res.globe_action.longitude,
            name: res.globe_action.name || g.name,
            area_km2: res.globe_action.area_km2 || g.area_km2,
            polygon: res.globe_action.polygon || g.polygon,
            flyTrigger: g.flyTrigger + 1,
          }));
        } else if (res.result.aoi?.center) {
          globeLocation.update((g) => ({
            ...g,
            latitude: res.result.aoi.center.latitude,
            longitude: res.result.aoi.center.longitude,
            name: res.result.aoi.name || g.name,
            area_km2: res.result.aoi.area_km2 || g.area_km2,
            polygon: res.result.aoi.polygon || g.polygon,
            flyTrigger: g.flyTrigger + 1,
          }));
        }
      }

      // Smooth brief transition to Analysis workspace
      await new Promise((r) => setTimeout(r, 450));
      viewState = 'analysis';
    } catch (err) {
      console.error('Landing query execution error:', err);
      processingError = err instanceof Error ? err.message : 'Live analysis failed.';
      currentProcessingStep = 0;
      globeLocation.update((g) => ({ ...g, name: 'AOI unavailable', area_km2: 0, bbox: [], polygon: [] }));
    } finally {
      $isAnalyzing = false;
    }
  }

  async function handleFollowupQuery(query: string) {
    $isAnalyzing = true;
    try {
      const res = await sendChatQuery(query, $conversationId);
      if (res.result) {
        $currentResult = res.result;
        $messages = [...$messages, res.user_message, res.assistant_message];
        $conversationId = res.conversation_id;
        localStorage.setItem('sq_conv_id', res.conversation_id);

        if (res.globe_action) {
          globeLocation.update((g) => ({
            ...g,
            latitude: res.globe_action.latitude,
            longitude: res.globe_action.longitude,
            name: res.globe_action.name || g.name,
            area_km2: res.globe_action.area_km2 || g.area_km2,
            polygon: res.globe_action.polygon || g.polygon,
            flyTrigger: g.flyTrigger + 1,
          }));
        } else if (res.result.aoi?.center) {
          globeLocation.update((g) => ({
            ...g,
            latitude: res.result.aoi.center.latitude,
            longitude: res.result.aoi.center.longitude,
            name: res.result.aoi.name || g.name,
            area_km2: res.result.aoi.area_km2 || g.area_km2,
            polygon: res.result.aoi.polygon || g.polygon,
            flyTrigger: g.flyTrigger + 1,
          }));
        }
      }
    } catch (err) {
      console.error('Follow-up query error:', err);
      processingError = err instanceof Error ? err.message : 'Live analysis failed.';
      globeLocation.update((g) => ({ ...g, name: 'AOI unavailable', area_km2: 0, bbox: [], polygon: [] }));
    } finally {
      $isAnalyzing = false;
    }
  }

  function handleNewChat() {
    $conversationId = '';
    localStorage.removeItem('sq_conv_id');
    $messages = [];
    $currentResult = null;
    submittedQuery = '';
    processingError = '';
    viewState = 'landing';
    $activeNav = 'home';
    $activeSidebarTab = 'chat';
    cesiumGlobeComponent?.resetToGlobalView();
  }

  function handleNavHome() {
    handleNewChat();
  }

  function handleActionClick(action: string) {
    if (action === 'aoi') {
      cesiumGlobeComponent?.flyTo($globeLocation.latitude, $globeLocation.longitude, 180000);
    } else if (action === 'compare') {
      handleFollowupQuery('Compare urban growth in Delhi with Shenzhen');
    }
  }
</script>

<div class="app-root space-stars">
  <!-- Top Navigation -->
  <Navbar on:navHome={handleNavHome} />

  <!-- Workspace Body -->
  <div class="workspace-body">
    <!-- Left Navigation Rail: visible in processing and analysis -->
    {#if viewState !== 'landing' && $activeNav === 'home'}
      <Sidebar on:newChat={handleNewChat} />
    {/if}

    <!-- Drawers -->
    {#if $activeSidebarTab === 'layers' && viewState !== 'landing' && $activeNav === 'home'}
      <LayersModal />
    {/if}
    {#if $activeSidebarTab === 'investigations' && viewState !== 'landing' && $activeNav === 'home'}
      <InvestigationsModal />
    {/if}
    {#if $activeSidebarTab === 'history' && viewState !== 'landing' && $activeNav === 'home'}
      <HistoryModal />
    {/if}

    <!-- Main Content Canvas -->
    <main class="main-content-canvas" class:is-landing={viewState === 'landing'}>
      {#if $activeNav === 'datasets'}
        <DatasetsPage />
      {:else if $activeNav === 'use-cases'}
        <UseCasesPage on:launchQuery={(e) => handleLandingQuery(e.detail)} />
      {:else if $activeNav === 'docs'}
        <DocsPage />
      {:else}
        <!-- Persistent Interactive Earth Canvas -->
        <div class="split-workspace-grid" class:is-landing={viewState === 'landing'}>
          <!-- LEFT COLUMN: Contains the persistent Cesium Globe, AOI info bar, Scientific Vis -->
          <div class="left-vis-column" class:is-landing={viewState === 'landing'}>
            <!-- Single Cesium Globe Instance (NEVER destroyed across states) -->
            <div class="globe-tile-box" class:is-landing={viewState === 'landing'}>
              <CesiumGlobe bind:this={cesiumGlobeComponent} {viewState} />
            </div>

            {#if viewState === 'analysis'}
              <!-- AOI Information Strip -->
              <div class="aoi-info-bar">
                <div class="aoi-left">
                  <div class="aoi-pulse-indicator"></div>
                  <div class="aoi-text">
                    <span class="aoi-title">{$globeLocation.name}</span>
                    <span class="aoi-coords">
                      {Math.abs($globeLocation.latitude).toFixed(2)}° {$globeLocation.latitude >= 0 ? 'N' : 'S'}, 
                      {Math.abs($globeLocation.longitude).toFixed(2)}° {$globeLocation.longitude >= 0 ? 'E' : 'W'}
                    </span>
                  </div>
                </div>
                <div class="aoi-right">
                  <div class="aoi-stat">
                    <span class="stat-lbl">AOI EXTENT</span>
                    <span class="stat-val">{Math.round($globeLocation.area_km2).toLocaleString()} km²</span>
                  </div>
                  <button
                    class="aoi-recenter-btn"
                    on:click={() => cesiumGlobeComponent?.flyTo($globeLocation.latitude, $globeLocation.longitude, 350000)}
                    title="Center on target AOI"
                  >
                    <Crosshair size={12} />
                  </button>
                </div>
              </div>

              <!-- Scientific Visualization Panel: below globe in analysis state -->
              <div class="scientific-tile-box">
                <ScientificVisPanel />
              </div>
            {/if}
          </div>

          <!-- LANDING OVERLAY: Centered on top of globe during Landing state -->
          {#if viewState === 'landing'}
            <HeroLanding
              isAnalyzing={$isAnalyzing}
              on:submitQuery={(e) => handleLandingQuery(e.detail)}
            />
          {/if}

          <!-- RIGHT COLUMN: ProcessingPanel during processing, ChatPanel during analysis -->
          {#if viewState === 'processing'}
            <div class="right-chat-column">
              <ProcessingPanel
                query={submittedQuery}
                progressStep={currentProcessingStep}
                errorMessage={processingError}
                onStartOver={handleNewChat}
              />
            </div>
          {:else if viewState === 'analysis'}
            <div class="right-chat-column">
              <ChatPanel
                isAnalyzingProp={$isAnalyzing}
                on:submitQuery={(e) => handleFollowupQuery(e.detail)}
                on:actionClick={(e) => handleActionClick(e.detail)}
                on:newChat={handleNewChat}
              />
            </div>
          {/if}
        </div>
      {/if}
    </main>
  </div>

  <!-- Modals -->
  <AuditTraceModal />
  <SettingsModal />
</div>

<style>
  .app-root {
    --navbar-total-height: 92px;
    width: 100vw;
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    background: #000000;
    box-sizing: border-box;
    padding-top: var(--navbar-total-height);
  }

  .workspace-body {
    flex: 1;
    width: 100%;
    display: flex;
    overflow: hidden;
    position: relative;
  }

  .main-content-canvas {
    flex: 1;
    height: 100%;
    overflow: hidden;
    position: relative;
  }

  .main-content-canvas.is-landing {
    padding: 0;
  }

  /* Split Workspace Grid - Smooth Transition */
  .split-workspace-grid {
    width: 100%;
    height: 100%;
    display: flex;
    gap: 14px;
    padding: 14px;
    overflow: hidden;
    position: relative;
    transition: padding 0.45s cubic-bezier(0.16, 1, 0.3, 1), gap 0.45s cubic-bezier(0.16, 1, 0.3, 1);
  }

  .split-workspace-grid.is-landing {
    padding: 0;
    gap: 0;
  }

  .left-vis-column {
    width: 38%;
    min-width: 380px;
    max-width: 500px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    height: 100%;
    overflow: hidden;
    transition: width 0.5s cubic-bezier(0.16, 1, 0.3, 1), max-width 0.5s cubic-bezier(0.16, 1, 0.3, 1);
    position: relative;
  }

  .left-vis-column.is-landing {
    width: 100%;
    min-width: 100%;
    max-width: 100%;
    gap: 0;
  }

  .globe-tile-box {
    flex: 1.1;
    min-height: 220px;
    border-radius: 12px;
    overflow: hidden;
    position: relative;
    background: #000000;
    border: 1px solid rgba(255, 255, 255, 0.08);
    transition: border-radius 0.45s cubic-bezier(0.16, 1, 0.3, 1);
  }

  .globe-tile-box.is-landing {
    flex: 1;
    width: 100%;
    height: 100%;
    min-height: 100%;
    border-radius: 0;
    border: none;
  }

  /* AOI Information Strip */
  .aoi-info-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: #080c14;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 6px 12px;
    animation: slideUp 0.35s ease-out;
  }

  .aoi-left {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .aoi-pulse-indicator {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #e2e8f0;
    box-shadow: 0 0 8px rgba(255, 255, 255, 0.5);
    flex-shrink: 0;
  }

  .aoi-text {
    display: flex;
    flex-direction: column;
  }

  .aoi-title {
    font-size: 12.5px;
    font-weight: 600;
    color: #ffffff;
  }

  .aoi-coords {
    font-size: 10px;
    font-family: var(--font-mono, monospace);
    color: #94a3b8;
  }

  .aoi-right {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .aoi-stat {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
  }

  .stat-lbl {
    font-size: 8.5px;
    letter-spacing: 0.8px;
    color: #64748b;
  }

  .stat-val {
    font-size: 11px;
    font-weight: 600;
    color: #f8fafc;
  }

  .aoi-recenter-btn {
    width: 24px;
    height: 24px;
    border-radius: 6px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #94a3b8;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .aoi-recenter-btn:hover {
    color: #ffffff;
    background: rgba(255, 255, 255, 0.08);
    border-color: rgba(255, 255, 255, 0.2);
  }

  .scientific-tile-box {
    flex: 1.1;
    min-height: 220px;
    border-radius: 12px;
    overflow: hidden;
    background: #080c14;
    border: 1px solid rgba(255, 255, 255, 0.08);
    animation: slideUp 0.4s cubic-bezier(0.16, 1, 0.3, 1);
  }


  @keyframes slideUp {
    from {
      opacity: 0;
      transform: translateY(14px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .right-chat-column {
    flex: 1;
    height: 100%;
    overflow: hidden;
    border-radius: 12px;
    animation: fadeIn 0.4s ease-out;
  }

  @keyframes fadeIn {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }
</style>
