/**
 * CesiumLayerManager Unit & Behavior Verification Test
 */

import { CesiumLayerManager } from './CesiumLayerManager';
import type { DataLayerSpec } from '../stores';

declare const process: any;

class MockImageryLayerCollection {
  public layers: any[] = [];
  addImageryProvider(provider: any) {
    const layer = { provider, alpha: 1.0, show: true };
    this.layers.push(layer);
    return layer;
  }
  remove(layer: any, destroy = true) {
    const idx = this.layers.indexOf(layer);
    if (idx !== -1) {
      this.layers.splice(idx, 1);
      return true;
    }
    return false;
  }
}

class MockEntityCollection {
  public entities: any[] = [];
  add(options: any) {
    const entity = { ...options, show: true, id: `ent_${Math.random()}` };
    this.entities.push(entity);
    return entity;
  }
  remove(entity: any) {
    const idx = this.entities.indexOf(entity);
    if (idx !== -1) {
      this.entities.splice(idx, 1);
      return true;
    }
    return false;
  }
}

class MockCamera {
  public lastFlyDestination: any = null;
  public lastDuration: number | null = null;
  flyTo(options: any) {
    this.lastFlyDestination = options.destination;
    this.lastDuration = options.duration;
  }
}

class MockViewer {
  public entities = new MockEntityCollection();
  public imageryLayers = new MockImageryLayerCollection();
  public camera = new MockCamera();
  private _destroyed = false;

  isDestroyed() {
    return this._destroyed;
  }
  destroy() {
    this._destroyed = true;
  }
}

async function runTests() {
  console.log('--- Testing CesiumLayerManager ---');
  const viewer = new MockViewer() as any;
  const manager = new CesiumLayerManager(viewer);

  // 1. Add AOI Layer
  const aoiSpec: DataLayerSpec = {
    layer_id: 'layer_aoi_test',
    type: 'aoi',
    title: 'Delhi AOI Footprint',
    description: 'Delineated test boundary',
    source: { type: 'geojson' },
    spatial: {
      bounds: [76.84, 28.40, 77.34, 28.88],
      center: { latitude: 28.6139, longitude: 77.2090 },
      polygon: [[76.84, 28.40], [77.34, 28.40], [77.34, 28.88], [76.84, 28.88], [76.84, 28.40]],
    },
    style: {
      opacity: 0.85,
      color: 'rgba(255, 255, 255, 0.08)',
      outline_color: '#ffffff',
      outline_width: 2.0,
      color_scale: 'white',
    },
    provenance: { source: 'mock' },
    access: { is_private: false },
  };

  await manager.addLayer(aoiSpec, false);
  console.assert(manager.hasLayer('layer_aoi_test'), 'Layer should be registered');
  console.assert(viewer.entities.entities.length >= 1, 'Entities should be created for AOI');
  console.log('✓ Add AOI Layer passed');

  // 2. Add Analytical Change Detection Layer
  const vegSpec: DataLayerSpec = {
    layer_id: 'layer_veg_test',
    type: 'change_detection',
    title: 'Vegetation Canopy Loss',
    description: 'Disturbance overlay',
    source: { type: 'geojson' },
    spatial: {
      bounds: [76.84, 28.40, 77.34, 28.88],
      polygon: [[76.84, 28.40], [77.34, 28.40], [77.34, 28.88], [76.84, 28.88], [76.84, 28.40]],
    },
    style: {
      opacity: 0.80,
      color: 'rgba(239, 68, 68, 0.40)',
      outline_color: '#ef4444',
      outline_width: 2.5,
      color_scale: 'red',
    },
    provenance: { source: 'mock' },
    access: { is_private: false },
  };

  await manager.addLayer(vegSpec, false);
  console.assert(manager.hasLayer('layer_veg_test'), 'Vegetation layer should be registered');
  console.assert(manager.getAllLayers().length === 2, 'Two layers should be managed');
  console.log('✓ Add Change Detection Layer passed');

  // 3. Visibility control
  manager.setLayerVisibility('layer_veg_test', false);
  console.assert(manager.getLayer('layer_veg_test')?.visible === false, 'Layer visibility should be false');
  manager.setLayerVisibility('layer_veg_test', true);
  console.assert(manager.getLayer('layer_veg_test')?.visible === true, 'Layer visibility should be true');
  console.log('✓ Layer Visibility control passed');

  // 4. Opacity control
  manager.setLayerOpacity('layer_veg_test', 0.45);
  console.assert(manager.getLayer('layer_veg_test')?.style.opacity === 0.45, 'Layer opacity should be 0.45');
  console.log('✓ Layer Opacity control passed');

  // 5. Camera flyTo
  manager.flyToLayer('layer_aoi_test', 1.5);
  console.assert(viewer.camera.lastFlyDestination !== null, 'Camera destination should be set');
  console.assert(viewer.camera.lastDuration === 1.5, 'Camera duration should be 1.5s');
  console.log('✓ Camera flyTo passed');

  // 6. Layer update without duplicate primitives
  const prevEntityCount = viewer.entities.entities.length;
  await manager.addLayer({ ...aoiSpec, title: 'Updated Title' }, false);
  console.assert(viewer.entities.entities.length === prevEntityCount, 'No duplicate primitives on update');
  console.assert(manager.getLayer('layer_aoi_test')?.title === 'Updated Title', 'Title should be updated');
  console.log('✓ Layer update without duplicate primitives passed');

  // 7. Layer removal
  const removed = manager.removeLayer('layer_veg_test');
  console.assert(removed === true, 'removeLayer should return true');
  console.assert(!manager.hasLayer('layer_veg_test'), 'Layer should no longer exist');
  console.log('✓ Layer removal passed');

  // 8. Clear layers (preserves viewer and basemap)
  manager.clearLayers();
  console.assert(manager.getAllLayers().length === 0, 'All data layers cleared');
  console.assert(!viewer.isDestroyed(), 'Viewer is not destroyed when clearing layers');
  console.log('✓ Clear layers passed');

  console.log('\nALL CESIUM LAYER MANAGER TESTS PASSED SUCCESSFULLY!');
}

runTests().catch(err => {
  console.error('Test failed:', err);
  process.exit(1);
});
