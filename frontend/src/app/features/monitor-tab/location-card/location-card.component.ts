import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule, DatePipe } from '@angular/common';
import { Location } from '../../../core/models/location.model';
import { ToggleComponent } from '../../../shared/toggle/toggle.component';

const SCRAPER_ICONS: Record<string, string> = {
  reserveca: '⛺',
  crystal_pier: '🏖️',
  crystal_cove: '🌊',
  campland: '🏕️',
};

interface LocationInfo {
  // Booking policies
  cancellation: string;
  minStay: string;
  // Monitoring approach
  howItWorks: string;
  peakSchedule: string;
  targetDates: string;
}

const LOCATION_INFO: Record<string, LocationInfo> = {
  reserveca: {
    cancellation: '48-hour policy — cancel 2+ days before check-in for a refund (minus $7.99 fee); cancelling within 48 hours forfeits the first night.',
    minStay: 'No minimum — single nights are available.',
    howItWorks: 'Queries the ReserveCalifornia availability API directly for RV hookup sites (unit type 29). Results are near real-time and reliable.',
    peakSchedule: 'Checks every 15 min on Wed & Thu all day (48-hr cancellation deadlines for Fri/Sat arrivals), Fri before noon, and daily 6–11 PM. Every 60 min at all other times.',
    targetDates: 'Fri + Sat check-in dates for the next 2 weekends. Automatically pivots past the current weekend after Friday 9 AM Pacific when it\'s too late to realistically book.',
  },
  crystal_cove: {
    cancellation: '48-hour policy — cancel 2+ days before check-in for a refund (minus $7.99 fee); cancelling within 48 hours forfeits the first night.',
    minStay: 'No minimum — single nights available. Note: maximum 7 nights per person per calendar year.',
    howItWorks: 'Queries the ReserveCalifornia availability API for Crystal Cove cottage units. Same API as state park campgrounds but targeting cottage inventory.',
    peakSchedule: 'Checks every 15 min on Wed & Thu all day, Fri before noon, and daily 6–11 PM. Every 60 min at all other times.',
    targetDates: 'Fri + Sat check-in dates for the next 2 weekends.',
  },
  crystal_pier: {
    cancellation: '7-day policy — cancel 7+ days before check-in for a full refund; cancel within 7 days and a $50 fee applies; within 48 hours forfeits the first night.',
    minStay: '2 nights October through mid-June; 3 nights mid-June through September.',
    howItWorks: 'Uses a headless browser (Playwright) to navigate the Crystal Pier reservations page and detect available cottage/room inventory. Slightly slower than API-based scrapers due to full page rendering.',
    peakSchedule: 'Checks every 15 min on Fri, Sat & Sun all day — these are the 7-day deadline days when people cancel for the following weekend. Also every 15 min daily 6–11 PM. Every 60 min otherwise.',
    targetDates: 'Off-season (Oct–mid Jun): Fri + Sat check-in dates. Summer (mid Jun–Sep): Thu + Fri check-in dates to accommodate the 3-night minimum stay. Covers the next 2 weekends.',
  },
  campland: {
    cancellation: '72-hour policy — cancel 3+ days before arrival for a refund (minus a $30 fee); cancelling within 72 hours forfeits the first night.',
    minStay: '2 nights on regular weekends; 3 nights on holiday weekends.',
    howItWorks: 'Uses a headless browser (Playwright) to navigate the Campland booking calendar and detect open site types. Campland has no public API, so full page rendering is required.',
    peakSchedule: 'Checks every 15 min on Tue, Wed & Thu all day — the 72-hr cancellation deadlines for Fri, Sat & Sun arrivals respectively. Also every 15 min daily 6–11 PM. Every 60 min otherwise.',
    targetDates: 'Fri + Sat check-in dates for the next 2 weekends. Pivots past the current weekend after Friday 9 AM Pacific.',
  },
};

@Component({
  selector: 'app-location-card',
  standalone: true,
  imports: [CommonModule, DatePipe, ToggleComponent],
  template: `
    <div class="card" [class.opacity-40]="!location.enabled">
      <!-- Main row -->
      <div class="flex items-center justify-between gap-4">
        <div class="flex items-center gap-3 min-w-0">
          <span class="text-2xl shrink-0">{{ icon }}</span>
          <div class="min-w-0">
            <h3 class="font-semibold text-white truncate">{{ location.name }}</h3>
            <p class="text-xs text-slate-400 mt-0.5 flex items-center gap-1.5">
              <span *ngIf="location.last_checked">
                Checked {{ location.last_checked | date:'h:mm a':'America/Los_Angeles' }}
              </span>
              <span *ngIf="!location.last_checked">Not yet checked</span>
              <span *ngIf="location.last_found" class="text-green-400">
                · Found {{ location.last_found | date:'MMM d':'America/Los_Angeles' }}
              </span>
              <span *ngIf="location.is_peak"
                    class="ml-1 px-1.5 py-0.5 rounded text-amber-400 bg-amber-900/40 border border-amber-700/50 text-[10px] font-medium leading-none">
                ⚡ peak
              </span>
            </p>
          </div>
        </div>
        <div class="flex items-center gap-3 shrink-0">
          <button
            (click)="showInfo = !showInfo"
            class="text-xs font-medium text-slate-500 hover:text-slate-300 transition-colors flex items-center gap-0.5"
            aria-label="Toggle info">
            Info <span class="text-[10px]">{{ showInfo ? '▲' : '▾' }}</span>
          </button>
          <app-toggle
            [checked]="location.enabled"
            (checkedChange)="toggled.emit($event)"
          ></app-toggle>
        </div>
      </div>

      <!-- Info panel -->
      <div *ngIf="showInfo && info" class="mt-3 pt-3 border-t border-navy-700 space-y-3 text-xs">

        <!-- Booking policies -->
        <div>
          <p class="text-slate-400 font-semibold uppercase tracking-wide text-[10px] mb-1.5">Booking Policies</p>
          <div class="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5">
            <span class="text-slate-400 font-medium whitespace-nowrap">Cancellation</span>
            <span class="text-slate-300">{{ info.cancellation }}</span>
            <span class="text-slate-400 font-medium whitespace-nowrap">Min stay</span>
            <span class="text-slate-300">{{ info.minStay }}</span>
          </div>
        </div>

        <!-- Monitoring approach -->
        <div>
          <p class="text-slate-400 font-semibold uppercase tracking-wide text-[10px] mb-1.5">How Monitoring Works</p>
          <div class="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5">
            <span class="text-slate-400 font-medium whitespace-nowrap">Method</span>
            <span class="text-slate-300">{{ info.howItWorks }}</span>
            <span class="text-slate-400 font-medium whitespace-nowrap">Schedule</span>
            <span class="text-slate-300">{{ info.peakSchedule }}</span>
            <span class="text-slate-400 font-medium whitespace-nowrap">Dates checked</span>
            <span class="text-slate-300">{{ info.targetDates }}</span>
          </div>
        </div>

        <a [href]="location.booking_url" target="_blank" rel="noopener"
           class="inline-block text-sky-400 hover:text-sky-300 transition-colors">
          Open {{ bookingDomain }} ↗
        </a>
      </div>
    </div>
  `
})
export class LocationCardComponent {
  @Input({ required: true }) location!: Location;
  @Output() toggled = new EventEmitter<boolean>();

  showInfo = false;

  get icon(): string {
    return SCRAPER_ICONS[this.location.scraper_type] ?? '📍';
  }

  get info(): LocationInfo | null {
    return LOCATION_INFO[this.location.scraper_type] ?? null;
  }

  get bookingDomain(): string {
    try {
      return new URL(this.location.booking_url).hostname.replace(/^www\./, '');
    } catch {
      return this.location.booking_url;
    }
  }
}
