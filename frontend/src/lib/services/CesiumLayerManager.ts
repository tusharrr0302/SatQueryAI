/**
 * SatQuery AI — Cesium Layer Manager (Phase 4)
 * 
 * Authoritative frontend layer lifecycle manager for CesiumJS.
 * Strictly manages dynamic geospatial data layers (AOI, analytical change overlays,
 * imagery surfaces, and user raster assets) separately from Globe Skins (basemaps).
 * 
 * Implements:
 * - addLayer(spec, autoFly)
 * - removeLayer(layerId)
 * - updateLayer(spec)
 * - setLayerVisibility(layerId, visible)
 * - setLayerOpacity(layerId, opacity)
 * - flyToLayer(layerId, duration)
 * - clearLayers()
 * - getLayers() / getLayer(layerId)
 */

import * as Cesium from 'cesium';
import type { DataLayerSpec } from '../stores';

interface ManagedLayerRecord {
  spec: DataLayerSpec;
  entities: Cesium.Entity[];
  imageryLayers: Cesium.ImageryLayer[];
}

export class CesiumLayerManager {
  private viewer: Cesium.Viewer | null = null;
  private layers = new Map<string, ManagedLayerRecord>();
  private activeFlyPromise: Promise<void> | null = null;

  constructor(viewer?: Cesium.Viewer | null) {
    if (viewer) {
      this.setViewer(viewer);
    }
  }

  /**
   * Bind or update the Cesium Viewer instance.
   */
  public setViewer(viewer: Cesium.Viewer): void {
    if (this.viewer === viewer) return;
    this.destroy();
    this.viewer = viewer;
  }

  /**
   * Add a canonical DataLayerSpec to the globe.
   * If the layer already exists, updates it dynamically without duplicate primitives.
   */
  public async addLayer(spec: DataLayerSpec, autoFly = false): Promise<void> {
    if (!this.viewer || this.viewer.isDestroyed()) {
      console.warn('[CesiumLayerManager] Cannot add layer: viewer not initialized or destroyed');
      return;
    }

    if (!spec || !spec.layer_id) {
      console.warn('[CesiumLayerManager] Invalid layer specification: missing layer_id', spec);
      return;
    }

    // If layer already registered, update properties instead of creating duplicates
    if (this.layers.has(spec.layer_id)) {
      this.updateLayer(spec);
      if (autoFly) {
        this.flyToLayer(spec.layer_id);
      }
      return;
    }

    const record: ManagedLayerRecord = {
      spec: { ...spec, visible: spec.visible !== false },
      entities: [],
      imageryLayers: [],
    };

    try {
      switch (spec.type) {
        case 'aoi':
          this.buildAoiLayer(spec, record);
          break;

        case 'imagery':
          await this.buildImageryLayer(spec, record);
          break;

        case 'change_detection':
        case 'polygon':
        case 'flood_extent':
          this.buildVectorOverlayLayer(spec, record);
          break;

        case 'user_asset':
          await this.buildUserAssetLayer(spec, record);
          break;

        default:
          // Fallback to vector overlay for any arbitrary polygon / geojson
          this.buildVectorOverlayLayer(spec, record);
          break;
      }

      this.layers.set(spec.layer_id, record);

      // Apply initial visibility and opacity
      const isVisible = spec.visible !== false;
      this.setLayerVisibility(spec.layer_id, isVisible);
      if (spec.style?.opacity !== undefined) {
        this.setLayerOpacity(spec.layer_id, spec.style.opacity);
      }

      if (autoFly) {
        this.flyToLayer(spec.layer_id);
      }
    } catch (err) {
      console.error(`[CesiumLayerManager] Failed to add layer '${spec.layer_id}':`, err);
    }
  }

  /**
   * Remove a managed layer and clean up all associated Cesium primitives and textures.
   */
  public removeLayer(layerId: string): boolean {
    const record = this.layers.get(layerId);
    if (!record || !this.viewer || this.viewer.isDestroyed()) {
      return false;
    }

    // Remove entities
    for (const entity of record.entities) {
      this.viewer.entities.remove(entity);
    }

    // Remove imagery layers
    for (const imgLayer of record.imageryLayers) {
      this.viewer.imageryLayers.remove(imgLayer, true);
    }

    this.layers.delete(layerId);
    return true;
  }

  /**
   * Update layer properties (style, opacity, visibility).
   */
  public updateLayer(spec: DataLayerSpec): void {
    const record = this.layers.get(spec.layer_id);
    if (!record) return;

    record.spec = { ...spec };

    if (spec.visible !== undefined) {
      this.setLayerVisibility(spec.layer_id, spec.visible);
    }
    if (spec.style?.opacity !== undefined) {
      this.setLayerOpacity(spec.layer_id, spec.style.opacity);
    }
  }

  /**
   * Set layer visibility.
   */
  public setLayerVisibility(layerId: string, visible: boolean): void {
    const record = this.layers.get(layerId);
    if (!record) return;

    record.spec.visible = visible;

    for (const entity of record.entities) {
      entity.show = visible;
    }
    for (const imgLayer of record.imageryLayers) {
      imgLayer.show = visible;
    }
  }

  /**
   * Set layer opacity (0.0 to 1.0).
   */
  public setLayerOpacity(layerId: string, opacity: number): void {
    const record = this.layers.get(layerId);
    if (!record) return;

    const clamped = Math.max(0, Math.min(1, opacity));
    record.spec.style.opacity = clamped;

    // Apply to imagery layers
    for (const imgLayer of record.imageryLayers) {
      imgLayer.alpha = clamped;
    }

    // Apply to polygon entities
    for (const entity of record.entities) {
      if (entity.polygon && entity.polygon.material) {
        const baseColorStr = record.spec.style.color || 'rgba(255, 255, 255, 0.4)';
        try {
          const c = Cesium.Color.fromCssColorString(baseColorStr);
          entity.polygon.material = new Cesium.ColorMaterialProperty(c.withAlpha(clamped * c.alpha));
        } catch (_) {
          // Keep existing material if color string parsing fails
        }
      }
    }
  }

  /**
   * Smoothly fly camera to a layer's bounds or center.
   */
  public flyToLayer(layerId: string, duration = 2.0): void {
    const record = this.layers.get(layerId);
    if (!record || !this.viewer || this.viewer.isDestroyed()) return;

    const spatial = record.spec.spatial;
    const bounds = spatial?.bounds;
    const center = spatial?.center;

    if (bounds && bounds.length === 4 && bounds.some((b) => b !== 0)) {
      const [west, south, east, north] = bounds;
      const rect = Cesium.Rectangle.fromDegrees(west, south, east, north);
      this.viewer.camera.flyTo({
        destination: rect,
        duration,
      });
    } else if (center && (center.latitude !== 0 || center.longitude !== 0)) {
      this.viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(center.longitude, center.latitude, 350000),
        duration,
      });
    }
  }

  /**
   * Clear all dynamic data layers managed by this manager.
   * CRITICAL: Does NOT touch the Globe Skin / basemap layer.
   */
  public clearLayers(): void {
    if (!this.viewer || this.viewer.isDestroyed()) {
      this.layers.clear();
      return;
    }

    for (const layerId of Array.from(this.layers.keys())) {
      this.removeLayer(layerId);
    }
    this.layers.clear();
  }

  /**
   * Check if a layer is currently registered.
   */
  public hasLayer(layerId: string): boolean {
    return this.layers.has(layerId);
  }

  /**
   * Get a single layer specification.
   */
  public getLayer(layerId: string): DataLayerSpec | undefined {
    return this.layers.get(layerId)?.spec;
  }

  /**
   * Get all registered data layer specifications.
   */
  public getAllLayers(): DataLayerSpec[] {
    return Array.from(this.layers.values()).map((r) => r.spec);
  }

  /**
   * Release all Cesium resources when destroyed.
   */
  public destroy(): void {
    this.clearLayers();
    this.viewer = null;
  }

  // ===========================================================================
  // PRIVATE BUILDER METHODS
  // ===========================================================================

  private buildAoiLayer(spec: DataLayerSpec, record: ManagedLayerRecord): void {
    if (!this.viewer) return;

    const polyCoords = spec.spatial.polygon;
    const bounds = spec.spatial.bounds;

    let coords: number[] = [];
    if (polyCoords && polyCoords.length >= 3) {
      coords = polyCoords.flat();
    } else if (bounds && bounds.length === 4) {
      const [w, s, e, n] = bounds;
      coords = [w, s, e, s, e, n, w, n, w, s];
    }

    if (coords.length >= 6) {
      const outlineColorStr = spec.style.outline_color || 'rgba(255, 255, 255, 0.9)';
      const fillColorStr = spec.style.color || 'rgba(255, 255, 255, 0.08)';

      const polyEntity = this.viewer.entities.add({
        name: spec.title,
        polygon: {
          hierarchy: Cesium.Cartesian3.fromDegreesArray(coords),
          material: new Cesium.ColorMaterialProperty(
            Cesium.Color.fromCssColorString(fillColorStr)
          ),
          outline: true,
          outlineColor: Cesium.Color.fromCssColorString(outlineColorStr),
          outlineWidth: spec.style.outline_width || 2.0,
          heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
        },
      });
      record.entities.push(polyEntity);
    }

    // Add marker at center if provided
    if (spec.spatial.center) {
      const { latitude, longitude } = spec.spatial.center;
      if (latitude !== 0 || longitude !== 0) {
        const marker = this.viewer.entities.add({
          name: spec.title,
          position: Cesium.Cartesian3.fromDegrees(longitude, latitude),
          point: {
            pixelSize: 8,
            color: Cesium.Color.fromCssColorString('#10b981'),
            outlineColor: Cesium.Color.WHITE,
            outlineWidth: 2,
            heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
          },
        });
        record.entities.push(marker);
      }
    }
  }

  private async buildImageryLayer(spec: DataLayerSpec, record: ManagedLayerRecord): Promise<void> {
    if (!this.viewer) return;

    const url = spec.source.url;
    const bounds = spec.spatial.bounds;
    if (!url || !bounds || bounds.length !== 4) return;

    const [w, s, e, n] = bounds;
    const rectangle = Cesium.Rectangle.fromDegrees(w, s, e, n);

    try {
      const provider = await Cesium.SingleTileImageryProvider.fromUrl(url, {
        rectangle,
      });

      const imageryLayer = this.viewer.imageryLayers.addImageryProvider(provider);
      imageryLayer.alpha = spec.style.opacity ?? 1.0;
      imageryLayer.show = spec.visible !== false;
      record.imageryLayers.push(imageryLayer);
    } catch (err) {
      console.warn(`[CesiumLayerManager] Failed to load imagery layer from '${url}':`, err);
    }
  }

  private buildVectorOverlayLayer(spec: DataLayerSpec, record: ManagedLayerRecord): void {
    if (!this.viewer) return;

    let coords: number[] = [];
    if (spec.spatial.polygon && spec.spatial.polygon.length >= 3) {
      coords = spec.spatial.polygon.flat();
    } else if (spec.spatial.bounds && spec.spatial.bounds.length === 4) {
      const [w, s, e, n] = spec.spatial.bounds;
      coords = [w, s, e, s, e, n, w, n, w, s];
    }

    if (coords.length < 6) return;

    let defaultFill = 'rgba(239, 68, 68, 0.38)';
    let defaultStroke = '#ef4444';

    if (spec.type === 'flood_extent' || spec.style.color_scale === 'blue') {
      defaultFill = 'rgba(37, 99, 235, 0.45)';
      defaultStroke = '#38bdf8';
    } else if (spec.style.color_scale === 'amber' || spec.type === 'polygon') {
      defaultFill = 'rgba(245, 158, 11, 0.38)';
      defaultStroke = '#f59e0b';
    }

    const fillColorStr = spec.style.color || defaultFill;
    const strokeColorStr = spec.style.outline_color || defaultStroke;

    const entity = this.viewer.entities.add({
      name: spec.title,
      description: new Cesium.ConstantProperty(spec.description),
      polygon: {
        hierarchy: Cesium.Cartesian3.fromDegreesArray(coords),
        material: new Cesium.ColorMaterialProperty(
          Cesium.Color.fromCssColorString(fillColorStr)
        ),
        outline: true,
        outlineColor: Cesium.Color.fromCssColorString(strokeColorStr),
        outlineWidth: spec.style.outline_width || 2.5,
        heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      },
    });
    record.entities.push(entity);
  }

  private async buildUserAssetLayer(spec: DataLayerSpec, record: ManagedLayerRecord): Promise<void> {
    if (!this.viewer) return;

    const bounds = spec.spatial.bounds;
    const url = spec.source.url;

    if (url && bounds && bounds.length === 4) {
      const [w, s, e, n] = bounds;
      const rectangle = Cesium.Rectangle.fromDegrees(w, s, e, n);

      try {
        const provider = await Cesium.SingleTileImageryProvider.fromUrl(url, {
          rectangle,
        });
        const imageryLayer = this.viewer.imageryLayers.addImageryProvider(provider);
        imageryLayer.alpha = spec.style.opacity ?? 0.9;
        imageryLayer.show = spec.visible !== false;
        record.imageryLayers.push(imageryLayer);
        return;
      } catch (err) {
        console.warn(`[CesiumLayerManager] User raster preview failed to load from '${url}':`, err);
      }
    }

    // Fallback: draw outline polygon for the user asset bounds
    this.buildVectorOverlayLayer(spec, record);
  }
}
