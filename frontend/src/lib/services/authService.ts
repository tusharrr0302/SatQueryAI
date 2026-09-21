/**
 * SatQuery AI — Clerk Authentication Service
 * Wraps @clerk/clerk-js with reactive Svelte stores and shadcn-inspired dark styling.
 */
import { writable, get } from 'svelte/store';
import { Clerk } from '@clerk/clerk-js';
import { dark } from '@clerk/themes';

export interface AuthUser {
  id: string;
  firstName: string | null;
  lastName: string | null;
  fullName: string | null;
  primaryEmailAddress: string | null;
  imageUrl: string | null;
  username: string | null;
}

export const isAuthLoaded = writable<boolean>(false);
export const isSignedIn = writable<boolean>(false);
export const currentUser = writable<AuthUser | null>(null);
export const authError = writable<string | null>(null);

let clerkInstance: Clerk | null = null;
let initPromise: Promise<Clerk | null> | null = null;

const PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY || '';

/**
 * Custom appearance options that align Clerk's components with SatQuery's
 * minimalist, shadcn-inspired dark workstation theme.
 */
export const satqueryClerkAppearance = {
  baseTheme: dark,
  variables: {
    colorPrimary: '#ffffff',
    colorBackground: '#080808',
    colorInputBackground: '#0d0d0d',
    colorInputText: '#f5f5f5',
    colorText: '#f5f5f5',
    colorTextSecondary: 'rgba(255, 255, 255, 0.52)',
    borderRadius: '0.5rem',
    fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, sans-serif',
  },
  elements: {
    card: {
      backgroundColor: '#080808',
      border: '1px solid rgba(255, 255, 255, 0.1)',
      boxShadow: '0 20px 40px rgba(0, 0, 0, 0.6)',
      borderRadius: '12px',
    },
    headerTitle: {
      color: '#f5f5f5',
      fontWeight: '600',
      fontSize: '18px',
      letterSpacing: '-0.02em',
    },
    headerSubtitle: {
      color: 'rgba(255, 255, 255, 0.52)',
      fontSize: '13px',
    },
    formButtonPrimary: {
      backgroundColor: '#ffffff',
      color: '#000000',
      fontWeight: '500',
      fontSize: '13px',
      borderRadius: '6px',
      transition: 'opacity 0.2s ease',
      '&:hover': {
        backgroundColor: '#e5e5e5',
      },
    },
    formFieldInput: {
      backgroundColor: '#0d0d0d',
      border: '1px solid rgba(255, 255, 255, 0.12)',
      color: '#f5f5f5',
      borderRadius: '6px',
      fontSize: '13px',
      '&:focus': {
        borderColor: 'rgba(255, 255, 255, 0.4)',
        boxShadow: '0 0 0 1px rgba(255, 255, 255, 0.2)',
      },
    },
    footerActionLink: {
      color: '#ffffff',
      fontWeight: '500',
      '&:hover': {
        textDecoration: 'underline',
      },
    },
    socialButtonsBlockButton: {
      backgroundColor: '#111111',
      border: '1px solid rgba(255, 255, 255, 0.1)',
      color: '#f5f5f5',
      borderRadius: '6px',
      fontSize: '13px',
      '&:hover': {
        backgroundColor: '#171717',
        borderColor: 'rgba(255, 255, 255, 0.2)',
      },
    },
    dividerLine: {
      backgroundColor: 'rgba(255, 255, 255, 0.08)',
    },
    dividerText: {
      color: 'rgba(255, 255, 255, 0.35)',
      fontSize: '11px',
      textTransform: 'uppercase',
      letterSpacing: '0.05em',
    },
    identityPreviewText: {
      color: '#f5f5f5',
    },
    identityPreviewEditButton: {
      color: 'rgba(255, 255, 255, 0.7)',
    },
  },
};

function mapClerkUser(user: any): AuthUser | null {
  if (!user) return null;
  return {
    id: user.id,
    firstName: user.firstName || null,
    lastName: user.lastName || null,
    fullName: user.fullName || `${user.firstName || ''} ${user.lastName || ''}`.trim() || null,
    primaryEmailAddress: user.primaryEmailAddress?.emailAddress || null,
    imageUrl: user.imageUrl || null,
    username: user.username || null,
  };
}

/**
 * Initializes Clerk singleton and sets up reactive store subscriptions.
 */
export async function initAuth(): Promise<Clerk | null> {
  if (clerkInstance && get(isAuthLoaded)) {
    return clerkInstance;
  }
  if (initPromise) {
    return initPromise;
  }

  initPromise = (async () => {
    if (!PUBLISHABLE_KEY) {
      console.warn(
        '[SatQuery Auth] VITE_CLERK_PUBLISHABLE_KEY is not set. Running in unauthenticated development mode.',
      );
      isAuthLoaded.set(true);
      isSignedIn.set(false);
      currentUser.set(null);
      return null;
    }

    try {
      // Clerk splits core logic and UI components; dynamically load UI bundle if needed
      if (typeof window !== 'undefined') {
        try {
          const parts = PUBLISHABLE_KEY.split('_');
          if (parts.length >= 3 && !(window as any).__internal_ClerkUICtor) {
            const rawB64 = parts[2].replace(/\$$/, '');
            const paddedB64 = rawB64 + '='.repeat((4 - (rawB64.length % 4)) % 4);
            const clerkDomain = atob(paddedB64).replace(/\$$/, '');

            await new Promise((resolve) => {
              const existing = document.querySelector('script[src*="@clerk/ui"]');
              if (existing) {
                if ((window as any).__internal_ClerkUICtor) return resolve(true);
                existing.addEventListener('load', () => resolve(true));
                existing.addEventListener('error', () => resolve(false));
              } else {
                const script = document.createElement('script');
                script.src = `https://${clerkDomain}/npm/@clerk/ui@1/dist/ui.browser.js`;
                script.async = true;
                script.crossOrigin = 'anonymous';
                script.onload = () => resolve(true);
                script.onerror = () => resolve(false);
                document.head.appendChild(script);
              }

              let elapsed = 0;
              const checkInterval = setInterval(() => {
                elapsed += 100;
                if ((window as any).__internal_ClerkUICtor || elapsed > 4000) {
                  clearInterval(checkInterval);
                  resolve(true);
                }
              }, 100);
            });
          }
        } catch (uiErr) {
          console.warn('[SatQuery Auth] Notice loading Clerk UI bundle:', uiErr);
        }
      }

      clerkInstance = new Clerk(PUBLISHABLE_KEY);
      const loadOptions: any = {
        appearance: satqueryClerkAppearance,
      };
      if (typeof window !== 'undefined' && (window as any).__internal_ClerkUICtor) {
        loadOptions.ui = { ClerkUI: (window as any).__internal_ClerkUICtor };
      }

      await clerkInstance.load(loadOptions);

      clerkInstance.addListener(({ user, session }) => {
        const signedIn = !!session;
        isSignedIn.set(signedIn);
        currentUser.set(mapClerkUser(user));
        isAuthLoaded.set(true);
      });

      isSignedIn.set(!!clerkInstance.session);
      currentUser.set(mapClerkUser(clerkInstance.user));
      isAuthLoaded.set(true);
      return clerkInstance;
    } catch (err: any) {
      console.error('[SatQuery Auth] Failed to initialize Clerk:', err);
      authError.set(err?.message || 'Failed to initialize authentication');
      isAuthLoaded.set(true);
      return null;
    }
  })();

  return initPromise;
}

/**
 * Returns the current Clerk JWT session token, or null if unauthenticated.
 */
export async function getAuthToken(): Promise<string | null> {
  try {
    const clerk = await initAuth();
    if (!clerk || !clerk.session) {
      // In local development without Clerk key configured, provide dev analyst token
      if (!PUBLISHABLE_KEY) {
        return 'test_token_analyst';
      }
      return null;
    }
    return await clerk.session.getToken();
  } catch (err) {
    console.warn('[SatQuery Auth] Error getting session token:', err);
    if (!PUBLISHABLE_KEY) return 'test_token_analyst';
    return null;
  }
}

/**
 * Signs the user out through Clerk.
 */
export async function signOutUser(): Promise<void> {
  try {
    const clerk = await initAuth();
    if (clerk) {
      await clerk.signOut();
    }
  } catch (err) {
    console.error('[SatQuery Auth] Sign-out error:', err);
  } finally {
    isSignedIn.set(false);
    currentUser.set(null);
  }
}

/**
 * Mounts Clerk's SignIn component into an existing DOM node.
 */
export async function mountSignInComponent(node: HTMLDivElement): Promise<void> {
  const clerk = await initAuth();
  if (clerk) {
    clerk.mountSignIn(node, {
      appearance: satqueryClerkAppearance,
    });
  }
}

/**
 * Unmounts Clerk's SignIn component from a DOM node.
 */
export function unmountSignInComponent(node: HTMLDivElement): void {
  if (clerkInstance) {
    try {
      clerkInstance.unmountSignIn(node);
    } catch {
      // Ignore if already unmounted
    }
  }
}

/**
 * Mounts Clerk's SignUp component into an existing DOM node.
 */
export async function mountSignUpComponent(node: HTMLDivElement): Promise<void> {
  const clerk = await initAuth();
  if (clerk) {
    clerk.mountSignUp(node, {
      appearance: satqueryClerkAppearance,
    });
  }
}

/**
 * Unmounts Clerk's SignUp component from a DOM node.
 */
export function unmountSignUpComponent(node: HTMLDivElement): void {
  if (clerkInstance) {
    try {
      clerkInstance.unmountSignUp(node);
    } catch {
      // Ignore if already unmounted
    }
  }
}

/**
 * Mounts Clerk's UserProfile modal or inline view.
 */
export async function mountUserProfileComponent(node: HTMLDivElement): Promise<void> {
  const clerk = await initAuth();
  if (clerk) {
    clerk.mountUserProfile(node, {
      appearance: satqueryClerkAppearance,
    });
  }
}

/**
 * Unmounts Clerk's UserProfile component from a DOM node.
 */
export function unmountUserProfileComponent(node: HTMLDivElement): void {
  if (clerkInstance) {
    try {
      clerkInstance.unmountUserProfile(node);
    } catch {
      // Ignore if already unmounted
    }
  }
}

