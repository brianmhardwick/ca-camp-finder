import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule, DatePipe, CurrencyPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { interval, Subscription, switchMap, startWith } from 'rxjs';
import { AvailabilityLog } from '../../core/models/log.model';
import { LogsService } from '../../core/services/logs.service';
import { LocationsService } from '../../core/services/locations.service';
import { Location } from '../../core/models/location.model';

@Component({
  selector: 'app-logs-tab',
  standalone: true,
  imports: [CommonModule, DatePipe, CurrencyPipe, FormsModule],
  template: `
    <div class="space-y-4">
      <!-- Filters -->
      <div class="flex flex-wrap items-center gap-3">
        <select [(ngModel)]="filterSlug" (ngModelChange)="onFilterChange()"
                class="text-sm border border-navy-600 rounded-lg px-3 py-2 bg-navy-800 text-slate-200
                       focus:outline-none focus:ring-2 focus:ring-ocean-500">
          <option value="">All Locations</option>
          <option *ngFor="let loc of locations" [value]="loc.slug">{{ loc.name }}</option>
        </select>
        <span class="text-sm text-slate-500 ml-auto">{{ logs.length }} entries</span>
      </div>

      <!-- Empty state -->
      <div *ngIf="!loading && logs.length === 0"
           class="card text-center py-12 text-slate-500">
        <p class="text-3xl mb-3">🏖️</p>
        <p class="font-medium text-slate-300">No availability found yet</p>
        <p class="text-sm mt-1">Results will appear here when campsites or rooms open up</p>
      </div>

      <!-- Table -->
      <div *ngIf="logs.length > 0" class="card overflow-x-auto p-0">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left text-xs text-slate-500 uppercase tracking-wide border-b border-navy-700">
              <th class="px-4 py-3 font-medium">Status</th>
              <th class="px-4 py-3 font-medium">Location</th>
              <th class="px-4 py-3 font-medium">Unit</th>
              <th class="px-4 py-3 font-medium">Check-in</th>
              <th class="px-4 py-3 font-medium">Price</th>
              <th class="px-4 py-3 font-medium">Found</th>
              <th class="px-4 py-3 font-medium"></th>
            </tr>
          </thead>
          <tbody>
            <tr *ngFor="let log of logs; trackBy: trackById"
                class="border-b border-navy-700/50 hover:bg-navy-700/30 transition-colors"
                [class.opacity-40]="!log.still_available">
              <td class="px-4 py-3">
                <span class="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full"
                      [class]="log.still_available
                        ? 'bg-green-900/50 text-green-400 border border-green-700/50'
                        : 'bg-navy-700 text-slate-500'">
                  <span class="w-1.5 h-1.5 rounded-full"
                        [class]="log.still_available ? 'bg-green-400' : 'bg-slate-600'"></span>
                  {{ log.still_available ? 'Available' : 'Gone' }}
                </span>
              </td>
              <td class="px-4 py-3 text-slate-200 font-medium">{{ log.location_name }}</td>
              <td class="px-4 py-3 text-slate-400 max-w-xs truncate">{{ log.unit_description }}</td>
              <td class="px-4 py-3 text-slate-300 whitespace-nowrap">
                {{ log.check_in_date | date:'EEE, MMM d' }}
              </td>
              <td class="px-4 py-3 text-slate-400">
                {{ log.price_per_night ? (log.price_per_night | currency) : '—' }}
              </td>
              <td class="px-4 py-3 text-slate-500 whitespace-nowrap text-xs">
                {{ log.detected_at | date:'MMM d, h:mm a':'America/Los_Angeles' }}
              </td>
              <td class="px-4 py-3">
                <div class="flex items-center gap-2">
                  <a *ngIf="log.still_available" [href]="log.booking_url" target="_blank" rel="noopener"
                     class="text-xs font-medium text-ocean-400 hover:text-ocean-300 whitespace-nowrap">
                    Book →
                  </a>
                  <button (click)="deleteLog(log.id)"
                          class="text-xs text-slate-600 hover:text-red-400 transition-colors">✕</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Pagination -->
      <div *ngIf="logs.length >= pageSize" class="flex justify-center">
        <button class="btn-secondary text-sm" (click)="loadMore()">Load more</button>
      </div>

      <!-- Skeleton -->
      <div *ngIf="loading" class="space-y-2">
        <div *ngFor="let i of [1,2,3,4,5]" class="card animate-pulse h-12"></div>
      </div>
    </div>
  `
})
export class LogsTabComponent implements OnInit, OnDestroy {
  private logsSvc = inject(LogsService);
  private locSvc = inject(LocationsService);

  logs: AvailabilityLog[] = [];
  locations: Location[] = [];
  loading = true;
  filterSlug = '';
  pageSize = 50;
  offset = 0;

  private sub?: Subscription;

  ngOnInit() {
    this.locSvc.getLocations().subscribe({ next: (l) => this.locations = l });
    this.sub = interval(60_000).pipe(startWith(0), switchMap(() => this.fetchLogs()))
      .subscribe({ next: (logs) => { this.logs = logs; this.loading = false; } });
  }

  ngOnDestroy() {
    this.sub?.unsubscribe();
  }

  trackById(_: number, log: AvailabilityLog) { return log.id; }

  onFilterChange() {
    this.offset = 0;
    this.fetchLogs().subscribe({ next: (logs) => this.logs = logs });
  }

  loadMore() {
    this.offset += this.pageSize;
    this.fetchLogs().subscribe({ next: (more) => this.logs = [...this.logs, ...more] });
  }

  deleteLog(id: number) {
    this.logsSvc.deleteLog(id).subscribe({ next: () => {
      this.logs = this.logs.filter(l => l.id !== id);
    }});
  }

  private fetchLogs() {
    return this.logsSvc.getLogs({
      location: this.filterSlug || undefined,
      limit: this.pageSize,
      offset: this.offset,
    });
  }
}
