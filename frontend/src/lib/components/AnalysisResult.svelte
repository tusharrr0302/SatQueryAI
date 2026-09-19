<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import {
    showAuditTraceModal,
    type NormalizedResult,
  } from '../stores';
  import EChartRenderer from './EChartRenderer.svelte';

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
  } from 'lucide-svelte';

  export let result: NormalizedResult;
  export let content: string = '';
  export let timestamp: string = '';

  const dispatch = createEventDispatcher<{
    submitQuery: string;
    actionClick: string;
  }>();

  $: visualizations = result?.visualizations || [];
  let activeVisIndex = 0;
  $: if (activeVisIndex >= visualizations.length) {
    activeVisIndex = 0;
  }
  $: currentVis = visualizations[activeVisIndex] || null;

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
          {result?.provenance?.model_name || 'Prithvi-EO-2.0'} • Remote Sensing Agent
        </span>
      </div>
    </div>

    <div class="header-right">
      {#if timestamp}
        <span class="result-time">{timestamp.split('T')[1]?.slice(0, 5) || '10:24 AM'}</span>
      {/if}
      {#if result?.confidence != null}
        <div class="confidence-pill" class:high={result.confidence >= 0.9}>
          <CheckCircle2 size={12} />
          <span>{Math.round(result.confidence * 100)}% Confidence</span>
        </div>
      {:else}
        <div class="confidence-pill measured">
          <CheckCircle2 size={12} />
          <span>Pixel-derived metrics</span>
        </div>
      {/if}
    </div>
  </div>

  <!-- 1. Natural Language Answer (GPT-OSS 120B) -->
  <div class="gpt-response-content">
    {@html parseMarkdown(displayContent)}
  </div>

  <!-- 2. Key Metrics Cards -->
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

  <!-- 3. Satellite Comparison Imagery -->
  {#if result?.image_comparison}
    {@const ic = result.image_comparison}
    <div class="imagery-section">
      <div class="section-title-row">
        <div class="title-left">
          <Layers size={13} class="accent-icon" />
          <span class="section-title">Satellite Multispectral Imagery</span>
        </div>
        <!-- Satellite Archive badge -->
        <span class="demo-badge" class:live={result.provenance?.source === 'worker'}>
          {result.provenance?.source === 'worker' ? 'LIVE OBSERVATION' : 'SATELLITE ARCHIVE'}
        </span>
      </div>

      <div class="comparison-grid">
        <!-- T1 Before Image -->
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

        <!-- T2 After Image -->
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

  <!-- 4. Dynamic Apache ECharts Visualization -->
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
      {#if chartPoints.length > 0 && currentVis.type === 'line'}
        <div class="chart-summary">
          <span>{chartPoints.length} Sentinel-2 observations</span>
          <span>Metric: {chartPoints[0].metric_name || chartPoints[0].unit || 'NDVI'}</span>
          <span>{chartPoints[0].date} → {chartPoints[chartPoints.length - 1].date}</span>
        </div>
      {/if}
    </div>
  {/if}


  <!-- 5. Provenance Strip -->
  <div
    class="provenance-strip"
    on:click={() => ($showAuditTraceModal = true)}
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
        <span class="prov-val">{result.provenance?.model_name || 'Prithvi-EO-2.0'}</span>
      </div>
      <div class="prov-cell">
        <span class="prov-lbl">PERIOD</span>
        <span class="prov-val">{result.provenance?.acquisition_dates || result.visualization?.date_range || '2016 → 2026'}</span>
      </div>
      <div class="prov-cell">
        <span class="prov-lbl">SOURCE</span>
        <span class="prov-source-tag" class:worker={result.provenance?.source === 'worker'}>
          {result.provenance?.source === 'worker' ? 'LIVE INFERENCE' : 'EARTH ARCHIVE'}
        </span>
      </div>
    </div>

    <div class="prov-trace-btn">
      <span>View audit trace</span>
      <ExternalLink size={12} />
    </div>
  </div>

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
  <div class="image-modal-backdrop" on:click={closeImageModal} role="dialog" aria-modal="true">
    <div class="image-modal-content" on:click|stopPropagation>
      <div class="modal-header">
        <span class="modal-title">{modalImage.label} ({modalImage.date})</span>
        <button class="modal-close-btn" on:click={closeImageModal}>
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
</style>
