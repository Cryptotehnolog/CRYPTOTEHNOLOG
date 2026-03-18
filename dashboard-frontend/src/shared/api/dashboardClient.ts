import { dashboardApiBaseUrl } from "../config/env";

export class DashboardApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "DashboardApiError";
    this.status = status;
  }
}

function buildUrl(path: string) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${dashboardApiBaseUrl}${normalizedPath}`;
}

export async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(buildUrl(path), {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new DashboardApiError(
      `Сервер панели вернул ошибку ${response.status}`,
      response.status,
    );
  }

  return (await response.json()) as T;
}
