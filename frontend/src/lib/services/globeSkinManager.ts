/**
 * SatQuery AI — Globe Skin Manager (Phase 8)
 * 
 * Manages the underlying Cesium basemap imagery layer independently
 * of any analytical geospatial data layers.
 * 
 * Core Invariant:
 * Switching globe skins modifies ONLY the base imagery layer at index 0.
 * It NEVER touches, alters, or destroys analytical data layers, AOI polygons,
 * chat messages, or active investigation state.
 */

import * as Cesium from 'cesium';
import {
  GLOBE_SKINS,
  DEFAULT_GLOBE_SKIN_ID,
  getSkinById,
  getAvailableSkins,
  type GlobeSkin,
} from './globeSkinRegistry';
import { currentGlobeSkin } from '../stores';

const STORAGE_KEY = 'sq_globe_skin';

export class GlobeSkinManager {
  private viewer: Cesium.Viewer | null = null;
  private currentSkinId: string = DEFAULT_GLOBE_SKIN_ID;
  private baseImageryLayer: Cesium.ImageryLayer | null = null;

  constructor(viewer?: Cesium.Viewer | null) {
    if (viewer) {
      this.setViewer(viewer);
    }
  }

  /**
   * Bind Cesium Viewer and apply persisted or default skin.
   */
  public async setViewer(viewer: Cesium.Viewer): Promise<void> {
    this.viewer = viewer;
    const saved = localStorage.getItem(STORAGE_KEY) || DEFAULT_GLOBE_SKIN_ID;
    await this.setSkin(saved);
  }

  /**
   * Switch the globe skin basemap.
   * Modifies only the layer at index 0. Preserves all analytical data layers.
   */
  public async setSkin(skinId: string): Promise<boolean> {
    if (!this.viewer || this.viewer.isDestroyed()) {
      return false;
    }

    const skin = getSkinById(skinId);
    const oldLayer = this.baseImageryLayer;

    try {
      let provider: Cesium.ImageryProvider;

      if (skin.provider === 'arcgis') {
        provider = new Cesium.UrlTemplateImageryProvider({
          url: skin.url,
          tilingScheme: new Cesium.WebMercatorTilingScheme(),
          maximumLevel: skin.maxLevel || 19,
          credit: skin.attribution,
        });
      } else {
        provider = new Cesium.UrlTemplateImageryProvider({
          url: skin.url,
          tilingScheme: new Cesium.WebMercatorTilingScheme(),
          maximumLevel: skin.maxLevel || 19,
          credit: skin.attribution,
        });
      }

      // Add the new basemap layer at index 0 (beneath any analytical data overlays)
      const newLayer = this.viewer.imageryLayers.addImageryProvider(provider, 0);
      newLayer.alpha = 1.0;
      newLayer.show = true;

      // Clean up previous base imagery layer
      if (oldLayer && this.viewer.imageryLayers.contains(oldLayer)) {
        this.viewer.imageryLayers.remove(oldLayer, true);
      }

      this.baseImageryLayer = newLayer;
      this.currentSkinId = skin.id;

      // Persist selection
      localStorage.setItem(STORAGE_KEY, skin.id);
      currentGlobeSkin.set(skin.id);

      return true;
    } catch (err) {
      console.error(`[GlobeSkinManager] Failed to apply skin '${skinId}':`, err);
      return false;
    }
  }

  /**
   * Retrieve currently active globe skin definition.
   */
  public getCurrentSkin(): GlobeSkin {
    return getSkinById(this.currentSkinId);
  }

  /**
   * Retrieve list of all available skins.
   */
  public getAvailableSkins(): GlobeSkin[] {
    return getAvailableSkins();
  }

  /**
   * Clean up resources when viewer is destroyed.
   */
  public destroy(): void {
    if (this.baseImageryLayer && this.viewer && !this.viewer.isDestroyed()) {
      if (this.viewer.imageryLayers.contains(this.baseImageryLayer)) {
        this.viewer.imageryLayers.remove(this.baseImageryLayer, true);
      }
    }
    this.baseImageryLayer = null;
    this.viewer = null;
  }
}
