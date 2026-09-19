<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { activeNav, showSettingsModal } from '../stores';
  import { Search, ChevronDown } from 'lucide-svelte';

  const dispatch = createEventDispatcher<{
    navHome: void;
  }>();

  function handleNav(item: 'home' | 'datasets' | 'use-cases' | 'docs') {
    $activeNav = item;

    if (item === 'home') {
      dispatch('navHome');
    }
  }

  function handleLogoClick() {
    $activeNav = 'home';
    dispatch('navHome');
  }
</script>

<header class="navbar-wrapper">
  <div class="navbar">

    <!-- Logo -->
    <button
      class="brand-container"
      on:click={handleLogoClick}
      aria-label="Go to home"
    >
      <img
        src="/satquery_logo.png"
        alt="SatQuery"
        class="brand-logo-img"
      />
    </button>

    <!-- Center Navigation -->
    <nav class="nav-links">

      <button
        class="nav-item"
        class:active={$activeNav === 'home'}
        on:click={() => handleNav('home')}
      >
        <span>Home</span>

        {#if $activeNav === 'home'}
          <span class="active-indicator"></span>
        {/if}
      </button>

      <button
        class="nav-item"
        class:active={$activeNav === 'datasets'}
        on:click={() => handleNav('datasets')}
      >
        <span>Datasets</span>

        {#if $activeNav === 'datasets'}
          <span class="active-indicator"></span>
        {/if}
      </button>

      <button
        class="nav-item"
        class:active={$activeNav === 'use-cases'}
        on:click={() => handleNav('use-cases')}
      >
        <span>Use Cases</span>

        {#if $activeNav === 'use-cases'}
          <span class="active-indicator"></span>
        {/if}
      </button>

      <button
        class="nav-item"
        class:active={$activeNav === 'docs'}
        on:click={() => handleNav('docs')}
      >
        <span>Docs</span>

        {#if $activeNav === 'docs'}
          <span class="active-indicator"></span>
        {/if}
      </button>

    </nav>

    <!-- Right Actions -->
    <div class="nav-right">

      <!-- Search -->
      <button
        class="icon-btn"
        aria-label="Search"
        title="Search"
      >
        <Search size={16} strokeWidth={1.7} />
      </button>

      <!-- User -->
      <button
        class="user-profile"
        on:click={() => ($showSettingsModal = true)}
        aria-label="Open profile"
      >
        <div class="avatar-badge">
          TK
        </div>

        <ChevronDown
          size={13}
          strokeWidth={1.7}
          class="chevron"
        />
      </button>

    </div>

  </div>
</header>

<style>
  /* =========================================
     NAVBAR
     ========================================= */

  .navbar-wrapper {
    position: fixed;
    top: 22px;
    left: 0;
    width: 100%;
    z-index: 1000;

    display: flex;
    justify-content: center;

    pointer-events: none;
  }

  .navbar {
    pointer-events: auto;

    width: calc(100% - 80px);
    max-width: 1180px;
    height: 62px;

    display: flex;
    align-items: center;
    justify-content: space-between;

    padding: 0 12px 0 20px;

    /* Deep black glass */
    background:
      linear-gradient(
        180deg,
        rgba(255, 255, 255, 0.055),
        rgba(255, 255, 255, 0.018)
      ),
      rgba(5, 5, 5, 0.72);

    backdrop-filter: blur(24px) saturate(110%);
    -webkit-backdrop-filter: blur(24px) saturate(110%);

    /* Reference-style glass border */
    border: 1px solid rgba(255, 255, 255, 0.16);

    border-radius: 999px;

    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.08),
      inset 0 -1px 0 rgba(255, 255, 255, 0.025),
      0 18px 50px rgba(0, 0, 0, 0.45),
      0 2px 10px rgba(0, 0, 0, 0.35);

    user-select: none;
  }


  /* =========================================
     LOGO
     ========================================= */

  .brand-container {
    width: 40px;
    height: 40px;

    display: flex;
    align-items: center;
    justify-content: center;

    padding: 0;
    margin: 0;

    background: transparent;
    border: none;
    border-radius: 50%;

    cursor: pointer;

    transition:
      background 0.2s ease,
      transform 0.2s ease;
  }

  .brand-container:hover {
    background: rgba(255, 255, 255, 0.07);
  }

  .brand-container:active {
    transform: scale(0.94);
  }

  .brand-logo-img {
    width: 31px;
    height: 31px;

    object-fit: contain;
    display: block;

    filter:
      grayscale(1)
      brightness(1.25);

    opacity: 0.95;

    transition:
      opacity 0.2s ease,
      filter 0.2s ease;
  }

  .brand-container:hover .brand-logo-img {
    opacity: 1;

    filter:
      grayscale(1)
      brightness(1.45);
  }


  /* =========================================
     CENTER NAVIGATION
     ========================================= */

  .nav-links {
    position: absolute;
    left: 50%;
    transform: translateX(-50%);

    display: flex;
    align-items: center;

    gap: 34px;

    height: 100%;
  }

  .nav-item {
    position: relative;

    height: 100%;

    display: flex;
    align-items: center;
    justify-content: center;

    padding: 0 2px;

    border: none;
    outline: none;

    background: transparent;

    color: rgba(255, 255, 255, 0.52);

    font-family: inherit;
    font-size: 12px;
    font-weight: 400;
    letter-spacing: -0.01em;

    white-space: nowrap;

    cursor: pointer;

    transition:
      color 0.2s ease,
      opacity 0.2s ease;
  }

  .nav-item:hover {
    color: rgba(255, 255, 255, 0.92);
  }

  .nav-item.active {
    color: #ffffff;
    font-weight: 500;
  }


  /* =========================================
     ACTIVE INDICATOR
     ========================================= */

  .active-indicator {
    position: absolute;

    left: 50%;
    bottom: 9px;

    transform: translateX(-50%);

    width: 18px;
    height: 1px;

    background: #ffffff;

    border-radius: 999px;

    box-shadow:
      0 0 7px rgba(255, 255, 255, 0.75),
      0 0 14px rgba(255, 255, 255, 0.25);
  }


  /* =========================================
     RIGHT SIDE
     ========================================= */

  .nav-right {
    display: flex;
    align-items: center;

    gap: 8px;

    margin-left: auto;
  }


  /* =========================================
     SEARCH
     ========================================= */

  .icon-btn {
    width: 36px;
    height: 36px;

    display: flex;
    align-items: center;
    justify-content: center;

    padding: 0;

    color: rgba(255, 255, 255, 0.62);

    background: rgba(255, 255, 255, 0.025);

    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 50%;

    cursor: pointer;

    transition:
      color 0.2s ease,
      background 0.2s ease,
      border-color 0.2s ease,
      transform 0.2s ease;
  }

  .icon-btn:hover {
    color: #ffffff;

    background: rgba(255, 255, 255, 0.075);

    border-color: rgba(255, 255, 255, 0.20);
  }

  .icon-btn:active {
    transform: scale(0.94);
  }


  /* =========================================
     PROFILE
     ========================================= */

  .user-profile {
    height: 38px;

    display: flex;
    align-items: center;

    gap: 6px;

    padding: 2px 6px 2px 3px;

    background: rgba(255, 255, 255, 0.025);

    border: 1px solid rgba(255, 255, 255, 0.10);

    border-radius: 999px;

    cursor: pointer;

    transition:
      background 0.2s ease,
      border-color 0.2s ease;
  }

  .user-profile:hover {
    background: rgba(255, 255, 255, 0.07);

    border-color: rgba(255, 255, 255, 0.18);
  }


  /* =========================================
     AVATAR
     ========================================= */

  .avatar-badge {
    width: 30px;
    height: 30px;

    display: flex;
    align-items: center;
    justify-content: center;

    border-radius: 50%;

    background:
      linear-gradient(
        145deg,
        #292929,
        #111111
      );

    border: 1px solid rgba(255, 255, 255, 0.17);

    color: rgba(255, 255, 255, 0.88);

    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.02em;

    box-shadow:
      inset 0 1px 1px rgba(255, 255, 255, 0.08),
      0 2px 6px rgba(0, 0, 0, 0.3);
  }

  .chevron {
    color: rgba(255, 255, 255, 0.42);

    transition:
      color 0.2s ease,
      transform 0.2s ease;
  }

  .user-profile:hover .chevron {
    color: rgba(255, 255, 255, 0.8);
  }


  /* =========================================
     RESPONSIVE
     ========================================= */

  @media (max-width: 800px) {
    .navbar {
      width: calc(100% - 32px);
      height: 58px;

      padding: 0 9px 0 14px;
    }

    .nav-links {
      gap: 20px;
    }

    .nav-item {
      font-size: 11px;
    }
  }

  @media (max-width: 620px) {
    .navbar-wrapper {
      top: 12px;
    }

    .navbar {
      width: calc(100% - 24px);
    }

    .nav-links {
      position: static;
      transform: none;

      margin-left: auto;
      margin-right: 12px;

      gap: 16px;
    }

    .nav-item:nth-child(3),
    .nav-item:nth-child(4) {
      display: none;
    }

    .icon-btn {
      display: none;
    }
  }
</style>