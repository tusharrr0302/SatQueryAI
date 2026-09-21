<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import {
    messages,
    currentResult,
    isAnalyzing,
    activeAsset,
    activeDataLayers,
    activeSidebarTab,
    liveAnalysisSteps,
    liveAnalysisStatus,
    aiMode,
    activeVisualizationPlan,
    type ChatMessage,
    type AIMode,
  } from '../stores';

  import { parseMarkdown } from '../markdown';
  import AnalysisResult from './AnalysisResult.svelte';
  import { pickSatelliteFile, uploadSatelliteFile } from '../services/fileService';

  import {
    Paperclip,
    ArrowUp,
    Plus,
    CheckCheck,
    FileText,
    Layers,
    X,
    Sparkles,
    ChevronDown,
    ChevronUp,
    ExternalLink,
    Image as ImageIcon,
    Sliders,
    Globe,
    HelpCircle,
    Info,
  } from 'lucide-svelte';

  /* =========================================================
     PROPS & EVENTS
     ========================================================= */

  export let isAnalyzingProp: boolean = false;

  const dispatch = createEventDispatcher<{
    submitQuery: string;
    actionClick: string;
    newChat: void;
  }>();

  /* =========================================================
     STATE
     ========================================================= */

  let inputQuery = '';
  let messagesContainer: HTMLElement;
  let isUploadingAsset = false;
  let uploadStatusText = '';
  let expandedExplanationIds: Record<string, boolean> = {};
  let expandedSections: Record<string, Record<string, boolean>> = {};

  function toggleExplanation(id: string) {
    expandedExplanationIds[id] = !expandedExplanationIds[id];
    expandedExplanationIds = { ...expandedExplanationIds };
  }

  function toggleSection(msgId: string, section: string) {
    if (!expandedSections[msgId]) expandedSections[msgId] = {};
    expandedSections[msgId][section] = !expandedSections[msgId][section];
    expandedSections = { ...expandedSections };
  }

  function isSectionOpen(msgId: string, section: string, isAdvanced: boolean): boolean {
    if (expandedSections[msgId] && expandedSections[msgId][section] !== undefined) {
      return expandedSections[msgId][section];
    }
    return isAdvanced;
  }

  function getRoleBadgeClass(role?: string): string {
    switch (role) {
      case 'primary_analysis': return 'role-primary';
      case 'study_area': return 'role-study';
      case 'comparison': return 'role-comparison';
      case 'reference': return 'role-reference';
      default: return 'role-default';
    }
  }

  function getRoleBadgeLabel(role?: string): string {
    switch (role) {
      case 'primary_analysis': return 'PRIMARY ANALYSIS';
      case 'study_area': return 'STUDY AREA';
      case 'comparison': return 'COMPARISON';
      case 'reference': return 'REFERENCE';
      default: return (role || 'LAYER').toUpperCase();
    }
  }

  const sampleQueries = [
    'Show vegetation loss around Delhi',
    'Compare urban expansion over 10 years',
    'Explain this satellite image',
    'Analyze my uploaded GeoTIFF'
  ];

  function deriveTitle(msgs: ChatMessage[], res: any): string {
    if (res?.aoi?.name) {
      const type = res.analysis_type ? res.analysis_type.replace(/_/g, ' ') : 'Analysis';
      return `${res.aoi.name} ${type}`;
    }
    const firstUser = msgs.find(m => m.role === 'user');
    if (firstUser && firstUser.content) {
      const cleaned = firstUser.content.replace(/^(show|analyze|what is|compare|tell me about)\s+/i, '');
      return cleaned.slice(0, 36) + (cleaned.length > 36 ? '...' : '');
    }
    return 'Earth Observation';
  }

  function deriveSubtitle(msgs: ChatMessage[], res: any): string {
    if (res?.provenance) {
      const ds = res.provenance.dataset_ids?.join(' · ') || 'Sentinel-2';
      const model = res.provenance.model_name || 'Prithvi';
      return `${ds} · ${model}`;
    }
    return 'Ask about Earth, imagery, or your data';
  }

  $: sessionTitle = deriveTitle($messages, $currentResult);
  $: sessionSubtitle = deriveSubtitle($messages, $currentResult);

  function scrollToBottom(smooth = true) {
    if (messagesContainer) {
      messagesContainer.scrollTo({
        top: messagesContainer.scrollHeight,
        behavior: smooth ? 'smooth' : 'auto',
      });
    }
  }

  $: if ($messages.length || isAnalyzingProp) {
    setTimeout(() => scrollToBottom(true), 60);
  }

  /* =========================================================
     ACTIONS
     ========================================================= */

  function handleSend() {
    if (!inputQuery.trim() || isAnalyzingProp) return;

    dispatch('submitQuery', inputQuery.trim());
    inputQuery = '';
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleAction(action: string) {
    dispatch('actionClick', action);
  }

  function handleSuggested(q: string) {
    dispatch('submitQuery', q);
  }

  function handleNewChat() {
    dispatch('newChat');
  }

  async function handleAttachData() {
    if (isAnalyzingProp || isUploadingAsset) return;
    try {
      isUploadingAsset = true;
      uploadStatusText = 'Opening dialog...';
      const selected = await pickSatelliteFile();
      if (!selected) {
        isUploadingAsset = false;
        return;
      }
      uploadStatusText = 'Inspecting raster asset...';
      const uploaded = await uploadSatelliteFile(selected, (msg) => {
        uploadStatusText = msg;
      });
      $activeAsset = {
        asset_id: uploaded.asset_id,
        filename: selected.name,
        profile: uploaded.profile,
        preview_url: uploaded.preview_url,
      };
    } catch (err) {
      console.error('File attach failed:', err);
      alert(err instanceof Error ? err.message : 'Asset upload failed');
    } finally {
      isUploadingAsset = false;
      uploadStatusText = '';
    }
  }

  $: activeVisibleLayersCount = ($activeDataLayers || []).filter(
    (l) => l.visible !== false && l.type !== 'metadata'
  ).length;
</script>

<div class="chat-workspace-panel">
  <!-- HEADER -->
  <header class="chat-header-bar">
    <div class="header-left">
      <div class="session-mark">
        <span class="session-dot"></span>
      </div>
      <div class="session-info">
        <span class="session-title">{sessionTitle}</span>
        <span class="session-subtitle">{sessionSubtitle}</span>
      </div>
    </div>

    <div class="header-actions">
      {#if activeVisibleLayersCount > 0}
        <button
          class="layers-indicator-pill"
          on:click={() => ($activeSidebarTab = 'layers')}
          title="Open layer management drawer"
        >
          <Layers size={13} />
          <span>{activeVisibleLayersCount} active {activeVisibleLayersCount === 1 ? 'layer' : 'layers'}</span>
        </button>
      {/if}

      <button
        class="new-chat-btn"
        on:click={handleNewChat}
        title="Start a new chat conversation"
      >
        <Plus size={14} strokeWidth={1.7} />
        <span>New Chat</span>
      </button>
    </div>
  </header>

  <!-- MESSAGE STREAM -->
  <main class="messages-container" bind:this={messagesContainer}>
    {#if $messages.length === 0}
      <!-- Empty State -->
      <div class="empty-state">
        <div class="empty-logo">
          <img src="/satquery_logo.png" alt="SatQuery AI" />
        </div>
        <h2>Ask Earth anything.</h2>
        <p>Query satellite imagery, analyze environmental change, investigate regions, or chat with your own uploaded GeoTIFF.</p>
        
        <div class="empty-suggestions-grid">
          {#each sampleQueries as sq}
            <button
              class="suggestion-card"
              on:click={() => handleSuggested(sq)}
              disabled={isAnalyzingProp}
            >
              <Sparkles size={13} class="sq-icon" />
              <span>{sq}</span>
            </button>
          {/each}
        </div>
      </div>
    {/if}

    {#each $messages as msg (msg.id)}
      {@const plan = msg.visualization_plan || msg.result?.visualization_plan}
      {@const evidence = msg.web_evidence || msg.result?.web_evidence}
      {#if msg.role === 'user'}
        <!-- USER MESSAGE -->
        <div class="user-message-row">
          <div class="user-message">
            <div class="user-message-content">
              {msg.content}
            </div>
            <div class="user-message-meta">
              <span>{msg.timestamp ? (msg.timestamp.split('T')[1]?.slice(0, 5) || '') : ''}</span>
              <CheckCheck size={12} strokeWidth={1.8} />
            </div>
          </div>
        </div>
      {:else}
        <div class="assistant-row">
          {#if msg.result && msg.result.analysis_type && msg.result.analysis_type !== 'conversational' && !msg.result.is_conversational && !msg.is_conversational}
            <AnalysisResult
              result={msg.result}
              content={msg.content}
              timestamp={msg.timestamp}
              on:submitQuery={(e) => handleSuggested(e.detail)}
              on:actionClick={(e) => handleAction(e.detail)}
            />
          {:else}
            <div class="assistant-message">
              <div class="assistant-header">
                <div class="assistant-logo">
                  <img src="/satquery_logo.png" alt="SatQuery AI" />
                </div>
                <div class="assistant-identity">
                  <span class="assistant-name">SatQuery AI</span>
                  <span class="assistant-label">EO AGENT</span>
                  {#if msg.ai_mode && msg.ai_mode !== 'auto'}
                    <span class="ai-mode-badge">{msg.ai_mode.toUpperCase()} MODE</span>
                  {/if}
                </div>
              </div>
              <div class="assistant-content gpt-response-content">
                {@html parseMarkdown(msg.content)}
              </div>
            </div>
          {/if}

          <!-- EARTH TELEMETRY & READING GUIDE PILL -->
          {#if msg.visualization_required !== false && (plan || (msg.layers && msg.layers.length > 0))}
            {@const layerList = plan?.active_layers || msg.layers || []}
            {@const layerCount = layerList.length}
            <div class="earth-telemetry-container">
              <div class="earth-telemetry-pill">
                <div class="pill-left">
                  <Globe size={13} class="pill-globe-icon" />
                  <span class="pill-main-label">Earth Telemetry</span>
                  {#if layerCount > 0}
                    <span class="pill-divider">•</span>
                    <button
                      class="pill-layer-badge"
                      on:click={() => activeSidebarTab.set('layers')}
                      title="Open Active Layers"
                    >
                      <Layers size={11} />
                      <span>{layerCount} {layerCount === 1 ? 'layer' : 'layers'}</span>
                    </button>
                  {/if}
                  {#if plan?.primary_visualization?.type}
                    <span class="pill-vis-type">{plan.primary_visualization.type.replace(/_/g, ' ').toUpperCase()}</span>
                  {/if}
                </div>

                <div class="pill-right">
                  {#if layerCount > 0}
                    <button
                      class="pill-action-btn"
                      on:click={() => activeSidebarTab.set('layers')}
                      title="Inspect active layers on globe"
                    >
                      <Layers size={11} />
                      <span>Layers</span>
                    </button>
                  {/if}
                  {#if plan?.explanation}
                    <button
                      class="pill-action-btn reading-guide-btn"
                      on:click={() => toggleExplanation(msg.id)}
                      title="Explain how this visual evidence was composed"
                    >
                      <HelpCircle size={12} />
                      <span>{expandedExplanationIds[msg.id] ? 'Hide Guide' : 'Reading Guide'}</span>
                      {#if expandedExplanationIds[msg.id]}
                        <ChevronUp size={12} />
                      {:else}
                        <ChevronDown size={12} />
                      {/if}
                    </button>
                  {/if}
                </div>
              </div>

              <!-- Collapsible Reading Guide (Authoritative Interpretation) -->
              {#if expandedExplanationIds[msg.id] && plan?.explanation}
                <div class="vis-guide-panel">
                  {#if plan.explanation?.what_this_represents || plan.explanation?.plain_language_summary}
                    <div class="vis-summary-banner">
                      <span class="vis-summary-label">WHAT YOU'RE SEEING</span>
                      <p class="vis-summary-text">{msg.ai_mode === 'beginner' && plan.explanation.plain_language_summary ? plan.explanation.plain_language_summary : (plan.explanation.what_this_represents || plan.primary_visualization?.title)}</p>
                    </div>
                  {/if}

                  {#if plan.explanation?.key_observation}
                    <div class="vis-key-obs-banner">
                      <span class="vis-key-obs-label">KEY OBSERVATION</span>
                      <p class="vis-key-obs-text">{plan.explanation.key_observation}</p>
                    </div>
                  {/if}

                  <!-- Progressive Disclosure Sections -->
                  <div class="vis-explanation-progressive">
                    <!-- Section 1: How to read this -->
                    <div class="disclosure-card">
                      <button
                        class="disclosure-toggle"
                        on:click={() => toggleSection(msg.id, 'how_to_read')}
                        aria-expanded={isSectionOpen(msg.id, 'how_to_read', msg.ai_mode === 'advanced')}
                      >
                        <span class="disclosure-title">How to read this</span>
                        {#if isSectionOpen(msg.id, 'how_to_read', msg.ai_mode === 'advanced')}
                          <ChevronUp size={13} />
                        {:else}
                          <ChevronDown size={13} />
                        {/if}
                      </button>
                      {#if isSectionOpen(msg.id, 'how_to_read', msg.ai_mode === 'advanced')}
                        <div class="disclosure-content">
                          {#if plan.explanation.visual_form}
                            <div class="disclosure-item"><span class="item-tag">VISUAL FORM</span> <p>{plan.explanation.visual_form}</p></div>
                          {/if}
                          {#if plan.explanation.palette_and_scale}
                            <div class="disclosure-item"><span class="item-tag">PALETTE & SCALE</span> <p>{plan.explanation.palette_and_scale}</p></div>
                          {/if}
                          {#if plan.explanation.critical_thresholds}
                            <div class="disclosure-item"><span class="item-tag">CRITICAL THRESHOLDS</span> <p>{plan.explanation.critical_thresholds}</p></div>
                          {/if}
                          {#if plan.explanation.primary_metric}
                            <div class="disclosure-item"><span class="item-tag">PRIMARY METRIC</span> <p>{plan.explanation.primary_metric}</p></div>
                          {/if}
                        </div>
                      {/if}
                    </div>

                    <!-- Section 2: Why this view -->
                    <div class="disclosure-card">
                      <button
                        class="disclosure-toggle"
                        on:click={() => toggleSection(msg.id, 'why_view')}
                        aria-expanded={isSectionOpen(msg.id, 'why_view', msg.ai_mode === 'advanced')}
                      >
                        <span class="disclosure-title">Why this view</span>
                        {#if isSectionOpen(msg.id, 'why_view', msg.ai_mode === 'advanced')}
                          <ChevronUp size={13} />
                        {:else}
                          <ChevronDown size={13} />
                        {/if}
                      </button>
                      {#if isSectionOpen(msg.id, 'why_view', msg.ai_mode === 'advanced')}
                        <div class="disclosure-content">
                          {#if plan.explanation.why_chosen}
                            <div class="disclosure-item"><span class="item-tag">ANALYTICAL REASON</span> <p>{plan.explanation.why_chosen}</p></div>
                          {/if}
                          {#if plan.explanation.visual_inferences}
                            <div class="disclosure-item"><span class="item-tag">INFERENCES</span> <p>{plan.explanation.visual_inferences}</p></div>
                          {/if}
                          {#if plan.explanation.spatial_context}
                            <div class="disclosure-item"><span class="item-tag">SPATIAL CONTEXT</span> <p>{plan.explanation.spatial_context}</p></div>
                          {/if}
                        </div>
                      {/if}
                    </div>

                    <!-- Section 3: Data & method -->
                    <div class="disclosure-card">
                      <button
                        class="disclosure-toggle"
                        on:click={() => toggleSection(msg.id, 'data_method')}
                        aria-expanded={isSectionOpen(msg.id, 'data_method', msg.ai_mode === 'advanced')}
                      >
                        <span class="disclosure-title">Data & method</span>
                        {#if isSectionOpen(msg.id, 'data_method', msg.ai_mode === 'advanced')}
                          <ChevronUp size={13} />
                        {:else}
                          <ChevronDown size={13} />
                        {/if}
                      </button>
                      {#if isSectionOpen(msg.id, 'data_method', msg.ai_mode === 'advanced')}
                        <div class="disclosure-content">
                          {#if plan.explanation.provenance_and_sensor}
                            <div class="disclosure-item"><span class="item-tag">SENSOR TELEMETRY</span> <p>{plan.explanation.provenance_and_sensor}</p></div>
                          {/if}
                          {#if plan.explanation.baseline_comparison}
                            <div class="disclosure-item"><span class="item-tag">BASELINE / EPOCHS</span> <p>{plan.explanation.baseline_comparison}</p></div>
                          {/if}
                          {#if plan.explanation.technical_summary}
                            <div class="disclosure-item technical-callout"><span class="item-tag">TECHNICAL FORMULATION</span> <p>{plan.explanation.technical_summary}</p></div>
                          {/if}
                        </div>
                      {/if}
                    </div>

                    <!-- Section 4: Limitations & caveats -->
                    <div class="disclosure-card">
                      <button
                        class="disclosure-toggle"
                        on:click={() => toggleSection(msg.id, 'limitations')}
                        aria-expanded={isSectionOpen(msg.id, 'limitations', msg.ai_mode === 'advanced')}
                      >
                        <span class="disclosure-title">Limitations & caveats</span>
                        {#if isSectionOpen(msg.id, 'limitations', msg.ai_mode === 'advanced')}
                          <ChevronUp size={13} />
                        {:else}
                          <ChevronDown size={13} />
                        {/if}
                      </button>
                      {#if isSectionOpen(msg.id, 'limitations', msg.ai_mode === 'advanced')}
                        <div class="disclosure-content">
                          {#if plan.explanation.limitations}
                            <div class="disclosure-item"><span class="item-tag">CAVEATS & CONSTRAINTS</span> <p>{plan.explanation.limitations}</p></div>
                          {/if}
                        </div>
                      {/if}
                    </div>
                  </div>
                </div>
              {/if}
            </div>
          {/if}

          <!-- GROUNDED WEB EVIDENCE CARD -->
          {#if evidence && evidence.length > 0}
            <div class="web-evidence-card">
              <div class="evidence-header">
                <Globe size={13} class="evidence-icon" />
                <span class="evidence-title">GROUNDED WEB EVIDENCE & EXTERNAL REFERENCE</span>
              </div>
              <div class="evidence-items-list">
                {#each evidence as item}
                  {#if item.is_reference_photo}
                    <div class="ref-photo-card">
                      <div class="ref-photo-badge-bar">
                        <span class="ref-photo-badge">
                          <ImageIcon size={11} />
                          Ground Reference Photo (Not Satellite Telemetry)
                        </span>
                        {#if item.source_domain}
                          <span class="ref-source-domain">{item.source_domain}</span>
                        {/if}
                      </div>
                      <div class="ref-photo-content">
                        {#if item.thumbnail_url}
                          <img src={item.thumbnail_url} alt={item.title} class="ref-thumb-img" />
                        {/if}
                        <div class="ref-photo-details">
                          <h5 class="ref-photo-title">{item.title}</h5>
                          <p class="ref-photo-snippet">{item.snippet}</p>
                          <a href={item.url} target="_blank" rel="noopener noreferrer" class="ref-source-link">
                            <span>{item.attribution || item.url}</span>
                            <ExternalLink size={11} />
                          </a>
                        </div>
                      </div>
                    </div>
                  {:else}
                    <div class="evidence-text-card">
                      <div class="evidence-text-top">
                        <span class="evidence-item-title">{item.title}</span>
                        {#if item.source_domain}
                          <span class="ref-source-domain">{item.source_domain}</span>
                        {/if}
                      </div>
                      <p class="evidence-snippet">{item.snippet}</p>
                      <a href={item.url} target="_blank" rel="noopener noreferrer" class="ref-source-link">
                        <span>{item.attribution || item.url}</span>
                        <ExternalLink size={11} />
                      </a>
                    </div>
                  {/if}
                {/each}
              </div>
            </div>
          {/if}
        </div>
      {/if}
    {/each}

    <!-- IN-CHAT ANALYZING STATE -->
    {#if isAnalyzingProp}
      <div class="assistant-row analyzing-row">
        <div class="assistant-message inline-analyzing-card">
          <div class="assistant-header">
            <div class="assistant-logo pulse">
              <img src="/satquery_logo.png" alt="SatQuery AI" />
            </div>
            <div class="assistant-identity">
              <span class="assistant-name">SatQuery AI</span>
              <span class="status-live-tag">PROCESSING</span>
            </div>
          </div>
          <div class="analyzing-body">
            <span class="analyzing-headline">{$liveAnalysisStatus || 'Analyzing Earth...'}</span>
            <div class="analysis-steps-list">
              {#each $liveAnalysisSteps as st}
                <div class="step-item" class:completed={st.status === 'completed'} class:running={st.status === 'running'}>
                  {#if st.status === 'completed'}
                    <span class="step-icon done">✓</span>
                  {:else if st.status === 'running'}
                    <span class="step-icon running">●</span>
                  {:else}
                    <span class="step-icon pending">○</span>
                  {/if}
                  <span class="step-label">{st.label}</span>
                </div>
              {/each}
            </div>
          </div>
        </div>
      </div>
    {/if}
  </main>

  <!-- INPUT AREA -->
  <footer class="input-container">
    {#if $activeAsset}
      <!-- Attached Asset Chip -->
      <div class="attached-asset-chip">
        <div class="chip-left">
          <FileText size={14} class="chip-icon" />
          <span class="chip-filename">{$activeAsset.filename || 'satellite_image.tif'}</span>
          {#if $activeAsset.profile?.bands}
            <span class="chip-badge">{$activeAsset.profile.bands.length} bands</span>
          {/if}
          {#if $activeAsset.profile?.resolution_m}
            <span class="chip-badge">{$activeAsset.profile.resolution_m}m</span>
          {/if}
          <span class="chip-context-label">Attached to Conversation</span>
        </div>
        <button
          class="chip-remove-btn"
          on:click={() => ($activeAsset = null)}
          title="Detach asset from conversation"
        >
          <X size={13} />
        </button>
      </div>
    {/if}

    <div class="input-controls-row">
      <div class="ai-mode-selector-wrap">
        <label for="ai-mode-select" class="ai-mode-label">
          <Sliders size={12} strokeWidth={1.7} />
          <span>AI MODE:</span>
        </label>
        <select id="ai-mode-select" bind:value={$aiMode} class="ai-mode-select" disabled={isAnalyzingProp}>
          <option value="auto">Auto (Balanced)</option>
          <option value="beginner">Beginner (Plain Language)</option>
          <option value="intermediate">Intermediate (Scientific)</option>
          <option value="advanced">Advanced (Mathematical & Research)</option>
        </select>
      </div>

      <div class="input-hint">
        <span>ENTER TO SEND</span>
        <span class="hint-divider">•</span>
        <span>SHIFT + ENTER FOR NEW LINE</span>
      </div>
    </div>

    <div class="input-bar">
      <!-- Attachment button -->
      <button
        class="attach-btn"
        on:click={handleAttachData}
        disabled={isAnalyzingProp || isUploadingAsset}
        title={isUploadingAsset ? uploadStatusText : "Attach satellite data (GeoTIFF, COG)..."}
        type="button"
      >
        {#if isUploadingAsset}
          <div class="send-spinner"></div>
        {:else}
          <Paperclip size={17} strokeWidth={1.5} />
        {/if}
      </button>

      <!-- Input text -->
      <input
        type="text"
        bind:value={inputQuery}
        on:keydown={handleKeydown}
        placeholder="Ask anything about Earth, imagery, change, or your data..."
        disabled={isAnalyzingProp}
        class="chat-input"
      />

      <!-- Send button -->
      <button
        class="send-btn"
        on:click={handleSend}
        disabled={isAnalyzingProp || !inputQuery.trim()}
        title="Send query"
        type="button"
      >
        {#if isAnalyzingProp}
          <div class="send-spinner"></div>
        {:else}
          <ArrowUp size={18} strokeWidth={1.6} />
        {/if}
      </button>
    </div>
  </footer>
</div>


<style>

  /* =========================================================
     DESIGN SYSTEM
     ========================================================= */

  :global(.chat-workspace-panel) {

    --white: #ffffff;
    --white-soft: rgba(255, 255, 255, 0.78);
    --white-muted: rgba(255, 255, 255, 0.48);
    --white-faint: rgba(255, 255, 255, 0.28);

    --glass:
      rgba(255, 255, 255, 0.035);

    --glass-strong:
      rgba(255, 255, 255, 0.055);

    --border:
      rgba(255, 255, 255, 0.10);

    --border-soft:
      rgba(255, 255, 255, 0.065);

    --black:
      #050505;

    --black-soft:
      #090909;

    --font-ui:
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
     MAIN WORKSPACE

     NAVBAR = 60px
     Workspace begins directly underneath it.
     ========================================================= */

  .chat-workspace-panel {

    position: relative;

    width: 100%;

    /*
     * IMPORTANT:
     * The workspace begins below the fixed navbar.
     */

    height: calc(100vh - var(--navbar-total-height));

    min-height: 0;

    display: flex;

    flex-direction: column;

    overflow: hidden;

    background:
      radial-gradient(
        ellipse at 50% -20%,
        rgba(255,255,255,0.045),
        transparent 48%
      ),
      #050505;

    border:
      1px solid
      var(--border-soft);

    border-top:
      0;

    border-radius:
      0;

    color:
      var(--white);

    font-family:
      var(--font-ui);

    box-sizing:
      border-box;
  }


  /* =========================================================
     HEADER
     ========================================================= */

  .chat-header-bar {

    height: 58px;

    min-height: 58px;

    display: flex;

    align-items: center;

    justify-content: space-between;

    padding:
      0 22px;

    background:
      rgba(8, 8, 8, 0.72);

    border-bottom:
      1px solid
      var(--border-soft);

    backdrop-filter:
      blur(24px)
      saturate(120%);

    -webkit-backdrop-filter:
      blur(24px)
      saturate(120%);

    position: relative;

    z-index: 5;

    flex-shrink: 0;
  }


  .chat-header-bar::after {

    content: "";

    position: absolute;

    left: 8%;

    right: 8%;

    bottom: 0;

    height: 1px;

    background:
      linear-gradient(
        90deg,
        transparent,
        rgba(255,255,255,0.08),
        transparent
      );
  }


  /* =========================================================
     HEADER LEFT
     ========================================================= */

  .header-left {

    display: flex;

    align-items: center;

    gap: 10px;
  }


  .session-mark {

    width: 27px;

    height: 27px;

    border-radius: 8px;

    display: flex;

    align-items: center;

    justify-content: center;

    background:
      rgba(255,255,255,0.045);

    border:
      1px solid
      rgba(255,255,255,0.10);

    box-shadow:
      inset 0 1px 0
      rgba(255,255,255,0.08);
  }


  .session-dot {

    width: 6px;

    height: 6px;

    border-radius: 50%;

    background:
      rgba(255,255,255,0.88);

    box-shadow:
      0 0 10px
      rgba(255,255,255,0.35);
  }


  .session-info {

    display: flex;

    flex-direction: column;

    gap: 1px;
  }


  .session-title {

    font-size: 12px;

    font-weight: 500;

    letter-spacing: -0.01em;

    color:
      rgba(255,255,255,0.82);
  }


  .session-subtitle {

    font-size: 9px;

    font-weight: 400;

    letter-spacing: 0.04em;

    color:
      rgba(255,255,255,0.30);

    text-transform: uppercase;
  }


  /* =========================================================
     NEW CHAT
     ========================================================= */

  .new-chat-btn {

    height: 32px;

    display: flex;

    align-items: center;

    gap: 7px;

    padding:
      0 12px;

    border-radius: 8px;

    border:
      1px solid
      rgba(255,255,255,0.11);

    background:
      rgba(255,255,255,0.035);

    color:
      rgba(255,255,255,0.68);

    font-family:
      inherit;

    font-size: 10px;

    font-weight: 500;

    letter-spacing: 0.02em;

    cursor: pointer;

    transition:
      all 0.2s ease;

    box-shadow:
      inset 0 1px 0
      rgba(255,255,255,0.05);
  }


  .new-chat-btn:hover {

    color:
      #ffffff;

    background:
      rgba(255,255,255,0.075);

    border-color:
      rgba(255,255,255,0.20);

    transform:
      translateY(-1px);
  }


  /* =========================================================
     MESSAGES
     ========================================================= */

  .messages-container {

    position: relative;

    flex: 1;

    min-height: 0;

    overflow-y: auto;

    padding:
      30px
      clamp(24px, 5vw, 80px)
      40px;

    display: flex;

    flex-direction: column;

    gap: 28px;

    scroll-behavior: smooth;

    scrollbar-width: thin;

    scrollbar-color:
      rgba(255,255,255,0.12)
      transparent;
  }


  .messages-container::-webkit-scrollbar {

    width: 5px;
  }


  .messages-container::-webkit-scrollbar-track {

    background:
      transparent;
  }


  .messages-container::-webkit-scrollbar-thumb {

    background:
      rgba(255,255,255,0.12);

    border-radius:
      999px;
  }


  .messages-container::-webkit-scrollbar-thumb:hover {

    background:
      rgba(255,255,255,0.20);
  }


  /* =========================================================
     EMPTY STATE
     ========================================================= */

  .empty-state {

    flex: 1;

    display: flex;

    flex-direction: column;

    align-items: center;

    justify-content: center;

    text-align: center;

    padding:
      40px 20px;

    opacity: 0.85;
  }


  .empty-logo {
    width: 54px;
    height: 54px;

    display: flex;
    align-items: center;
    justify-content: center;

    margin-bottom: 20px;
    border-radius: 16px;

    background:
      rgba(255,255,255,0.045);

    border:
      1px solid
      rgba(255,255,255,0.12);

    box-shadow:
      inset 0 1px 0
      rgba(255,255,255,0.1),
      0 12px 36px
      rgba(0,0,0,0.45),
      0 0 24px
      rgba(255,255,255,0.06);
  }

  .empty-logo img {
    width: 36px;
    height: 36px;
    object-fit: contain;
    filter: drop-shadow(0 0 8px rgba(255,255,255,0.3));
  }


  .empty-state h2 {

    margin:
      0 0 8px;

    color:
      rgba(255,255,255,0.90);

    font-size: 22px;

    line-height: 1.2;

    font-weight: 400;

    letter-spacing:
      -0.045em;
  }


  .empty-state p {

    max-width: 390px;

    margin: 0;

    color:
      rgba(255,255,255,0.35);

    font-size: 12px;
    line-height: 1.7;
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .layers-indicator-pill {
    height: 32px;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 0 11px;
    border-radius: 8px;
    border: 1px solid rgba(56, 189, 248, 0.25);
    background: rgba(56, 189, 248, 0.08);
    color: #38bdf8;
    font-size: 10px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .layers-indicator-pill:hover {
    background: rgba(56, 189, 248, 0.16);
    border-color: rgba(56, 189, 248, 0.4);
  }

  .empty-suggestions-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
    margin-top: 24px;
    width: 100%;
    max-width: 520px;
  }

  .suggestion-card {
    display: flex;
    align-items: center;
    gap: 9px;
    padding: 10px 14px;
    background: rgba(255, 255, 255, 0.035);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    color: rgba(255, 255, 255, 0.75);
    font-size: 11px;
    font-weight: 450;
    text-align: left;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .suggestion-card:hover {
    background: rgba(255, 255, 255, 0.075);
    border-color: rgba(255, 255, 255, 0.18);
    color: #ffffff;
    transform: translateY(-1px);
  }

  :global(.suggestion-card .sq-icon) {
    color: rgba(255, 255, 255, 0.4);
    flex-shrink: 0;
  }

  .inline-analyzing-card {
    padding: 14px 18px;
    background: rgba(255, 255, 255, 0.025);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 12px;
  }

  .status-live-tag {
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.06em;
    padding: 2px 7px;
    border-radius: 4px;
    background: rgba(255, 255, 255, 0.08);
    color: #ffffff;
  }

  .analyzing-body {
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-top: 4px;
  }

  .analyzing-headline {
    font-size: 13px;
    font-weight: 500;
    color: rgba(255, 255, 255, 0.9);
  }

  .analysis-steps-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .step-item {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 11px;
    color: rgba(255, 255, 255, 0.35);
    transition: color 0.2s ease;
  }

  .step-item.running {
    color: rgba(255, 255, 255, 0.9);
    font-weight: 500;
  }

  .step-item.completed {
    color: rgba(255, 255, 255, 0.65);
  }

  .step-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 14px;
    height: 14px;
    font-size: 11px;
  }

  .step-icon.done {
    color: #34d399;
  }

  .step-icon.running {
    color: #38bdf8;
    animation: pulseGlow 1.2s infinite ease-in-out;
  }

  .step-icon.pending {
    color: rgba(255, 255, 255, 0.2);
  }

  .attached-asset-chip {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 6px 12px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 8px;
    margin-bottom: 8px;
    animation: slideUp 0.2s ease-out;
  }

  .chip-left {
    display: flex;
    align-items: center;
    gap: 8px;
    overflow: hidden;
  }

  :global(.chip-icon) {
    color: #a78bfa;
    flex-shrink: 0;
  }

  .chip-filename {
    font-size: 11.5px;
    font-weight: 500;
    color: #ffffff;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .chip-badge {
    font-size: 9.5px;
    padding: 1px 6px;
    background: rgba(255, 255, 255, 0.08);
    border-radius: 4px;
    color: rgba(255, 255, 255, 0.7);
    white-space: nowrap;
  }

  .chip-context-label {
    font-size: 9px;
    color: #a78bfa;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-weight: 600;
  }

  .chip-remove-btn {
    background: transparent;
    border: none;
    color: rgba(255, 255, 255, 0.4);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 2px;
    border-radius: 4px;
    transition: color 0.15s ease;
  }

  .chip-remove-btn:hover {
    color: #ffffff;
    background: rgba(255, 255, 255, 0.1);
  }


  /* =========================================================
     USER MESSAGE
     ========================================================= */

  .user-message-row {

    display: flex;

    justify-content: flex-end;

    align-items: flex-start;

    gap: 10px;

    width: 100%;
  }


  .user-message {

    max-width:
      min(620px, 75%);

    padding:
      12px 15px
      10px;

    border-radius:
      16px
      5px
      16px
      16px;

    background:
      linear-gradient(
        145deg,
        rgba(255,255,255,0.075),
        rgba(255,255,255,0.035)
      );

    border:
      1px solid
      rgba(255,255,255,0.105);

    box-shadow:
      inset 0 1px 0
      rgba(255,255,255,0.055),

      0 12px 30px
      rgba(0,0,0,0.22);

    backdrop-filter:
      blur(18px);

    -webkit-backdrop-filter:
      blur(18px);
  }


  .user-message-content {

    color:
      rgba(255,255,255,0.88);

    font-size: 13px;

    line-height: 1.55;

    font-weight: 400;

    letter-spacing:
      -0.008em;

    white-space:
      pre-wrap;

    word-break:
      break-word;
  }


  .user-message-meta {

    display: flex;

    justify-content: flex-end;

    align-items: center;

    gap: 5px;

    margin-top: 7px;

    color:
      rgba(255,255,255,0.25);

    font-size: 8px;

    letter-spacing: 0.03em;
  }


  .user-message-meta :global(svg) {

    color:
      rgba(255,255,255,0.55);
  }





  /* =========================================================
     ASSISTANT
     ========================================================= */

  .assistant-row {

    width: 100%;

    display: flex;

    flex-direction: column;

    align-items: flex-start;
  }


  .assistant-message {

    width: 100%;

    max-width: 850px;

    padding:
      3px 0;
  }


  /* =========================================================
     ASSISTANT HEADER
     ========================================================= */

  .assistant-header {

    display: flex;

    align-items: center;

    gap: 9px;

    margin-bottom: 12px;
  }


  .assistant-logo {

    width: 27px;

    height: 27px;

    display: flex;

    align-items: center;

    justify-content: center;

    border-radius: 8px;

    background:
      rgba(255,255,255,0.045);

    border:
      1px solid
      rgba(255,255,255,0.09);

    box-shadow:
      inset 0 1px 0
      rgba(255,255,255,0.08);
  }


  .assistant-logo img {
    width: 20px;
    height: 20px;
    object-fit: contain;
    filter: drop-shadow(0 0 4px rgba(255, 255, 255, 0.3));
  }


  .assistant-identity {

    display: flex;

    align-items: center;

    gap: 8px;
  }


  .assistant-name {

    color:
      rgba(255,255,255,0.82);

    font-size: 11px;

    font-weight: 600;

    letter-spacing:
      -0.01em;
  }


  .assistant-label {

    padding:
      3px 6px;

    border-radius: 4px;

    color:
      rgba(255,255,255,0.30);

    background:
      rgba(255,255,255,0.035);

    border:
      1px solid
      rgba(255,255,255,0.065);

    font-size: 7px;

    font-weight: 600;

    letter-spacing: 0.12em;
  }


  /* =========================================================
     ASSISTANT CONTENT
     ========================================================= */

  .assistant-content {

    padding-left:
      36px;

    color:
      rgba(255,255,255,0.68);

    font-size: 13px;

    line-height: 1.72;

    letter-spacing:
      -0.008em;
  }


  /* =========================================================
     MARKDOWN
     ========================================================= */

  :global(.assistant-content .md-p) {

    margin:
      0 0 12px;

    color:
      rgba(255,255,255,0.67);

    line-height:
      1.72;
  }


  :global(.assistant-content .md-p:last-child) {

    margin-bottom: 0;
  }


  :global(.assistant-content .md-h3) {

    margin:
      20px 0 8px;

    color:
      rgba(255,255,255,0.92);

    font-size: 15px;

    line-height: 1.35;

    font-weight: 550;

    letter-spacing:
      -0.025em;
  }


  :global(.assistant-content .md-h4) {

    margin:
      16px 0 6px;

    color:
      rgba(255,255,255,0.78);

    font-size: 12px;

    font-weight: 600;
  }


  :global(.assistant-content .md-ul),
  :global(.assistant-content .md-ol) {

    margin:
      8px 0 14px;

    padding-left:
      20px;

    display: flex;

    flex-direction: column;

    gap: 5px;
  }


  :global(.assistant-content .md-li) {

    color:
      rgba(255,255,255,0.64);

    line-height:
      1.6;
  }


  :global(.assistant-content strong) {

    color:
      rgba(255,255,255,0.90);

    font-weight: 600;
  }


  :global(.assistant-content .md-quote) {

    margin:
      14px 0;

    padding:
      10px 14px;

    border-left:
      1px solid
      rgba(255,255,255,0.40);

    border-radius:
      0 8px 8px 0;

    background:
      rgba(255,255,255,0.025);

    color:
      rgba(255,255,255,0.52);

    font-size: 12px;
  }





  /* =========================================================
     INPUT CONTAINER
     ========================================================= */

  .input-container {

    position: relative;

    flex-shrink: 0;

    padding:
      12px
      clamp(20px, 5vw, 80px)
      18px;

    background:
      linear-gradient(
        180deg,
        rgba(5,5,5,0.72),
        rgba(5,5,5,0.96)
      );

    border-top:
      1px solid
      rgba(255,255,255,0.055);

    backdrop-filter:
      blur(24px);

    -webkit-backdrop-filter:
      blur(24px);

    z-index: 5;
  }


  .input-container::before {

    content: "";

    position: absolute;

    top: 0;

    left: 15%;

    width: 70%;

    height: 1px;

    background:
      linear-gradient(
        90deg,
        transparent,
        rgba(255,255,255,0.08),
        transparent
      );
  }


  /* =========================================================
     INPUT HINT
     ========================================================= */

  .input-hint {

    display: flex;

    align-items: center;

    justify-content: center;

    gap: 7px;

    margin-bottom: 7px;

    color:
      rgba(255,255,255,0.18);

    font-size: 7px;

    font-weight: 500;

    letter-spacing: 0.11em;

    text-transform: uppercase;
  }


  .hint-divider {

    opacity: 0.5;
  }


  /* =========================================================
     INPUT BAR
     ========================================================= */

  .input-bar {

    width: 100%;

    max-width: 900px;

    min-height: 54px;

    margin:
      0 auto;

    display: flex;

    align-items: center;

    gap: 8px;

    padding:
      5px 6px 5px 13px;

    box-sizing: border-box;

    border-radius:
      999px;

    background:
      linear-gradient(
        180deg,
        rgba(255,255,255,0.065),
        rgba(255,255,255,0.025)
      );

    border:
      1px solid
      rgba(255,255,255,0.13);

    box-shadow:
      inset 0 1px 0
      rgba(255,255,255,0.075),

      inset 0 -1px 0
      rgba(255,255,255,0.015),

      0 18px 50px
      rgba(0,0,0,0.48);

    backdrop-filter:
      blur(30px)
      saturate(110%);

    -webkit-backdrop-filter:
      blur(30px)
      saturate(110%);

    transition:
      border-color 0.2s ease,
      box-shadow 0.2s ease;
  }


  .input-bar:focus-within {

    border-color:
      rgba(255,255,255,0.24);

    box-shadow:
      inset 0 1px 0
      rgba(255,255,255,0.09),

      0 20px 60px
      rgba(0,0,0,0.58),

      0 0 0 1px
      rgba(255,255,255,0.025);
  }


  /* =========================================================
     ATTACHMENT
     ========================================================= */

  .attach-btn {

    width: 34px;

    height: 34px;

    flex-shrink: 0;

    display: flex;

    align-items: center;

    justify-content: center;

    border: none;

    border-radius: 50%;

    background:
      transparent;

    color:
      rgba(255,255,255,0.34);

    cursor: pointer;

    transition:
      all 0.18s ease;
  }


  .attach-btn:hover {

    color:
      rgba(255,255,255,0.80);

    background:
      rgba(255,255,255,0.055);
  }


  /* =========================================================
     INPUT
     ========================================================= */

  .chat-input {

    flex: 1;

    min-width: 0;

    height: 42px;

    padding: 0 4px;

    border: none;

    outline: none;

    background:
      transparent;

    color:
      rgba(255,255,255,0.88);

    font-family:
      inherit;

    font-size: 12.5px;

    font-weight: 400;

    letter-spacing:
      -0.008em;
  }


  .chat-input::placeholder {

    color:
      rgba(255,255,255,0.30);
  }


  .chat-input:disabled {

    opacity: 0.45;
  }


  /* =========================================================
     SEND
     ========================================================= */

  .send-btn {

    width: 42px;

    height: 42px;

    flex-shrink: 0;

    display: flex;

    align-items: center;

    justify-content: center;

    padding: 0;

    border: 1px solid
      rgba(255,255,255,0.16);

    border-radius: 50%;

    background:
      rgba(255,255,255,0.88);

    color:
      #080808;

    cursor: pointer;

    box-shadow:
      0 3px 15px
      rgba(0,0,0,0.35);

    transition:
      transform 0.18s ease,
      background 0.18s ease,
      opacity 0.18s ease;
  }


  .send-btn:hover:not(:disabled) {

    background:
      #ffffff;

    transform:
      scale(1.045);

    box-shadow:
      0 5px 20px
      rgba(0,0,0,0.50);
  }


  .send-btn:active:not(:disabled) {

    transform:
      scale(0.94);
  }


  .send-btn:disabled {

    opacity: 0.20;

    cursor:
      not-allowed;
  }


  /* =========================================================
     SEND SPINNER
     ========================================================= */

  .send-spinner {

    width: 15px;

    height: 15px;

    border:
      1.5px solid
      rgba(0,0,0,0.22);

    border-top-color:
      #000000;

    border-radius: 50%;

    animation:
      sendSpin 0.75s linear infinite;
  }


  @keyframes sendSpin {

    to {
      transform:
        rotate(360deg);
    }

  }


  /* =========================================================
     RESPONSIVE
     ========================================================= */

  @media (max-width: 900px) {

    .messages-container {

      padding-left: 24px;

      padding-right: 24px;
    }


    .input-container {

      padding-left: 24px;

      padding-right: 24px;
    }


    .assistant-content {

      padding-left: 0;
    }

  }


  @media (max-width: 600px) {

    .chat-header-bar {

      padding:
        0 14px;
    }


    .session-subtitle {

      display: none;
    }


    .new-chat-btn span {

      display: none;
    }


    .new-chat-btn {

      width: 32px;

      padding: 0;

      justify-content: center;
    }


    .messages-container {

      padding:
        20px
        14px
        30px;

      gap: 22px;
    }


    .user-message {

      max-width: 82%;
    }


    .input-container {

      padding:
        9px
        12px
        12px;
    }


    .input-hint {

      display: none;
    }


    .input-bar {

      min-height: 52px;
    }


    .chat-input {

      font-size: 12px;
    }

  /* =========================================================
     AI MODE & INPUT CONTROLS
     ========================================================= */

  .input-controls-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 4px 6px;
    gap: 8px;
  }

  .ai-mode-selector-wrap {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 6px;
    padding: 2px 8px;
  }

  .ai-mode-label {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 10px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.5);
    letter-spacing: 0.04em;
    cursor: pointer;
  }

  .ai-mode-select {
    background: transparent;
    border: none;
    color: #48bb78;
    font-size: 11px;
    font-weight: 600;
    font-family: var(--font-ui);
    cursor: pointer;
    outline: none;
    padding: 2px 4px;
  }

  .ai-mode-select option {
    background: #111;
    color: #eee;
  }

  .ai-mode-badge {
    display: inline-block;
    background: rgba(56, 178, 172, 0.12);
    border: 1px solid rgba(56, 178, 172, 0.25);
    color: #38b2ac;
    font-size: 9px;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 4px;
    letter-spacing: 0.05em;
  }

  /* =========================================================
     EARTH TELEMETRY PILL & READING GUIDE
     ========================================================= */

  .earth-telemetry-container {
    margin-top: 8px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .earth-telemetry-pill {
    display: inline-flex;
    align-items: center;
    justify-content: space-between;
    background: rgba(18, 24, 34, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.09);
    border-radius: 9999px;
    padding: 4px 10px 4px 8px;
    gap: 10px;
    font-size: 11px;
    backdrop-filter: blur(8px);
    width: fit-content;
    max-width: 100%;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.35);
  }

  .pill-left {
    display: flex;
    align-items: center;
    gap: 6px;
    color: #94a3b8;
  }

  :global(.pill-globe-icon) {
    color: #38bdf8;
  }

  .pill-main-label {
    font-weight: 600;
    color: #e2e8f0;
    font-size: 11px;
    letter-spacing: 0.01em;
  }

  .pill-divider {
    color: rgba(255, 255, 255, 0.2);
    font-size: 10px;
  }

  .pill-layer-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 9999px;
    padding: 1px 7px;
    font-size: 10px;
    font-weight: 500;
    color: #cbd5e1;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .pill-layer-badge:hover {
    background: rgba(255, 255, 255, 0.12);
    color: #ffffff;
    border-color: rgba(255, 255, 255, 0.2);
  }

  .pill-vis-type {
    font-size: 9px;
    font-weight: 700;
    padding: 1px 6px;
    border-radius: 4px;
    background: rgba(56, 189, 248, 0.1);
    color: #38bdf8;
    border: 1px solid rgba(56, 189, 248, 0.2);
    letter-spacing: 0.04em;
  }

  .pill-right {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .pill-action-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 10.5px;
    font-weight: 500;
    background: transparent;
    border: none;
    color: #94a3b8;
    padding: 2px 6px;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .pill-action-btn:hover {
    color: #e2e8f0;
    background: rgba(255, 255, 255, 0.06);
  }

  .reading-guide-btn {
    color: #38bdf8;
  }

  .reading-guide-btn:hover {
    color: #7dd3fc;
    background: rgba(56, 189, 248, 0.1);
  }

  .vis-guide-panel {
    background: rgba(14, 18, 26, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 10px 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }



  /* =========================================================
     PROGRESSIVE DISCLOSURE VISUALIZATION EXPLANATION
     ========================================================= */

  .vis-summary-banner {
    background: rgba(255, 255, 255, 0.03);
    border-left: 3px solid #4299e1;
    border-radius: 4px;
    padding: 6px 10px;
  }

  .vis-summary-label {
    display: block;
    font-size: 8.5px;
    font-weight: 700;
    color: #63b3ed;
    letter-spacing: 0.05em;
    margin-bottom: 2px;
  }

  .vis-summary-text {
    margin: 0;
    font-size: 11.5px;
    color: #e2e8f0;
    line-height: 1.4;
  }

  .vis-key-obs-banner {
    background: rgba(72, 187, 120, 0.06);
    border-left: 3px solid #48bb78;
    border-radius: 4px;
    padding: 6px 10px;
  }

  .vis-key-obs-label {
    display: block;
    font-size: 8.5px;
    font-weight: 700;
    color: #48bb78;
    letter-spacing: 0.05em;
    margin-bottom: 2px;
  }

  .vis-key-obs-text {
    margin: 0;
    font-size: 11.5px;
    color: #e2e8f0;
    line-height: 1.4;
  }

  .vis-explanation-progressive {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-top: 4px;
  }

  .disclosure-card {
    background: rgba(0, 0, 0, 0.35);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 6px;
    overflow: hidden;
  }

  .disclosure-toggle {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 7px 10px;
    background: transparent;
    border: none;
    color: #cbd5e0;
    font-size: 11px;
    font-weight: 600;
    cursor: pointer;
    text-align: left;
    transition: background 0.15s ease;
  }

  .disclosure-toggle:hover {
    background: rgba(255, 255, 255, 0.04);
    color: #edf2f7;
  }

  .disclosure-title {
    color: #63b3ed;
  }

  .disclosure-content {
    padding: 8px 10px;
    border-top: 1px solid rgba(255, 255, 255, 0.04);
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-size: 11px;
  }

  .disclosure-item {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .disclosure-item p {
    margin: 0;
    color: #e2e8f0;
    line-height: 1.4;
  }

  .disclosure-item .item-tag {
    font-size: 8px;
    font-weight: 700;
    color: rgba(255, 255, 255, 0.45);
    letter-spacing: 0.05em;
  }

  .technical-callout {
    background: rgba(147, 51, 234, 0.08);
    border-left: 2px solid #a855f7;
    padding: 4px 6px;
    border-radius: 3px;
  }

  /* =========================================================
     GROUNDED WEB EVIDENCE
     ========================================================= */

  .web-evidence-card {
    background: rgba(14, 18, 26, 0.5);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 8px;
    padding: 10px 12px;
    margin-top: 10px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .evidence-header {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .evidence-icon {
    color: #38b2ac;
  }

  .evidence-title {
    font-size: 9.5px;
    font-weight: 700;
    letter-spacing: 0.05em;
    color: #38b2ac;
  }

  .evidence-items-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .ref-photo-card {
    background: rgba(0, 0, 0, 0.35);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 6px;
    padding: 8px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .ref-photo-badge-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }

  .ref-photo-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: rgba(246, 173, 85, 0.15);
    border: 1px solid rgba(246, 173, 85, 0.3);
    color: #f6ad55;
    font-size: 9px;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 4px;
    letter-spacing: 0.04em;
  }

  .ref-source-domain {
    font-size: 9px;
    color: rgba(255, 255, 255, 0.4);
  }

  .ref-photo-content {
    display: flex;
    gap: 10px;
    align-items: flex-start;
  }

  .ref-thumb-img {
    width: 72px;
    height: 72px;
    object-fit: cover;
    border-radius: 4px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    flex-shrink: 0;
  }

  .ref-photo-details {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  .ref-photo-title {
    margin: 0;
    font-size: 11.5px;
    font-weight: 600;
    color: #e2e8f0;
  }

  .ref-photo-snippet {
    margin: 0;
    font-size: 10.5px;
    color: rgba(255, 255, 255, 0.65);
    line-height: 1.35;
  }

  .ref-source-link {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 10px;
    color: #63b3ed;
    text-decoration: none;
    margin-top: 2px;
  }

  .ref-source-link:hover {
    text-decoration: underline;
  }

  .evidence-text-card {
    background: rgba(0, 0, 0, 0.25);
    border: 1px solid rgba(255, 255, 255, 0.04);
    border-radius: 6px;
    padding: 8px 10px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .evidence-text-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }

  .evidence-item-title {
    font-size: 11px;
    font-weight: 600;
    color: #edf2f7;
  }

  .evidence-snippet {
    margin: 0;
    font-size: 10.5px;
    color: rgba(255, 255, 255, 0.65);
    line-height: 1.35;
  }
}
</style>