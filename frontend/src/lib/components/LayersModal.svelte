<script lang="ts">
  import { onMount } from 'svelte';
  import {
    activeDataLayers,
    currentGlobeSkin,
    flyToLayerTrigger,
    activeSidebarTab,
    type DataLayerSpec,
  } from '../stores';
  import { getAvailableSkins, type GlobeSkin } from '../services/globeSkinRegistry';
  import {
    X,
    Eye,
    EyeOff,
    Layers,
    Sliders,
    Crosshair,
    Trash2,
    Sparkles,
    Globe2,
    Compass,
    Check,
    Info,
    Search,
    Database,
    Plus,
    ChevronDown,
    ChevronRight,
    ShieldCheck,
    Tag,
  } from 'lucide-svelte';

  type TabType = 'active' | 'explore' | 'skins';
  let currentTab: TabType = 'active';

  const skins: GlobeSkin[] = getAvailableSkins();

  // Catalog state
  interface CatalogDataset {
    dataset_id: string;
    name: string;
    provider: string;
    mission: string;
    sensor: string;
    modality: string;
    spatial_resolution: string;
    temporal_resolution: string;
    bands: string[];
    products: string[];
    supported_analyses: string[];
    available_visualizations: string[];
    description?: string;
    verified_layer_count?: number;
    layers?: CatalogLayer[];
  }

  interface CatalogLayer {
    layer_id: string;
    dataset_id: string;
    name: string;
    category: string;
    visualization_type: string;
    required_bands: string[];
    units: string;
    description: string;
    role?: string;
  }

  interface CatalogSummary {
    verified_dataset_count: number;
    verified_layer_count: number;
    providers: string[];
    modalities: string[];
    ecosystem: string;
    verified_note: string;
  }

  let catalogSummary: CatalogSummary | null = null;
  let catalogDatasets: CatalogDataset[] = [];
  let catalogLayers: CatalogLayer[] = [];
  let searchQuery = '';
  let selectedCategory = 'all';
  let isLoadingCatalog = false;
  let catalogLoaded = false;
  let expandedDatasets: Record<string, boolean> = {};

  const categories = [
    { id: 'all', label: 'All Layers' },
    { id: 'vegetation', label: 'Vegetation' },
    { id: 'atmospheric', label: 'Atmospheric' },
    { id: 'sar_radar', label: 'SAR / Radar' },
    { id: 'elevation', label: 'Elevation' },
    { id: 'land_cover', label: 'Land Cover' },
    { id: 'water_quality', label: 'Water Quality' },
  ];

  const semanticRoles = [
    { id: 'primary', label: 'PRIMARY', color: '#f8fafc', border: 'rgba(255, 255, 255, 0.2)', bg: 'rgba(255, 255, 255, 0.08)', aliases: ['primary', 'primary_analysis'] },
    { id: 'reference', label: 'REFERENCE', color: '#cbd5e1', border: 'rgba(203, 213, 225, 0.2)', bg: 'rgba(203, 213, 225, 0.06)', aliases: ['reference', 'comparison', 'evidence'] },
    { id: 'context', label: 'CONTEXT', color: '#94a3b8', border: 'rgba(148, 163, 184, 0.2)', bg: 'rgba(148, 163, 184, 0.06)', aliases: ['context', 'boundary'] },
    { id: 'study_area', label: 'STUDY AREA', color: '#94a3b8', border: 'rgba(148, 163, 184, 0.2)', bg: 'rgba(148, 163, 184, 0.06)', aliases: ['study_area', 'aoi', 'bbox'] },
  ];

  function closePanel() {
    $activeSidebarTab = 'chat';
  }

  function setSkin(skinId: string) {
    $currentGlobeSkin = skinId;
  }

  function toggleLayerVisibility(layerId: string) {
    activeDataLayers.update((layers) =>
      layers.map((l) =>
        l.layer_id === layerId
          ? { ...l, visible: l.visible === false ? true : false }
          : l
      )
    );
  }

  function updateLayerOpacity(layerId: string, opacity: number) {
    activeDataLayers.update((layers) =>
      layers.map((l) =>
        l.layer_id === layerId
          ? { ...l, style: { ...l.style, opacity } }
          : l
      )
    );
  }

  function focusLayer(layerId: string) {
    flyToLayerTrigger.set({ layerId, timestamp: Date.now() });
  }

  function removeLayer(layerId: string) {
    activeDataLayers.update((layers) =>
      layers.filter((l) => l.layer_id !== layerId)
    );
  }

  function clearAllLayers() {
    activeDataLayers.set([]);
  }

  function toggleDatasetExpand(datasetId: string) {
    expandedDatasets[datasetId] = !expandedDatasets[datasetId];
    expandedDatasets = { ...expandedDatasets };
  }

  async function loadCatalog() {
    if (catalogLoaded || isLoadingCatalog) return;
    isLoadingCatalog = true;
    try {
      const [summaryRes, datasetsRes, layersRes] = await Promise.all([
        fetch('/api/catalog/summary'),
        fetch('/api/catalog/datasets'),
        fetch('/api/catalog/layers'),
      ]);

      if (summaryRes.ok) {
        catalogSummary = await summaryRes.json();
      }
      if (datasetsRes.ok) {
        const data = await datasetsRes.json();
        catalogDatasets = data.datasets || [];
        // Expand first dataset by default
        if (catalogDatasets.length > 0) {
          expandedDatasets[catalogDatasets[0].dataset_id] = true;
        }
      }
      if (layersRes.ok) {
        const data = await layersRes.json();
        catalogLayers = data.layers || [];
      }
      catalogLoaded = true;
    } catch (e) {
      console.warn('Failed to load catalog data:', e);
    } finally {
      isLoadingCatalog = false;
    }
  }

  function activateCatalogLayer(layer: CatalogLayer, dataset?: CatalogDataset) {
    // Check if already active
    const existing = $activeDataLayers.find((l) => l.layer_id === layer.layer_id);
    if (existing) {
      focusLayer(layer.layer_id);
      currentTab = 'active';
      return;
    }

    // Determine representative bounds from current active layers or default
    const refLayer = $activeDataLayers.find((l) => l.spatial?.bounds?.length === 4);
    const bounds = refLayer?.spatial?.bounds || [76.84, 28.40, 77.34, 28.88];
    const center = refLayer?.spatial?.center || { latitude: 28.6139, longitude: 77.2090 };

    const newLayer: DataLayerSpec = {
      layer_id: layer.layer_id,
      type: layer.visualization_type === 'rgb_composite' ? 'imagery' : 'change_detection',
      title: layer.name,
      description: layer.description,
      role: (layer.role as any) || 'primary_analysis',
      purpose: `Activated from Earth Observation Data Catalog: ${layer.description}`,
      dataset: dataset?.name || layer.dataset_id,
      model: 'Authoritative Formulation',
      date: 'Latest Available Acquisition',
      resolution: dataset?.spatial_resolution || '10m GSD',
      source: {
        type: 'geojson',
        data: {
          type: 'Feature',
          geometry: {
            type: 'Polygon',
            coordinates: [
              [
                [bounds[0], bounds[1]],
                [bounds[2], bounds[1]],
                [bounds[2], bounds[3]],
                [bounds[0], bounds[3]],
                [bounds[0], bounds[1]],
              ],
            ],
          },
          properties: { name: layer.name, category: layer.category },
        },
      },
      spatial: {
        bounds,
        center,
      },
      style: {
        opacity: 0.85,
        color: layer.category === 'vegetation' ? 'rgba(34, 197, 94, 0.35)' : 'rgba(56, 189, 248, 0.35)',
        outline_color: layer.category === 'vegetation' ? '#22c55e' : '#38bdf8',
        outline_width: 2.0,
      },
      legend: {
        type: 'categorical',
        title: layer.name,
        unit: layer.units,
        items: [{ label: layer.name, color: layer.category === 'vegetation' ? '#22c55e' : '#38bdf8' }],
      },
      provenance: {
        dataset_id: layer.dataset_id,
        model_id: 'catalog-layer',
        source: 'live',
        dataset_name: dataset?.name || layer.dataset_id,
        model_name: 'Catalog Formulation',
        date: 'Latest',
        resolution: dataset?.spatial_resolution || '10m',
      },
      access: {
        is_private: false,
      },
      visible: true,
    };

    activeDataLayers.update((prev) => [newLayer, ...prev]);
    currentTab = 'active';
  }

  $: filteredDatasets = catalogDatasets.filter((ds) => {
    const dsLayers = (ds.layers || []).filter((l) =>
      selectedCategory === 'all' || l.category.toLowerCase() === selectedCategory.toLowerCase()
    );
    const matchesCat = selectedCategory === 'all' || ds.modality.toLowerCase() === selectedCategory.toLowerCase() || dsLayers.length > 0;
    if (!matchesCat) return false;

    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      ds.name.toLowerCase().includes(q) ||
      ds.dataset_id.toLowerCase().includes(q) ||
      ds.provider.toLowerCase().includes(q) ||
      ds.mission.toLowerCase().includes(q) ||
      (ds.description || '').toLowerCase().includes(q) ||
      (ds.bands || []).some((b) => b.toLowerCase().includes(q)) ||
      (ds.layers || []).some((l) => l.name.toLowerCase().includes(q) || l.description.toLowerCase().includes(q))
    );
  });

  $: if (searchQuery.trim()) {
    filteredDatasets.forEach((ds) => {
      expandedDatasets[ds.dataset_id] = true;
    });
    expandedDatasets = { ...expandedDatasets };
  }

  function formatBounds(bounds?: number[]): string {
    if (!bounds || bounds.length !== 4) return '';
    const [w, s, e, n] = bounds;
    return `${s.toFixed(2)}°N, ${w.toFixed(2)}°E to ${n.toFixed(2)}°N, ${e.toFixed(2)}°E`;
  }

  function getTypeBadgeColor(type: string): string {
    switch (type.toLowerCase()) {
      case 'geojson':
        return '#38bdf8';
      case 'raster':
      case 'imagery':
        return '#a78bfa';
      case 'point_cloud':
      case '3d_tiles_points':
        return '#38bdf8';
      case 'heatmap':
      case 'spatial_heatmap':
        return '#fb923c';
      case '3d_surface':
      case 'terrain_elevation':
        return '#10b981';
      case '3d_extruded_polygon':
        return '#818cf8';
      case 'point':
      case 'point_detections':
        return '#ec4899';
      case 'bbox':
      case 'aoi':
        return '#34d399';
      case 'marker':
        return '#f472b6';
      default:
        return '#94a3b8';
    }
  }

  function getRoleBadge(role?: string): { label: string; bg: string; color: string; border: string } {
    const r = (role || 'primary').toLowerCase();
    const matched = semanticRoles.find((s) => s.id === r || s.aliases.includes(r));
    if (matched) {
      return { label: matched.label, bg: matched.bg, color: matched.color, border: matched.border };
    }
    return { label: 'PRIMARY', bg: 'rgba(255, 255, 255, 0.08)', color: '#f8fafc', border: 'rgba(255, 255, 255, 0.2)' };
  }

  function getSourceBadgeLabel(source?: string): { label: string; bg: string; color: string } {
    const s = source?.toLowerCase() || 'mock';
    if (s.includes('planetary') || s === 'live') {
      return { label: 'LIVE SATELLITE', bg: 'rgba(56, 189, 248, 0.12)', color: '#38bdf8' };
    }
    if (s === 'user_data') {
      return { label: 'USER RASTER', bg: 'rgba(167, 139, 250, 0.12)', color: '#c084fc' };
    }
    return { label: 'BENCHMARK', bg: 'rgba(255, 255, 255, 0.08)', color: 'rgba(255, 255, 255, 0.65)' };
  }
</script>

<aside class="layers-drawer" aria-label="Geospatial Layers Drawer">
  <!-- Header -->
  <header class="drawer-header">
    <div class="title-row">
      <div class="title-icon">
        <Layers size={16} strokeWidth={2} />
      </div>
      <div class="title-content">
        <h3 class="drawer-title">Data & Layer Catalog</h3>
        <span class="drawer-subtitle">Copernicus & federated satellite layers</span>
      </div>
    </div>

    <button
      class="close-btn"
      on:click={closePanel}
      title="Close layers panel"
      aria-label="Close layers panel"
    >
      <X size={16} strokeWidth={1.8} />
    </button>
  </header>

  <!-- Navigation Tabs -->
  <nav class="drawer-nav" aria-label="Catalog Navigation">
    <button
      class="nav-tab-btn"
      class:active={currentTab === 'active'}
      on:click={() => (currentTab = 'active')}
    >
      <span>Active Layers</span>
      <span class="tab-badge" class:has-items={$activeDataLayers.length > 0}>
        {$activeDataLayers.length}
      </span>
    </button>
    <button
      class="nav-tab-btn"
      class:active={currentTab === 'explore'}
      on:click={() => {
        currentTab = 'explore';
        loadCatalog();
      }}
    >
      <Database size={12} strokeWidth={2} />
      <span>Explore Data</span>
    </button>
    <button
      class="nav-tab-btn"
      class:active={currentTab === 'skins'}
      on:click={() => (currentTab = 'skins')}
    >
      <Globe2 size={12} strokeWidth={2} />
      <span>Globe Skins</span>
    </button>
  </nav>

  <!-- Scrollable Content -->
  <div class="drawer-content">
    <!-- =========================================================
         TAB 1: ACTIVE LAYERS (ORGANIZED BY SEMANTIC ROLES)
         ========================================================= -->
    {#if currentTab === 'active'}
      <div class="active-tab-container">
        <!-- Actions Toolbar -->
        <div class="section-heading-row">
          <div class="heading-with-icon">
            <Sparkles size={12} class="section-icon" />
            <span class="section-heading">ACTIVE SATELLITE LAYERS</span>
          </div>
          <div class="heading-actions">
            {#if $activeDataLayers.length > 0}
              <button
                class="clear-all-btn"
                on:click={clearAllLayers}
                title="Remove all active analysis layers"
              >
                <Trash2 size={11} />
                <span>Clear All</span>
              </button>
            {/if}
          </div>
        </div>

        <!-- EMPTY STATE -->
        {#if $activeDataLayers.length === 0}
          <div class="empty-layers-card">
            <div class="empty-icon-box">
              <Compass size={22} strokeWidth={1.5} />
            </div>
            <h4 class="empty-title">No Active Layers in Session</h4>
            <p class="empty-desc">
              Submit a natural language Earth Observation query or browse the <strong>Explore Data</strong> catalog to activate satellite and analytical layers.
            </p>
            <button
              class="explore-now-btn"
              on:click={() => {
                currentTab = 'explore';
                loadCatalog();
              }}
            >
              <Database size={13} />
              <span>Explore 13 Satellite Datasets</span>
            </button>
          </div>
        {:else}
          <!-- ORGANIZED BY SEMANTIC ROLE -->
          {#each semanticRoles as roleDef}
            {@const roleLayers = $activeDataLayers.filter((l) => {
              const r = (l.role || 'primary').toLowerCase();
              const matched = semanticRoles.find((s) => s.id === r || s.aliases.includes(r));
              if (matched) return matched.id === roleDef.id;
              return roleDef.id === 'primary';
            })}
            {#if roleLayers.length > 0}
              <div class="role-group">
                <div class="role-group-header">
                  <span class="role-pill" style="color: {roleDef.color}; background: {roleDef.bg}; border-color: {roleDef.border};">
                    {roleDef.label}
                  </span>
                  <span class="role-count-indicator">{roleLayers.length}</span>
                </div>

                <div class="role-layers-stack">
                  {#each roleLayers as layer (layer.layer_id)}
                    {@const isVisible = layer.visible !== false}
                    {@const opacity = layer.style?.opacity ?? 1.0}
                    {@const typeColor = getTypeBadgeColor(layer.type)}
                    {@const srcBadge = getSourceBadgeLabel(layer.provenance?.source)}

                    <div class="layer-item" class:dimmed={!isVisible}>
                      <!-- Top Control Bar -->
                      <div class="layer-top-row">
                        <button
                          class="vis-toggle"
                          class:visible={isVisible}
                          on:click={() => toggleLayerVisibility(layer.layer_id)}
                          title={isVisible ? 'Hide layer' : 'Show layer'}
                          aria-label={isVisible ? `Hide ${layer.title}` : `Show ${layer.title}`}
                        >
                          {#if isVisible}
                            <Eye size={14} strokeWidth={1.8} />
                          {:else}
                            <EyeOff size={14} strokeWidth={1.8} />
                          {/if}
                        </button>

                        <div class="layer-info">
                          <div class="layer-title-line">
                            <span class="layer-title" title={layer.title}>{layer.title}</span>
                          </div>
                          <div class="layer-badges">
                            <span
                              class="layer-badge type-badge"
                              style="color: {typeColor}; border-color: {typeColor}33; background: {typeColor}15;"
                            >
                              {layer.type.replace(/_/g, ' ').toUpperCase()}
                            </span>
                            <span
                              class="layer-badge src-badge"
                              style="color: {srcBadge.color}; background: {srcBadge.bg};"
                            >
                              {srcBadge.label}
                            </span>
                          </div>
                        </div>

                        <!-- Actions -->
                        <div class="layer-actions-group">
                          <button
                            class="action-icon-btn"
                            on:click={() => focusLayer(layer.layer_id)}
                            title="Fly camera to layer extent"
                            aria-label="Fly camera to layer extent"
                          >
                            <Crosshair size={13} strokeWidth={1.8} />
                          </button>
                          <button
                            class="action-icon-btn remove-btn"
                            on:click={() => removeLayer(layer.layer_id)}
                            title="Remove layer"
                            aria-label="Remove layer"
                          >
                            <Trash2 size={12} strokeWidth={1.8} />
                          </button>
                        </div>
                      </div>

                      <!-- Authoritative Metadata Grid: DATASET | MODEL | DATE | RESOLUTION -->
                      <div class="layer-metadata-grid">
                        <div class="meta-cell">
                          <span class="meta-label">DATASET</span>
                          <span class="meta-value" title={layer.dataset || layer.provenance?.dataset_name || layer.provenance?.dataset_id || 'Satellite Sensor'}>
                            {layer.dataset || layer.provenance?.dataset_name || layer.provenance?.dataset_id || 'Satellite Sensor'}
                          </span>
                        </div>
                        <div class="meta-cell">
                          <span class="meta-label">MODEL</span>
                          <span class="meta-value" title={layer.model || layer.provenance?.model_name || layer.provenance?.model_id || 'Deterministic'}>
                            {layer.model || layer.provenance?.model_name || layer.provenance?.model_id || 'Deterministic'}
                          </span>
                        </div>
                        <div class="meta-cell">
                          <span class="meta-label">DATE</span>
                          <span class="meta-value" title={layer.date || layer.temporal?.acquisition_date || layer.provenance?.date || 'Current'}>
                            {layer.date || layer.temporal?.acquisition_date || layer.provenance?.date || 'Current'}
                          </span>
                        </div>
                        <div class="meta-cell">
                          <span class="meta-label">RESOLUTION</span>
                          <span class="meta-value" title={layer.resolution || layer.provenance?.resolution || '10m GSD'}>
                            {layer.resolution || layer.provenance?.resolution || '10m GSD'}
                          </span>
                        </div>
                      </div>

                      <!-- Purpose ("Why is this here?") -->
                      {#if layer.purpose}
                        <div class="layer-purpose-card">
                          <div class="purpose-header">
                            <Info size={11} class="purpose-icon" />
                            <span class="purpose-heading">WHY IS THIS HERE?</span>
                          </div>
                          <p class="purpose-body">{layer.purpose}</p>
                        </div>
                      {/if}

                      <!-- Description -->
                      {#if layer.description}
                        <p class="layer-description-text">{layer.description}</p>
                      {/if}

                      <!-- Spatial Extent -->
                      {#if layer.spatial?.bounds && layer.spatial.bounds.length === 4}
                        <div class="layer-extent-row">
                          <span class="extent-label">EXTENT:</span>
                          <span class="extent-val">{formatBounds(layer.spatial.bounds)}</span>
                        </div>
                      {/if}

                      <!-- Opacity Slider -->
                      {#if isVisible}
                        <div class="opacity-control">
                          <Sliders size={11} strokeWidth={1.6} class="slider-icon" />
                          <input
                            type="range"
                            min="0.05"
                            max="1.0"
                            step="0.05"
                            value={opacity}
                            on:input={(e) =>
                              updateLayerOpacity(layer.layer_id, parseFloat(e.currentTarget.value))
                            }
                            class="opacity-slider"
                            aria-label={`${layer.title} opacity`}
                          />
                          <span class="opacity-val">{Math.round(opacity * 100)}%</span>
                        </div>
                      {/if}

                      <!-- Legend Preview -->
                      {#if isVisible && layer.legend}
                        <div class="legend-box">
                          <div class="legend-header">
                            <span class="legend-title">{layer.legend.title || 'Layer Legend'}</span>
                            {#if layer.legend.unit}
                              <span class="legend-unit">({layer.legend.unit})</span>
                            {/if}
                          </div>

                          {#if layer.legend.items && layer.legend.items.length > 0}
                            <div class="legend-items-list">
                              {#each layer.legend.items as item}
                                <div class="legend-item-pill">
                                  <span
                                    class="legend-color-dot"
                                    style="background: {item.color};"
                                  ></span>
                                  <span class="legend-item-lbl">{item.label}</span>
                                  {#if item.value}
                                    <span class="legend-item-val">{item.value}</span>
                                  {/if}
                                </div>
                              {/each}
                            </div>
                          {:else if layer.legend.min !== undefined && layer.legend.max !== undefined}
                            <div class="continuous-legend">
                              <div class="spectrum-bar"></div>
                              <div class="spectrum-labels">
                                <span>{layer.legend.min}</span>
                                <span>{layer.legend.max}</span>
                              </div>
                            </div>
                          {/if}
                        </div>
                      {/if}
                    </div>
                  {/each}
                </div>
              </div>
            {/if}
          {/each}

          <div class="add-data-footer">
            <button
              class="add-data-btn"
              on:click={() => {
                currentTab = 'explore';
                loadCatalog();
              }}
            >
              <Plus size={13} strokeWidth={2} />
              <span>+ Add data</span>
            </button>
          </div>
        {/if}
      </div>

    <!-- =========================================================
         TAB 2: EXPLORE DATA CATALOG (COPERNICUS & FEDERATED DATASETS)
         ========================================================= -->
    {:else if currentTab === 'explore'}
      <div class="explore-tab-container">
        <!-- Verified Ecosystem Banner (Section 26 Compliance) -->
        <div class="catalog-summary-banner">
          <div class="banner-top">
            <ShieldCheck size={14} class="verified-icon" />
            <span class="banner-title">Copernicus Data Space Ecosystem</span>
          </div>
          <div class="stats-row">
            <div class="stat-box">
              <span class="stat-number">{catalogSummary?.verified_dataset_count || 13}</span>
              <span class="stat-label">Datasets</span>
            </div>
            <div class="stat-divider"></div>
            <div class="stat-box">
              <span class="stat-number">{catalogSummary?.verified_layer_count || 21}+</span>
              <span class="stat-label">Layers</span>
            </div>
            <div class="stat-divider"></div>
            <div class="stat-box">
              <span class="stat-number">9</span>
              <span class="stat-label">Modalities</span>
            </div>
          </div>
          <p class="verified-subtext">
            Verified provider feeds including Sentinel missions, Copernicus services, Landsat, and Cartosat.
          </p>
        </div>

        <!-- Search Input -->
        <div class="catalog-search-box">
          <Search size={13} class="search-icon" />
          <input
            type="text"
            placeholder="Search missions, bands, NO2, SAR, NDVI..."
            bind:value={searchQuery}
            class="catalog-search-input"
          />
          {#if searchQuery}
            <button class="clear-search-btn" on:click={() => (searchQuery = '')}>
              <X size={12} />
            </button>
          {/if}
        </div>

        <!-- Category Filters -->
        <div class="category-pills-row">
          {#each categories as cat}
            <button
              class="category-pill"
              class:active={selectedCategory === cat.id}
              on:click={() => (selectedCategory = cat.id)}
            >
              {cat.label}
            </button>
          {/each}
        </div>

        <!-- Datasets List -->
        {#if isLoadingCatalog}
          <div class="catalog-loading-box">
            <Sparkles size={18} class="spinning-icon" />
            <span>Loading verified Earth observation catalog...</span>
          </div>
        {:else if filteredDatasets.length === 0}
          <div class="empty-state">
            <Layers size={22} class="empty-icon" />
            <span class="empty-title">No matching datasets found</span>
            <span class="empty-subtitle">Try adjusting your search terms or selecting a different category filter.</span>
          </div>
        {:else}
          <div class="catalog-datasets-list">
            {#each filteredDatasets as ds (ds.dataset_id)}
              {@const isExpanded = !!expandedDatasets[ds.dataset_id]}
              {@const dsLayers = (ds.layers || []).filter((l) =>
                selectedCategory === 'all' || l.category.toLowerCase() === selectedCategory.toLowerCase()
              )}

              {#if selectedCategory === 'all' || dsLayers.length > 0}
                <div class="catalog-dataset-card">
                  <!-- Dataset Header -->
                  <button type="button" class="dataset-card-header" on:click={() => toggleDatasetExpand(ds.dataset_id)}>
                    <div class="dataset-title-col">
                      <div class="dataset-name-line">
                        <span class="dataset-name">{ds.name}</span>
                        <span class="modality-tag">{ds.modality.toUpperCase()}</span>
                      </div>
                      <span class="dataset-provider">{ds.provider} • {ds.spatial_resolution}</span>
                    </div>

                    <span class="expand-btn" aria-hidden="true">
                      {#if isExpanded}
                        <ChevronDown size={14} />
                      {:else}
                        <ChevronRight size={14} />
                      {/if}
                    </span>
                  </button>

                  <!-- Expanded Layer List -->
                  {#if isExpanded}
                    <div class="dataset-body">
                      {#if ds.description}
                        <p class="dataset-desc">{ds.description}</p>
                      {/if}

                      <div class="dataset-meta-specs">
                        <div class="spec-chip">
                          <span class="spec-k">Sensor:</span>
                          <span class="spec-v">{ds.sensor}</span>
                        </div>
                        <div class="spec-chip">
                          <span class="spec-k">Resolution:</span>
                          <span class="spec-v">{ds.spatial_resolution}</span>
                        </div>
                        {#if ds.bands && ds.bands.length > 0}
                          <div class="spec-chip bands-chip">
                            <span class="spec-k">Bands:</span>
                            <span class="spec-v">{ds.bands.slice(0, 6).join(', ')}{ds.bands.length > 6 ? ` +${ds.bands.length - 6}` : ''}</span>
                          </div>
                        {/if}
                      </div>

                      <div class="dataset-layers-header">
                        <span class="layers-header-title">Exposed Layers ({dsLayers.length})</span>
                      </div>

                      <div class="dataset-layer-items">
                        {#each dsLayers as layer}
                          <div class="catalog-layer-row">
                            <div class="cat-layer-info">
                              <div class="cat-layer-name-line">
                                <span class="cat-layer-name">{layer.name}</span>
                                <span class="cat-layer-cat">{layer.category}</span>
                              </div>
                              <span class="cat-layer-desc">{layer.description}</span>
                              {#if layer.required_bands && layer.required_bands.length > 0}
                                <span class="cat-layer-bands">Requires: {layer.required_bands.join(', ')}</span>
                              {/if}
                            </div>

                            <button
                              class="activate-layer-btn"
                              on:click={() => activateCatalogLayer(layer, ds)}
                              title="Activate layer in 3D globe session"
                            >
                              <Plus size={12} strokeWidth={2.5} />
                              <span>Activate</span>
                            </button>
                          </div>
                        {/each}
                      </div>
                    </div>
                  {/if}
                </div>
              {/if}
            {/each}
          </div>
        {/if}
      </div>

    <!-- =========================================================
         TAB 3: GLOBE SKINS (BASEMAPS)
         ========================================================= -->
    {:else if currentTab === 'skins'}
      <section class="layer-section">
        <div class="section-heading-row">
          <div class="heading-with-icon">
            <Globe2 size={12} class="section-icon" />
            <span class="section-heading">GLOBE SKIN / BASEMAP</span>
          </div>
          <span class="section-badge">Base index 0</span>
        </div>

        <p class="section-description">
          Modifies base Earth presentation without reloading or altering analytical satellite layers.
        </p>

        <div class="skins-grid">
          {#each skins as skin}
            {@const isSelected = $currentGlobeSkin === skin.id}
            <button
              class="skin-card"
              class:active={isSelected}
              on:click={() => setSkin(skin.id)}
              title={skin.description}
            >
              <div class="skin-header">
                <span
                  class="skin-swatch"
                  style="background: {skin.previewColor};"
                ></span>
                <span class="skin-name">{skin.name}</span>
                {#if isSelected}
                  <span class="active-check">
                    <Check size={11} strokeWidth={2.5} />
                  </span>
                {/if}
              </div>
              <span class="skin-desc">{skin.description}</span>
            </button>
          {/each}
        </div>
      </section>
    {/if}
  </div>
</aside>

<style>
  /* DRAWER CONTAINER */
  .layers-drawer {
    width: 330px;
    height: 100%;
    flex-shrink: 0;
    position: relative;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    background: #080a0f;
    border-right: 1px solid rgba(255, 255, 255, 0.08);
    color: #ffffff;
    z-index: 35;
    font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    box-shadow: 12px 0 32px rgba(0, 0, 0, 0.45);
  }

  /* HEADER */
  .drawer-header {
    height: 56px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 16px;
    background: rgba(255, 255, 255, 0.015);
    border-bottom: 1px solid rgba(255, 255, 255, 0.07);
  }

  .title-row {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .title-icon {
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 8px;
    background: rgba(56, 189, 248, 0.1);
    border: 1px solid rgba(56, 189, 248, 0.22);
    color: #38bdf8;
  }

  .title-content {
    display: flex;
    flex-direction: column;
    gap: 1px;
  }

  .drawer-title {
    margin: 0;
    font-size: 13px;
    font-weight: 650;
    letter-spacing: -0.01em;
    color: #ffffff;
  }

  .drawer-subtitle {
    font-size: 9px;
    color: rgba(255, 255, 255, 0.42);
  }

  .close-btn {
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 6px;
    border: 1px solid transparent;
    background: transparent;
    color: rgba(255, 255, 255, 0.4);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .close-btn:hover {
    color: #ffffff;
    background: rgba(255, 255, 255, 0.08);
    border-color: rgba(255, 255, 255, 0.12);
  }

  /* TABS NAV */
  .drawer-nav {
    display: flex;
    align-items: center;
    background: rgba(0, 0, 0, 0.35);
    border-bottom: 1px solid rgba(255, 255, 255, 0.07);
    padding: 0 8px;
    gap: 4px;
    height: 40px;
    flex-shrink: 0;
  }

  .nav-tab-btn {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 5px;
    font-size: 10.5px;
    font-weight: 600;
    padding: 6px 8px;
    border-radius: 6px;
    background: transparent;
    border: none;
    color: rgba(255, 255, 255, 0.45);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .nav-tab-btn:hover {
    color: rgba(255, 255, 255, 0.8);
    background: rgba(255, 255, 255, 0.04);
  }

  .nav-tab-btn.active {
    color: #38bdf8;
    background: rgba(56, 189, 248, 0.1);
  }

  .tab-badge {
    font-size: 9px;
    padding: 1px 5px;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.08);
    color: rgba(255, 255, 255, 0.5);
  }

  .tab-badge.has-items {
    background: rgba(56, 189, 248, 0.2);
    color: #38bdf8;
  }

  /* DRAWER CONTENT */
  .drawer-content {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding: 14px 12px 24px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .drawer-content::-webkit-scrollbar {
    width: 4px;
  }

  .drawer-content::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.14);
    border-radius: 4px;
  }

  /* ACTIVE TAB */
  .active-tab-container {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .section-heading-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 2px;
  }

  .heading-with-icon {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  :global(.section-icon) {
    color: #38bdf8;
  }

  .section-heading {
    font-size: 9.5px;
    font-weight: 700;
    letter-spacing: 0.09em;
    color: rgba(255, 255, 255, 0.65);
  }

  .heading-actions {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .clear-all-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 9.5px;
    padding: 2px 7px;
    border-radius: 4px;
    background: rgba(239, 68, 68, 0.08);
    border: 1px solid rgba(239, 68, 68, 0.2);
    color: #f87171;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .clear-all-btn:hover {
    background: rgba(239, 68, 68, 0.18);
    color: #fca5a5;
  }

  .add-data-footer {
    padding: 10px 0 16px 0;
    display: flex;
    justify-content: center;
  }

  .add-data-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    width: 100%;
    padding: 8px 14px;
    font-size: 11.5px;
    font-weight: 500;
    color: #cbd5e1;
    background: rgba(255, 255, 255, 0.04);
    border: 1px dashed rgba(255, 255, 255, 0.16);
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .add-data-btn:hover {
    background: rgba(255, 255, 255, 0.08);
    border-color: rgba(255, 255, 255, 0.28);
    color: #ffffff;
  }

  /* ROLE GROUPS */
  .role-group {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .role-group-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 2px 4px;
  }

  .role-pill {
    font-size: 8.5px;
    font-weight: 750;
    letter-spacing: 0.08em;
    padding: 2px 7px;
    border-radius: 4px;
    border: 1px solid;
  }

  .role-count-indicator {
    font-size: 9px;
    color: rgba(255, 255, 255, 0.35);
  }

  .role-layers-stack {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  /* LAYER CARD */
  .layer-item {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 11px;
    border-radius: 9px;
    background: rgba(255, 255, 255, 0.025);
    border: 1px solid rgba(255, 255, 255, 0.07);
    transition: all 0.15s ease;
  }

  .layer-item:hover {
    border-color: rgba(255, 255, 255, 0.12);
    background: rgba(255, 255, 255, 0.035);
  }

  .layer-item.dimmed {
    opacity: 0.45;
  }

  .layer-top-row {
    display: flex;
    align-items: flex-start;
    gap: 8px;
  }

  .vis-toggle {
    width: 26px;
    height: 26px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 6px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: rgba(255, 255, 255, 0.4);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .vis-toggle.visible {
    background: rgba(56, 189, 248, 0.14);
    border-color: rgba(56, 189, 248, 0.35);
    color: #38bdf8;
  }

  .layer-info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  .layer-title-line {
    display: flex;
    align-items: center;
  }

  .layer-title {
    font-size: 11.5px;
    font-weight: 650;
    color: #ffffff;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .layer-badges {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 4px;
  }

  .layer-badge {
    font-size: 8px;
    font-weight: 700;
    padding: 1px 5px;
    border-radius: 3px;
    letter-spacing: 0.04em;
    border: 1px solid transparent;
  }

  .layer-actions-group {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .action-icon-btn {
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 5px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: rgba(255, 255, 255, 0.45);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .action-icon-btn:hover {
    color: #ffffff;
    background: rgba(255, 255, 255, 0.1);
  }

  .action-icon-btn.remove-btn:hover {
    color: #f87171;
    border-color: rgba(239, 68, 68, 0.3);
  }

  /* METADATA GRID */
  .layer-metadata-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px;
    padding: 7px 8px;
    background: rgba(0, 0, 0, 0.35);
    border-radius: 6px;
    border: 1px solid rgba(255, 255, 255, 0.05);
  }

  .meta-cell {
    display: flex;
    flex-direction: column;
    gap: 1px;
    min-width: 0;
  }

  .meta-label {
    font-size: 7.5px;
    font-weight: 700;
    letter-spacing: 0.08em;
    color: rgba(255, 255, 255, 0.35);
  }

  .meta-value {
    font-size: 9.5px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.85);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  /* PURPOSE BOX */
  .layer-purpose-card {
    display: flex;
    flex-direction: column;
    gap: 3px;
    padding: 6px 8px;
    background: rgba(56, 189, 248, 0.05);
    border: 1px solid rgba(56, 189, 248, 0.15);
    border-radius: 6px;
  }

  .purpose-header {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  :global(.purpose-icon) {
    color: #38bdf8;
  }

  .purpose-heading {
    font-size: 8px;
    font-weight: 750;
    letter-spacing: 0.08em;
    color: #38bdf8;
  }

  .purpose-body {
    margin: 0;
    font-size: 9px;
    line-height: 1.35;
    color: rgba(255, 255, 255, 0.75);
  }

  .layer-description-text {
    margin: 0;
    font-size: 9px;
    line-height: 1.35;
    color: rgba(255, 255, 255, 0.45);
  }

  .layer-extent-row {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 8.5px;
    color: rgba(255, 255, 255, 0.35);
  }

  .extent-label {
    font-weight: 700;
    letter-spacing: 0.05em;
  }

  .extent-val {
    font-family: monospace;
    color: rgba(255, 255, 255, 0.55);
  }

  /* OPACITY CONTROL */
  .opacity-control {
    display: flex;
    align-items: center;
    gap: 7px;
    padding-top: 2px;
  }

  :global(.slider-icon) {
    color: rgba(255, 255, 255, 0.35);
    flex-shrink: 0;
  }

  .opacity-slider {
    flex: 1;
    height: 4px;
    border-radius: 2px;
    accent-color: #38bdf8;
    background: rgba(255, 255, 255, 0.12);
    cursor: pointer;
  }

  .opacity-val {
    font-size: 8.5px;
    font-family: monospace;
    color: rgba(255, 255, 255, 0.45);
    min-width: 24px;
    text-align: right;
  }

  /* LEGEND */
  .legend-box {
    display: flex;
    flex-direction: column;
    gap: 5px;
    padding: 6px 8px;
    background: rgba(0, 0, 0, 0.25);
    border-radius: 6px;
    border: 1px solid rgba(255, 255, 255, 0.05);
  }

  .legend-header {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 8.5px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.6);
  }

  .legend-unit {
    font-size: 8px;
    color: rgba(255, 255, 255, 0.35);
  }

  .legend-items-list {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
  }

  .legend-item-pill {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 8.5px;
    background: rgba(255, 255, 255, 0.04);
    padding: 2px 6px;
    border-radius: 4px;
    color: rgba(255, 255, 255, 0.8);
  }

  .legend-color-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .legend-item-val {
    color: rgba(255, 255, 255, 0.4);
  }

  .continuous-legend {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  .spectrum-bar {
    height: 6px;
    border-radius: 3px;
    background: linear-gradient(to right, #22c55e, #eab308, #ef4444);
  }

  .spectrum-labels {
    display: flex;
    justify-content: space-between;
    font-size: 8px;
    font-family: monospace;
    color: rgba(255, 255, 255, 0.4);
  }

  /* EMPTY CARD */
  .empty-layers-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    padding: 24px 16px;
    border-radius: 10px;
    background: rgba(255, 255, 255, 0.015);
    border: 1px dashed rgba(255, 255, 255, 0.1);
    gap: 8px;
  }

  .empty-icon-box {
    width: 44px;
    height: 44px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(255, 255, 255, 0.03);
    color: rgba(255, 255, 255, 0.3);
    margin-bottom: 4px;
  }

  .empty-title {
    margin: 0;
    font-size: 12px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.7);
  }

  .empty-desc {
    margin: 0;
    font-size: 9.5px;
    line-height: 1.45;
    color: rgba(255, 255, 255, 0.35);
  }

  .empty-desc strong {
    color: #38bdf8;
  }

  .explore-now-btn {
    margin-top: 8px;
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 10.5px;
    font-weight: 600;
    padding: 7px 12px;
    border-radius: 6px;
    background: rgba(56, 189, 248, 0.12);
    border: 1px solid rgba(56, 189, 248, 0.28);
    color: #38bdf8;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .explore-now-btn:hover {
    background: rgba(56, 189, 248, 0.22);
    border-color: rgba(56, 189, 248, 0.45);
  }

  /* EXPLORE CATALOG TAB */
  .explore-tab-container {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .catalog-summary-banner {
    padding: 10px 12px;
    border-radius: 8px;
    background: linear-gradient(135deg, rgba(56, 189, 248, 0.08), rgba(99, 102, 241, 0.08));
    border: 1px solid rgba(56, 189, 248, 0.2);
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .banner-top {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  :global(.verified-icon) {
    color: #38bdf8;
  }

  .banner-title {
    font-size: 11px;
    font-weight: 700;
    color: #ffffff;
  }

  .stats-row {
    display: flex;
    align-items: center;
    justify-content: space-around;
    padding: 6px 0;
    background: rgba(0, 0, 0, 0.3);
    border-radius: 6px;
  }

  .stat-box {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1px;
  }

  .stat-number {
    font-size: 13px;
    font-weight: 750;
    color: #38bdf8;
  }

  .stat-label {
    font-size: 7.5px;
    font-weight: 600;
    letter-spacing: 0.06em;
    color: rgba(255, 255, 255, 0.45);
    text-transform: uppercase;
  }

  .stat-divider {
    width: 1px;
    height: 18px;
    background: rgba(255, 255, 255, 0.1);
  }

  .verified-subtext {
    margin: 0;
    font-size: 8.5px;
    line-height: 1.35;
    color: rgba(255, 255, 255, 0.4);
  }

  /* SEARCH BOX */
  .catalog-search-box {
    position: relative;
    display: flex;
    align-items: center;
  }

  :global(.search-icon) {
    position: absolute;
    left: 9px;
    color: rgba(255, 255, 255, 0.35);
    pointer-events: none;
  }

  .catalog-search-input {
    width: 100%;
    height: 32px;
    padding: 0 28px 0 28px;
    font-size: 10.5px;
    border-radius: 6px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #ffffff;
    outline: none;
    transition: all 0.15s ease;
  }

  .catalog-search-input:focus {
    border-color: rgba(56, 189, 248, 0.4);
    background: rgba(56, 189, 248, 0.05);
  }

  .clear-search-btn {
    position: absolute;
    right: 8px;
    width: 18px;
    height: 18px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: transparent;
    border: none;
    color: rgba(255, 255, 255, 0.4);
    cursor: pointer;
  }

  /* CATEGORY PILLS */
  .category-pills-row {
    display: flex;
    align-items: center;
    gap: 4px;
    overflow-x: auto;
    padding-bottom: 2px;
  }

  .category-pills-row::-webkit-scrollbar {
    display: none;
  }

  .category-pill {
    white-space: nowrap;
    font-size: 9px;
    font-weight: 600;
    padding: 4px 8px;
    border-radius: 12px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: rgba(255, 255, 255, 0.55);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .category-pill:hover {
    color: #ffffff;
    background: rgba(255, 255, 255, 0.08);
  }

  .category-pill.active {
    background: rgba(56, 189, 248, 0.16);
    border-color: rgba(56, 189, 248, 0.4);
    color: #38bdf8;
  }

  /* DATASET CARD IN CATALOG */
  .catalog-datasets-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .catalog-dataset-card {
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.07);
    overflow: hidden;
    transition: all 0.15s ease;
  }

  .dataset-card-header {
    width: 100%;
    border: none;
    text-align: left;
    padding: 10px 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    cursor: pointer;
    background: rgba(255, 255, 255, 0.015);
    user-select: none;
  }

  .dataset-card-header:hover {
    background: rgba(255, 255, 255, 0.04);
  }

  .dataset-title-col {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }

  .dataset-name-line {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .dataset-name {
    font-size: 11.5px;
    font-weight: 650;
    color: #ffffff;
  }

  .modality-tag {
    font-size: 7.5px;
    font-weight: 700;
    padding: 1px 4px;
    border-radius: 3px;
    background: rgba(56, 189, 248, 0.12);
    color: #38bdf8;
    border: 1px solid rgba(56, 189, 248, 0.25);
  }

  .dataset-provider {
    font-size: 8.5px;
    color: rgba(255, 255, 255, 0.4);
  }

  .expand-btn {
    width: 22px;
    height: 22px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
    background: transparent;
    border: none;
    color: rgba(255, 255, 255, 0.4);
    cursor: pointer;
  }

  .dataset-body {
    padding: 8px 12px 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    border-top: 1px solid rgba(255, 255, 255, 0.05);
    background: rgba(0, 0, 0, 0.25);
  }

  .dataset-desc {
    margin: 0;
    font-size: 9px;
    line-height: 1.35;
    color: rgba(255, 255, 255, 0.55);
  }

  .dataset-meta-specs {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }

  .spec-chip {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 8px;
    padding: 2px 6px;
    border-radius: 4px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.06);
  }

  .spec-k {
    color: rgba(255, 255, 255, 0.35);
  }

  .spec-v {
    color: rgba(255, 255, 255, 0.8);
    font-weight: 550;
  }

  .dataset-layers-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-top: 4px;
  }

  .layers-header-title {
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.06em;
    color: rgba(255, 255, 255, 0.4);
    text-transform: uppercase;
  }

  .dataset-layer-items {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .catalog-layer-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 7px 8px;
    border-radius: 6px;
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.05);
  }

  .catalog-layer-row:hover {
    background: rgba(255, 255, 255, 0.04);
    border-color: rgba(255, 255, 255, 0.09);
  }

  .cat-layer-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
    flex: 1;
  }

  .cat-layer-name-line {
    display: flex;
    align-items: center;
    gap: 5px;
  }

  .cat-layer-name {
    font-size: 10px;
    font-weight: 650;
    color: #ffffff;
  }

  .cat-layer-cat {
    font-size: 7.5px;
    padding: 1px 4px;
    border-radius: 3px;
    background: rgba(255, 255, 255, 0.05);
    color: rgba(255, 255, 255, 0.45);
  }

  .cat-layer-desc {
    font-size: 8.5px;
    line-height: 1.3;
    color: rgba(255, 255, 255, 0.4);
  }

  .cat-layer-bands {
    font-size: 8px;
    font-family: monospace;
    color: #38bdf8;
  }

  .activate-layer-btn {
    display: flex;
    align-items: center;
    gap: 3px;
    font-size: 9px;
    font-weight: 600;
    padding: 4px 8px;
    border-radius: 5px;
    background: rgba(56, 189, 248, 0.12);
    border: 1px solid rgba(56, 189, 248, 0.28);
    color: #38bdf8;
    cursor: pointer;
    transition: all 0.15s ease;
    flex-shrink: 0;
  }

  .activate-layer-btn:hover {
    background: rgba(56, 189, 248, 0.22);
    border-color: rgba(56, 189, 248, 0.45);
  }

  .catalog-loading-box {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    padding: 32px 16px;
    font-size: 10px;
    color: rgba(255, 255, 255, 0.45);
  }

  :global(.spinning-icon) {
    color: #38bdf8;
    animation: spin 2s linear infinite;
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }

  /* SKINS GRID */
  .layer-section {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .section-badge {
    font-size: 8.5px;
    font-family: monospace;
    padding: 2px 6px;
    border-radius: 4px;
    background: rgba(255, 255, 255, 0.05);
    color: rgba(255, 255, 255, 0.4);
    border: 1px solid rgba(255, 255, 255, 0.06);
  }

  .section-description {
    margin: 0;
    font-size: 9.5px;
    line-height: 1.4;
    color: rgba(255, 255, 255, 0.38);
  }

  .skins-grid {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .skin-card {
    text-align: left;
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 9px 11px;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.06);
    color: #ffffff;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .skin-card:hover {
    background: rgba(255, 255, 255, 0.05);
    border-color: rgba(255, 255, 255, 0.12);
  }

  .skin-card.active {
    background: rgba(56, 189, 248, 0.08);
    border-color: rgba(56, 189, 248, 0.35);
    box-shadow: 0 0 16px rgba(56, 189, 248, 0.08);
  }

  .skin-header {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .skin-swatch {
    width: 12px;
    height: 12px;
    border-radius: 3px;
    border: 1px solid rgba(255, 255, 255, 0.25);
    flex-shrink: 0;
  }

  .skin-name {
    flex: 1;
    font-size: 11.5px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.9);
  }

  .skin-card.active .skin-name {
    color: #ffffff;
  }

  .active-check {
    color: #38bdf8;
    display: flex;
  }

  .skin-desc {
    font-size: 9px;
    line-height: 1.35;
    color: rgba(255, 255, 255, 0.35);
  }
</style>