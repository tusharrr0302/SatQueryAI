<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { activeNav, showSettingsModal, showAuthModal, authModalMode, activeSidebarTab, activeDataLayers } from '../stores';
  import { isSignedIn, currentUser, signOutUser } from '../services/authService';
  import { Search, ChevronDown, User, Settings, LogOut, LogIn, Layers } from 'lucide-svelte';

  const dispatch = createEventDispatcher<{
    navHome: void;
  }>();

  let isUserMenuOpen = false;

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

  function toggleUserMenu() {
    isUserMenuOpen = !isUserMenuOpen;
  }

  function closeUserMenu() {
    isUserMenuOpen = false;
  }

  function openSignIn() {
    $authModalMode = 'sign-in';
    $showAuthModal = true;
    closeUserMenu();
  }

  function openUserProfile() {
    $authModalMode = 'user-profile';
    $showAuthModal = true;
    closeUserMenu();
  }

  function openSettings() {
    $showSettingsModal = true;
    closeUserMenu();
  }

  function toggleLayers() {
    $activeSidebarTab = $activeSidebarTab === 'layers' ? 'chat' : 'layers';
  }

  async function handleSignOut() {
    await signOutUser();
    closeUserMenu();
  }

  function getInitials(user: any): string {
    if (!user) return 'SQ';
    if (user.firstName && user.lastName) {
      return `${user.firstName[0]}${user.lastName[0]}`.toUpperCase();
    }
    if (user.fullName) {
      const parts = user.fullName.trim().split(' ');
      if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
      return user.fullName.slice(0, 2).toUpperCase();
    }
    if (user.primaryEmailAddress) {
      return user.primaryEmailAddress.slice(0, 2).toUpperCase();
    }
    return 'SQ';
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
        src="/nav_logo.png"
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

      <!-- Globe Skins & Layers Button -->
      <button
        class="icon-btn layers-nav-btn"
        class:active={$activeSidebarTab === 'layers'}
        on:click={toggleLayers}
        aria-label="Globe Skins & Layers"
        title="Globe Skins & Layers"
      >
        <Layers size={16} strokeWidth={1.7} />
        {#if $activeDataLayers.length > 0}
          <span class="nav-layer-dot"></span>
        {/if}
      </button>

      <!-- User Profile / Auth Button -->
      {#if $isSignedIn && $currentUser}
        <div class="user-menu-wrapper">
          <button
            class="user-profile"
            on:click={toggleUserMenu}
            aria-label="Open user menu"
            aria-expanded={isUserMenuOpen}
          >
            {#if $currentUser.imageUrl}
              <img src={$currentUser.imageUrl} alt={$currentUser.fullName || 'User'} class="avatar-img" />
            {:else}
              <div class="avatar-badge">
                {getInitials($currentUser)}
              </div>
            {/if}

            <ChevronDown
              size={13}
              strokeWidth={1.7}
              class={`chevron ${isUserMenuOpen ? 'rotate' : ''}`}
            />
          </button>

          {#if isUserMenuOpen}
            <div class="user-dropdown-backdrop" on:click={closeUserMenu}></div>
            <div class="user-dropdown-card">
              <div class="dropdown-header">
                <div class="user-name">{$currentUser.fullName || 'SatQuery Analyst'}</div>
                <div class="user-email">{$currentUser.primaryEmailAddress || 'analyst@satquery.ai'}</div>
              </div>

              <div class="dropdown-divider"></div>

              <button class="dropdown-item" on:click={openUserProfile}>
                <User size={14} />
                <span>Account Profile</span>
              </button>

              <button class="dropdown-item" on:click={openSettings}>
                <Settings size={14} />
                <span>Workstation Settings</span>
              </button>

              <div class="dropdown-divider"></div>

              <button class="dropdown-item danger" on:click={handleSignOut}>
                <LogOut size={14} />
                <span>Sign Out</span>
              </button>
            </div>
          {/if}
        </div>
      {:else}
        <!-- Unauthenticated: Sign In CTA -->
        <button
          class="sign-in-btn"
          on:click={openSignIn}
          aria-label="Sign in"
        >
          <LogIn size={13} />
          <span>Sign In</span>
        </button>
      {/if}
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
    width: 32px;
    height: 32px;

    object-fit: contain;
    display: block;

    opacity: 0.95;
    filter: drop-shadow(0 0 4px rgba(255, 255, 255, 0.2));

    transition:
      opacity 0.2s ease,
      filter 0.2s ease,
      transform 0.2s ease;
  }

  .brand-container:hover .brand-logo-img {
    opacity: 1;
    filter: drop-shadow(0 0 10px rgba(255, 255, 255, 0.65));
    transform: scale(1.06);
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

  .layers-nav-btn {
    position: relative;
  }

  .layers-nav-btn.active {
    color: #38bdf8;
    background: rgba(56, 189, 248, 0.12);
    border-color: rgba(56, 189, 248, 0.35);
  }

  .nav-layer-dot {
    position: absolute;
    top: 6px;
    right: 6px;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #38bdf8;
    box-shadow: 0 0 6px #38bdf8;
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

  .chevron.rotate {
    transform: rotate(180deg);
  }

  .avatar-img {
    width: 30px;
    height: 30px;
    border-radius: 50%;
    object-fit: cover;
    border: 1px solid rgba(255, 255, 255, 0.17);
  }

  .user-menu-wrapper {
    position: relative;
  }

  .user-dropdown-backdrop {
    position: fixed;
    inset: 0;
    z-index: 1001;
    background: transparent;
  }

  .user-dropdown-card {
    position: absolute;
    top: calc(100% + 12px);
    right: 0;
    width: 230px;
    z-index: 1002;
    background: rgba(12, 12, 12, 0.96);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 12px;
    padding: 6px;
    box-shadow: 0 16px 36px rgba(0, 0, 0, 0.65), inset 0 1px 0 rgba(255, 255, 255, 0.08);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    animation: dropdownIn 0.15s ease-out;
  }

  @keyframes dropdownIn {
    from {
      opacity: 0;
      transform: translateY(-4px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .dropdown-header {
    padding: 8px 10px;
  }

  .user-name {
    font-size: 13px;
    font-weight: 500;
    color: #ffffff;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .user-email {
    font-size: 11px;
    color: rgba(255, 255, 255, 0.45);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    margin-top: 2px;
  }

  .dropdown-divider {
    height: 1px;
    background: rgba(255, 255, 255, 0.08);
    margin: 4px 0;
  }

  .dropdown-item {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 10px;
    background: transparent;
    border: none;
    border-radius: 6px;
    color: rgba(255, 255, 255, 0.75);
    font-size: 12px;
    font-weight: 400;
    cursor: pointer;
    text-align: left;
    transition: all 0.15s ease;
  }

  .dropdown-item:hover {
    background: rgba(255, 255, 255, 0.08);
    color: #ffffff;
  }

  .dropdown-item.danger {
    color: rgba(239, 68, 68, 0.85);
  }

  .dropdown-item.danger:hover {
    background: rgba(239, 68, 68, 0.12);
    color: #ef4444;
  }

  .sign-in-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    height: 36px;
    padding: 0 14px;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 999px;
    color: #ffffff;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .sign-in-btn:hover {
    background: #ffffff;
    color: #000000;
    border-color: #ffffff;
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