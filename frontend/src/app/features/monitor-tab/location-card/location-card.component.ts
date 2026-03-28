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

interface PolicyInfo {
  cancellation: string;
  minStay: string;
  peakPolling: string;
  searches: string;
}

const POLICY_INFO: Record<string, PolicyInfo> = {
  reserveca: {
    cancellation: '48-hour policy — cancel 2+ days before check-in for a refund (minus $7.99 fee); cancelling within 48 hours forfeits the first night.',
    minStay: 'No minimum — single nights available.',
    peakPolling: 'Every 15 min on Wed & Thu all day (48-hr deadline for Fri/Sat arrivals), Fri before noon, and daily 6–11 PM. Every 60 min otherwise.',
    searches: 'Fri + Sat check-in dates across the next 2 weekends. Pivots past the current weekend after Friday 9 AM Pacific.',
  },
  crystal_cove: {
    cancellation: '48-hour policy — cancel 2+ days before check-in for a refund (minus $7.99 fee); cancelling within 48 hours forfeits the first night.',
    minStay: 'No minimum — single nights available. Maximum 7 nights per person per year at Crystal Cove.',
    peakPolling: 'Every 15 min on Wed & Thu all day, Fri before noon, and daily 6–11 PM. Every 60 min otherwise.',
    searches: 'Fri + Sat check-in dates across the next 2 weekends.',
  },
  crystal_pier: {
    cancellation: '7-day policy — cancel 7+ days before check-in for a full refund; within 7 days incurs a $50 fee; within 48 hours forfeits the first night.',
    minStay: '2 nights October through mid-June; 3 nights mid-June through September.',
    peakPolling: 'Every 15 min on Fri, Sat & Sun all day (7-day deadline days for upcoming weekend arrivals) and daily 6–11 PM. Every 60 min otherwise.',
    searches: 'Off-season (Oct–mid Jun): Fri + Sat check-ins. Summer (mid Jun–Sep): Thu + Fri check-ins to cover the 3-night minimum. Next 2 weekends rolling.',
  },
  campland: {
    cancellation: '72-hour policy — cancel 3+ days before arrival for a refund (minus $30 fee); cancelling within 72 hours forfeits the first night.',
    minStay: '2 nights on weekends; 3 nights on holiday weekends.',
    peakPolling: 'Every 15 min on Tue, Wed & Thu all day (72-hr deadline for Fri, Sat & Sun arrivals) and daily 6–11 PM. Every 60 min otherwise.',
    searches: 'Fri + Sat check-in dates across the next 2 weekends. Pivots past the current weekend after Friday 9 AM Pacific.',
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
            (click)="showAbout = !showAbout"
            class="text-slate-500 hover:text-slate-300 transition-colors text-sm leading-none"
            [title]="showAbout ? 'Hide details' : 'Show booking policy & polling logic'"
            aria-label="Toggle details">
            {{ showAbout ? '▲' : 'ⓘ' }}
          </button>
          <app-toggle
            [checked]="location.enabled"
            (checkedChange)="toggled.emit($event)"
          ></app-toggle>
        </div>
      </div>

      <!-- Collapsible about section -->
      <div *ngIf="showAbout && policy" class="mt-3 pt-3 border-t border-navy-700 space-y-2">
        <div class="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-xs">
          <span class="text-slate-400 font-medium whitespace-nowrap">Cancellation</span>
          <span class="text-slate-300">{{ policy.cancellation }}</span>

          <span class="text-slate-400 font-medium whitespace-nowrap">Min stay</span>
          <span class="text-slate-300">{{ policy.minStay }}</span>

          <span class="text-slate-400 font-medium whitespace-nowrap">Peak polling</span>
          <span class="text-slate-300">{{ policy.peakPolling }}</span>

          <span class="text-slate-400 font-medium whitespace-nowrap">Searches</span>
          <span class="text-slate-300">{{ policy.searches }}</span>
        </div>
        <a [href]="location.booking_url" target="_blank" rel="noopener"
           class="inline-block text-xs text-sky-400 hover:text-sky-300 transition-colors mt-1">
          Book at {{ bookingDomain }} ↗
        </a>
      </div>
    </div>
  `
})
export class LocationCardComponent {
  @Input({ required: true }) location!: Location;
  @Output() toggled = new EventEmitter<boolean>();

  showAbout = false;

  get icon(): string {
    return SCRAPER_ICONS[this.location.scraper_type] ?? '📍';
  }

  get policy(): PolicyInfo | null {
    return POLICY_INFO[this.location.scraper_type] ?? null;
  }

  get bookingDomain(): string {
    try {
      return new URL(this.location.booking_url).hostname.replace(/^www\./, '');
    } catch {
      return this.location.booking_url;
    }
  }
}
