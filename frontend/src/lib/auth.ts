export const ADMIN_TOKEN_KEY = 'sorty_admin_token';

export function getAdminToken(): string | null {
  return sessionStorage.getItem(ADMIN_TOKEN_KEY) || localStorage.getItem(ADMIN_TOKEN_KEY);
}

export function setAdminToken(token: string, remember: boolean = false) {
  if (remember) {
    localStorage.setItem(ADMIN_TOKEN_KEY, token);
    sessionStorage.removeItem(ADMIN_TOKEN_KEY);
  } else {
    sessionStorage.setItem(ADMIN_TOKEN_KEY, token);
    localStorage.removeItem(ADMIN_TOKEN_KEY);
  }
}

export function clearAdminToken() {
  sessionStorage.removeItem(ADMIN_TOKEN_KEY);
  localStorage.removeItem(ADMIN_TOKEN_KEY);
}

export function dispatchAuthLocked() {
  window.dispatchEvent(new Event("sorty-admin-locked"));
}
