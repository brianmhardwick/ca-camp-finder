export interface AvailabilityLog {
  id: number;
  location_id: number;
  location_name: string;
  check_in_date: string;
  unit_description: string;
  unit_type: string | null;
  price_per_night: number | null;
  detected_at: string;
  booking_url: string;
  still_available: boolean;
}

export interface HealthStatus {
  status: string;
  locations_enabled: number;
  total_found_today: number;
  last_check: string | null;
  next_check: string | null;
  current_interval_minutes: number;
}
