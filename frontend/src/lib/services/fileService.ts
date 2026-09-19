/**
 * SatQuery AI — Native File Access & Ingestion Service
 * Handles native Tauri file dialogs and web browser file picker abstractions.
 */
import { isTauri } from '../platform';
import { getApiBaseUrl } from '../config';

export interface SelectedFile {
  name: string;
  path?: string;
  file?: File;
}

export interface UploadResult {
  asset_id: string;
  profile: any;
  preview_url: string;
  thumbnail_url?: string;
}

export async function pickSatelliteFile(): Promise<SelectedFile | null> {
  if (isTauri()) {
    try {
      const { open } = await import('@tauri-apps/plugin-dialog');
      const selected = await open({
        multiple: false,
        title: 'Select Satellite / Earth Observation Data',
        filters: [
          {
            name: 'Earth Observation Data (*.tif, *.tiff, *.cog, *.png, *.jpg)',
            extensions: ['tif', 'tiff', 'cog', 'png', 'jpg', 'jpeg'],
          },
        ],
      });
      if (!selected) return null;
      const filePath = typeof selected === 'string' ? selected : selected[0];
      const filename = filePath.split(/[/\\]/).pop() || 'satellite_image.tif';
      return {
        name: filename,
        path: filePath,
      };
    } catch (err) {
      console.warn('Tauri native dialog failed, falling back to browser picker:', err);
    }
  }

  // Web Browser Fallback: standard input element
  return new Promise((resolve) => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.tif,.tiff,.cog,.png,.jpg,.jpeg';
    input.style.display = 'none';
    input.onchange = () => {
      const file = input.files?.[0];
      if (file) {
        resolve({
          name: file.name,
          file,
        });
      } else {
        resolve(null);
      }
      document.body.removeChild(input);
    };
    input.oncancel = () => {
      resolve(null);
      document.body.removeChild(input);
    };
    document.body.appendChild(input);
    input.click();
  });
}

export async function uploadSatelliteFile(
  selected: SelectedFile,
  onProgress?: (msg: string) => void
): Promise<UploadResult> {
  const apiBase = getApiBaseUrl();

  if (selected.path) {
    // Native Tauri Mode: pass local absolute path securely to FastAPI
    onProgress?.('Inspecting local Earth observation raster...');
    const res = await fetch(`${apiBase}/data/upload`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        local_path: selected.path,
        filename: selected.name,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
      throw new Error(err.detail || `Upload failed with status ${res.status}`);
    }
    return await res.json();
  }

  if (selected.file) {
    // Web Mode: multipart form upload
    onProgress?.('Uploading satellite raster stream...');
    const formData = new FormData();
    formData.append('file', selected.file);

    const res = await fetch(`${apiBase}/data/upload`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
      throw new Error(err.detail || `Upload failed with status ${res.status}`);
    }
    return await res.json();
  }

  throw new Error('No valid file or local path selected.');
}
