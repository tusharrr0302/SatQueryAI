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
    activeAsset,
    activeVisualizationTab,
    activeDataLayers,
    flyToLayerTrigger,
    showAuthModal,
    authModalMode,
    liveAnalysisSteps,
    liveAnalysisStatus,
    type ChatMessage,
    type DataLayerSpec,
  } from './lib/stores';
  import { sendChatQuery, initWebSocket, fetchConversation } from './lib/api';

  // Components
  import Navbar from './lib/components/Navbar.svelte';
  import Sidebar from './lib/components/Sidebar.svelte';
  import HeroLanding from './lib/components/HeroLanding.svelte';
  import CesiumGlobe from './lib/components/CesiumGlobe.svelte';
  import DataWorkspace from './lib/components/DataWorkspace.svelte';
  import ChatPanel from './lib/components/ChatPanel.svelte';
  import LayersModal from './lib/components/LayersModal.svelte';
  import InvestigationsModal from './lib/components/InvestigationsModal.svelte';
  import AuditTraceModal from './lib/components/AuditTraceModal.svelte';
  import SettingsModal from './lib/components/SettingsModal.svelte';
  import DatasetsPage from './lib/components/DatasetsPage.svelte';
  import UseCasesPage from './lib/components/UseCasesPage.svelte';
  import DocsPage from './lib/components/DocsPage.svelte';
  import HistoryModal from './lib/components/HistoryModal.svelte';
  import AuthModal from './lib/components/AuthModal.svelte';
  import { initAuth, isAuthLoaded, isSignedIn } from './lib/services/authService';
  import { Crosshair } from 'lucide-svelte';

  $: viewState = $appViewState;
  let submittedQuery = '';
  let processingError = '';
  let cesiumGlobeComponent: any;
  let wsSocket: WebSocket | null = null;
  let lastSignedInState = false;
  let isConnectingWs = false;
  let pendingQuery = '';

  $: $isLandingPage = $appViewState === 'landing';

  onMount(async () => {
    $showAuthModal = false;
    initAuth().catch((err) => console.warn('[App] Clerk init note:', err));

    // Restore active conversation from DB upon reload
    const savedConvId = localStorage.getItem('sq_conv_id');
    if (savedConvId) {
      try {
        const conv = await fetchConversation(savedConvId);
        if (conv && conv.messages && conv.messages.length) {
          $conversationId = conv.id;
          $messages = conv.messages;
          if (conv.last_result) {
            $currentResult = conv.last_result;
          }
          if (conv.layers && conv.layers.length) {
            $activeDataLayers = conv.layers;
          } else if (conv.last_result?.layers && conv.last_result.layers.length) {
            $activeDataLayers = conv.last_result.layers;
          }
          const aoi = conv.last_result?.aoi;
          if (aoi?.center) {
            globeLocation.update((g) => ({
              ...g,
              latitude: aoi.center.latitude,
              longitude: aoi.center.longitude,
              name: aoi.name || g.name,
              area_km2: aoi.area_km2 || g.area_km2,
              polygon: aoi.polygon || g.polygon,
              flyTrigger: g.flyTrigger + 1,
            }));
          }
          viewState = 'analysis';
          $appViewState = 'analysis';
        }
      } catch (e) {
        console.warn('[App] Stored conversation reload note:', e);
      }
    }
  });

  function disconnectUserWebSocket() {
    if (wsSocket) {
      try { wsSocket.close(); } catch {}
      wsSocket = null;
    }
  }

  async function connectUserWebSocket() {
    if (isConnectingWs) return;
    isConnectingWs = true;
    disconnectUserWebSocket();
    try {
      const sock = await initWebSocket((event, data) => {
        console.log('[App WS Event]', event, data);
        if (event === 'planning') {
          liveAnalysisStatus.set('Understanding request with GPT-OSS...');
          liveAnalysisSteps.set([
            { step: 'understanding', label: 'Understanding query with GPT-OSS', status: 'running' },
            { step: 'aoi', label: 'Resolving AOI & geospatial bounds', status: 'pending' },
            { step: 'imagery', label: 'Selecting Earth Observation imagery', status: 'pending' },
            { step: 'analysis', label: 'Executing geospatial analysis model', status: 'pending' },
            { step: 'visualization', label: 'Preparing map layers & visualizations', status: 'pending' },
          ]);
        } else if (event === 'aoi_resolving') {
          liveAnalysisStatus.set(data?.name ? `Resolving AOI: ${data.name}` : 'Resolving target AOI...');
          liveAnalysisSteps.update((steps) => steps.map((s) => {
            if (s.step === 'understanding') return { ...s, status: 'completed' };
            if (s.step === 'aoi') return { ...s, status: 'running' };
            return s;
          }));
          if (data?.name) {
            globeLocation.update((g) => ({ ...g, name: `Resolving ${data.name}...` }));
          }
        } else if (event === 'scenario_matched' || event === 'gpt_started') {
          liveAnalysisStatus.set('Matching Earth observation pipeline...');
          liveAnalysisSteps.update((steps) => steps.map((s) => {
            if (s.step === 'understanding' || s.step === 'aoi') return { ...s, status: 'completed' };
            if (s.step === 'imagery') return { ...s, status: 'running' };
            return s;
          }));
        } else if (event === 'imagery_started') {
          liveAnalysisStatus.set('Retrieving satellite imagery...');
          liveAnalysisSteps.update((steps) => steps.map((s) => {
            if (s.step === 'understanding' || s.step === 'aoi') return { ...s, status: 'completed' };
            if (s.step === 'imagery') return { ...s, status: 'running' };
            return s;
          }));
        } else if (event === 'analysis_started' || event === 'tool_started') {
          liveAnalysisStatus.set('Executing remote sensing analysis model...');
          liveAnalysisSteps.update((steps) => steps.map((s) => {
            if (s.step === 'understanding' || s.step === 'aoi' || s.step === 'imagery') return { ...s, status: 'completed' };
            if (s.step === 'analysis') return { ...s, status: 'running' };
            return s;
          }));
        } else if (event === 'globe_action') {
          if (data?.latitude && data?.longitude) {
            globeLocation.update((g) => ({
              ...g,
              latitude: data.latitude,
              longitude: data.longitude,
              name: data.name || g.name,
              flyTrigger: g.flyTrigger + 1,
            }));
          }
        } else if (event === 'visualization_created') {
          liveAnalysisStatus.set('Generating geospatial layers...');
          liveAnalysisSteps.update((steps) => steps.map((s) => {
            if (s.step !== 'visualization') return { ...s, status: 'completed' };
            return { ...s, status: 'running' };
          }));
        } else if (event === 'completed') {
          liveAnalysisStatus.set('Analysis complete');
          liveAnalysisSteps.update((steps) => steps.map((s) => ({ ...s, status: 'completed' })));
        }
      });
      wsSocket = sock;
    } catch (err) {
      console.warn('[App] WS connect note:', err);
    } finally {
      isConnectingWs = false;
    }
  }

  // Guard WebSocket connection against infinite reactive re-triggering
  $: if ($isSignedIn && !lastSignedInState) {
    lastSignedInState = true;
    connectUserWebSocket();
  } else if (!$isSignedIn && lastSignedInState) {
    lastSignedInState = false;
    disconnectUserWebSocket();
  }

  // Seamlessly resume query if user submitted before signing in
  $: if ($isSignedIn && pendingQuery) {
    const q = pendingQuery;
    pendingQuery = '';
    executeChatQuery(q);
  }

  /* =========================================================
     CORE UNIFIED CHAT EXECUTION (MULTI-TURN PERSISTENT)
     ========================================================= */

  async function executeChatQuery(query: string) {
    if (!$isSignedIn) {
      pendingQuery = query;
      $authModalMode = 'sign-in';
      $showAuthModal = true;
      return;
    }

    if ($isAnalyzing) return;

    submittedQuery = query;
    viewState = 'analysis';
    $appViewState = 'analysis';
    $isAnalyzing = true;
    processingError = '';
    $activeNav = 'home';
    $activeSidebarTab = 'chat';

    // Step 1: Add provisional user message so user immediately sees their query
    const tempId = `temp_${Date.now()}`;
    const tempUserMsg: ChatMessage = {
      id: tempId,
      role: 'user',
      content: query,
      timestamp: new Date().toISOString(),
    };
    $messages = [...$messages, tempUserMsg];

    // Initialize in-chat live analysis indicator
    liveAnalysisStatus.set('Analyzing Earth...');
    liveAnalysisSteps.set([
      { step: 'understanding', label: 'Understanding query with GPT-OSS', status: 'running' },
      { step: 'aoi', label: 'Resolving AOI & geospatial bounds', status: 'pending' },
      { step: 'imagery', label: 'Selecting Earth Observation imagery', status: 'pending' },
      { step: 'analysis', label: 'Executing geospatial analysis model', status: 'pending' },
      { step: 'visualization', label: 'Preparing map layers & visualizations', status: 'pending' },
    ]);

    try {
      const res = await sendChatQuery(query, $conversationId, $activeAsset?.asset_id);

      if (res.result) {
        $currentResult = res.result;

        // Replace provisional message with canonical user_message and append assistant_message
        const withoutTemp = $messages.filter((m) => m.id !== tempId);
        $messages = [...withoutTemp, res.user_message, res.assistant_message];

        $conversationId = res.conversation_id;
        localStorage.setItem('sq_conv_id', res.conversation_id);

        // Merge incoming layers into activeDataLayers (accumulate across multi-turn queries)
        const incomingLayers: DataLayerSpec[] = res.layers || res.result.layers || [];
        if (incomingLayers.length > 0) {
          activeDataLayers.update((existing) => {
            const map = new Map<string, DataLayerSpec>();
            for (const l of existing || []) map.set(l.layer_id, l);
            for (const l of incomingLayers) map.set(l.layer_id, l);
            return Array.from(map.values());
          });
        }

        // Update camera / globe location
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

        // Automatic fly to layer bounds
        if (incomingLayers.length > 0) {
          const targetLayer = incomingLayers[0];
          setTimeout(() => {
            $flyToLayerTrigger = { layerId: targetLayer.layer_id, timestamp: Date.now() };
          }, 350);
        }
      }
    } catch (err) {
      console.error('[App] Chat query error:', err);
      processingError = err instanceof Error ? err.message : 'Live analysis failed.';
      const errorMsg: ChatMessage = {
        id: `err_${Date.now()}`,
        role: 'assistant',
        content: `I couldn't complete that analysis: ${processingError}. The requested imagery or service was unavailable. Please try asking again or refine your query.`,
        timestamp: new Date().toISOString(),
      };
      // Convert provisional message to permanent and append assistant error message
      const finalUserMsg: ChatMessage = {
        ...tempUserMsg,
        id: `msg_${Date.now()}_u`,
      };
      const withoutTemp = $messages.filter((m) => m.id !== tempId);
      $messages = [...withoutTemp, finalUserMsg, errorMsg];
    } finally {
      $isAnalyzing = false;
    }
  }

  function handleNewChat() {
    $conversationId = '';
    localStorage.removeItem('sq_conv_id');
    $messages = [];
    $currentResult = null;
    $activeDataLayers = [];
    $activeAsset = null;
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

  async function handleSelectConversation(conv: any) {
    $conversationId = conv.id;
    localStorage.setItem('sq_conv_id', conv.id);
    try {
      const fullConv = await fetchConversation(conv.id);
      if (fullConv && fullConv.messages && fullConv.messages.length) {
        $messages = fullConv.messages;
        if (fullConv.last_result) $currentResult = fullConv.last_result;
        if (fullConv.layers && fullConv.layers.length) {
          $activeDataLayers = fullConv.layers;
        } else if (fullConv.last_result?.layers && fullConv.last_result.layers.length) {
          $activeDataLayers = fullConv.last_result.layers;
        }
      }
    } catch (e) {
      console.warn('[App] Select conversation error:', e);
    }
    const lat = conv.last_result?.aoi?.center?.latitude ?? conv.lat ?? 28.6139;
    const lon = conv.last_result?.aoi?.center?.longitude ?? conv.lon ?? 77.2090;
    globeLocation.update((g) => ({
      ...g,
      latitude: lat,
      longitude: lon,
      name: conv.last_result?.aoi?.name || conv.aoi_name || 'Target AOI',
      area_km2: conv.last_result?.aoi?.area_km2 || 1500,
      polygon: conv.last_result?.aoi?.polygon || [],
      flyTrigger: g.flyTrigger + 1,
    }));
    viewState = 'analysis';
    $appViewState = 'analysis';
    $activeSidebarTab = 'chat';
  }

  function handleActionClick(action: string) {
    if (action === 'aoi') {
      cesiumGlobeComponent?.flyTo($globeLocation.latitude, $globeLocation.longitude, 180000);
    } else if (action === 'compare') {
      executeChatQuery('Compare urban growth in Delhi with Shenzhen');
    }
  }
</script>

<div class="app-root space-stars">
    <!-- Top Navigation -->
    <Navbar on:navHome={handleNavHome} />

    <!-- Workspace Body -->
    <div class="workspace-body">
      <!-- Left Navigation Rail: always accessible when viewing main workspace -->
      {#if $activeNav === 'home'}
        <Sidebar on:newChat={handleNewChat} />
      {/if}

      <!-- Drawers -->
      {#if $activeSidebarTab === 'layers' && $activeNav === 'home'}
        <LayersModal />
      {/if}
      {#if $activeSidebarTab === 'investigations' && $activeNav === 'home'}
        <InvestigationsModal />
      {/if}
      {#if $activeSidebarTab === 'history' && $activeNav === 'home'}
        <HistoryModal on:selectConversation={(e) => handleSelectConversation(e.detail)} />
      {/if}

      <!-- Main Content Canvas -->
      <main class="main-content-canvas" class:is-landing={viewState === 'landing'}>
        {#if $activeNav === 'datasets'}
          <DatasetsPage />
        {:else if $activeNav === 'use-cases'}
          <UseCasesPage on:launchQuery={(e) => executeChatQuery(e.detail)} />
        {:else if $activeNav === 'docs'}
          <DocsPage />
        {:else if $activeSidebarTab === 'data' && viewState !== 'landing'}
          <div class="data-workspace-canvas">
            <DataWorkspace
              on:selectAsset={(e) => {
                $activeAsset = e.detail;
                $activeVisualizationTab = 'raster';
              }}
              on:askQuery={(e) => executeChatQuery(e.detail)}
            />
          </div>
        {:else}
          <!-- Persistent Interactive Earth Canvas -->
          <div class="split-workspace-grid" class:is-landing={viewState === 'landing'}>
            <!-- LEFT COLUMN: Cesium 3D Globe Workspace -->
            <div class="left-vis-column" class:is-landing={viewState === 'landing'}>
              <!-- Single Cesium Globe Instance (Always preserved for WebGL context) -->
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
                      on:click={() => {
                        cesiumGlobeComponent?.flyTo($globeLocation.latitude, $globeLocation.longitude, 350000);
                      }}
                      title="Center on target AOI in globe"
                    >
                      <Crosshair size={12} />
                    </button>
                  </div>
                </div>
              {/if}
            </div>

            <!-- LANDING OVERLAY: Centered on top of globe during Landing state -->
            {#if viewState === 'landing'}
              <HeroLanding
                isAnalyzing={$isAnalyzing}
                on:submitQuery={(e) => executeChatQuery(e.detail)}
              />
            {/if}

            <!-- RIGHT COLUMN: ChatPanel during analysis -->
            {#if viewState === 'analysis'}
              <div class="right-chat-column">
                <ChatPanel
                  isAnalyzingProp={$isAnalyzing}
                  on:submitQuery={(e) => executeChatQuery(e.detail)}
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
    <AuthModal isGateMode={false} />
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
    flex: 1;
    min-width: 400px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    height: 100%;
    overflow: hidden;
    transition: all 0.5s cubic-bezier(0.16, 1, 0.3, 1);
    position: relative;
  }

  .left-vis-column.is-landing {
    flex: 1;
    width: 100%;
    min-width: 100%;
    max-width: 100%;
    gap: 0;
  }

  .globe-tile-box {
    flex: 1;
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

  .globe-tile-box.is-hidden {
    display: none !important;
  }

  /* Visualization Renderer Switcher */
  .renderer-selector-bar {
    display: flex;
    gap: 4px;
    padding: 3px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    flex-shrink: 0;
  }

  .renderer-tab-btn {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 6px 8px;
    border-radius: 6px;
    background: transparent;
    border: none;
    color: rgba(255, 255, 255, 0.5);
    font-size: 10px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s ease;
    white-space: nowrap;
  }

  .renderer-tab-btn:hover {
    color: #fff;
    background: rgba(255, 255, 255, 0.05);
  }

  .renderer-tab-btn.active {
    background: rgba(255, 255, 255, 0.12);
    color: #fff;
    font-weight: 600;
  }

  .raster-tile-box {
    flex: 1;
    width: 100%;
    min-height: 260px;
    border-radius: 12px;
    overflow: hidden;
    position: relative;
    border: 1px solid rgba(255, 255, 255, 0.08);
  }

  .data-workspace-canvas {
    width: 100%;
    height: 100%;
    padding: 14px;
    box-sizing: border-box;
    overflow: hidden;
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

  /* =========================================================
     AUTH GATE & LOADING SCREEN STYLES
     ========================================================= */

  .auth-gate-loading {
    width: 100vw;
    height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    background: radial-gradient(circle at 50% 30%, rgba(255, 255, 255, 0.03) 0%, #030303 60%, #000000 100%);
  }

  .gate-loading-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    padding: 36px 48px;
    background: rgba(10, 10, 10, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
    backdrop-filter: blur(16px);
    box-shadow: 0 30px 60px rgba(0, 0, 0, 0.7);
  }

  .gate-loading-logo {
    width: 48px;
    height: 48px;
    object-fit: contain;
    margin-bottom: 20px;
    filter: drop-shadow(0 0 16px rgba(255, 255, 255, 0.15));
  }

  .gate-spinner-ring {
    width: 26px;
    height: 26px;
    border: 2px solid rgba(255, 255, 255, 0.1);
    border-top-color: #ffffff;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin-bottom: 16px;
  }

  .gate-loading-title {
    font-size: 15px;
    font-weight: 600;
    color: #f5f5f5;
    letter-spacing: -0.01em;
    margin-bottom: 6px;
  }

  .gate-loading-subtitle {
    font-size: 12px;
    color: rgba(255, 255, 255, 0.45);
  }

  .auth-gate-screen {
    width: 100vw;
    min-height: 100vh;
    display: flex;
    align-items: flex-start;
    justify-content: center;
    background: radial-gradient(circle at 50% 15%, rgba(255, 255, 255, 0.04) 0%, #040404 65%, #000000 100%);
    padding: 48px 20px 64px 20px;
    box-sizing: border-box;
    overflow-y: auto;
  }

  .auth-gate-container {
    width: 100%;
    max-width: 520px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 20px;
    animation: fadeIn 0.3s ease-out;
  }

  .auth-gate-branding {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
  }

  .gate-brand-logo {
    width: 54px;
    height: 54px;
    object-fit: contain;
    margin-bottom: 14px;
    filter: drop-shadow(0 0 20px rgba(255, 255, 255, 0.18));
  }

  .gate-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    border-radius: 9999px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.15);
    color: #ffffff;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.06em;
    margin-bottom: 12px;
    text-transform: uppercase;
  }

  .gate-title {
    font-size: 24px;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: -0.03em;
    margin: 0 0 8px 0;
  }

  .gate-description {
    font-size: 13px;
    line-height: 1.55;
    color: rgba(255, 255, 255, 0.58);
    margin: 0;
    max-width: 440px;
  }

  .auth-gate-card-box {
    width: 100%;
    display: flex;
    justify-content: center;
  }

  .auth-gate-footer {
    display: flex;
    align-items: center;
    gap: 7px;
    font-size: 11px;
    color: rgba(255, 255, 255, 0.4);
    text-align: center;
  }

  .pulse {
    animation: pulseGlow 2.5s ease-in-out infinite;
  }

  @keyframes pulseGlow {
    0%, 100% {
      opacity: 0.8;
      transform: scale(1);
    }
    50% {
      opacity: 1;
      transform: scale(1.05);
    }
  }
</style>
