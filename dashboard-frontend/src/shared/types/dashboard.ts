export type ModuleStatus = "inactive" | "read-only" | "active" | "restricted";

export type OverviewSnapshotResponse = {
  system_state: {
    is_running: boolean;
    is_shutting_down: boolean;
    current_state: string;
    startup_phase: string;
    shutdown_phase: string;
    uptime_seconds: number;
    trade_allowed: boolean;
    last_error: string | null;
  };
  health_summary: {
    overall_status: string;
    component_count: number;
    unhealthy_components: string[];
    timestamp: number | null;
  };
  pending_approvals: {
    pending_count: number;
    total_requests: number;
    request_timeout_minutes: number;
  };
  event_summary: {
    total_published: number;
    total_delivered: number;
    total_dropped: number;
    total_rate_limited: number;
    subscriber_count: number;
    persistence_enabled: boolean;
    backpressure_strategy: string;
  };
  circuit_breaker_summary: Array<{
    name: string;
    state: string;
    failure_count: number;
    success_count: number;
    failure_threshold: number;
    recovery_timeout: number;
  }>;
  module_availability: Array<{
    key: string;
    title: string;
    description: string;
    route: string;
    status: ModuleStatus;
    phase: string;
    status_reason: string | null;
  }>;
  alerts_summary: {
    connected: boolean;
    note: string;
  };
};
