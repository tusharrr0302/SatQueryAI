<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { showAuthModal, authModalMode, type AuthModalMode } from '../stores';
  import {
    isSignedIn,
    currentUser,
    mountSignInComponent,
    unmountSignInComponent,
    mountSignUpComponent,
    unmountSignUpComponent,
    mountUserProfileComponent,
    unmountUserProfileComponent,
    signOutUser,
    isAuthLoaded,
  } from '../services/authService';
  import { X, ShieldCheck, UserCheck, AlertCircle, LogOut, KeyRound } from 'lucide-svelte';

  export let isGateMode: boolean = false;

  let containerEl: HTMLDivElement | null = null;
  let activeMountedMode: AuthModalMode | null = null;

  const hasPublishableKey = !!import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

  function closeModal() {
    if (isGateMode) return;
    $showAuthModal = false;
  }

  function handleBackdropClick(e: MouseEvent) {
    if (isGateMode) return;
    if (e.target === e.currentTarget) {
      closeModal();
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (isGateMode) return;
    if (e.key === 'Escape' && $showAuthModal) {
      closeModal();
    }
  }

  function setMode(mode: AuthModalMode) {
    $authModalMode = mode;
  }

  function cleanupActiveComponent() {
    if (containerEl && activeMountedMode) {
      if (activeMountedMode === 'sign-in') {
        unmountSignInComponent(containerEl);
      } else if (activeMountedMode === 'sign-up') {
        unmountSignUpComponent(containerEl);
      } else if (activeMountedMode === 'user-profile') {
        unmountUserProfileComponent(containerEl);
      }
      activeMountedMode = null;
      containerEl.innerHTML = '';
    }
  }

  let isLoadingClerk = false;
  let mountError: string | null = null;

  function mountClerkTarget(node: HTMLDivElement) {
    containerEl = node;
    mountCurrentMode();
    return {
      destroy() {
        cleanupActiveComponent();
        containerEl = null;
      }
    };
  }

  async function mountCurrentMode() {
    if (!containerEl || !hasPublishableKey) return;
    cleanupActiveComponent();

    const mode = $authModalMode;
    activeMountedMode = mode;
    isLoadingClerk = true;
    mountError = null;

    try {
      if (mode === 'sign-in') {
        await mountSignInComponent(containerEl);
      } else if (mode === 'sign-up') {
        await mountSignUpComponent(containerEl);
      } else if (mode === 'user-profile') {
        await mountUserProfileComponent(containerEl);
      }
    } catch (err: any) {
      console.error('[AuthModal] Failed mounting Clerk component:', err);
      mountError = err?.message || 'Failed to initialize Clerk UI';
    } finally {
      isLoadingClerk = false;
    }
  }

  $: if (containerEl && $authModalMode && ($showAuthModal || isGateMode)) {
    if (activeMountedMode !== $authModalMode) {
      mountCurrentMode();
    }
  }

  $: if (!$showAuthModal && !isGateMode) {
    cleanupActiveComponent();
  }

  // Auto-close modal or switch mode when user status changes
  $: if ($isSignedIn && ($authModalMode === 'sign-in' || $authModalMode === 'sign-up')) {
    if (!isGateMode) {
      $showAuthModal = false;
    } else {
      $authModalMode = 'user-profile';
    }
  } else if (!$isSignedIn && $authModalMode === 'user-profile') {
    $authModalMode = 'sign-in';
  }

  onDestroy(() => {
    cleanupActiveComponent();
  });
</script>

<svelte:window on:keydown={handleKeydown} />

{#if $showAuthModal || isGateMode}
  <div
    class="auth-modal-backdrop"
    class:is-gate={isGateMode}
    on:click={handleBackdropClick}
    on:keydown={handleKeydown}
    role="presentation"
  >
    <div
      class="auth-modal-card"
      class:is-gate={isGateMode}
      class:wide={$authModalMode === 'user-profile'}
      role="dialog"
      aria-modal="true"
      aria-labelledby="auth-modal-title"
      tabindex="-1"
    >
      <!-- Top header bar -->
      <div class="auth-card-header">
        <div class="brand-pill">
          <img src="/nav_logo.png" alt="SatQuery" class="brand-icon" />
          <span class="brand-text">SatQuery AI Auth</span>
        </div>

        <!-- Mode switcher tabs for unauthenticated users -->
        {#if !$isSignedIn && hasPublishableKey}
          <div class="auth-mode-tabs">
            <button
              class="auth-tab-btn"
              class:active={$authModalMode === 'sign-in'}
              on:click={() => setMode('sign-in')}
            >
              Sign In
            </button>
            <button
              class="auth-tab-btn"
              class:active={$authModalMode === 'sign-up'}
              on:click={() => setMode('sign-up')}
            >
              Create Account
            </button>
          </div>
        {/if}

        {#if !isGateMode}
          <button class="close-btn" on:click={closeModal} aria-label="Close authentication modal">
            <X size={16} />
          </button>
        {/if}
      </div>

      <!-- Main Clerk container -->
      <div class="auth-card-content">
        {#if !hasPublishableKey}
          <div class="dev-auth-placeholder">
            <div class="dev-icon-badge">
              <KeyRound size={26} strokeWidth={1.5} />
            </div>
            <h3 class="dev-title" id="auth-modal-title">Authentication Required</h3>
            <p class="dev-desc">
              SatQuery AI requires Clerk authentication. Please configure <code>VITE_CLERK_PUBLISHABLE_KEY</code> to sign in.
            </p>
          </div>
        {:else}
          {#if isLoadingClerk}
            <div class="clerk-loading-spinner">
              <div class="spinner-ring"></div>
              <span>Connecting to secure identity provider...</span>
            </div>
          {/if}
          {#if mountError}
            <div class="clerk-mount-error">
              <AlertCircle size={20} class="text-rose-400" />
              <span>{mountError}</span>
              <button class="retry-btn" on:click={mountCurrentMode}>Retry</button>
            </div>
          {/if}
          <!-- Live Clerk container -->
          <div use:mountClerkTarget class="clerk-mount-target" class:hidden={isLoadingClerk}></div>
        {/if}
      </div>

      <!-- Footer security tag -->
      <div class="auth-card-footer">
        <div class="security-indicator">
          <ShieldCheck size={12} strokeWidth={1.8} />
          <span>Zero passwords stored &bull; Encrypted RS256 JWT tokens</span>
        </div>

        {#if $isSignedIn}
          <button
            class="signout-link"
            on:click={async () => {
              await signOutUser();
              closeModal();
            }}
          >
            <LogOut size={12} />
            <span>Sign Out</span>
          </button>
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  .auth-modal-backdrop {
    position: fixed;
    inset: 0;
    z-index: 9999;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
    background: rgba(0, 0, 0, 0.78);
    backdrop-filter: blur(18px) saturate(130%);
    -webkit-backdrop-filter: blur(18px) saturate(130%);
    animation: fadeIn 0.18s ease-out;
  }

  .auth-modal-backdrop.is-gate {
    position: static;
    inset: auto;
    z-index: auto;
    background: transparent;
    backdrop-filter: none;
    -webkit-backdrop-filter: none;
    padding: 0;
    animation: none;
    width: 100%;
    display: flex;
    justify-content: center;
  }

  @keyframes fadeIn {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  .auth-modal-card {
    position: relative;
    width: 100%;
    max-width: 480px;
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    background: #080808;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 14px;
    box-shadow:
      0 30px 70px rgba(0, 0, 0, 0.8),
      0 0 0 1px rgba(255, 255, 255, 0.04),
      inset 0 1px 0 rgba(255, 255, 255, 0.08);
    overflow: hidden;
    animation: scaleIn 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  }

  .auth-modal-card.is-gate {
    max-width: 480px;
    box-shadow:
      0 30px 80px rgba(0, 0, 0, 0.9),
      0 0 0 1px rgba(255, 255, 255, 0.08),
      inset 0 1px 0 rgba(255, 255, 255, 0.12);
  }

  .auth-modal-card.wide {
    max-width: 860px;
    height: 82vh;
  }

  @keyframes scaleIn {
    from {
      opacity: 0;
      transform: scale(0.96) translateY(6px);
    }
    to {
      opacity: 1;
      transform: scale(1) translateY(0);
    }
  }

  .auth-card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(255, 255, 255, 0.02);
  }

  .brand-pill {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .brand-icon {
    width: 20px;
    height: 20px;
    object-fit: contain;
  }

  .brand-text {
    font-size: 13px;
    font-weight: 600;
    color: #f5f5f5;
    letter-spacing: -0.01em;
  }

  .auth-mode-tabs {
    display: flex;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 2px;
    gap: 2px;
  }

  .auth-tab-btn {
    border: none;
    background: transparent;
    color: rgba(255, 255, 255, 0.55);
    font-size: 12px;
    font-weight: 500;
    padding: 5px 12px;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .auth-tab-btn:hover {
    color: #ffffff;
  }

  .auth-tab-btn.active {
    background: #ffffff;
    color: #000000;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
  }

  .close-btn {
    width: 30px;
    height: 30px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 6px;
    color: rgba(255, 255, 255, 0.6);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .close-btn:hover {
    background: rgba(255, 255, 255, 0.1);
    color: #ffffff;
    border-color: rgba(255, 255, 255, 0.2);
  }

  .auth-card-content {
    flex: 1;
    overflow-y: auto;
    padding: 24px;
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 340px;
  }

  .clerk-mount-target {
    width: 100%;
    display: flex;
    justify-content: center;
  }

  .clerk-mount-target.hidden {
    display: none !important;
  }

  .clerk-loading-spinner {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;
    padding: 32px 16px;
    color: rgba(255, 255, 255, 0.6);
    font-size: 13px;
  }

  .spinner-ring {
    width: 28px;
    height: 28px;
    border: 2px solid rgba(255, 255, 255, 0.1);
    border-top-color: #ffffff;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .clerk-mount-error {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    color: #f87171;
    font-size: 13px;
    padding: 24px;
    text-align: center;
  }

  .retry-btn {
    padding: 6px 16px;
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 6px;
    color: #ffffff;
    cursor: pointer;
    font-size: 12px;
  }

  /* Dev / Placeholder styling */
  .dev-auth-placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    max-width: 380px;
    padding: 10px 0;
  }

  .dev-icon-badge {
    width: 52px;
    height: 52px;
    border-radius: 12px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    display: flex;
    align-items: center;
    justify-content: center;
    color: #ffffff;
    margin-bottom: 16px;
  }

  .dev-title {
    font-size: 17px;
    font-weight: 600;
    color: #ffffff;
    margin: 0 0 8px 0;
    letter-spacing: -0.02em;
  }

  .dev-desc {
    font-size: 13px;
    line-height: 1.5;
    color: rgba(255, 255, 255, 0.58);
    margin: 0 0 16px 0;
  }

  .auth-card-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 20px;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(255, 255, 255, 0.015);
    font-size: 11px;
    color: rgba(255, 255, 255, 0.45);
  }

  .security-indicator {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .signout-link {
    display: flex;
    align-items: center;
    gap: 5px;
    background: transparent;
    border: none;
    color: rgba(239, 68, 68, 0.8);
    cursor: pointer;
    font-size: 11px;
    font-weight: 500;
    padding: 4px 8px;
    border-radius: 4px;
    transition: all 0.15s ease;
  }

  .signout-link:hover {
    color: #ef4444;
    background: rgba(239, 68, 68, 0.1);
  }
</style>
