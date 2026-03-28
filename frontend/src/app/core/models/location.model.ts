export interface Location {
  id: number;
  name: string;
  slug: string;
  scraper_type: string;
  enabled: boolean;
  booking_url: string;
  last_checked: string | null;
  last_found: string | null;
}
