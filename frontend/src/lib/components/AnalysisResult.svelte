<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import {
    showAuditTraceModal,
    globeLocation,
    activeDataLayers,
    type NormalizedResult,
    type EvidenceItem,
    type DataLayerSpec,
  } from '../stores';
  import EChartRenderer from './EChartRenderer.svelte';
  import ChatEvidenceImage from './ChatEvidenceImage.svelte';
  import ImageComparisonSlider from './ImageComparisonSlider.svelte';
  import VisualizationRenderer from './VisualizationRenderer.svelte';

  import {
    Maximize2,
    TrendingUp,
    Crosshair,
    Layers,
    Activity,
    ExternalLink,
    Sparkles,
    CheckCircle2,
    X,
    AlertTriangle,
    Database,
    Cpu,
    Box,
    Eye,
    EyeOff,
    Sliders,
  } from 'lucide-svelte';

  export let result: NormalizedResult;
  export let content: string = '';
  export let timestamp: string = '';

  const dispatch = createEventDispatcher<{
    submitQuery: string;
    actionClick: string;
  }>();

  $: presPlan = result?.presentation_plan;
  $: evidenceItems = presPlan?.evidence_items || result?.evidence_items || [];
  $: primaryEvidence = evidenceItems.find((i) => i.id === presPlan?.primary_evidence_id) || evidenceItems.find((i) => i.type === 'optical_scene') || (evidenceItems.length > 0 ? evidenceItems[0] : null);
  $: baselineEvidence = evidenceItems.find((i) => i.id === presPlan?.baseline_evidence_id) || evidenceItems.find((i) => i.type === 'optical_baseline') || null;
  $: differenceItem = evidenceItems.find((i) => i.type === 'sar_change' || i.type === 'change_map' || i.type === 'difference') || null;
  $: hasBaseline = presPlan ? presPlan.has_baseline : (baselineEvidence != null);
  $: baselineReason = presPlan?.baseline_missing_reason || 'No pre-event optical baseline meeting the quality constraints was found in the catalog prior to the event window.';
  $: methodInfo = presPlan?.method;
  $: limitationsList = presPlan?.limitations || [];

  let isSplitCompare: boolean = false;

  type PrimaryTab = 'satellite' | 'timeline' | 'ndvi' | 'sar' | 'change' | '3d' | 'terrain';
  let activeTab: PrimaryTab = 'satellite';

  $: ndviEvidence = evidenceItems.find((i) => i.type === 'ndvi' || i.rendering === 'ndvi') || null;
  $: sarEvidence = evidenceItems.find((i) => i.type?.includes('sar') || i.rendering?.includes('sar')) || null;
  $: changeEvidence = differenceItem || evidenceItems.find((i) => i.type === 'change_map' || i.type === 'sar_change' || i.type === 'flood_extent') || null;

  $: visualizations = result?.visualizations || [];
  let activeVisIndex = 0;
  $: if (activeVisIndex >= visualizations.length) {
    activeVisIndex = 0;
  }
  $: currentVis = visualizations[activeVisIndex] || null;

  $: visPlan = result?.visualization_plan;
  $: active3dGrid = (result as any)?.surface_grid || currentVis?.surface_grid || null;
  $: activeExplanation = currentVis?.explanation || visPlan?.explanation || null;
  $: dataAvailability = (result as any)?.data_availability || [];
  $: temporalObservations = (result as any)?.temporal_observations || [];

  function toggleLayerVisibility(layerId: string) {
    activeDataLayers.update((layers) =>
      layers.map((l) => (l.layer_id === layerId ? { ...l, visible: l.visible === false } : l))
    );
  }

  function updateLayerOpacity(layerId: string, opacity: number) {
    activeDataLayers.update((layers) =>
      layers.map((l) => (l.layer_id === layerId ? { ...l, style: { ...(l.style || {}), opacity } } : l))
    );
  }

  function focusLayer(layer: any) {
    const bounds = layer.spatial?.bounds || layer.bbox;
    if (bounds && bounds.length === 4) {
      const lon = (bounds[0] + bounds[2]) / 2;
      const lat = (bounds[1] + bounds[3]) / 2;
      globeLocation.update((g) => ({
        ...g,
        latitude: lat,
        longitude: lon,
        altitude: 45000,
        bbox: bounds,
        name: layer.title,
        flyTrigger: g.flyTrigger + 1,
      }));
    }
  }

  // Auto-switch tab if query intent matches
  $: {
    const qLower = (content || result?.key_finding || '').toLowerCase();
    if (qLower.includes('terrain') || qLower.includes('dem') || qLower.includes('elevation')) {
      activeTab = 'terrain';
    } else if (qLower.includes('point cloud') || (qLower.includes('3d') && !qLower.includes('dem'))) {
      activeTab = '3d';
    } else if (qLower.includes('over time') || qLower.includes('trend') || qLower.includes('decade') || (result?.time_series && result.time_series.length > 1 && !primaryEvidence?.image_url)) {
      activeTab = 'timeline';
    } else if (qLower.includes('sar') || qLower.includes('radar')) {
      activeTab = 'sar';
    } else if (qLower.includes('change') && (hasBaseline || changeEvidence)) {
      activeTab = 'change';
    }
  }

  let modalImage: { url: string; label: string; date: string } | null = null;

  $: displayContent = content || result?.scientific_explanation || result?.key_finding || '';
  $: chartPoints = (result?.time_series || []).filter((point: any) => Number.isFinite(Number(point.value)));
  $: chartData = chartPoints.map((point: any) => ({
    ...point,
    value: Number(point.value),
    label: point.date,
  }));


  import { parseMarkdown } from '../markdown';

  function handleAction(action: string) {
    if (action === 'timeseries') {
      const idx = visualizations.findIndex((v: any) => v.type === 'timeseries' || v.title?.toLowerCase().includes('time series'));
      if (idx !== -1) activeVisIndex = idx;
    }
    dispatch('actionClick', action);
  }

  function handleFocusGlobe(item?: EvidenceItem | null) {
    if (item && item.bbox && item.bbox.length === 4) {
      const centerLon = (item.bbox[0] + item.bbox[2]) / 2;
      const centerLat = (item.bbox[1] + item.bbox[3]) / 2;
      globeLocation.update((g) => ({
        ...g,
        latitude: centerLat,
        longitude: centerLon,
        name: item.aoi_name || g.name,
        polygon: [
          [item.bbox[0], item.bbox[1]],
          [item.bbox[2], item.bbox[1]],
          [item.bbox[2], item.bbox[3]],
          [item.bbox[0], item.bbox[3]],
          [item.bbox[0], item.bbox[1]],
        ],
        flyTrigger: g.flyTrigger + 1,
      }));
    }
    dispatch('actionClick', 'aoi');
  }

  function handleOpenLayer(item?: EvidenceItem | null) {
    if (!item || (!item.image_url && item.type !== 'flood_extent') || item.available === false) return;
    const layerId = item.cesium_layer_id || `layer_${item.id}`;

    activeDataLayers.update((existing) => {
      const idx = existing.findIndex((l) => l.layer_id === layerId);
      if (idx !== -1) {
        const copy = [...existing];
        copy[idx] = { ...copy[idx], visible: !copy[idx].visible };
        return copy;
      }
      const specFromItem = (item as any).data_layer_spec;
      const newLayer: DataLayerSpec = specFromItem ? {
        ...specFromItem,
        layer_id: layerId,
        visible: true,
      } : {
        layer_id: layerId,
        type: item.type === 'flood_extent' ? 'flood_extent' : 'imagery',
        title: item.title,
        description: item.description || item.title,
        role: 'evidence',
        source: { type: 'image', url: item.image_url || '' },
        spatial: { bounds: item.bbox },
        temporal: { acquisition_date: item.acquisition_date },
        style: { opacity: 0.85 },
        visible: true,
        provenance: {
          dataset_id: item.dataset_id,
          model_id: methodInfo?.model || 'specialist',
          source: item.source,
          date: item.acquisition_date,
          resolution: `${item.resolution_m}m`,
        },
      };
      return [newLayer, ...existing];
    });

    handleFocusGlobe(item);
  }

  function handleSyncCesiumComparison(target: 'before' | 'current' | 'difference') {
    const targetItem = target === 'before' ? baselineEvidence : (target === 'current' ? primaryEvidence : differenceItem);
    if (targetItem) {
      handleOpenLayer(targetItem);
    }
  }

  function handleExpandEvidence(item: EvidenceItem) {
    modalImage = {
      url: resolveAssetUrl(item.image_url || ''),
      label: item.title,
      date: item.acquisition_date,
    };
  }

  function handleCompareEvidence() {
    isSplitCompare = !isSplitCompare;
  }

  function handleSuggested(q: string) {
    dispatch('submitQuery', q);
  }

  function openImageModal(url: string, label: string, date: string) {
    modalImage = { url, label, date };
  }

  function closeImageModal() {
    modalImage = null;
  }

  function resolveAssetUrl(url: string): string {
    if (!url) return '';
    if (/^https?:\/\//.test(url)) return url;
    return `${window.location.origin}${url.startsWith('/') ? url : `/${url}`}`;
  }
</script>

<div class="analysis-result-card">
  <!-- Assistant Header -->
  <div class="result-header">
    <div class="header-left">
      <div class="logo-box">
        <img src="/satquery_logo.png" alt="SatQuery AI" class="logo-img" />
      </div>
      <div class="model-info">
        <div class="name-row">
          <span class="brand-name">SatQuery <span class="ai-text">AI</span></span>
          <span class="reasoning-badge">
            <Sparkles size={11} />
            GPT-OSS 120B
          </span>
        </div>
        <span class="model-pipeline">
          {result?.provenance?.execution_status === 'unavailable' || result?.provenance?.source === 'unavailable' ? 'Specialist Model Unavailable' : (result?.provenance?.model_name || 'Model Unavailable')} • Remote Sensing Agent
        </span>
      </div>
    </div>

    <div class="header-right">
      {#if timestamp}
        <span class="result-time">{timestamp.split('T')[1]?.slice(0, 5) || '10:24 AM'}</span>
      {/if}
      {#if result?.confidence != null && result?.provenance?.source !== 'mock' && result?.provenance?.source !== 'unavailable'}
        <div class="confidence-pill" class:high={result.confidence >= 0.9} title="Algorithmic model prediction confidence (not ground-validated accuracy)">
          <CheckCircle2 size={12} />
          <span>{Math.round(result.confidence * 100)}% Model Confidence</span>
        </div>
      {:else}
        <div class="confidence-pill measured" title="Model confidence not provided by specialist worker">
          <CheckCircle2 size={12} />
          <span>Confidence: Not provided</span>
        </div>
      {/if}
    </div>
  </div>

  {#if presPlan}
    <!-- 1. Investigation Title -->
    <div class="investigation-title-block">
      <span class="investigation-label">INVESTIGATION</span>
      <h3 class="investigation-title">{presPlan.title || 'Earth Observation Assessment'}</h3>
    </div>

    <!-- Primary Visualization Switcher (Part 10 / UI UX) -->
    <div class="primary-vis-switcher">
      <button 
        class="switcher-tab-btn" 
        class:active={activeTab === 'satellite'}
        on:click={() => (activeTab = 'satellite')}
        title="View optical satellite scene and baseline"
      >
        <Layers size={12} />
        <span>Satellite</span>
      </button>

      <button 
        class="switcher-tab-btn" 
        class:active={activeTab === 'timeline'}
        on:click={() => (activeTab = 'timeline')}
        title="View multi-year observation timeline & trajectory"
      >
        <Activity size={12} />
        <span>Timeline</span>
      </button>

      <button 
        class="switcher-tab-btn" 
        class:active={activeTab === 'ndvi'}
        on:click={() => (activeTab = 'ndvi')}
        title="View NDVI vegetation canopy vigor index"
      >
        <TrendingUp size={12} />
        <span>NDVI</span>
      </button>

      <button 
        class="switcher-tab-btn" 
        class:active={activeTab === 'sar'}
        on:click={() => (activeTab = 'sar')}
        title="View Sentinel-1 SAR radar backscatter & polarimetry"
      >
        <Crosshair size={12} />
        <span>SAR</span>
      </button>

      <button 
        class="switcher-tab-btn" 
        class:active={activeTab === 'change'}
        on:click={() => (activeTab = 'change')}
        title="View bi-temporal landscape conversion and disturbance"
      >
        <Sparkles size={12} />
        <span>Change</span>
      </button>

      <button 
        class="switcher-tab-btn" 
        class:active={activeTab === '3d'}
        on:click={() => (activeTab = '3d')}
        title="View 3D scientific point cloud or response surface"
      >
        <Box size={12} />
        <span>3D</span>
      </button>

      <button 
        class="switcher-tab-btn" 
        class:active={activeTab === 'terrain'}
        on:click={() => (activeTab = 'terrain')}
        title="View Copernicus DEM GLO-30 3D topographic relief"
      >
        <Layers size={12} />
        <span>Terrain</span>
      </button>
    </div>

    <!-- Primary Canvas Container -->
    <div class="primary-canvas-container">
      {#if activeTab === 'satellite'}
        <div class="evidence-images-section">
          {#if primaryEvidence}
            <div class="evidence-sub-block">
              <h4 class="evidence-block-title">Current optical image</h4>
              <ChatEvidenceImage
                item={primaryEvidence}
                badge="Current Optical Image"
                isBaseline={false}
                hasComparePartner={hasBaseline && !!baselineEvidence}
                on:focusGlobe={(e) => handleFocusGlobe(e.detail.item)}
                on:openLayer={(e) => handleOpenLayer(e.detail.item)}
                on:expand={(e) => handleExpandEvidence(e.detail.item)}
                on:compare={handleCompareEvidence}
              />
            </div>
          {/if}

          {#if hasBaseline && baselineEvidence && baselineEvidence.available && baselineEvidence.image_url && primaryEvidence && primaryEvidence.available && primaryEvidence.image_url}
            <div class="evidence-sub-block">
              <h4 class="evidence-block-title">{presPlan?.baseline_role === 'temporal_baseline' ? 'Observation vs Earlier temporal baseline' : 'Before / after comparison'}</h4>
              <ImageComparisonSlider
                beforeItem={baselineEvidence}
                currentItem={primaryEvidence}
                differenceItem={differenceItem}
                on:focusGlobe={(e) => handleFocusGlobe(e.detail.item)}
                on:syncCesium={(e) => handleSyncCesiumComparison(e.detail.mode)}
                on:expand={(e) => openImageModal(e.detail.url, e.detail.label, '')}
              />
            </div>
          {:else if hasBaseline && baselineEvidence}
            <div class="evidence-sub-block">
              <h4 class="evidence-block-title">{presPlan?.baseline_role === 'temporal_baseline' ? 'Earlier temporal baseline' : 'Before-event baseline'}</h4>
              <ChatEvidenceImage
                item={baselineEvidence}
                badge={presPlan?.baseline_role === 'temporal_baseline' ? 'Earlier Temporal Baseline' : 'Before-Event Baseline'}
                isBaseline={true}
                hasComparePartner={!!primaryEvidence}
                on:focusGlobe={(e) => handleFocusGlobe(e.detail.item)}
                on:openLayer={(e) => handleOpenLayer(e.detail.item)}
                on:expand={(e) => handleExpandEvidence(e.detail.item)}
                on:compare={handleCompareEvidence}
              />
            </div>
          {:else if presPlan.baseline_missing_reason}
            <div class="evidence-sub-block">
              <h4 class="evidence-block-title">{presPlan?.baseline_role === 'temporal_baseline' ? 'Earlier temporal baseline' : 'Before-event baseline'}</h4>
              <div class="baseline-missing-card">
                <div class="missing-badge-row">
                  <AlertTriangle size={13} class="missing-icon" />
                  <span class="missing-badge">BASELINE OBSERVATION UNAVAILABLE</span>
                </div>
                <p class="missing-reason">{baselineReason}</p>
              </div>
            </div>
          {/if}
        </div>

      {:else if activeTab === 'timeline'}
        <div class="canvas-panel-view">
          <div class="canvas-header-bar">
            <span class="canvas-view-tag">LONGITUDINAL TEMPORAL TRAJECTORY</span>
            <span class="canvas-source-tag">Sentinel-2 Multi-Temporal Observations</span>
          </div>
          {#if chartData.length > 0}
            <div class="canvas-chart-wrapper">
              <EChartRenderer
                type="line"
                title=""
                subTitle=""
                data={chartData}
                height="280px"
              />
            </div>
          {:else}
            <div class="canvas-empty-state">
              <AlertTriangle size={16} class="empty-icon" />
              <p>No multi-year numerical time series records available for this study area.</p>
            </div>
          {/if}
        </div>

      {:else if activeTab === 'ndvi'}
        <div class="canvas-panel-view">
          <div class="canvas-header-bar">
            <span class="canvas-view-tag">NORMALIZED DIFFERENCE VEGETATION INDEX (NDVI)</span>
            <span class="canvas-source-tag">Sentinel-2 B08/B04 (10m GSD)</span>
          </div>
          {#if ndviEvidence}
            <ChatEvidenceImage
              item={ndviEvidence}
              badge="NDVI Radiometric Index"
              on:focusGlobe={(e) => handleFocusGlobe(e.detail.item)}
              on:openLayer={(e) => handleOpenLayer(e.detail.item)}
              on:expand={(e) => handleExpandEvidence(e.detail.item)}
            />
          {:else if chartData.length > 0}
            <div class="canvas-chart-wrapper">
              <EChartRenderer
                type="line"
                title=""
                subTitle=""
                data={chartData}
                height="280px"
              />
            </div>
          {:else}
            <div class="canvas-empty-state">
              <p>NDVI map layer is rendering directly on the 3D globe.</p>
            </div>
          {/if}
        </div>

      {:else if activeTab === 'sar'}
        <div class="canvas-panel-view">
          <div class="canvas-header-bar">
            <span class="canvas-view-tag">SYNTHETIC APERTURE RADAR (SAR)</span>
            <span class="canvas-source-tag">Sentinel-1 C-Band SAR GRD</span>
          </div>
          {#if sarEvidence}
            <ChatEvidenceImage
              item={sarEvidence}
              badge="Sentinel-1 SAR Amplitude"
              on:focusGlobe={(e) => handleFocusGlobe(e.detail.item)}
              on:openLayer={(e) => handleOpenLayer(e.detail.item)}
              on:expand={(e) => handleExpandEvidence(e.detail.item)}
            />
          {:else}
            <div class="canvas-empty-state">
              <p>Sentinel-1 SAR GRD backscatter layer is active on the 3D globe.</p>
            </div>
          {/if}
        </div>

      {:else if activeTab === 'change'}
        <div class="canvas-panel-view">
          <div class="canvas-header-bar">
            <span class="canvas-view-tag">BI-TEMPORAL DISTURBANCE & CHANGE</span>
            <span class="canvas-source-tag">Prithvi-EO-2.0 / Specialist ML</span>
          </div>
          {#if changeEvidence}
            <ChatEvidenceImage
              item={changeEvidence}
              badge="Change Detection Footprint"
              on:focusGlobe={(e) => handleFocusGlobe(e.detail.item)}
              on:openLayer={(e) => handleOpenLayer(e.detail.item)}
              on:expand={(e) => handleExpandEvidence(e.detail.item)}
            />
          {:else if hasBaseline && baselineEvidence && primaryEvidence}
            <ImageComparisonSlider
              beforeItem={baselineEvidence}
              currentItem={primaryEvidence}
              differenceItem={differenceItem}
              on:focusGlobe={(e) => handleFocusGlobe(e.detail.item)}
              on:syncCesium={(e) => handleSyncCesiumComparison(e.detail.mode)}
              on:expand={(e) => openImageModal(e.detail.url, e.detail.label, '')}
            />
          {:else}
            <div class="canvas-empty-state">
              <p>Change detection vector layer is active on the 3D globe.</p>
            </div>
          {/if}
        </div>

      {:else if activeTab === '3d'}
        <div class="canvas-panel-view">
          <div class="canvas-header-bar">
            <span class="canvas-view-tag">3D SCIENTIFIC POINT CLOUD</span>
            <span class="canvas-source-tag">Sampled Spatial Grid (Zero synthetic math)</span>
          </div>
          <div class="canvas-3d-wrapper">
            {#if active3dGrid && active3dGrid.length > 0}
              <VisualizationRenderer
                activeMode="3D Point Cloud"
                spec={{
                  type: 'point_cloud',
                  title: '3D Scientific Point Cloud',
                  surface_grid: active3dGrid,
                  surface_opacity: 0.85,
                  vertical_exaggeration: 2.2,
                  legend_min: 0,
                  legend_max: 1,
                  legend_unit: 'Index',
                }}
              />
            {:else}
              <div class="canvas-empty-state">
                <p class="empty-state-title">3D Point Cloud Unavailable</p>
                <p class="empty-state-desc">No raster grid was returned for 3D point cloud generation for this target area.</p>
              </div>
            {/if}
          </div>
        </div>

      {:else if activeTab === 'terrain'}
        <div class="canvas-panel-view">
          <div class="canvas-header-bar">
            <span class="canvas-view-tag">COPERNICUS DEM GLO-30 3D TERRAIN</span>
            <span class="canvas-source-tag">Digital Surface Model (30m GSD)</span>
          </div>
          <div class="canvas-3d-wrapper">
            {#if active3dGrid && active3dGrid.length > 0}
              <VisualizationRenderer
                activeMode="3D Surface"
                spec={{
                  type: '3d_surface',
                  title: 'Copernicus DEM 3D Surface',
                  surface_grid: active3dGrid,
                  surface_opacity: 0.9,
                  vertical_exaggeration: 2.5,
                  legend_min: 0,
                  legend_max: 4500,
                  legend_unit: 'm AMSL',
                }}
              />
            {:else}
              <div class="canvas-empty-state">
                <p class="empty-state-title">3D Terrain Surface Unavailable</p>
                <p class="empty-state-desc">Copernicus DEM elevation raster is unavailable for the selected AOI window.</p>
              </div>
            {/if}
          </div>
        </div>
      {/if}
    </div>

    <!-- Grounded Factual Explanation Card (Part 8 / Part 10) -->
    {#if activeExplanation}
      <div class="grounded-explanation-card">
        <div class="card-header-row">
          <div class="badge-title">
            <span class="canon-badge">FACTUAL GROUNDING</span>
            <h4 class="canon-title">{activeExplanation.title || 'Earth Observation Telemetry'}</h4>
          </div>
          <span class="source-tag">{activeExplanation.data_source || 'Sentinel-2 / Copernicus DEM'}</span>
        </div>

        <div class="canon-grid">
          {#if activeExplanation.what_it_shows}
            <div class="canon-field full-width">
              <span class="field-label">WHAT IT SHOWS</span>
              <p class="field-content">{activeExplanation.what_it_shows}</p>
            </div>
          {/if}

          {#if activeExplanation.variables && activeExplanation.variables.length > 0}
            <div class="canon-field">
              <span class="field-label">VARIABLES MEASURED</span>
              <div class="var-pills">
                {#each activeExplanation.variables as v}
                  <span class="var-pill">{v}</span>
                {/each}
              </div>
            </div>
          {/if}

          {#if activeExplanation.how_to_read}
            <div class="canon-field">
              <span class="field-label">HOW TO READ</span>
              <p class="field-content">{activeExplanation.how_to_read}</p>
            </div>
          {/if}

          {#if activeExplanation.why_it_matters}
            <div class="canon-field">
              <span class="field-label">WHY IT MATTERS</span>
              <p class="field-content">{activeExplanation.why_it_matters}</p>
            </div>
          {/if}

          {#if activeExplanation.limitations}
            <div class="canon-field full-width">
              <span class="field-label">LIMITATIONS</span>
              <p class="field-content warning-text">{activeExplanation.limitations}</p>
            </div>
          {/if}
        </div>
      </div>
    {/if}

    <!-- 3. Change Analysis (GPT-OSS grounded explanation) -->
    <div class="change-analysis-block">
      <h4 class="evidence-block-title">Scientific Telemetry Assessment</h4>
      <div class="gpt-response-content">
        {@html parseMarkdown(displayContent)}
      </div>

      <!-- Explicit Decoupling of Observation vs Advisory for Agricultural Queries -->
      {#if displayContent.toLowerCase().includes('apple') || displayContent.toLowerCase().includes('farm') || displayContent.toLowerCase().includes('crop')}
        <div class="unobserved-advisory-box">
          <div class="advisory-title-row">
            <AlertTriangle size={12} class="advisory-icon" />
            <span class="advisory-title">WHAT IS NOT OBSERVABLE FROM SATELLITE TELEMETRY</span>
          </div>
          <ul class="unobserved-list">
            <li><strong>Cadastral Property Lines:</strong> Exact individual farm plot boundaries and ownership rights cannot be determined from optical orbiters without local land registry cadastre GIS vectors.</li>
            <li><strong>Sub-Surface Moisture:</strong> Sentinel-2 optical bands measure top-of-canopy photosynthesis; deep root-zone water content requires in-situ moisture sensors or L-band microwave probes.</li>
            <li><strong>Tree-Level Yield / Fruit Grading:</strong> 10m spatial resolution integrates canopy blocks and does not measure per-tree yield, fruit caliber, or subterranean root pests.</li>
          </ul>
        </div>
      {/if}
    </div>


    <!-- 4. Evidence Layers (Phase 25 & 27: Active vs Available Layers) -->
    <div class="evidence-layers-block">
      <div class="layers-section-header">
        <h4 class="evidence-block-title">Investigation Layers</h4>
        <span class="layers-count-badge">
          {$activeDataLayers.filter((l) => l.visible !== false).length} Active / {$activeDataLayers.length} Registered
        </span>
      </div>

      <!-- Quick Toggle Pill Row -->
      <div class="layers-pill-row">
        {#each evidenceItems as evItem}
          {@const isLayerActive = $activeDataLayers.some((l) => l.layer_id === (evItem.cesium_layer_id || `layer_${evItem.id}`) && l.visible !== false)}
          {@const pillLabel = evItem.type === 'flood_extent' ? '[Flood Extent]' :
                              evItem.type === 'sar_change' ? '[SAR Change]' :
                              evItem.type === 'sar_vh' || (evItem.type === 'sar_amplitude' && evItem.title?.toLowerCase().includes('vh')) ? '[SAR VH]' :
                              evItem.type === 'sar_vv' || (evItem.type === 'sar_amplitude' && evItem.title?.toLowerCase().includes('vv')) ? '[SAR VV]' :
                              evItem.rendering === 'ndwi' || evItem.type === 'ndwi' ? '[NDWI]' :
                              evItem.rendering === 'ndvi' || evItem.type === 'ndvi' ? '[NDVI]' :
                              evItem.type === 'terrain_dem' || evItem.rendering === 'elevation' ? '[DEM Terrain]' :
                              (evItem.role === 'baseline' || evItem.type === 'optical_baseline') ? '[Baseline Optical]' :
                              (evItem.role === 'current' || evItem.type === 'optical_scene') ? '[Current Optical]' :
                              `[${evItem.rendering?.replace(/_/g, ' ')?.toUpperCase() || 'DATA'}]`}
          <button
            class="layer-pill"
            class:active={isLayerActive}
            on:click={() => handleOpenLayer(evItem)}
            title={`Toggle & focus ${evItem.title} on 3D globe`}
          >
            <span class="layer-dot"></span>
            <span class="layer-pill-title">{pillLabel}</span>
          </button>
        {/each}
      </div>

      <!-- Detailed Active vs Available Layer Cards -->
      {#if $activeDataLayers.length > 0}
        <div class="layer-management-container">
          <!-- Active Layers -->
          <div class="layer-group active-group">
            <div class="group-heading">
              <span class="group-dot active"></span>
              <span class="group-title">ACTIVE LAYERS ({$activeDataLayers.filter((l) => l.visible !== false).length})</span>
            </div>
            <div class="layer-cards-grid">
              {#each $activeDataLayers.filter((l) => l.visible !== false) as layer}
                <div class="layer-manager-card active">
                  <div class="card-left">
                    <button
                      class="visibility-toggle-btn active"
                      on:click={() => toggleLayerVisibility(layer.layer_id)}
                      title="Hide layer on 3D globe"
                    >
                      <Eye size={13} />
                    </button>
                    <div class="card-details">
                      <span class="card-title">{layer.title}</span>
                      <div class="card-meta-chips">
                        <span class="meta-chip sensor">{layer.provenance?.dataset_name || layer.dataset || 'Copernicus'}</span>
                        <span class="meta-chip res">{layer.provenance?.resolution || layer.resolution || '10m'}</span>
                        {#if layer.temporal?.acquisition_date || layer.date}
                          <span class="meta-chip date">{layer.temporal?.acquisition_date || layer.date}</span>
                        {/if}
                      </div>
                    </div>
                  </div>
                  <div class="card-right">
                    <div class="opacity-slider-wrapper" title={`Layer opacity: ${Math.round((layer.style?.opacity ?? 0.85) * 100)}%`}>
                      <span class="opacity-text">{Math.round((layer.style?.opacity ?? 0.85) * 100)}%</span>
                      <input
                        type="range"
                        min="0.1"
                        max="1.0"
                        step="0.05"
                        value={layer.style?.opacity ?? 0.85}
                        on:input={(e) => updateLayerOpacity(layer.layer_id, parseFloat(e.currentTarget.value))}
                        class="layer-opacity-range"
                      />
                    </div>
                    <button class="layer-focus-btn" on:click={() => focusLayer(layer)} title="Focus camera on layer bounds">
                      <Crosshair size={12} />
                    </button>
                  </div>
                </div>
              {/each}
            </div>
          </div>

          <!-- Available Layers -->
          {#if $activeDataLayers.filter((l) => l.visible === false).length > 0}
            <div class="layer-group available-group">
              <div class="group-heading">
                <span class="group-dot inactive"></span>
                <span class="group-title">AVAILABLE LAYERS ({$activeDataLayers.filter((l) => l.visible === false).length})</span>
              </div>
              <div class="layer-cards-grid">
                {#each $activeDataLayers.filter((l) => l.visible === false) as layer}
                  <div class="layer-manager-card available">
                    <div class="card-left">
                      <button
                        class="visibility-toggle-btn inactive"
                        on:click={() => toggleLayerVisibility(layer.layer_id)}
                        title="Activate layer on 3D globe"
                      >
                        <EyeOff size={13} />
                      </button>
                      <div class="card-details">
                        <span class="card-title muted">{layer.title}</span>
                        <div class="card-meta-chips">
                          <span class="meta-chip sensor">{layer.provenance?.dataset_name || layer.dataset || 'Copernicus'}</span>
                          <span class="meta-chip res">{layer.provenance?.resolution || layer.resolution || '10m'}</span>
                        </div>
                      </div>
                    </div>
                    <button class="activate-layer-btn" on:click={() => toggleLayerVisibility(layer.layer_id)}>
                      + Activate
                    </button>
                  </div>
                {/each}
              </div>
            </div>
          {/if}
        </div>
      {/if}
    </div>

    <!-- 5. Key Measurements -->
    {#if result?.metrics && result.metrics.length > 0}
      <div class="measurements-block">
        <h4 class="evidence-block-title">Key measurements</h4>
        <div class="metrics-grid">
          {#each result.metrics as m, i}
            <div class="metric-card" class:primary={i === 0}>
              <span class="metric-label">{m.label}</span>
              <div class="metric-value-row">
                <span class="metric-value">{m.value}</span>
                {#if m.change}
                  <span
                    class="metric-change"
                    class:increase={m.trend === 'increase' || m.change.startsWith('+')}
                    class:decrease={m.trend === 'decrease' || m.change.startsWith('-')}
                  >
                    {m.change}
                  </span>
                {/if}
              </div>
              {#if m.unit}
                <span class="metric-unit">{m.unit}</span>
              {/if}
              {#if m.label?.toLowerCase().includes('alignment')}
                <p class="metric-context-note">
                  Output of CLOSP cross-modal representation. Model-specific alignment metric, not a flood probability.
                </p>
              {/if}
            </div>
          {/each}
        </div>
      </div>
    {/if}

    <!-- 6. Method Strip -->
    <div class="method-block">
      <h4 class="evidence-block-title">Method</h4>
      <div class="method-card">
        <div class="method-row">
          <span class="method-key">DATA</span>
          <span class="method-val">{methodInfo?.data?.join(' + ') || result.provenance?.dataset_ids?.join(' + ') || 'Sentinel-1 GRD + Sentinel-2 L2A'}</span>
        </div>
        <div class="method-row">
          <span class="method-key">MODEL</span>
          <span class="method-val model-accent">{methodInfo?.model || result.provenance?.model_name || 'Unavailable'}</span>
        </div>
        <div class="method-row">
          <span class="method-key">DISCOVERY PROVIDER</span>
          <span class="method-val">{methodInfo?.discovery_provider || result.provenance?.discovery_provider || 'Planetary Computer / Copernicus'}</span>
        </div>
        <div class="method-row">
          <span class="method-key">PROCESSING</span>
          <span class="method-val">{methodInfo?.processing_provider || result.provenance?.processing_provider || 'Remote GPU inference'}</span>
        </div>
        <div class="method-row">
          <span class="method-key">SOURCE</span>
          <span class="method-val source-badge">{methodInfo?.source || result.provenance?.source || 'unavailable'}</span>
        </div>
      </div>
    </div>

    <!-- 7. Limitations -->
    {#if limitationsList.length > 0}
      <div class="limitations-block">
        <h4 class="evidence-block-title">Limitations</h4>
        <div class="limitations-box">
          {#each limitationsList as lim}
            <div class="limit-item">
              <span class="limit-bullet">·</span>
              <span class="limit-text">{lim}</span>
            </div>
          {/each}
        </div>
      </div>
    {/if}

    <!-- 8. Multi-Year Temporal Observation Timeline (Phase 24) -->
    {#if temporalObservations && temporalObservations.length > 0}
      <div class="temporal-observations-block">
        <h4 class="evidence-block-title">Temporal Observation Timeline</h4>
        <div class="temporal-timeline-row">
          {#each temporalObservations as obs}
            <div class="timeline-slot" class:observed={obs.status === 'observed'} class:cloudy={obs.status === 'cloud_covered'} class:missing={obs.status === 'missing'}>
              <span class="slot-year">{obs.year}</span>
              <div class="slot-status-indicator {obs.status}">
                {#if obs.status === 'observed'}
                  <span class="indicator-icon">✓</span>
                  <span class="indicator-val">{obs.value !== null ? obs.value.toFixed(2) : 'Observed'}</span>
                {:else if obs.status === 'cloud_covered'}
                  <span class="indicator-icon">☁</span>
                  <span class="indicator-val">Cloud Filtered</span>
                {:else}
                  <span class="indicator-icon">✕</span>
                  <span class="indicator-val">No Scene</span>
                {/if}
              </div>
              <span class="slot-dataset">{obs.dataset}</span>
            </div>
          {/each}
        </div>
      </div>
    {/if}

    <!-- 9. Data Product Availability & Status (Phase 29 & 32) -->
    {#if dataAvailability && dataAvailability.length > 0}
      <div class="data-availability-block">
        <h4 class="evidence-block-title">Data Product Availability & Status</h4>
        <div class="data-avail-grid">
          {#each dataAvailability as prod}
            <div class="avail-card {prod.status}">
              <div class="avail-top">
                <span class="avail-label">{prod.label}</span>
                <span class="avail-status-chip {prod.status}">
                  {prod.status === 'ready' ? 'READY' : prod.status === 'unavailable' ? 'UNAVAILABLE' : 'NOT COMPUTED'}
                </span>
              </div>
              <div class="avail-source">{prod.source}</div>
              {#if prod.human_reason}
                <div class="avail-reason">{prod.human_reason}</div>
              {/if}
            </div>
          {/each}
        </div>
      </div>
    {/if}

    <!-- Optional Visualizations (ECharts / Cesium meshes) -->
    {#if visualizations && visualizations.length > 0 && currentVis && currentVis.type !== 'imagery'}
      <div class="vis-section">
        <div class="section-title-row">
          <div class="title-left">
            <Activity size={13} class="accent-icon" />
            <span class="section-title">{currentVis.title || 'Secondary Telemetry'}</span>
            <span class="type-pill">{(currentVis.type || 'chart').toUpperCase()}</span>
          </div>
        </div>
        <div class="vis-chart-box">
          <EChartRenderer
            type={currentVis.type}
            title=""
            subTitle=""
            data={currentVis.data?.length ? currentVis.data : chartData}
            height="240px"
          />
        </div>
      </div>
    {/if}

  {:else}
    <!-- Legacy presentation when presPlan is not present -->
    <div class="gpt-response-content">
      {@html parseMarkdown(displayContent)}
    </div>

    {#if result?.metrics && result.metrics.length > 0}
      <div class="metrics-grid">
        {#each result.metrics as m, i}
          <div class="metric-card" class:primary={i === 0}>
            <span class="metric-label">{m.label}</span>
            <div class="metric-value-row">
              <span class="metric-value">{m.value}</span>
              {#if m.change}
                <span
                  class="metric-change"
                  class:increase={m.trend === 'increase' || m.change.startsWith('+')}
                  class:decrease={m.trend === 'decrease' || m.change.startsWith('-')}
                >
                  {m.change}
                </span>
              {/if}
            </div>
            {#if m.unit}
              <span class="metric-unit">{m.unit}</span>
            {/if}
          </div>
        {/each}
      </div>
    {/if}

    {#if result?.image_comparison}
      {@const ic = result.image_comparison}
      <div class="imagery-section">
        <div class="section-title-row">
          <div class="title-left">
            <Layers size={13} class="accent-icon" />
            <span class="section-title">Satellite Multispectral Imagery</span>
          </div>
          <span class="demo-badge" class:live={result.provenance?.source === 'worker'}>
            {result.provenance?.source === 'worker' ? 'LIVE OBSERVATION' : 'SATELLITE ARCHIVE'}
          </span>
        </div>

        <div class="comparison-grid">
          <div class="image-box">
            <div class="image-header">
              <span class="image-date">{ic.t1_date}</span>
              <button
                class="expand-btn"
                on:click={() => openImageModal(ic.t1_url, ic.t1_label, ic.t1_date)}
                title="Expand image"
              >
                <Maximize2 size={12} />
              </button>
            </div>
            <div class="img-wrapper">
              <img
                src={resolveAssetUrl(ic.t1_url)}
                alt={ic.t1_label}
                class="sat-photo"
                loading="lazy"
              />
            </div>
            <div class="image-footer">
              <span class="footer-label">{ic.t1_label}</span>
            </div>
          </div>

          <div class="image-box">
            <div class="image-header">
              <span class="image-date">{ic.t2_date}</span>
              <button
                class="expand-btn"
                on:click={() => openImageModal(ic.t2_url, ic.t2_label, ic.t2_date)}
                title="Expand image"
              >
                <Maximize2 size={12} />
              </button>
            </div>
            <div class="img-wrapper">
              <img
                src={resolveAssetUrl(ic.t2_url)}
                alt={ic.t2_label}
                class="sat-photo"
                loading="lazy"
              />
            </div>
            <div class="image-footer">
              <span class="footer-label">{ic.t2_label}</span>
            </div>
          </div>
        </div>

        {#if ic.description}
          <p class="imagery-description">{ic.description}</p>
        {/if}
      </div>
    {/if}

    {#if visualizations && visualizations.length > 0 && currentVis}
      <div class="vis-section">
        <div class="section-title-row">
          <div class="title-left">
            <Activity size={13} class="accent-icon" />
            <span class="section-title">{currentVis.title || 'Observed NDVI trend'}</span>
            <span class="type-pill">{(currentVis.type || 'chart').toUpperCase()}</span>
          </div>

          {#if visualizations.length > 1}
            <div class="vis-mode-tabs">
              {#each visualizations as v, idx}
                <button
                  class="mode-tab"
                  class:active={activeVisIndex === idx}
                  on:click={() => (activeVisIndex = idx)}
                >
                  {v.title || `Vis ${idx + 1}`}
                </button>
              {/each}
            </div>
          {/if}
        </div>

        <div class="vis-chart-box">
          {#if currentVis.renderer === 'cesium'}
            <div class="inline-cesium-card">
              <div class="inline-card-top">
                <span class="inline-cesium-badge">ACTIVE 3D GEOSPATIAL OVERLAY</span>
                <span class="inline-cesium-title">{currentVis.title}</span>
              </div>
              <p class="inline-cesium-desc">{currentVis.description || 'Geospatial vector and raster layer rendered directly on the 3D globe.'}</p>
              <div class="inline-3d-mesh-container">
                <EChartRenderer
                  type="3d_surface"
                  data={currentVis.data}
                  height="190px"
                />
              </div>
            </div>
          {:else}
            <EChartRenderer
              type={currentVis.type}
              title=""
              subTitle=""
              data={currentVis.data?.length ? currentVis.data : chartData}
              xAxis={currentVis.xAxis}
              yAxis={currentVis.yAxis}
              series={currentVis.series}
              visualMap={currentVis.visualMap}
              height="280px"
            />
          {/if}
        </div>
      </div>
    {/if}

    <!-- Provenance Strip -->
    <div
      class="provenance-strip"
      on:click={() => ($showAuditTraceModal = true)}
      on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && ($showAuditTraceModal = true)}
      role="button"
      tabindex="0"
      title="Click to view detailed execution audit trace"
    >
      <div class="prov-group">
        <div class="prov-cell">
          <span class="prov-lbl">DATA</span>
          <span class="prov-val">{result.provenance?.dataset_ids?.join(', ') || 'Sentinel-2'}</span>
        </div>
        <div class="prov-cell">
          <span class="prov-lbl">MODEL</span>
          <span class="prov-val">{result.provenance?.model_name || (result.provenance?.source === 'unavailable' ? 'Specialist Model Unavailable' : 'Optical Pipeline')}</span>
        </div>
        <div class="prov-cell">
          <span class="prov-lbl">PERIOD</span>
          <span class="prov-val">{result.provenance?.acquisition_dates || result.visualization?.date_range || '2016 → 2026'}</span>
        </div>
        <div class="prov-cell">
          <span class="prov-lbl">SOURCE</span>
          <span
            class="prov-source-tag"
            class:worker={result.provenance?.source === 'worker' || result.provenance?.source === 'remote_worker'}
            class:unavailable={result.provenance?.source === 'unavailable'}
            class:mock={result.provenance?.source === 'mock'}
          >
            {#if result.provenance?.source === 'worker' || result.provenance?.source === 'remote_worker'}
              LIVE INFERENCE
            {:else if result.provenance?.source === 'unavailable'}
              WORKER UNAVAILABLE
            {:else if result.provenance?.source === 'mock'}
              MOCK DATA
            {:else}
              EARTH ARCHIVE
            {/if}
          </span>
        </div>
      </div>

      <div class="prov-trace-btn">
        <span>View audit trace</span>
        <ExternalLink size={12} />
      </div>
    </div>
  {/if}

  <!-- 6. Quick Action Buttons -->
  <div class="actions-row">
    <button class="action-btn" on:click={() => handleAction('timeseries')}>
      <TrendingUp size={13} />
      <span>Show time series</span>
    </button>
    <button class="action-btn" on:click={() => handleAction('aoi')}>
      <Crosshair size={13} />
      <span>Focus AOI on globe</span>
    </button>
    <button class="action-btn" on:click={() => handleAction('compare')}>
      <Layers size={13} />
      <span>Compare with another region</span>
    </button>
  </div>

  <!-- 7. Suggested Questions Chips -->
  {#if result?.suggested_questions && result.suggested_questions.length > 0}
    <div class="suggested-row">
      <div class="suggested-label">
        <Activity size={12} class="suggested-icon" />
        <span>Suggested follow-up questions:</span>
      </div>
      <div class="chips-wrap">
        {#each result.suggested_questions as q}
          <button class="chip-btn" on:click={() => handleSuggested(q)}>
            {q}
          </button>
        {/each}
      </div>
    </div>
  {/if}
</div>

<!-- Satellite Image Fullscreen Modal -->
{#if modalImage}
  <div
    class="image-modal-backdrop"
    on:click={(e) => { if (e.target === e.currentTarget) closeImageModal(); }}
    on:keydown={(e) => { if (e.key === 'Escape') closeImageModal(); }}
    role="dialog"
    aria-modal="true"
    tabindex="-1"
    aria-label="Satellite Image Modal"
  >
    <div class="image-modal-content">
      <div class="modal-header">
        <span class="modal-title">{modalImage.label} ({modalImage.date})</span>
        <button class="modal-close-btn" on:click={closeImageModal} aria-label="Close modal">
          <X size={18} />
        </button>
      </div>
      <div class="modal-body">
        <img src={modalImage.url} alt={modalImage.label} class="modal-sat-img" />
      </div>
    </div>
  </div>
{/if}

<style>
  .analysis-result-card {
    display: flex;
    flex-direction: column;
    gap: 16px;
    width: 100%;
    color: #e2e8f0;
  }

  .chart-summary {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 18px;
    padding: 8px 12px 0;
    color: #94a3b8;
    font-size: 11px;
    font-family: var(--font-mono);
  }

  /* Header */
  .result-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-bottom: 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .logo-box {
    width: 32px;
    height: 32px;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
  }

  .logo-img {
    width: 22px;
    height: 22px;
    object-fit: contain;
  }

  .model-info {
    display: flex;
    flex-direction: column;
    gap: 1px;
  }

  .name-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .brand-name {
    font-size: 0.92rem;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: -0.01em;
  }

  .ai-text {
    color: #e2e8f0;
  }

  .reasoning-badge {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 0.68rem;
    font-weight: 600;
    color: #f8fafc;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    padding: 1px 7px;
    border-radius: 12px;
    letter-spacing: 0.02em;
  }

  .model-pipeline {
    font-size: 0.72rem;
    color: #94a3b8;
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .result-time {
    font-size: 0.72rem;
    color: #64748b;
  }

  .confidence-pill {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 0.7rem;
    font-weight: 600;
    color: #f8fafc;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    padding: 3px 8px;
    border-radius: 14px;
  }

  /* GPT Natural Language Typography */
  .gpt-response-content {
    font-size: 0.93rem;
    line-height: 1.7;
    color: #e2e8f0;
    letter-spacing: 0.01em;
  }

  :global(.gpt-response-content .md-p) {
    margin: 0 0 14px 0;
    color: #cbd5e1;
    line-height: 1.7;
  }

  :global(.gpt-response-content .md-h2) {
    font-size: 1.18rem;
    font-weight: 700;
    color: #ffffff;
    margin: 20px 0 10px 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    padding-bottom: 6px;
    letter-spacing: -0.01em;
  }

  :global(.gpt-response-content .md-h3) {
    font-size: 1.04rem;
    font-weight: 700;
    color: #ffffff;
    margin: 18px 0 8px 0;
    display: flex;
    align-items: center;
    gap: 8px;
    letter-spacing: -0.01em;
  }

  :global(.gpt-response-content .md-h3::before) {
    content: '';
    display: inline-block;
    width: 3px;
    height: 14px;
    background: #e2e8f0;
    border-radius: 2px;
  }

  :global(.gpt-response-content .md-h4) {
    font-size: 0.94rem;
    font-weight: 600;
    color: #f8fafc;
    margin: 14px 0 6px 0;
    letter-spacing: 0.01em;
    text-transform: uppercase;
    font-size: 0.82rem;
  }

  :global(.gpt-response-content .md-h5) {
    font-size: 0.88rem;
    font-weight: 600;
    color: #cbd5e1;
    margin: 12px 0 4px 0;
  }

  :global(.gpt-response-content .md-ul),
  :global(.gpt-response-content .md-ol) {
    margin: 8px 0 16px 0;
    padding-left: 20px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  :global(.gpt-response-content .md-ul) {
    list-style-type: none;
    padding-left: 4px;
  }

  :global(.gpt-response-content .md-ul .md-li) {
    position: relative;
    padding-left: 18px;
    line-height: 1.6;
    color: #e2e8f0;
  }

  :global(.gpt-response-content .md-ul .md-li::before) {
    content: '•';
    position: absolute;
    left: 4px;
    color: #e2e8f0;
    font-size: 1.1rem;
    line-height: 1.4;
  }

  :global(.gpt-response-content .md-ol .md-li) {
    line-height: 1.6;
    color: #e2e8f0;
    margin-bottom: 4px;
  }

  :global(.gpt-response-content strong) {
    font-weight: 700;
    color: #f8fafc;
  }

  :global(.gpt-response-content em) {
    color: #94a3b8;
    font-style: italic;
  }

  :global(.gpt-response-content del) {
    color: #64748b;
    text-decoration: line-through;
  }

  :global(.gpt-response-content .md-inline-code) {
    background: rgba(15, 23, 42, 0.8);
    border: 1px solid rgba(255, 255, 255, 0.12);
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.82rem;
    font-family: monospace;
    color: #e2e8f0;
  }

  :global(.gpt-response-content .md-code-block) {
    background: #090d16;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    margin: 14px 0;
    position: relative;
    overflow: hidden;
  }

  :global(.gpt-response-content .md-code-lang) {
    position: absolute;
    top: 6px;
    right: 10px;
    font-size: 0.68rem;
    color: #64748b;
    text-transform: uppercase;
    font-family: monospace;
  }

  :global(.gpt-response-content .md-code) {
    margin: 0;
    padding: 12px 16px;
    overflow-x: auto;
    font-family: monospace;
    font-size: 0.84rem;
    color: #cbd5e1;
    line-height: 1.5;
  }

  :global(.gpt-response-content .md-quote) {
    border-left: 3px solid #e2e8f0;
    background: rgba(255, 255, 255, 0.04);
    border-radius: 0 8px 8px 0;
    padding: 10px 14px;
    margin: 14px 0;
    color: #cbd5e1;
    font-size: 0.9rem;
    line-height: 1.6;
  }

  :global(.gpt-response-content .md-quote.md-callout) {
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-left: 3px solid #e2e8f0;
    background: rgba(255, 255, 255, 0.03);
    border-radius: 8px;
  }

  :global(.gpt-response-content .md-hr) {
    border: none;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    margin: 18px 0;
  }

  :global(.gpt-response-content .md-table-wrapper) {
    width: 100%;
    overflow-x: auto;
    margin: 14px 0;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    background: rgba(11, 17, 28, 0.6);
  }

  :global(.gpt-response-content .md-table) {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
    text-align: left;
  }

  :global(.gpt-response-content .md-table th) {
    background: rgba(255, 255, 255, 0.04);
    color: #f8fafc;
    font-weight: 600;
    padding: 8px 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  }

  :global(.gpt-response-content .md-table td) {
    padding: 8px 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    color: #cbd5e1;
  }

  :global(.gpt-response-content .md-table tr:last-child td) {
    border-bottom: none;
  }

  /* Key Metrics Grid */
  .metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
    gap: 10px;
  }

  .metric-card {
    background: rgba(15, 23, 42, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 10px;
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 4px;
    transition: all 0.2s ease;
  }

  .metric-card.primary {
    border-color: rgba(16, 185, 129, 0.35);
    background: rgba(16, 185, 129, 0.05);
  }

  .metric-label {
    font-size: 0.72rem;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    font-weight: 500;
  }

  .metric-value-row {
    display: flex;
    align-items: baseline;
    gap: 6px;
  }

  .metric-value {
    font-size: 1.25rem;
    font-weight: 700;
    color: #ffffff;
    font-variant-numeric: tabular-nums;
  }

  .metric-change {
    font-size: 0.74rem;
    font-weight: 600;
    padding: 1px 5px;
    border-radius: 4px;
  }

  .metric-context-note {
    margin: 6px 0 0 0;
    font-size: 0.68rem;
    color: #94a3b8;
    line-height: 1.35;
    font-style: italic;
    background: rgba(255, 255, 255, 0.03);
    padding: 4px 6px;
    border-radius: 4px;
    border-left: 2px solid rgba(56, 178, 172, 0.5);
  }

  .metric-change.increase {
    color: #f8fafc;
    background: rgba(255, 255, 255, 0.06);
  }

  .metric-change.decrease {
    color: #f87171;
    background: rgba(248, 113, 113, 0.12);
  }

  .metric-unit {
    font-size: 0.68rem;
    color: #64748b;
  }

  /* Satellite Comparison Imagery */
  .imagery-section {
    background: rgba(10, 15, 26, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 12px;
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .section-title-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .title-left {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .section-title {
    font-size: 0.82rem;
    font-weight: 600;
    color: #e2e8f0;
  }

  :global(.accent-icon) {
    color: #10b981;
  }

  .demo-badge {
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    color: #fbbf24;
    background: rgba(251, 191, 36, 0.14);
    border: 1px solid rgba(251, 191, 36, 0.3);
    padding: 2px 7px;
    border-radius: 10px;
  }

  .demo-badge.live {
    color: #f8fafc;
    background: rgba(255, 255, 255, 0.06);
    border-color: rgba(255, 255, 255, 0.18);
  }

  .comparison-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }

  .image-box {
    background: #050811;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 8px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }

  .image-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 10px;
    background: rgba(0, 0, 0, 0.4);
    font-size: 0.72rem;
    color: #94a3b8;
    font-weight: 600;
  }

  .expand-btn {
    background: transparent;
    border: none;
    color: #94a3b8;
    cursor: pointer;
    padding: 2px;
    display: flex;
    align-items: center;
    transition: color 0.15s ease;
  }

  .expand-btn:hover {
    color: #ffffff;
  }

  .img-wrapper {
    width: 100%;
    height: 160px;
    overflow: hidden;
    position: relative;
    background: #000000;
  }

  .sat-photo {
    width: 100%;
    height: 100%;
    object-fit: cover;
    transition: transform 0.3s ease;
  }

  .sat-photo:hover {
    transform: scale(1.03);
  }

  .image-footer {
    padding: 6px 10px;
    font-size: 0.68rem;
    color: #64748b;
    background: rgba(0, 0, 0, 0.3);
  }

  .imagery-description {
    font-size: 0.78rem;
    color: #94a3b8;
    line-height: 1.45;
  }

  /* Dynamic ECharts Visualization */
  .vis-section {
    background: rgba(10, 15, 26, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 12px;
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .type-pill {
    font-size: 0.62rem;
    font-weight: 700;
    letter-spacing: 0.4px;
    padding: 1px 6px;
    border-radius: 4px;
    background: rgba(255, 255, 255, 0.06);
    color: #e2e8f0;
    border: 1px solid rgba(255, 255, 255, 0.12);
    margin-left: 6px;
  }

  .vis-mode-tabs {
    display: flex;
    gap: 4px;
    background: rgba(0, 0, 0, 0.3);
    padding: 3px;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.05);
  }


  .mode-tab {
    background: transparent;
    border: none;
    color: #94a3b8;
    font-size: 0.7rem;
    font-weight: 500;
    padding: 3px 8px;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .mode-tab.active {
    background: rgba(255, 255, 255, 0.08);
    color: #ffffff;
    font-weight: 600;
  }

  .vis-chart-box {
    width: 100%;
    height: 250px;
    position: relative;
    border-radius: 8px;
    overflow: hidden;
  }

  /* Provenance Strip */
  .provenance-strip {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 10px 14px;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .provenance-strip:hover {
    background: rgba(15, 23, 42, 0.85);
    border-color: rgba(16, 185, 129, 0.3);
  }

  .prov-group {
    display: flex;
    align-items: center;
    gap: 20px;
    flex-wrap: wrap;
  }

  .prov-cell {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.72rem;
  }

  .prov-lbl {
    color: #64748b;
    font-weight: 600;
    letter-spacing: 0.04em;
  }

  .prov-val {
    color: #cbd5e1;
    font-weight: 500;
  }

  .prov-source-tag {
    font-size: 0.65rem;
    font-weight: 700;
    padding: 1px 6px;
    border-radius: 4px;
    color: #fbbf24;
    background: rgba(251, 191, 36, 0.15);
  }

  .prov-source-tag.worker {
    color: #f8fafc;
    background: rgba(255, 255, 255, 0.08);
  }

  .prov-source-tag.unavailable {
    color: #f87171;
    background: rgba(239, 68, 68, 0.15);
    border: 1px solid rgba(239, 68, 68, 0.3);
  }

  .prov-source-tag.mock {
    color: #fbbf24;
    background: rgba(251, 191, 36, 0.15);
    border: 1px solid rgba(251, 191, 36, 0.3);
  }

  .prov-trace-btn {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 0.74rem;
    font-weight: 600;
    color: #e2e8f0;
    flex-shrink: 0;
  }

  /* Quick Actions */
  .actions-row {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }

  .action-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: #cbd5e1;
    font-size: 0.75rem;
    font-weight: 500;
    padding: 6px 12px;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .action-btn:hover {
    background: rgba(255, 255, 255, 0.08);
    border-color: rgba(255, 255, 255, 0.15);
    color: #ffffff;
  }

  /* Suggested Questions */
  .suggested-row {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding-top: 6px;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
  }

  .suggested-label {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.72rem;
    color: #94a3b8;
    font-weight: 500;
  }

  :global(.suggested-icon) {
    color: #e2e8f0;
  }

  .chips-wrap {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .chip-btn {
    background: rgba(30, 41, 59, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: #94a3b8;
    font-size: 0.74rem;
    padding: 6px 11px;
    border-radius: 16px;
    cursor: pointer;
    transition: all 0.15s ease;
    text-align: left;
  }

  .chip-btn:hover {
    background: rgba(255, 255, 255, 0.08);
    border-color: rgba(255, 255, 255, 0.15);
    color: #ffffff;
  }

  /* Modal Image */
  .image-modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.85);
    backdrop-filter: blur(8px);
    z-index: 1000;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
  }

  .image-modal-content {
    background: #080c14;
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 14px;
    max-width: 800px;
    width: 100%;
    overflow: hidden;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7);
  }

  .modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }

  .modal-title {
    font-size: 0.88rem;
    font-weight: 600;
    color: #ffffff;
  }

  .modal-close-btn {
    background: transparent;
    border: none;
    color: #94a3b8;
    cursor: pointer;
    padding: 4px;
    display: flex;
    align-items: center;
  }

  .modal-close-btn:hover {
    color: #ffffff;
  }

  .modal-body {
    width: 100%;
    max-height: 70vh;
    overflow: hidden;
    background: #000;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .modal-sat-img {
    max-width: 100%;
    max-height: 70vh;
    object-fit: contain;
  }

  .inline-cesium-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 28px 16px;
    background: radial-gradient(circle at 50% 30%, rgba(255, 255, 255, 0.04) 0%, transparent 70%);
    border: 1px dashed rgba(255, 255, 255, 0.12);
    border-radius: 8px;
    height: 100%;
  }

  .inline-cesium-badge {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.08em;
    color: #f8fafc;
    background: rgba(255, 255, 255, 0.06);
    padding: 3px 9px;
    border-radius: 12px;
    margin-bottom: 8px;
  }

  .inline-cesium-title {
    font-size: 13.5px;
    font-weight: 600;
    color: #f8fafc;
    margin-bottom: 4px;
  }

  .inline-cesium-desc {
    font-size: 11px;
    color: #94a3b8;
    max-width: 380px;
    line-height: 1.4;
    margin: 0;
  }

  .inline-card-top {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
  }

  .inline-3d-mesh-container {
    width: 100%;
    height: 190px;
    margin-top: 10px;
    position: relative;
    border-radius: 6px;
    overflow: hidden;
  }

  /* Evidence-First Multimodal Styles */
  .investigation-title-block {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }

  .investigation-label {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.08em;
    color: #38bdf8;
    text-transform: uppercase;
  }

  .investigation-title {
    margin: 0;
    font-size: 1.15rem;
    font-weight: 700;
    color: #f8fafc;
    letter-spacing: -0.01em;
  }

  .evidence-block-title {
    margin: 0 0 8px 0;
    font-size: 12px;
    font-weight: 600;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .evidence-images-section {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .evidence-sub-block {
    display: flex;
    flex-direction: column;
  }

  .comparison-split-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }

  @media (max-width: 768px) {
    .comparison-split-grid {
      grid-template-columns: 1fr;
    }
  }

  .baseline-missing-card {
    background: rgba(245, 158, 11, 0.06);
    border: 1px dashed rgba(245, 158, 11, 0.35);
    border-radius: 10px;
    padding: 12px 14px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .missing-badge-row {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  :global(.missing-icon) {
    color: #f59e0b;
  }

  .missing-badge {
    font-size: 10px;
    font-weight: 700;
    color: #fbbf24;
    letter-spacing: 0.05em;
  }

  .missing-reason {
    margin: 0;
    font-size: 12px;
    color: #cbd5e1;
    line-height: 1.4;
  }

  .change-analysis-block,
  .evidence-layers-block,
  .measurements-block,
  .method-block,
  .limitations-block {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .layers-pill-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .layer-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #e2e8f0;
    font-size: 11.5px;
    font-weight: 500;
    padding: 5px 10px;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .layer-pill:hover,
  .layer-pill.active {
    background: rgba(56, 189, 248, 0.14);
    border-color: rgba(56, 189, 248, 0.35);
    color: #38bdf8;
  }

  .layer-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #38bdf8;
  }

  .method-card {
    background: rgba(18, 22, 34, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 10px;
    padding: 10px 14px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .method-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 11.5px;
    padding: 3px 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.03);
  }

  .method-row:last-child {
    border-bottom: none;
  }

  .method-key {
    color: #94a3b8;
    font-weight: 600;
    font-size: 10.5px;
    letter-spacing: 0.04em;
  }

  .method-val {
    color: #f1f5f9;
    font-weight: 500;
  }

  .model-accent {
    color: #38bdf8;
    font-weight: 600;
  }

  .source-badge {
    background: rgba(56, 189, 248, 0.12);
    color: #38bdf8;
    padding: 2px 6px;
    border-radius: 4px;
    font-family: var(--font-mono);
    font-size: 10.5px;
  }

  .limitations-box {
    background: rgba(239, 68, 68, 0.04);
    border: 1px solid rgba(239, 68, 68, 0.18);
    border-radius: 10px;
    padding: 10px 14px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .limit-item {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    font-size: 11.5px;
    color: #cbd5e1;
    line-height: 1.4;
  }

  .limit-bullet {
    color: #f87171;
    font-weight: 700;
    line-height: 1;
  }

  .limit-text {
    flex: 1;
  }

  /* Primary Visualization Switcher (Part 10) */
  .primary-vis-switcher {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 10px;
    margin-bottom: 12px;
    padding: 3px;
    background: rgba(15, 23, 42, 0.5);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 8px;
    width: fit-content;
  }

  .switcher-tab-btn {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 5px 11px;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 500;
    color: #94a3b8;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .switcher-tab-btn:hover {
    color: #e2e8f0;
    background: rgba(255, 255, 255, 0.04);
  }

  .switcher-tab-btn.active {
    background: rgba(56, 189, 248, 0.12);
    border-color: rgba(56, 189, 248, 0.35);
    color: #38bdf8;
    font-weight: 600;
    box-shadow: 0 0 10px rgba(56, 189, 248, 0.15);
  }

  /* Primary Canvas Container */
  .primary-canvas-container {
    margin-top: 10px;
    margin-bottom: 14px;
    background: rgba(11, 17, 32, 0.45);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 10px;
    overflow: hidden;
  }

  .canvas-panel-view {
    padding: 12px 14px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .canvas-header-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  }

  .canvas-view-tag {
    font-size: 9.5px;
    font-weight: 700;
    letter-spacing: 0.06em;
    color: #38bdf8;
    text-transform: uppercase;
  }

  .canvas-source-tag {
    font-size: 10px;
    color: #94a3b8;
    font-family: var(--font-mono, monospace);
  }

  .canvas-chart-wrapper {
    width: 100%;
    min-height: 280px;
  }

  .canvas-3d-wrapper {
    width: 100%;
    min-height: 320px;
  }

  .canvas-empty-state {
    padding: 30px;
    text-align: center;
    color: #64748b;
    font-size: 12px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
  }

  /* Grounded Factual Explanation Card */
  .grounded-explanation-card {
    background: rgba(15, 23, 42, 0.65);
    border: 1px solid rgba(56, 189, 248, 0.22);
    border-radius: 10px;
    padding: 14px;
    margin-top: 12px;
    margin-bottom: 14px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
  }

  .card-header-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    padding-bottom: 8px;
  }

  .badge-title {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  .canon-badge {
    font-size: 8.5px;
    font-weight: 800;
    letter-spacing: 0.08em;
    color: #38bdf8;
    background: rgba(56, 189, 248, 0.12);
    padding: 2px 6px;
    border-radius: 4px;
    width: fit-content;
  }

  .canon-title {
    font-size: 13.5px;
    font-weight: 600;
    color: #f8fafc;
    margin: 0;
  }

  .source-tag {
    font-size: 10px;
    font-family: var(--font-mono, monospace);
    color: #94a3b8;
    background: rgba(255, 255, 255, 0.04);
    padding: 3px 8px;
    border-radius: 4px;
    border: 1px solid rgba(255, 255, 255, 0.06);
  }

  .canon-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 12px;
  }

  .canon-field {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  .canon-field.full-width {
    grid-column: 1 / -1;
  }

  .field-label {
    font-size: 8.5px;
    font-weight: 700;
    letter-spacing: 0.05em;
    color: #64748b;
    text-transform: uppercase;
  }

  .field-content {
    font-size: 11px;
    color: #cbd5e1;
    line-height: 1.45;
    margin: 0;
  }

  .field-content.warning-text {
    color: #fbbf24;
  }

  .var-pills {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-top: 2px;
  }

  .var-pill {
    font-size: 10px;
    font-family: var(--font-mono, monospace);
    background: rgba(56, 189, 248, 0.08);
    border: 1px solid rgba(56, 189, 248, 0.2);
    color: #7dd3fc;
    padding: 1px 6px;
    border-radius: 4px;
  }

  /* Unobserved Advisory Decoupling Box */
  .unobserved-advisory-box {
    margin-top: 14px;
    background: rgba(245, 158, 11, 0.05);
    border: 1px solid rgba(245, 158, 11, 0.25);
    border-radius: 8px;
    padding: 12px 14px;
  }

  .advisory-title-row {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 8px;
  }

  .advisory-icon {
    color: #f59e0b;
    flex-shrink: 0;
  }

  .advisory-title {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.05em;
    color: #fbbf24;
  }

  .unobserved-list {
    margin: 0;
    padding-left: 18px;
    display: flex;
    flex-direction: column;
    gap: 5px;
    font-size: 11px;
    color: #cbd5e1;
    line-height: 1.4;
  }

  .unobserved-list strong {
    color: #fef08a;
  }

  /* Phase 25 & 27: Layer Management Styles */
  .layers-section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 6px;
  }

  .layers-count-badge {
    font-size: 10px;
    font-weight: 600;
    color: #38bdf8;
    background: rgba(56, 189, 248, 0.1);
    border: 1px solid rgba(56, 189, 248, 0.25);
    padding: 2px 8px;
    border-radius: 9999px;
  }

  .layer-management-container {
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin-top: 10px;
    background: rgba(15, 23, 42, 0.5);
    border: 1px solid rgba(51, 65, 85, 0.5);
    border-radius: 8px;
    padding: 10px;
  }

  .layer-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .group-heading {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.05em;
    color: #94a3b8;
    margin-bottom: 2px;
  }

  .group-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
  }

  .group-dot.active {
    background: #10b981;
    box-shadow: 0 0 6px #10b981;
  }

  .group-dot.inactive {
    background: #64748b;
  }

  .layer-cards-grid {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .layer-manager-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: rgba(30, 41, 59, 0.6);
    border: 1px solid rgba(71, 85, 105, 0.4);
    border-radius: 6px;
    padding: 6px 10px;
    transition: all 0.2s ease;
  }

  .layer-manager-card.active {
    border-color: rgba(56, 189, 248, 0.35);
    background: rgba(15, 23, 42, 0.75);
  }

  .card-left {
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 1;
    min-width: 0;
  }

  .visibility-toggle-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    border-radius: 4px;
    border: 1px solid rgba(71, 85, 105, 0.5);
    background: rgba(15, 23, 42, 0.6);
    cursor: pointer;
    transition: all 0.2s;
  }

  .visibility-toggle-btn.active {
    color: #38bdf8;
    border-color: rgba(56, 189, 248, 0.5);
  }

  .visibility-toggle-btn.inactive {
    color: #64748b;
  }

  .card-details {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }

  .card-title {
    font-size: 11px;
    font-weight: 600;
    color: #f1f5f9;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .card-title.muted {
    color: #94a3b8;
  }

  .card-meta-chips {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .meta-chip {
    font-size: 9px;
    font-weight: 500;
    padding: 1px 4px;
    border-radius: 3px;
    background: rgba(51, 65, 85, 0.5);
    color: #cbd5e1;
  }

  .meta-chip.sensor {
    color: #38bdf8;
    background: rgba(56, 189, 248, 0.1);
  }

  .meta-chip.res {
    color: #a78bfa;
    background: rgba(167, 139, 250, 0.1);
  }

  .card-right {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .opacity-slider-wrapper {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .opacity-text {
    font-size: 9px;
    font-weight: 600;
    color: #94a3b8;
    min-width: 24px;
  }

  .layer-opacity-range {
    width: 60px;
    height: 4px;
    accent-color: #38bdf8;
    cursor: pointer;
  }

  .layer-focus-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    border-radius: 4px;
    border: 1px solid rgba(71, 85, 105, 0.4);
    background: transparent;
    color: #94a3b8;
    cursor: pointer;
    transition: all 0.15s;
  }

  .layer-focus-btn:hover {
    color: #38bdf8;
    border-color: #38bdf8;
  }

  .activate-layer-btn {
    font-size: 10px;
    font-weight: 600;
    color: #38bdf8;
    background: rgba(56, 189, 248, 0.1);
    border: 1px solid rgba(56, 189, 248, 0.3);
    padding: 3px 8px;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.15s;
  }

  .activate-layer-btn:hover {
    background: rgba(56, 189, 248, 0.2);
  }

  /* Phase 24: Temporal Observation Timeline */
  .temporal-observations-block {
    margin-top: 14px;
  }

  .temporal-timeline-row {
    display: flex;
    gap: 8px;
    overflow-x: auto;
    padding-bottom: 6px;
  }

  .timeline-slot {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 3px;
    padding: 6px 10px;
    background: rgba(30, 41, 59, 0.6);
    border: 1px solid rgba(71, 85, 105, 0.4);
    border-radius: 6px;
    min-width: 64px;
  }

  .timeline-slot.observed {
    border-color: rgba(16, 185, 129, 0.4);
  }

  .timeline-slot.cloudy {
    border-color: rgba(245, 158, 11, 0.4);
  }

  .timeline-slot.missing {
    border-color: rgba(239, 68, 68, 0.3);
    opacity: 0.75;
  }

  .slot-year {
    font-size: 10px;
    font-weight: 700;
    color: #f1f5f9;
  }

  .slot-status-indicator {
    display: flex;
    align-items: center;
    gap: 3px;
    font-size: 9px;
    font-weight: 600;
  }

  .slot-status-indicator.observed {
    color: #10b981;
  }

  .slot-status-indicator.cloud_covered {
    color: #f59e0b;
  }

  .slot-status-indicator.missing {
    color: #ef4444;
  }

  .slot-dataset {
    font-size: 8px;
    color: #64748b;
  }

  /* Phase 29 & 32: Data Availability System */
  .data-availability-block {
    margin-top: 14px;
  }

  .data-avail-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 8px;
  }

  .avail-card {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 8px 10px;
    background: rgba(15, 23, 42, 0.7);
    border: 1px solid rgba(51, 65, 85, 0.5);
    border-radius: 6px;
  }

  .avail-card.ready {
    border-color: rgba(16, 185, 129, 0.3);
  }

  .avail-card.unavailable {
    border-color: rgba(245, 158, 11, 0.3);
  }

  .avail-card.not_computed {
    border-color: rgba(100, 116, 139, 0.3);
  }

  .avail-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 4px;
  }

  .avail-label {
    font-size: 10px;
    font-weight: 600;
    color: #f1f5f9;
  }

  .avail-status-chip {
    font-size: 8px;
    font-weight: 700;
    padding: 1px 5px;
    border-radius: 9999px;
    letter-spacing: 0.05em;
  }

  .avail-status-chip.ready {
    background: rgba(16, 185, 129, 0.15);
    color: #34d399;
    border: 1px solid rgba(16, 185, 129, 0.3);
  }

  .avail-status-chip.unavailable {
    background: rgba(245, 158, 11, 0.15);
    color: #fbbf24;
    border: 1px solid rgba(245, 158, 11, 0.3);
  }

  .avail-status-chip.not_computed {
    background: rgba(100, 116, 139, 0.15);
    color: #94a3b8;
    border: 1px solid rgba(100, 116, 139, 0.3);
  }

  .avail-source {
    font-size: 9px;
    color: #64748b;
  }

  .avail-reason {
    font-size: 9px;
    color: #fca5a5;
    line-height: 1.3;
  }
</style>

