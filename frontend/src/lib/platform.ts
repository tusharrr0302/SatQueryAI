/**
 * SatQuery AI — Platform detection abstraction.
 * Cleanly separates Tauri desktop runtime from standard web browser execution.
 */

export function isTauri(): boolean {
  if (typeof window === 'undefined') return false;
  return (
    '__TAURI_INTERNALS__' in window ||
    '__TAURI__' in window ||
    Boolean((window as any).__TAURI_METADATA__)
  );
}

export function isWeb(): boolean {
  return !isTauri();
}
