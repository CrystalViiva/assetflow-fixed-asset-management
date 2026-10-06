import { ApiClient } from './apiClient';
import { parseDashboardMetrics } from './dashboardDtos';
export class DjangoDashboardRepository {
  constructor(private readonly api: ApiClient) {}
  async metrics(signal?: AbortSignal) { return parseDashboardMetrics(await this.api.request('/dashboard/metrics/', { signal })); }
}
