<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { globeLocation, layersState, currentResult, activeDataLayers, currentGlobeSkin, flyToLayerTrigger, type DataLayerSpec } from '../stores';
  import { Plus, Minus, Crosshair, Edit3 } from 'lucide-svelte';
  import * as Cesium from 'cesium';
  import 'cesium/Build/Cesium/Widgets/widgets.css';
  import { CesiumLayerManager } from '../services/CesiumLayerManager';
  import { GlobeSkinManager } from '../services/globeSkinManager';

  export let viewState: 'landing' | 'processing' | 'analysis' = 'landing';

  let container: HTMLDivElement;
  let viewer: Cesium.Viewer | null = null;
  let layerManager: CesiumLayerManager | null = null;
  let skinManager: GlobeSkinManager | null = null;

  let markerEntity: Cesium.Entity | null = null;
  let polygonEntity: Cesium.Entity | null = null;
  let satelliteLayer: any = null;

  let spatialOverlayEntities: Cesium.Entity[] = [];
  let changeOverlayEntity: Cesium.Entity | null = null;
  let floodOverlayEntity: Cesium.Entity | null = null;
  let heatmapEntities: Cesium.Entity[] = [];

  let removePostRenderListener: (() => void) | null = null;

  let previousTrigger = 0;
  let isUserInteracting = false;
  let resizeObserver: ResizeObserver | null = null;


  /* =========================================================
     LANDING CAMERA
     ========================================================= */

  function setLandingView() {
    if (!viewer || viewer.isDestroyed()) return;

    viewer.camera.setView({
      destination: Cesium.Cartesian3.fromDegrees(
  78.0,
  14.0,
  6500000
),

      orientation: {
        heading: Cesium.Math.toRadians(0),
        pitch: Cesium.Math.toRadians(-81),
        roll: 0.0
      }
    });
  }


  /* =========================================================
     INITIALIZE CESIUM
     ========================================================= */

  onMount(() => {
    Cesium.Ion.defaultAccessToken = '';

    try {
      viewer = new Cesium.Viewer(container, {
        animation: false,
        baseLayerPicker: false,
        fullscreenButton: false,
        geocoder: false,
        homeButton: false,
        infoBox: false,
        sceneModePicker: false,
        selectionIndicator: false,
        timeline: false,
        navigationHelpButton: false,
        navigationInstructionsInitiallyVisible: false,

        baseLayer: false,

        /*
         * IMPORTANT:
         * Transparent Cesium canvas.
         * This allows the static space background
         * to remain fixed while only the Earth
         * container is moved.
         */
        contextOptions: {
          webgl: {
            alpha: true
          }
        },

        /*
         * Disable Cesium's own sky.
         * The space background is rendered separately.
         */
        skyAtmosphere: false
      });


      /* =====================================================
         GLOBE SKIN / BASEMAP SYSTEM (PHASE 8)
         ===================================================== */
      try {
        skinManager = new GlobeSkinManager(viewer);
        skinManager.setSkin($currentGlobeSkin || 'dark');
      } catch (skinErr) {
        console.warn('GlobeSkinManager setup failed:', skinErr);
      }


      /* =====================================================
         SCENE SETTINGS
         ===================================================== */

      viewer.scene.globe.depthTestAgainstTerrain = false;

      /*
       * Transparent scene.
       */
      viewer.scene.backgroundColor =
        Cesium.Color.TRANSPARENT;

      viewer.scene.globe.showGroundAtmosphere = true;
      viewer.scene.globe.enableLighting = false;


      /* =====================================================
         USER INTERACTION
         ===================================================== */

      let resumeTimeout: ReturnType<typeof setTimeout> | null =
        null;

      const handler =
        new Cesium.ScreenSpaceEventHandler(
          viewer.scene.canvas
        );


      handler.setInputAction(() => {
        isUserInteracting = true;

        if (resumeTimeout) {
          clearTimeout(resumeTimeout);
          resumeTimeout = null;
        }
      }, Cesium.ScreenSpaceEventType.LEFT_DOWN);


      handler.setInputAction(() => {
        if (resumeTimeout) {
          clearTimeout(resumeTimeout);
        }

        resumeTimeout = setTimeout(() => {
          isUserInteracting = false;
        }, 2000);

      }, Cesium.ScreenSpaceEventType.LEFT_UP);


      handler.setInputAction(() => {
        isUserInteracting = true;

        if (resumeTimeout) {
          clearTimeout(resumeTimeout);
        }

        resumeTimeout = setTimeout(() => {
          isUserInteracting = false;
        }, 2000);

      }, Cesium.ScreenSpaceEventType.WHEEL);


      /* =====================================================
         SLOW LANDING ROTATION
         ===================================================== */

      const onPostRender = () => {
        if (
          viewState === 'landing' &&
          !isUserInteracting &&
          viewer
        ) {
          viewer.scene.camera.rotate(
            Cesium.Cartesian3.UNIT_Z,
            0.00035
          );
        }
      };

      viewer.scene.postRender.addEventListener(
        onPostRender
      );

      removePostRenderListener = () => {
        viewer?.scene.postRender.removeEventListener(
          onPostRender
        );
      };


      /* =====================================================
         RESIZE
         ===================================================== */

      if (window.ResizeObserver) {
        resizeObserver = new ResizeObserver(() => {
          if (
            viewer &&
            !viewer.isDestroyed()
          ) {
            viewer.resize();
          }
        });

        resizeObserver.observe(container);
      }


      /* =====================================================
         INITIAL VIEW
         ===================================================== */

      layerManager = new CesiumLayerManager(viewer);

      if (viewState === 'landing') {
        setLandingView();
      } else {
        updateGlobeEntities(
          $globeLocation.latitude,
          $globeLocation.longitude,
          $globeLocation.polygon
        );

        flyToLocation(
          $globeLocation.latitude,
          $globeLocation.longitude,
          350000
        );
      }

    } catch (err) {
      console.error(
        'Cesium initialization failed:',
        err
      );
    }
  });


  /* =========================================================
     DESTROY
     ========================================================= */

  onDestroy(() => {
    if (skinManager) {
      skinManager.destroy();
      skinManager = null;
    }

    if (layerManager) {
      layerManager.destroy();
      layerManager = null;
    }

    if (resizeObserver) {
      resizeObserver.disconnect();
      resizeObserver = null;
    }

    if (removePostRenderListener) {
      removePostRenderListener();
      removePostRenderListener = null;
    }

    if (
      viewer &&
      !viewer.isDestroyed()
    ) {
      viewer.destroy();
      viewer = null;
    }
  });


  /* =========================================================
     PUBLIC RESIZE
     ========================================================= */

  export function triggerResize() {
    setTimeout(() => {
      if (
        viewer &&
        !viewer.isDestroyed()
      ) {
        viewer.resize();
      }
    }, 50);
  }


  /* =========================================================
     PUBLIC FLY TO
     ========================================================= */

  export function flyTo(
    lat: number,
    lon: number,
    altitude = 350000
  ) {
    flyToLocation(
      lat,
      lon,
      altitude
    );
  }


  /* =========================================================
     RESET GLOBAL VIEW
     ========================================================= */

  export function resetToGlobalView() {
    if (!viewer) return;

    if (viewState === 'landing') {
      setLandingView();
      return;
    }

    viewer.camera.flyTo({
      destination:
        Cesium.Cartesian3.fromDegrees(
          78.0,
          14.0,
          6500000
        ),

      duration: 2.2,

      orientation: {
        heading:
          Cesium.Math.toRadians(0),

        pitch:
          Cesium.Math.toRadians(-80),

        roll: 0.0
      }
    });
  }


  /* =========================================================
     UPDATE GLOBE ENTITIES
     ========================================================= */

  function updateGlobeEntities(
    lat: number,
    lon: number,
    polygonCoords?: number[][]
  ) {
    if (!viewer) return;


    /* -------------------------------------------------------
       REMOVE OLD MARKER
       ------------------------------------------------------- */

    if (markerEntity) {
      viewer.entities.remove(
        markerEntity
      );

      markerEntity = null;
    }


    /* -------------------------------------------------------
       LANDING MODE HAS NO MARKERS
       ------------------------------------------------------- */

    if (viewState === 'landing') {
      if (polygonEntity) {
        viewer.entities.remove(
          polygonEntity
        );

        polygonEntity = null;
      }

      return;
    }


    /* =======================================================
       CUSTOM PIN
       ======================================================= */

    const pinCanvas =
      document.createElement('canvas');

    pinCanvas.width = 48;
    pinCanvas.height = 48;

    const ctx =
      pinCanvas.getContext('2d');

    if (ctx) {

      ctx.shadowColor =
        'rgba(255, 255, 255, 0.35)';

      ctx.shadowBlur = 10;


      /* Pin head */

      ctx.beginPath();

      ctx.arc(
        24,
        18,
        12,
        0,
        Math.PI * 2
      );

      ctx.fillStyle =
        '#10b981';

      ctx.fill();


      ctx.lineWidth = 2.5;

      ctx.strokeStyle =
        '#ffffff';

      ctx.stroke();


      /* Pin pointer */

      ctx.beginPath();

      ctx.moveTo(16, 24);
      ctx.lineTo(24, 38);
      ctx.lineTo(32, 24);

      ctx.fillStyle =
        '#10b981';

      ctx.fill();


      /* Inner dot */

      ctx.beginPath();

      ctx.arc(
        24,
        18,
        4.5,
        0,
        Math.PI * 2
      );

      ctx.fillStyle =
        '#ffffff';

      ctx.fill();
    }


    /* =======================================================
       MARKER ENTITY
       ======================================================= */

    markerEntity =
      viewer.entities.add({
        name: $globeLocation.name,

        position:
          Cesium.Cartesian3.fromDegrees(
            lon,
            lat,
            100
          ),

        billboard: {
          image: pinCanvas,

          verticalOrigin:
            Cesium.VerticalOrigin.BOTTOM,

          heightReference:
            Cesium.HeightReference.NONE
        },

        label: {
          text:
            $globeLocation.name.split(',')[0],

          font:
            '13px Plus Jakarta Sans, sans-serif',

          style:
            Cesium.LabelStyle.FILL_AND_OUTLINE,

          fillColor:
            Cesium.Color.WHITE,

          outlineColor:
            Cesium.Color.BLACK,

          outlineWidth: 3,

          verticalOrigin:
            Cesium.VerticalOrigin.TOP,

          pixelOffset:
            new Cesium.Cartesian2(0, 6)
        }
      });


    /* =======================================================
       AOI POLYGON
       ======================================================= */

    if (polygonEntity) {
      viewer.entities.remove(
        polygonEntity
      );

      polygonEntity = null;
    }


    const coords =
      polygonCoords &&
      polygonCoords.length > 2

        ? polygonCoords

        : [
            [
              lon - 0.25,
              lat - 0.22
            ],

            [
              lon + 0.25,
              lat - 0.22
            ],

            [
              lon + 0.25,
              lat + 0.22
            ],

            [
              lon - 0.25,
              lat + 0.22
            ]
          ];


    const flatHierarchy: number[] = [];

    coords.forEach((p) => {
      flatHierarchy.push(
        p[0],
        p[1]
      );
    });


    polygonEntity =
      viewer.entities.add({
        polygon: {
          hierarchy:
            Cesium.Cartesian3.fromDegreesArray(
              flatHierarchy
            ),

          material:
            Cesium.Color.fromCssColorString(
              'rgba(255, 255, 255, 0.12)'
            ),

          outline: true,

          outlineColor:
            Cesium.Color.fromCssColorString(
              'rgba(255, 255, 255, 0.7)'
            ),

          outlineWidth: 2.0
        }
      });
  }


  /* =========================================================
     FLY TO LOCATION
     ========================================================= */

  function flyToLocation(
    lat: number,
    lon: number,
    altitude = 350000
  ) {
    if (!viewer) return;

    viewer.camera.flyTo({
      destination:
        Cesium.Cartesian3.fromDegrees(
          lon,
          lat,
          altitude
        ),

      duration: 2.0,

      orientation: {
        heading:
          Cesium.Math.toRadians(0),

        pitch:
          Cesium.Math.toRadians(-62),

        roll: 0.0
      }
    });
  }


  /* =========================================================
     ZOOM
     ========================================================= */

  function zoomIn() {
    if (!viewer) return;

    viewer.camera.zoomIn(
      viewer.camera.positionCartographic.height *
        0.35
    );
  }


  function zoomOut() {
    if (!viewer) return;

    viewer.camera.zoomOut(
      viewer.camera.positionCartographic.height *
        0.35
    );
  }


  /* =========================================================
     RESET VIEW
     ========================================================= */

  function resetView() {
    if (viewState === 'landing') {
      setLandingView();
      return;
    }

    flyToLocation(
      $globeLocation.latitude,
      $globeLocation.longitude,
      350000
    );
  }


  /* =========================================================
     VIEW STATE REACTION
     ========================================================= */

  $: if (viewState) {

    triggerResize();

    if (viewState === 'landing') {

      if (
        markerEntity &&
        viewer
      ) {
        viewer.entities.remove(
          markerEntity
        );

        markerEntity = null;
      }


      if (
        polygonEntity &&
        viewer
      ) {
        viewer.entities.remove(
          polygonEntity
        );

        polygonEntity = null;
      }


      /*
       * Re-apply the landing camera
       * whenever we return to landing.
       */

      if (viewer) {
        setTimeout(() => {
          setLandingView();
        }, 50);
      }

    } else {

      updateGlobeEntities(
        $globeLocation.latitude,
        $globeLocation.longitude,
        $globeLocation.polygon
      );
    }
  }


  /* =========================================================
     FLY TRIGGER
     ========================================================= */

  $: if (
    $globeLocation.flyTrigger >
    previousTrigger
  ) {

    previousTrigger =
      $globeLocation.flyTrigger;

    updateGlobeEntities(
      $globeLocation.latitude,
      $globeLocation.longitude,
      $globeLocation.polygon
    );

    flyToLocation(
      $globeLocation.latitude,
      $globeLocation.longitude,
      viewState === 'landing'
        ? 7500000
        : 350000
    );
  }


  /* =========================================================
     CLEAR LAYERS
     ========================================================= */

  export function clearLayers() {
    if (!viewer) return;


    spatialOverlayEntities.forEach(
      (e) =>
        viewer?.entities.remove(e)
    );

    spatialOverlayEntities = [];


    heatmapEntities.forEach(
      (e) =>
        viewer?.entities.remove(e)
    );

    heatmapEntities = [];


    if (changeOverlayEntity) {

      viewer.entities.remove(
        changeOverlayEntity
      );

      changeOverlayEntity = null;
    }


    if (floodOverlayEntity) {

      viewer.entities.remove(
        floodOverlayEntity
      );

      floodOverlayEntity = null;
    }
  }


  /* =========================================================
     CHANGE LAYER
     ========================================================= */

  export function addChangeLayer(
    name: string,
    polygonCoords?: number[][],
    metric?: any,
    colorHint = 'amber'
  ) {
    if (!viewer) return;

    const lon =
      $globeLocation.longitude;

    const lat =
      $globeLocation.latitude;


    const coords =
      polygonCoords &&
      polygonCoords.length > 2

        ? polygonCoords

        : [
            [
              lon - 0.15,
              lat - 0.12
            ],

            [
              lon + 0.15,
              lat - 0.12
            ],

            [
              lon + 0.15,
              lat + 0.12
            ],

            [
              lon - 0.15,
              lat + 0.12
            ]
          ];


    const flat: number[] = [];

    coords.forEach((p) => {
      flat.push(
        p[0],
        p[1]
      );
    });


    const colorCss =
      colorHint === 'red'

        ? 'rgba(239, 68, 68, 0.35)'

        : 'rgba(245, 158, 11, 0.35)';


    const borderCss =
      colorHint === 'red'

        ? '#ef4444'

        : '#f59e0b';


    changeOverlayEntity =
      viewer.entities.add({
        name:
          name ||
          'Change Layer',

        polygon: {
          hierarchy:
            Cesium.Cartesian3.fromDegreesArray(
              flat
            ),

          material:
            Cesium.Color.fromCssColorString(
              colorCss
            ),

          outline: true,

          outlineColor:
            Cesium.Color.fromCssColorString(
              borderCss
            ),

          outlineWidth: 2.5
        }
      });


    spatialOverlayEntities.push(
      changeOverlayEntity
    );
  }


  /* =========================================================
     FLOOD LAYER
     ========================================================= */

  export function addFloodLayer(
    name: string,
    polygonCoords?: number[][],
    metric?: any
  ) {
    if (!viewer) return;

    const lon =
      $globeLocation.longitude;

    const lat =
      $globeLocation.latitude;


    const coords =
      polygonCoords &&
      polygonCoords.length > 2

        ? polygonCoords

        : [
            [
              lon - 0.18,
              lat - 0.14
            ],

            [
              lon + 0.18,
              lat - 0.14
            ],

            [
              lon + 0.18,
              lat + 0.14
            ],

            [
              lon - 0.18,
              lat + 0.14
            ]
          ];


    const flat: number[] = [];

    coords.forEach((p) => {
      flat.push(
        p[0],
        p[1]
      );
    });


    floodOverlayEntity =
      viewer.entities.add({
        name:
          name ||
          'Flood Extent Layer',

        polygon: {
          hierarchy:
            Cesium.Cartesian3.fromDegreesArray(
              flat
            ),

          material:
            Cesium.Color.fromCssColorString(
              'rgba(37, 99, 235, 0.35)'
            ),

          outline: true,

          outlineColor:
            Cesium.Color.fromCssColorString(
              'rgba(56, 189, 248, 0.95)'
            ),

          outlineWidth: 3.0
        }
      });


    spatialOverlayEntities.push(
      floodOverlayEntity
    );
  }


  /* =========================================================
     HEATMAP
     ========================================================= */

  export function addHeatmap(
    name: string,
    centerLat: number,
    centerLon: number
  ) {

    if (!viewer) return;


    const deltas = [
      [-0.1, -0.1, 'rgba(16, 185, 129, 0.4)'],
      [0.0, -0.1, 'rgba(16, 185, 129, 0.5)'],
      [0.1, -0.1, 'rgba(52, 211, 153, 0.35)'],

      [-0.1, 0.0, 'rgba(5, 150, 105, 0.55)'],
      [0.0, 0.0, 'rgba(4, 120, 87, 0.65)'],
      [0.1, 0.0, 'rgba(16, 185, 129, 0.45)'],

      [-0.1, 0.1, 'rgba(234, 179, 8, 0.4)'],
      [0.0, 0.1, 'rgba(52, 211, 153, 0.5)'],
      [0.1, 0.1, 'rgba(16, 185, 129, 0.35)']
    ];


    const cellSize = 0.08;


    deltas.forEach(
      ([dx, dy, color]) => {

        const minLon =
          centerLon +
          Number(dx) -
          cellSize / 2;

        const maxLon =
          centerLon +
          Number(dx) +
          cellSize / 2;

        const minLat =
          centerLat +
          Number(dy) -
          cellSize / 2;

        const maxLat =
          centerLat +
          Number(dy) +
          cellSize / 2;


        const cell =
          viewer?.entities.add({
            rectangle: {
              coordinates:
                Cesium.Rectangle.fromDegrees(
                  minLon,
                  minLat,
                  maxLon,
                  maxLat
                ),

              material:
                Cesium.Color.fromCssColorString(
                  String(color)
                )
            }
          });


        if (cell) {

          heatmapEntities.push(
            cell
          );

          spatialOverlayEntities.push(
            cell
          );
        }
      }
    );
  }


  /* =========================================================
     PLACEHOLDER LAYERS
     ========================================================= */

  export function addRasterLayer(
    url: string
  ) {
    console.log(
      'addRasterLayer:',
      url
    );
  }


  export function removeRasterLayer() {
    console.log(
      'removeRasterLayer'
    );
  }


  export function addChoropleth(
    geojson: any
  ) {
    console.log(
      'addChoropleth:',
      geojson
    );
  }


  export function addGrid(
    gridData: any
  ) {
    console.log(
      'addGrid:',
      gridData
    );
  }


  /* =========================================================
     LAYER VISIBILITY
     ========================================================= */

  $: if (
    $layersState &&
    viewer
  ) {

    const satLayerConfig =
      $layersState.find(
        (l) =>
          l.id === 'sentinel2_rgb'
      );


    if (
      satelliteLayer &&
      satLayerConfig
    ) {

      satelliteLayer.show =
        satLayerConfig.visible;

      satelliteLayer.alpha =
        satLayerConfig.opacity;
    }


    const aoiConfig =
      $layersState.find(
        (l) =>
          l.id === 'aoi_boundary'
      );


    if (
      polygonEntity &&
      aoiConfig
    ) {

      polygonEntity.show =
        aoiConfig.visible;
    }


    const changeConfig =
      $layersState.find(
        (l) =>
          l.id === 'change_detection' ||
          l.id === 'builtup_layer'
      );


    if (
      changeOverlayEntity &&
      changeConfig
    ) {

      changeOverlayEntity.show =
        changeConfig.visible;
    }


    const floodConfig =
      $layersState.find(
        (l) =>
          l.id === 'water_layer'
      );


    if (
      floodOverlayEntity &&
      floodConfig
    ) {

      floodOverlayEntity.show =
        floodConfig.visible;
    }


    if (
      heatmapEntities.length > 0
    ) {

      const vegConfig =
        $layersState.find(
          (l) =>
            l.id === 'ndvi_mask'
        );


      if (vegConfig) {

        heatmapEntities.forEach(
          (e) =>
            (e.show =
              vegConfig.visible)
        );
      }
    }
  }


  /* =========================================================
     CURRENT RESULT
     ========================================================= */

  $: if (
    $currentResult &&
    viewer &&
    viewState !== 'landing'
  ) {

    clearLayers();


    const visList =
      $currentResult.visualizations ||
      [];


    const cesiumVis =
      visList.find(
        (v: any) =>
          v.renderer === 'cesium'
      );


    const cat =
      (
        $currentResult.analysis_type ||
        ''
      ).toLowerCase();


    if (cesiumVis) {

      const vType =
        cesiumVis.type;

      const layer =
        cesiumVis.layer || {};


      if (
        vType === 'flood_extent'
      ) {

        addFloodLayer(
          cesiumVis.title,
          $globeLocation.polygon,
          layer.metric
        );

      } else if (
        vType === 'change_layer'
      ) {

        addChangeLayer(
          cesiumVis.title,
          $globeLocation.polygon,
          layer.metric,
          layer.color_hint ||
            'amber'
        );

      } else if (
        vType === 'heatmap'
      ) {

        addHeatmap(
          cesiumVis.title,
          $globeLocation.latitude,
          $globeLocation.longitude
        );

      } else {

        addChangeLayer(
          cesiumVis.title,
          $globeLocation.polygon,
          layer.metric,
          layer.color_hint ||
            'red'
        );
      }

    } else if (
      cat === 'flood'
    ) {

      addFloodLayer(
        'Flood Inundation Extent',
        $globeLocation.polygon
      );

    } else if (
      cat === 'urban'
    ) {

      addChangeLayer(
        'Urban Built-Up Expansion',
        $globeLocation.polygon,
        null,
        'amber'
      );

    } else if (
      cat === 'vegetation' ||
      cat === 'wildfire'
    ) {

        addChangeLayer(
        'Vegetation Disturbance',
        $globeLocation.polygon,
        null,
        'red'
      );
    }
  }


  /* =========================================================
     CESIUM DATA LAYER MANAGER SYNCHRONIZATION (PHASE 4)
     ========================================================= */

  let renderedLayerIds = new Set<string>();

  $: if (layerManager && viewer && !viewer.isDestroyed() && viewState !== 'landing') {
    const currentSpecs = $activeDataLayers || [];
    const newIds = new Set(currentSpecs.map((s) => s.layer_id));

    // Remove any layers no longer present in store
    for (const id of Array.from(renderedLayerIds)) {
      if (!newIds.has(id)) {
        layerManager.removeLayer(id);
      }
    }

    // Add or update layers
    for (const spec of currentSpecs) {
      if (!renderedLayerIds.has(spec.layer_id)) {
        layerManager.addLayer(spec, false);
      } else {
        layerManager.updateLayer(spec);
      }
    }

    renderedLayerIds = newIds;
  }

  // When currentResult emits layers, merge into activeDataLayers store
  $: if ($currentResult && $currentResult.layers && $currentResult.layers.length > 0) {
    const incoming = $currentResult.layers;
    activeDataLayers.update((existing) => {
      const map = new Map<string, DataLayerSpec>();
      for (const l of existing || []) {
        map.set(l.layer_id, l);
      }
      for (const l of incoming) {
        map.set(l.layer_id, l);
      }
      return Array.from(map.values());
    });
  }

  // Reactive Globe Skin switching (Phase 8)
  $: if (skinManager && $currentGlobeSkin) {
    skinManager.setSkin($currentGlobeSkin);
  }

  // Camera flight trigger from external components (Phase 6 / 7)
  let lastHandledFlyTimestamp = 0;
  $: if (layerManager && $flyToLayerTrigger && $flyToLayerTrigger.timestamp > lastHandledFlyTimestamp) {
    lastHandledFlyTimestamp = $flyToLayerTrigger.timestamp;
    layerManager.flyToLayer($flyToLayerTrigger.layerId);
  }

  export function getLayerManager(): CesiumLayerManager | null {
    return layerManager;
  }

  export function setLayerVisibility(layerId: string, visible: boolean) {
    layerManager?.setLayerVisibility(layerId, visible);
    activeDataLayers.update((layers) =>
      layers.map((l) => (l.layer_id === layerId ? { ...l, visible } : l))
    );
  }

  export function setLayerOpacity(layerId: string, opacity: number) {
    layerManager?.setLayerOpacity(layerId, opacity);
    activeDataLayers.update((layers) =>
      layers.map((l) => (l.layer_id === layerId ? { ...l, style: { ...l.style, opacity } } : l))
    );
  }

  export function flyToDataLayer(layerId: string, duration = 2.0) {
    layerManager?.flyToLayer(layerId, duration);
  }

  export function clearDataLayers() {
    layerManager?.clearLayers();
    renderedLayerIds.clear();
    activeDataLayers.set([]);
  }
</script>


<!-- =========================================================
     MAIN CONTAINER
     ========================================================= -->

<div
  class="globe-panel-wrapper"
  class:is-landing={viewState === 'landing'}
  class:is-split={viewState !== 'landing'}
>


  <!-- =======================================================
       STATIC SPACE BACKGROUND

       THIS NEVER MOVES.

       The Earth is rendered above this layer.
       ======================================================= -->

  {#if viewState === 'landing'}
    <div
      class="space-background"
      aria-hidden="true"
    ></div>
  {/if}


  <!-- =======================================================
       CESIUM EARTH

       Only THIS layer is moved down.
       ======================================================= -->

  <div
    bind:this={container}
    class="cesium-container"
    class:landing-earth={viewState === 'landing'}
  ></div>


  <!-- =======================================================
       ANALYSIS UI
       ======================================================= -->

  {#if viewState !== 'landing'}

    <div class="header-overlay">

      <div class="loc-name">
        {$globeLocation.name}
      </div>

      <div class="loc-coords">
        {$globeLocation.latitude.toFixed(4)}° N,
        {$globeLocation.longitude.toFixed(4)}° E
      </div>

    </div>


    <div
      class="compass-btn"
      title="North orientation"
    >
      <div class="compass-ring">
        <span class="compass-n">
          N
        </span>
      </div>
    </div>


    <div class="nav-controls">

      <button
        class="ctrl-btn"
        on:click={zoomIn}
        title="Zoom In"
      >
        <Plus size={16} />
      </button>


      <button
        class="ctrl-btn"
        on:click={zoomOut}
        title="Zoom Out"
      >
        <Minus size={16} />
      </button>


      <button
        class="ctrl-btn"
        on:click={resetView}
        title="Center on AOI"
      >
        <Crosshair size={16} />
      </button>

    </div>


    <div class="aoi-card">

      <div class="aoi-info">

        <div class="aoi-title-row">

          <Crosshair
            size={13}
            class="aoi-icon"
          />

          <span class="aoi-name">
            AOI: {$globeLocation.name}
          </span>

        </div>


        <div class="aoi-sub">
          {$globeLocation.latitude.toFixed(4)}° N,
          {$globeLocation.longitude.toFixed(4)}° E
        </div>


        <div class="aoi-area">
          Area:
          {$globeLocation.area_km2.toLocaleString()}
          km²
        </div>

      </div>


      <button
        class="edit-aoi-btn"
        title="Edit area of interest"
      >

        <Edit3 size={12} />

        <span>
          Edit AOI
        </span>

      </button>

    </div>

  {/if}

</div>


<style>

  /* =========================================================
     ROOT
     ========================================================= */

  .globe-panel-wrapper {

    width: 100%;
    height: 100%;

    position: relative;

    overflow: hidden;

    background: #000000;

    isolation: isolate;

    transition:
      all 0.5s
      cubic-bezier(
        0.16,
        1,
        0.3,
        1
      );
  }


  /* =========================================================
     STATIC SPACE
     ========================================================= */

  .space-background {

    position: absolute;

    inset: 0;

    z-index: 0;

    pointer-events: none;

    background-color: #000000;

    /*
     * Subtle static stars.
     *
     * This layer stays completely fixed.
     */

    background-image:

      radial-gradient(
        1px 1px at 7% 14%,
        rgba(255,255,255,0.65),
        transparent
      ),

      radial-gradient(
        1px 1px at 16% 68%,
        rgba(255,255,255,0.45),
        transparent
      ),

      radial-gradient(
        1px 1px at 27% 29%,
        rgba(255,255,255,0.5),
        transparent
      ),

      radial-gradient(
        1px 1px at 39% 76%,
        rgba(255,255,255,0.42),
        transparent
      ),

      radial-gradient(
        1px 1px at 51% 18%,
        rgba(255,255,255,0.55),
        transparent
      ),

      radial-gradient(
        1px 1px at 62% 48%,
        rgba(255,255,255,0.4),
        transparent
      ),

      radial-gradient(
        1px 1px at 73% 12%,
        rgba(255,255,255,0.5),
        transparent
      ),

      radial-gradient(
        1px 1px at 84% 61%,
        rgba(255,255,255,0.45),
        transparent
      ),

      radial-gradient(
        1px 1px at 94% 34%,
        rgba(255,255,255,0.55),
        transparent
      ),

      radial-gradient(
        1px 1px at 91% 87%,
        rgba(255,255,255,0.35),
        transparent
      ),

      radial-gradient(
        1px 1px at 12% 92%,
        rgba(255,255,255,0.35),
        transparent
      ),

      radial-gradient(
        1px 1px at 46% 91%,
        rgba(255,255,255,0.3),
        transparent
      ),

      radial-gradient(
        1px 1px at 68% 82%,
        rgba(255,255,255,0.35),
        transparent
      );

    background-size: 100% 100%;

  }


  /* =========================================================
     CESIUM CONTAINER
     ========================================================= */

  .cesium-container {

    position: absolute;

    left: 0;
    top: 0;

    width: 100%;
    height: 100%;

    z-index: 1;

    background: transparent;

    pointer-events: auto;
  }


  /* =========================================================
     IMPORTANT LANDING EARTH POSITION
     
     ONLY THE EARTH CANVAS MOVES.
     
     SPACE BACKGROUND DOES NOT MOVE.
     ========================================================= */

  .cesium-container.landing-earth {

    /*
     * Move the Earth downward.
     */

    top: 15%;

    /*
     * Slightly enlarge the rendering area.
     */

    height: 110%;
  }


  /* =========================================================
     CESIUM TRANSPARENCY
     ========================================================= */

  .cesium-container :global(.cesium-widget),
  .cesium-container :global(.cesium-widget canvas) {

    background: transparent !important;
  }


  .cesium-container :global(.cesium-widget) {

    width: 100%;
    height: 100%;
  }


  .cesium-container :global(.cesium-widget canvas) {

    width: 100%;
    height: 100%;
  }


  /* =========================================================
     SPLIT MODE
     ========================================================= */

  .globe-panel-wrapper.is-split {

    border-radius: 16px;

    border:
      1px solid
      rgba(255,255,255,0.08);
  }


  .globe-panel-wrapper.is-landing {

    border-radius: 0;

    border: none;
  }


  /* =========================================================
     HEADER
     ========================================================= */

  .header-overlay {

    position: absolute;

    top: 18px;
    left: 18px;

    z-index: 15;

    background:
      rgba(10,14,23,0.75);

    backdrop-filter:
      blur(10px);

    border:
      1px solid
      rgba(255,255,255,0.08);

    border-radius: 8px;

    padding:
      8px 14px;

    pointer-events: none;
  }


  .loc-name {

    font-size: 14px;

    font-weight: 700;

    color: #ffffff;

    letter-spacing: -0.2px;
  }


  .loc-coords {

    font-size: 11px;

    font-family:
      var(--font-mono);

    color:
      #94a3b8;

    margin-top: 2px;
  }


  /* =========================================================
     COMPASS
     ========================================================= */

  .compass-btn {

    position: absolute;

    top: 18px;
    right: 18px;

    z-index: 15;

    width: 36px;
    height: 36px;

    border-radius: 50%;

    background:
      rgba(10,14,23,0.85);

    border:
      1px solid
      rgba(255,255,255,0.12);

    display: flex;

    align-items: center;
    justify-content: center;

    backdrop-filter:
      blur(8px);
  }


  .compass-ring {

    display: flex;

    align-items: center;
    justify-content: center;
  }


  .compass-n {

    font-size: 12px;

    font-weight: 700;

    color: #ffffff;

    font-family:
      var(--font-mono);
  }


  /* =========================================================
     NAV CONTROLS
     ========================================================= */

  .nav-controls {

    position: absolute;

    top: 65px;
    right: 18px;

    z-index: 15;

    display: flex;

    flex-direction: column;

    gap: 4px;

    background:
      rgba(10,14,23,0.85);

    border:
      1px solid
      rgba(255,255,255,0.1);

    border-radius: 8px;

    padding: 3px;

    backdrop-filter:
      blur(8px);
  }


  .ctrl-btn {

    width: 30px;
    height: 30px;

    border-radius: 6px;

    display: flex;

    align-items: center;
    justify-content: center;

    color:
      #cbd5e1;

    background: transparent;

    border: none;

    cursor: pointer;

    transition:
      all 0.15s ease;
  }


  .ctrl-btn:hover {

    background:
      rgba(255,255,255,0.1);

    color:
      #ffffff;
  }


  /* =========================================================
     AOI CARD
     ========================================================= */

  .aoi-card {

    position: absolute;

    bottom: 18px;

    left: 18px;
    right: 18px;

    z-index: 15;

    display: flex;

    align-items: center;

    justify-content: space-between;

    background:
      rgba(11,16,27,0.88);

    border:
      1px solid
      rgba(255,255,255,0.12);

    border-radius: 10px;

    padding:
      10px 14px;

    backdrop-filter:
      blur(12px);

    box-shadow:
      0 4px 20px
      rgba(0,0,0,0.4);
  }


  .aoi-info {

    display: flex;

    flex-direction: column;

    gap: 2px;
  }


  .aoi-title-row {

    display: flex;

    align-items: center;

    gap: 6px;
  }


  :global(.aoi-icon) {

    color:
      var(--accent-emerald);
  }


  .aoi-name {

    font-size: 12px;

    font-weight: 600;

    color: #ffffff;
  }


  .aoi-sub,
  .aoi-area {

    font-size: 11px;

    font-family:
      var(--font-mono);

    color:
      #94a3b8;
  }


  .edit-aoi-btn {

    display: flex;

    align-items: center;

    gap: 6px;

    padding:
      6px 12px;

    background:
      rgba(255,255,255,0.05);

    border:
      1px solid
      rgba(255,255,255,0.15);

    border-radius: 6px;

    font-size: 11.5px;

    font-weight: 500;

    color:
      #e2e8f0;

    cursor: pointer;

    transition:
      all 0.15s ease;
  }


  .edit-aoi-btn:hover {

    background:
      rgba(255,255,255,0.10);

    border-color:
      rgba(255,255,255,0.25);

    color: #ffffff;
  }


  /* =========================================================
     MOBILE
     ========================================================= */

  @media (max-width: 700px) {

    .cesium-container.landing-earth {

      top: 18%;

      height: 108%;
    }


    .aoi-card {

      left: 10px;
      right: 10px;
      bottom: 10px;
    }

  }

</style>