<script lang="ts">
  import { showSettingsModal, userSettings, showAuthModal, authModalMode } from '../stores';
  import { isSignedIn, currentUser, signOutUser } from '../services/authService';
  import {
    X,
    Settings,
    User,
    ShieldCheck,
    LogOut,
    LogIn,
    ExternalLink,
  } from 'lucide-svelte';

  function closeModal() {
    $showSettingsModal = false;
  }
</script>

{#if $showSettingsModal}
  <div
    class="modal-backdrop"
    on:click={closeModal}
    role="button"
    tabindex="0"
  >
    <div
      class="modal-card"
      on:click|stopPropagation
      role="region"
      tabindex="-1"
    >

      <!-- =====================================================
           HEADER
           ===================================================== -->

      <div class="modal-header">

        <div class="title-row">

          <div class="title-icon">
            <Settings
              size={17}
              strokeWidth={1.8}
            />
          </div>

          <div class="title-content">

            <h2 class="modal-title">
              System Settings
            </h2>

            <span class="modal-subtitle">
              Configure analysis and visualization behavior
            </span>

          </div>

        </div>


        <button
          class="close-btn"
          on:click={closeModal}
          aria-label="Close settings"
        >
          <X
            size={18}
            strokeWidth={1.8}
          />
        </button>

      </div>


      <!-- =====================================================
           BODY
           ===================================================== -->

      <div class="modal-body">

        <!-- USER ACCOUNT & IDENTITY -->
        <div class="setting-section-title">
          <User size={14} />
          <span>Identity & Account</span>
        </div>

        <div class="setting-item account-setting-item">
          {#if $isSignedIn && $currentUser}
            <div class="account-info-box">
              <div class="account-avatar">
                {#if $currentUser.imageUrl}
                  <img src={$currentUser.imageUrl} alt={$currentUser.fullName || 'User'} class="avatar-pic" />
                {:else}
                  <span class="avatar-text">{($currentUser.fullName || 'U').slice(0, 2).toUpperCase()}</span>
                {/if}
              </div>
              <div class="account-meta">
                <span class="account-name">{$currentUser.fullName || 'SatQuery Analyst'}</span>
                <span class="account-email">{$currentUser.primaryEmailAddress || 'analyst@satquery.ai'}</span>
                <span class="account-id">Clerk ID: {$currentUser.id}</span>
              </div>
            </div>

            <div class="account-actions">
              <button
                class="account-action-btn"
                on:click={() => {
                  $authModalMode = 'user-profile';
                  $showAuthModal = true;
                  closeModal();
                }}
              >
                <span>Manage Profile</span>
                <ExternalLink size={12} />
              </button>
              <button
                class="account-action-btn danger"
                on:click={async () => {
                  await signOutUser();
                  closeModal();
                }}
              >
                <LogOut size={12} />
                <span>Sign Out</span>
              </button>
            </div>
          {:else}
            <div class="account-info-box">
              <div class="guest-badge">
                <ShieldCheck size={18} />
              </div>
              <div class="account-meta">
                <span class="account-name">Anonymous Workstation Session</span>
                <span class="account-desc">Sign in with Clerk to persist chats, datasets, and investigations to your private cloud profile.</span>
              </div>
            </div>

            <button
              class="account-login-btn"
              on:click={() => {
                $authModalMode = 'sign-in';
                $showAuthModal = true;
                closeModal();
              }}
            >
              <LogIn size={13} />
              <span>Sign In with Clerk</span>
            </button>
          {/if}
        </div>

        <div class="setting-section-title">
          <Settings size={14} />
          <span>Analysis & Visualization</span>
        </div>

        <!-- MODEL EXECUTION MODE -->

        <div class="setting-item">

          <div class="setting-text">

            <span class="setting-label">
              Model Execution Mode
            </span>

            <span class="setting-desc">
              Choose between fast local mock inference or live
              external Prithvi worker.
            </span>

          </div>


          <div class="mode-toggle-group">

            <button
              class="mode-btn"
              class:active={$userSettings.modelMode === 'mock'}
              on:click={() =>
                ($userSettings.modelMode = 'mock')
              }
            >
              Mock Mode
            </button>

            <button
              class="mode-btn"
              class:active={$userSettings.modelMode === 'worker'}
              on:click={() =>
                ($userSettings.modelMode = 'worker')
              }
            >
              Remote Worker
            </button>

          </div>

        </div>


        <!-- MOCK FALLBACK -->

        <div class="setting-item">

          <div class="setting-text">

            <span class="setting-label">
              Automatic Mock Fallback
            </span>

            <span class="setting-desc">
              If the remote worker times out or fails,
              return audited mock results.
            </span>

          </div>


          <label class="switch">

            <input
              type="checkbox"
              bind:checked={$userSettings.allowFallback}
            />

            <span class="slider"></span>

          </label>

        </div>


        <!-- VERTICAL EXAGGERATION -->

        <div class="setting-item slider-setting">

          <div class="setting-text">

            <span class="setting-label">
              3D Vertical Exaggeration:
              <strong>
                {$userSettings.verticalExaggeration.toFixed(1)}x
              </strong>
            </span>

            <span class="setting-desc">
              Scale 3D surface elevation amplitude for
              topographic emphasis (1.0x - 5.0x).
            </span>

          </div>


          <div class="range-control">

            <input
              type="range"
              min="1.0"
              max="5.0"
              step="0.1"
              bind:value={$userSettings.verticalExaggeration}
              class="range-slider"
            />

            <span class="range-value">
              {$userSettings.verticalExaggeration.toFixed(1)}
            </span>

          </div>

        </div>


        <!-- SURFACE OPACITY -->

        <div class="setting-item slider-setting">

          <div class="setting-text">

            <span class="setting-label">
              Surface Opacity:
              <strong>
                {Math.round(
                  $userSettings.surfaceOpacity * 100
                )}%
              </strong>
            </span>

            <span class="setting-desc">
              Transparency of 3D analytical meshes and
              raster overlays (10% - 100%).
            </span>

          </div>


          <div class="range-control">

            <input
              type="range"
              min="0.1"
              max="1.0"
              step="0.05"
              bind:value={$userSettings.surfaceOpacity}
              class="range-slider"
            />

            <span class="range-value">
              {Math.round(
                $userSettings.surfaceOpacity * 100
              )}%
            </span>

          </div>

        </div>


        <!-- REVERSE DEPTH -->

        <div class="setting-item">

          <div class="setting-text">

            <span class="setting-label">
              Reverse Subsurface Depth
            </span>

            <span class="setting-desc">
              Invert elevation vectors for bathymetry and
              subsurface geological analysis.
            </span>

          </div>


          <label class="switch">

            <input
              type="checkbox"
              bind:checked={$userSettings.reverseDepth}
            />

            <span class="slider"></span>

          </label>

        </div>

      </div>


      <!-- =====================================================
           FOOTER
           ===================================================== -->

      <div class="modal-footer">

        <div class="footer-status">
          <span class="status-dot"></span>
          <span>Configuration ready</span>
        </div>


        <button
          class="cancel-btn"
          on:click={closeModal}
        >
          Cancel
        </button>


        <button
          class="save-btn"
          on:click={closeModal}
        >
          Apply Changes
        </button>

      </div>

    </div>
  </div>
{/if}


<style>

  /* =========================================================
     GLOBAL
     ========================================================= */

  :global(*) {
    box-sizing: border-box;
  }


  /* =========================================================
     BACKDROP
     ========================================================= */

  .modal-backdrop {

    position: fixed;

    inset: 0;

    z-index: 100;

    display: flex;

    align-items: center;

    justify-content: center;

    padding: 20px;

    background:
      rgba(0, 0, 0, 0.76);

    backdrop-filter:
      blur(18px);

    -webkit-backdrop-filter:
      blur(18px);

    animation:
      backdropIn 0.18s ease;
  }


  @keyframes backdropIn {

    from {
      opacity: 0;
    }

    to {
      opacity: 1;
    }
  }


  /* =========================================================
     MODAL
     ========================================================= */

  .modal-card {

    width: 100%;

    max-width: 600px;

    max-height:
      calc(100vh - 40px);

    display: flex;

    flex-direction: column;

    overflow: hidden;

    border-radius: 18px;

    background:
      linear-gradient(
        145deg,
        rgba(22,22,22,0.97),
        rgba(7,7,7,0.985)
      );

    border:
      1px solid
      rgba(255,255,255,0.12);

    box-shadow:
      0 30px 80px rgba(0,0,0,0.72),
      0 8px 30px rgba(0,0,0,0.45),
      inset 0 1px 0 rgba(255,255,255,0.055);

    color:
      #ffffff;

    font-family:
      Inter,
      "SF Pro Display",
      "SF Pro Text",
      -apple-system,
      BlinkMacSystemFont,
      "Helvetica Neue",
      Arial,
      sans-serif;

    animation:
      modalIn 0.2s ease;
  }


  @keyframes modalIn {

    from {
      opacity: 0;
      transform: translateY(8px) scale(0.985);
    }

    to {
      opacity: 1;
      transform: translateY(0) scale(1);
    }
  }


  /* =========================================================
     HEADER
     ========================================================= */

  .modal-header {

    min-height: 76px;

    display: flex;

    align-items: center;

    justify-content: space-between;

    padding:
      16px 20px;

    border-bottom:
      1px solid
      rgba(255,255,255,0.075);

    background:
      rgba(255,255,255,0.018);
  }


  .title-row {

    display: flex;

    align-items: center;

    gap: 12px;
  }


  .title-icon {

    width: 34px;

    height: 34px;

    display: flex;

    align-items: center;

    justify-content: center;

    border-radius: 9px;

    color:
      #ffffff;

    background:
      rgba(255,255,255,0.075);

    border:
      1px solid
      rgba(255,255,255,0.11);

    box-shadow:
      inset 0 1px 0
      rgba(255,255,255,0.06);
  }


  .title-content {

    display: flex;

    flex-direction: column;

    gap: 3px;
  }


  .modal-title {

    margin: 0;

    font-size: 15px;

    line-height: 1.2;

    font-weight: 650;

    letter-spacing: -0.02em;

    color:
      #ffffff;
  }


  .modal-subtitle {

    font-size: 10.5px;

    line-height: 1.3;

    color:
      rgba(255,255,255,0.38);
  }


  /* =========================================================
     CLOSE BUTTON
     ========================================================= */

  .close-btn {

    width: 32px;

    height: 32px;

    display: flex;

    align-items: center;

    justify-content: center;

    border-radius: 8px;

    color:
      rgba(255,255,255,0.42);

    background:
      transparent;

    border:
      1px solid transparent;

    cursor: pointer;

    transition:
      all 0.16s ease;
  }


  .close-btn:hover {

    color:
      #ffffff;

    background:
      rgba(255,255,255,0.07);

    border-color:
      rgba(255,255,255,0.1);
  }


  /* =========================================================
     BODY
     ========================================================= */

  .modal-body {

    padding:
      8px 20px;

    display: flex;

    flex-direction: column;

    overflow-y: auto;
  }

  .setting-section-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: rgba(255, 255, 255, 0.45);
    padding: 12px 0 6px 0;
  }

  .account-setting-item {
    background: rgba(255, 255, 255, 0.025);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 14px 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin-bottom: 8px;
  }

  .account-info-box {
    display: flex;
    align-items: center;
    gap: 14px;
  }

  .account-avatar {
    width: 44px;
    height: 44px;
    border-radius: 50%;
    background: #1c1c1c;
    border: 1px solid rgba(255, 255, 255, 0.15);
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    flex-shrink: 0;
  }

  .avatar-pic {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .avatar-text {
    font-size: 14px;
    font-weight: 600;
    color: #ffffff;
  }

  .guest-badge {
    width: 40px;
    height: 40px;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    display: flex;
    align-items: center;
    justify-content: center;
    color: rgba(255, 255, 255, 0.7);
    flex-shrink: 0;
  }

  .account-meta {
    display: flex;
    flex-direction: column;
    gap: 2px;
    overflow: hidden;
  }

  .account-name {
    font-size: 13px;
    font-weight: 500;
    color: #ffffff;
  }

  .account-email {
    font-size: 11px;
    color: rgba(255, 255, 255, 0.55);
  }

  .account-id {
    font-size: 10px;
    font-family: ui-monospace, monospace;
    color: rgba(255, 255, 255, 0.35);
  }

  .account-desc {
    font-size: 11px;
    color: rgba(255, 255, 255, 0.5);
    line-height: 1.4;
  }

  .account-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .account-action-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    border-radius: 6px;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: rgba(255, 255, 255, 0.85);
    font-size: 11px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .account-action-btn:hover {
    background: rgba(255, 255, 255, 0.12);
    color: #ffffff;
  }

  .account-action-btn.danger {
    color: rgba(239, 68, 68, 0.85);
    border-color: rgba(239, 68, 68, 0.2);
  }

  .account-action-btn.danger:hover {
    background: rgba(239, 68, 68, 0.12);
    color: #ef4444;
  }

  .account-login-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 7px 14px;
    border-radius: 6px;
    background: #ffffff;
    color: #000000;
    border: none;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: opacity 0.15s ease;
    align-self: flex-start;
  }

  .account-login-btn:hover {
    opacity: 0.9;
  }


  .modal-body::-webkit-scrollbar {

    width: 4px;
  }


  .modal-body::-webkit-scrollbar-track {

    background:
      transparent;
  }


  .modal-body::-webkit-scrollbar-thumb {

    background:
      rgba(255,255,255,0.15);

    border-radius:
      10px;
  }


  /* =========================================================
     SETTING ITEM
     ========================================================= */

  .setting-item {

    min-height: 86px;

    display: flex;

    align-items: center;

    justify-content: space-between;

    gap: 24px;

    padding:
      16px 4px;

    border-bottom:
      1px solid
      rgba(255,255,255,0.055);
  }


  .setting-item:last-child {

    border-bottom:
      none;
  }


  .setting-text {

    min-width: 0;

    flex: 1;

    display: flex;

    flex-direction: column;

    gap: 5px;
  }


  .setting-label {

    font-size: 12.5px;

    line-height: 1.3;

    font-weight: 600;

    letter-spacing:
      -0.005em;

    color:
      rgba(255,255,255,0.88);
  }


  .setting-label strong {

    color:
      #ffffff;

    font-weight:
      650;
  }


  .setting-desc {

    max-width: 360px;

    font-size: 10.5px;

    line-height: 1.5;

    color:
      rgba(255,255,255,0.38);
  }


  /* =========================================================
     MODEL MODE
     ========================================================= */

  .mode-toggle-group {

    flex-shrink: 0;

    display: flex;

    align-items: center;

    gap: 2px;

    padding: 3px;

    border-radius: 9px;

    background:
      rgba(255,255,255,0.035);

    border:
      1px solid
      rgba(255,255,255,0.09);
  }


  .mode-btn {

    min-height: 29px;

    padding:
      0 10px;

    border-radius: 6px;

    border:
      1px solid transparent;

    background:
      transparent;

    color:
      rgba(255,255,255,0.42);

    font-family:
      inherit;

    font-size: 10px;

    font-weight: 500;

    cursor: pointer;

    white-space: nowrap;

    transition:
      all 0.16s ease;
  }


  .mode-btn:hover {

    color:
      rgba(255,255,255,0.78);

    background:
      rgba(255,255,255,0.045);
  }


  .mode-btn.active {

    color:
      #050505;

    background:
      #ffffff;

    border-color:
      rgba(255,255,255,0.8);

    font-weight:
      650;

    box-shadow:
      0 2px 8px
      rgba(0,0,0,0.28);
  }


  /* =========================================================
     RANGE CONTROL
     ========================================================= */

  .slider-setting {

    align-items:
      center;
  }


  .range-control {

    width:
      145px;

    flex-shrink:
      0;

    display:
      flex;

    align-items:
      center;

    gap:
      9px;
  }


  .range-slider {

    width:
      108px;

    height:
      3px;

    appearance:
      none;

    -webkit-appearance:
      none;

    background:
      rgba(255,255,255,0.16);

    border-radius:
      20px;

    outline:
      none;

    cursor:
      pointer;
  }


  .range-slider::-webkit-slider-thumb {

    appearance:
      none;

    -webkit-appearance:
      none;

    width:
      13px;

    height:
      13px;

    border-radius:
      50%;

    background:
      #ffffff;

    border:
      2px solid
      #0a0a0a;

    box-shadow:
      0 0 0 1px
      rgba(255,255,255,0.3);

    cursor:
      pointer;
  }


  .range-slider::-moz-range-thumb {

    width:
      13px;

    height:
      13px;

    border-radius:
      50%;

    background:
      #ffffff;

    border:
      2px solid
      #0a0a0a;

    box-shadow:
      0 0 0 1px
      rgba(255,255,255,0.3);

    cursor:
      pointer;
  }


  .range-slider:focus-visible {

    outline:
      1px solid
      rgba(255,255,255,0.5);

    outline-offset:
      4px;
  }


  .range-value {

    min-width:
      27px;

    font-size:
      9.5px;

    font-variant-numeric:
      tabular-nums;

    text-align:
      right;

    color:
      rgba(255,255,255,0.5);
  }


  /* =========================================================
     TOGGLE SWITCH
     ========================================================= */

  .switch {

    width:
      40px;

    height:
      22px;

    position:
      relative;

    display:
      inline-block;

    flex-shrink:
      0;
  }


  .switch input {

    position:
      absolute;

    opacity:
      0;

    width:
      0;

    height:
      0;
  }


  .slider {

    position:
      absolute;

    inset:
      0;

    cursor:
      pointer;

    border-radius:
      20px;

    background:
      rgba(255,255,255,0.10);

    border:
      1px solid
      rgba(255,255,255,0.11);

    transition:
      all 0.18s ease;
  }


  .slider::before {

    content:
      "";

    position:
      absolute;

    width:
      16px;

    height:
      16px;

    left:
      2px;

    top:
      2px;

    border-radius:
      50%;

    background:
      rgba(255,255,255,0.65);

    box-shadow:
      0 2px 6px
      rgba(0,0,0,0.45);

    transition:
      all 0.18s ease;
  }


  .switch input:checked + .slider {

    background:
      rgba(255,255,255,0.88);

    border-color:
      rgba(255,255,255,0.95);

    box-shadow:
      0 0 12px
      rgba(255,255,255,0.07);
  }


  .switch input:checked + .slider::before {

    transform:
      translateX(18px);

    background:
      #080808;
  }


  .switch input:focus-visible + .slider {

    outline:
      1px solid
      rgba(255,255,255,0.5);

    outline-offset:
      3px;
  }


  /* =========================================================
     FOOTER
     ========================================================= */

  .modal-footer {

    min-height:
      64px;

    display:
      flex;

    align-items:
      center;

    justify-content:
      flex-end;

    gap:
      8px;

    padding:
      12px 20px;

    background:
      rgba(255,255,255,0.018);

    border-top:
      1px solid
      rgba(255,255,255,0.075);
  }


  /* =========================================================
     STATUS
     ========================================================= */

  .footer-status {

    margin-right:
      auto;

    display:
      flex;

    align-items:
      center;

    gap:
      7px;

    font-size:
      9.5px;

    color:
      rgba(255,255,255,0.30);
  }


  .status-dot {

    width:
      5px;

    height:
      5px;

    border-radius:
      50%;

    background:
      rgba(255,255,255,0.65);

    box-shadow:
      0 0 7px
      rgba(255,255,255,0.25);
  }


  /* =========================================================
     CANCEL
     ========================================================= */

  .cancel-btn {

    height:
      34px;

    padding:
      0 14px;

    border-radius:
      8px;

    background:
      transparent;

    border:
      1px solid
      rgba(255,255,255,0.10);

    color:
      rgba(255,255,255,0.5);

    font-family:
      inherit;

    font-size:
      10.5px;

    font-weight:
      500;

    cursor:
      pointer;

    transition:
      all 0.16s ease;
  }


  .cancel-btn:hover {

    color:
      #ffffff;

    background:
      rgba(255,255,255,0.05);

    border-color:
      rgba(255,255,255,0.18);
  }


  /* =========================================================
     SAVE
     ========================================================= */

  .save-btn {

    height:
      34px;

    padding:
      0 17px;

    border-radius:
      8px;

    background:
      #ffffff;

    border:
      1px solid
      #ffffff;

    color:
      #050505;

    font-family:
      inherit;

    font-size:
      10.5px;

    font-weight:
      650;

    cursor:
      pointer;

    transition:
      all 0.16s ease;

    box-shadow:
      0 3px 12px
      rgba(0,0,0,0.35);
  }


  .save-btn:hover {

    background:
      #e8e8e8;

    border-color:
      #e8e8e8;

    transform:
      translateY(-1px);

    box-shadow:
      0 5px 18px
      rgba(0,0,0,0.45);
  }


  .save-btn:active {

    transform:
      translateY(0);
  }


  /* =========================================================
     RESPONSIVE
     ========================================================= */

  @media (max-width: 640px) {

    .modal-backdrop {

      padding:
        12px;
    }


    .modal-card {

      max-height:
        calc(100vh - 24px);

      border-radius:
        15px;
    }


    .setting-item {

      align-items:
        flex-start;

      flex-direction:
        column;

      gap:
        12px;

      padding:
        15px 4px;
    }


    .setting-text {

      width:
        100%;
    }


    .setting-desc {

      max-width:
        100%;
    }


    .mode-toggle-group {

      width:
        100%;
    }


    .mode-btn {

      flex:
        1;
    }


    .range-control {

      width:
        100%;
    }


    .range-slider {

      flex:
        1;

      width:
        auto;
    }


    .modal-footer {

      flex-wrap:
        wrap;
    }


    .footer-status {

      width:
        100%;

      margin-bottom:
        3px;
    }
  }

</style>