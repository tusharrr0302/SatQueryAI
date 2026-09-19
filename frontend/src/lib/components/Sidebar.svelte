<script lang="ts">
  import { createEventDispatcher } from 'svelte';

  import {
    activeSidebarTab,
    isLandingPage,
    showSettingsModal,
    activeNav
  } from '../stores';

  import {
    Plus,
    MessageSquare,
    Database,
    Layers,
    Shield,
    Clock,
    Settings
  } from 'lucide-svelte';


  const dispatch = createEventDispatcher<{
    newChat: void;
  }>();


  function selectTab(
    tab:
      | 'chat'
      | 'data'
      | 'layers'
      | 'investigations'
      | 'history'
      | 'settings'
  ) {

    if (tab === 'settings') {
      $showSettingsModal = true;
      return;
    }

    $activeSidebarTab = tab;
    $activeNav = 'home';
    $isLandingPage = false;
  }


  function handleNewChat() {
    dispatch('newChat');
  }
</script>


<aside class="sidebar">

  <!-- TOP -->
  <div class="top-section">

    <!-- New Chat -->
    <button
      class="new-chat"
      on:click={handleNewChat}
      title="New Chat"
      aria-label="New Chat"
    >
      <Plus size={19} strokeWidth={1.8} />
    </button>


    <div class="separator"></div>


    <!-- Chat -->
    <button
      class="nav-item"
      class:active={$activeSidebarTab === 'chat' && !$isLandingPage}
      on:click={() => selectTab('chat')}
      title="Chat"
    >
      <MessageSquare
        size={18}
        strokeWidth={1.7}
      />

      <span>Chat</span>
    </button>


    <!-- Data -->
    <button
      class="nav-item"
      class:active={$activeSidebarTab === 'data' && !$isLandingPage}
      on:click={() => selectTab('data')}
      title="Your Data"
    >
      <Database
        size={18}
        strokeWidth={1.7}
      />

      <span>Data</span>
    </button>


    <!-- Layers -->
    <button
      class="nav-item"
      class:active={$activeSidebarTab === 'layers' && !$isLandingPage}
      on:click={() => selectTab('layers')}
      title="Layers"
    >
      <Layers
        size={18}
        strokeWidth={1.7}
      />

      <span>Layers</span>
    </button>


    <!-- Studies -->
    <button
      class="nav-item"
      class:active={$activeSidebarTab === 'investigations' && !$isLandingPage}
      on:click={() => selectTab('investigations')}
      title="Studies"
    >
      <Shield
        size={18}
        strokeWidth={1.7}
      />

      <span>Studies</span>
    </button>


    <!-- History -->
    <button
      class="nav-item"
      class:active={$activeSidebarTab === 'history' && !$isLandingPage}
      on:click={() => selectTab('history')}
      title="History"
    >
      <Clock
        size={18}
        strokeWidth={1.7}
      />

      <span>History</span>
    </button>

  </div>


  <!-- BOTTOM -->

  <div class="bottom-section">

    <button
      class="nav-item"
      class:active={$activeSidebarTab === 'settings'}
      on:click={() => selectTab('settings')}
      title="Settings"
    >
      <Settings
        size={18}
        strokeWidth={1.7}
      />

      <span>Settings</span>
    </button>

  </div>

</aside>


<style>

  /* =========================================================
     SIDEBAR
     ========================================================= */

  .sidebar {

    width: 72px;
    height: 100%;

    flex-shrink: 0;

    position: relative;

    display: flex;
    flex-direction: column;
    justify-content: space-between;

    padding:
      14px 8px;

    box-sizing: border-box;

    background:
      #050505;

    border-right:
      1px solid
      rgba(255,255,255,0.075);

    color:
      #ffffff;

    font-family:
      Inter,
      -apple-system,
      BlinkMacSystemFont,
      "SF Pro Display",
      "Helvetica Neue",
      Arial,
      sans-serif;

    z-index: 40;

    user-select: none;
  }


  /* subtle inner edge */

  .sidebar::after {

    content: "";

    position: absolute;

    top: 0;
    right: 0;

    width: 1px;
    height: 100%;

    background:
      rgba(255,255,255,0.035);

    pointer-events: none;
  }


  /* =========================================================
     SECTIONS
     ========================================================= */

  .top-section,
  .bottom-section {

    display: flex;

    flex-direction: column;

    align-items: center;

    gap: 5px;

    position: relative;

    z-index: 1;
  }


  /* =========================================================
     NEW CHAT
     ========================================================= */

  .new-chat {

    width: 44px;
    height: 44px;

    display: flex;

    align-items: center;
    justify-content: center;

    margin-bottom: 4px;

    border-radius: 12px;

    background:
      rgba(255,255,255,0.055);

    border:
      1px solid
      rgba(255,255,255,0.14);

    color:
      rgba(255,255,255,0.88);

    cursor:
      pointer;

    box-shadow:
      inset 0 1px 0
      rgba(255,255,255,0.045);

    transition:
      background 0.15s ease,
      border-color 0.15s ease,
      color 0.15s ease,
      transform 0.15s ease;
  }


  .new-chat:hover {

    background:
      rgba(255,255,255,0.10);

    border-color:
      rgba(255,255,255,0.24);

    color:
      #ffffff;

    transform:
      translateY(-1px);
  }


  .new-chat:active {

    transform:
      translateY(0);
  }


  /* =========================================================
     SEPARATOR
     ========================================================= */

  .separator {

    width:
      36px;

    height:
      1px;

    margin:
      3px 0 5px;

    background:
      rgba(255,255,255,0.09);
  }


  /* =========================================================
     NAV ITEM
     ========================================================= */

  .nav-item {

    width: 54px;
    height: 54px;

    display: flex;

    flex-direction: column;

    align-items: center;
    justify-content: center;

    gap: 5px;

    padding: 0;

    border-radius: 10px;

    background:
      transparent;

    border:
      1px solid transparent;

    color:
      rgba(255,255,255,0.38);

    cursor:
      pointer;

    transition:
      background 0.15s ease,
      border-color 0.15s ease,
      color 0.15s ease;
  }


  /* =========================================================
     HOVER
     ========================================================= */

  .nav-item:hover {

    color:
      rgba(255,255,255,0.82);

    background:
      rgba(255,255,255,0.035);
  }


  /* =========================================================
     ACTIVE
     ========================================================= */

  .nav-item.active {

    color:
      #ffffff;

    background:
      rgba(255,255,255,0.075);

    border-color:
      rgba(255,255,255,0.10);

    box-shadow:
      inset 0 1px 0
      rgba(255,255,255,0.035);
  }


  /* =========================================================
     LABEL
     ========================================================= */

  .nav-item span {

    font-size:
      8.5px;

    line-height:
      1;

    font-weight:
      500;

    letter-spacing:
      -0.01em;

    color:
      inherit;
  }


  .nav-item.active span {

    font-weight:
      600;
  }


  /* =========================================================
     FOCUS
     ========================================================= */

  .new-chat:focus-visible,
  .nav-item:focus-visible {

    outline:
      1px solid
      rgba(255,255,255,0.5);

    outline-offset:
      2px;
  }


  /* =========================================================
     SHORT SCREEN
     ========================================================= */

  @media (max-height: 700px) {

    .sidebar {

      padding:
        9px 8px;
    }


    .new-chat {

      width: 40px;
      height: 40px;

      border-radius:
        10px;
    }


    .nav-item {

      width: 52px;
      height: 50px;
    }
  }

</style>