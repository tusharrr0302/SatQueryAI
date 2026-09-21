/**
 * SatQuery AI — Globe Skin Registry (Phase 8)
 * 
 * Declarative catalog of globe skins / basemaps.
 * Defines how the Earth surface looks independently from analytical data layers.
 */

export interface GlobeSkin {
  id: string;
  name: string;
  description: string;
  type: 'imagery' | 'terrain' | 'solid';
  previewColor: string;
  provider: 'url_template' | 'arcgis' | 'osm';
  url: string;
  attribution: string;
  maxLevel?: number;
  options?: Record<string, unknown>;
}

export const GLOBE_SKINS: Record<string, GlobeSkin> = {
  dark: {
    id: 'dark',
    name: 'Dark Canvas',
    description: 'High-contrast midnight cartographic basemap ideal for remote sensing overlays',
    type: 'imagery',
    previewColor: '#090d16',
    provider: 'arcgis',
    url: 'https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Esri, HERE, Garmin, © OpenStreetMap contributors, and the GIS user community',
    maxLevel: 16,
  },
  satellite: {
    id: 'satellite',
    name: 'Satellite',
    description: 'High-resolution true-color optical Earth surface imagery',
    type: 'imagery',
    previewColor: '#1e3a5f',
    provider: 'arcgis',
    url: 'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Esri, Maxar, Earthstar Geographics, USDA FSA, USGS, Aerogrid, IGN, IGP, and the GIS User Community',
    maxLevel: 19,
  },
  light: {
    id: 'light',
    name: 'Light Canvas',
    description: 'Clean, subtle daylight cartography highlighting spatial distributions',
    type: 'imagery',
    previewColor: '#e2e8f0',
    provider: 'arcgis',
    url: 'https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Esri, HERE, Garmin, © OpenStreetMap contributors, and the GIS user community',
    maxLevel: 16,
  },
  minimal: {
    id: 'minimal',
    name: 'Minimal Dark',
    description: 'Ultra-low contrast monochrome basemap designed for scientific telemetry',
    type: 'imagery',
    previewColor: '#121316',
    provider: 'arcgis',
    url: 'https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Esri, HERE, Garmin, © OpenStreetMap contributors, and the GIS user community',
    maxLevel: 16,
  },
  terrain: {
    id: 'terrain',
    name: 'Terrain',
    description: 'Physical shaded relief delineating topographic slope and elevation',
    type: 'imagery',
    previewColor: '#2d3748',
    provider: 'url_template',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Shaded_Relief/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Esri, USGS, NOAA',
    maxLevel: 13,
  },
};

export const DEFAULT_GLOBE_SKIN_ID = 'dark';

export function getAvailableSkins(): GlobeSkin[] {
  return Object.values(GLOBE_SKINS);
}

export function getSkinById(id: string): GlobeSkin {
  return GLOBE_SKINS[id] || GLOBE_SKINS[DEFAULT_GLOBE_SKIN_ID];
}
