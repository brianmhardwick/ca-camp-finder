import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule, DatePipe } from '@angular/common';
import { interval, Subscription, switchMap, startWith } from 'rxjs';
import { Location } from '../../core/models/location.model';
import { LocationsService } from '../../core/services/locations.service';
import { LocationCardComponent } from './location-card/location-card.component';

@Component({
  selector: 'app-monitor-tab',
  standalone: true,
  imports: [CommonModule, DatePipe, LocationCardComponent],
  template: `
    <div class="space-y-4">
      <!-- Header bar -->
      <div class="flex items-center justify-between">
        <div>
          <p class="text-sm text-slate-400">
            <span *ngIf="health">
              {{ health.locations_enabled }} active · {{ health.total_found_today }} found today
              <span *ngIf="health.next_check" class="ml-2">
                · Next check {{ health.next_check | date:'h:mm a':'America/Los_Angeles' }}
              </span>
            </span>
          </p>
        </div>
        <div class="flex gap-2">
          <button class="btn-secondary text-sm" (click)="sendTestNotification()">
            🔔 Test Alert
          </button>
          <button class="btn-primary text-sm" (click)="checkNow()" [disabled]="checking">
            {{ checking ? 'Checking…' : '🔍 Check Now' }}
          </button>
        </div>
      </div>

      <!-- Error -->
      <div *ngIf="error" class="bg-red-900/40 text-red-400 text-sm rounded-lg px-4 py-3 border border-red-700/50">
        {{ error }}
      </div>

      <!-- Location cards -->
      <div *ngIf="!loading; else skeleton" class="space-y-3">
        <app-location-card
          *ngFor="let loc of locations; trackBy: trackBySlug"
          [location]="loc"
          (toggled)="onToggle(loc, $event)"
        ></app-location-card>
      </div>

      <ng-template #skeleton>
        <div *ngFor="let i of [1,2,3,4,5,6]" class="card animate-pulse">
          <div class="h-4 bg-navy-700 rounded w-2/3 mb-2"></div>
          <div class="h-3 bg-navy-700 rounded w-1/3"></div>
        </div>
      </ng-template>

      <!-- Toast -->
      <div *ngIf="toast"
           class="fixed bottom-6 left-1/2 -translate-x-1/2 bg-navy-700 text-white text-sm
                  px-5 py-3 rounded-xl shadow-lg border border-navy-600 z-50 transition-all">
        {{ toast }}
      </div>
    </div>
  `
})
export class MonitorTabComponent implements OnInit, OnDestroy {
  private svc = inject(LocationsService);

  locations: Location[] = [];
  health: any = null;
  loading = true;
  checking = false;
  error: string | null = null;
  toast: string | null = null;

  private sub?: Subscription;

  ngOnInit() {
    this.sub = interval(30_000).pipe(startWith(0), switchMap(() => this.svc.getLocations()))
      .subscribe({
        next: (locs) => { this.locations = locs; this.loading = false; },
        error: () => { this.error = 'Unable to reach backend.'; this.loading = false; }
      });

    this.svc.getHealth().subscribe({ next: (h) => this.health = h });
    interval(30_000).subscribe(() => this.svc.getHealth().subscribe({ next: (h) => this.health = h }));
  }

  ngOnDestroy() {
    this.sub?.unsubscribe();
  }

  trackBySlug(_: number, loc: Location) { return loc.slug; }

  onToggle(location: Location, enabled: boolean) {
    this.svc.toggleLocation(location.slug, enabled).subscribe({
      next: (updated) => {
        const idx = this.locations.findIndex(l => l.slug === location.slug);
        if (idx >= 0) this.locations[idx] = updated;
        this.showToast(enabled ? `${location.name} enabled` : `${location.name} paused`);
      },
      error: () => this.showToast('Failed to update — try again')
    });
  }

  checkNow() {
    this.checking = true;
    this.svc.triggerCheckNow().subscribe({
      next: () => {
        this.showToast('Check triggered — results will appear shortly');
        setTimeout(() => { this.checking = false; }, 3000);
      },
      error: () => { this.checking = false; this.showToast('Check failed'); }
    });
  }

  sendTestNotification() {
    this.svc.sendTestNotification().subscribe({
      next: (r) => this.showToast(r.message),
      error: () => this.showToast('Test notification failed')
    });
  }

  private showToast(msg: string) {
    this.toast = msg;
    setTimeout(() => this.toast = null, 3500);
  }
}
