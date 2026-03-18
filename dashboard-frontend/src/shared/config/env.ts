const rawBaseUrl = import.meta.env.VITE_DASHBOARD_API_BASE_URL?.trim() ?? "";

export const dashboardApiBaseUrl = rawBaseUrl.endsWith("/")
  ? rawBaseUrl.slice(0, -1)
  : rawBaseUrl;
