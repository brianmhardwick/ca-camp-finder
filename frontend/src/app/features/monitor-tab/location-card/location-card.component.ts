import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule, DatePipe } from '@angular/common';
import { Location } from '../../../core/models/location.model';
import { ToggleComponent } from '../../../shared/toggle/toggle.component';

const SCRAPER_ICONS: Record<string, string> = {
  reserveca: '⛺',
  crystal_pier: '🏖️',
  crystal_cove: '🌊',
};

@Component({
  selector: 'app-location-card',
  standalone: true,
  imports: [CommonModule, DatePipe, ToggleComponent],
  template: `
    <div class="card flex items-center justify-between gap-4"
         [class.opacity-40]="!location.enabled">
      <div class="flex items-center gap-3 min-w-0">
        <span class="text-2xl shrink-0">{{ icon }}</span>
        <div class="min-w-0">
          <h3 class="font-semibold text-white truncate">{{ location.name }}</h3>
          <p class="text-xs text-slate-400 mt-0.5">
            <span *ngIf="location.last_checked">
              Checked {{ location.last_checked | date:'MMM d, h:mm a':'America/Los_Angeles' }}
            </span>
            <span *ngIf="!location.last_checked">Not yet checked</span>
            <span *ngIf="location.last_found" class="ml-2 text-green-400">
              · Found {{ location.last_found | date:'MMM d':'America/Los_Angeles' }}
            </span>
          </p>
        </div>
      </div>
      <div class="flex items-center gap-3 shrink-0">
        <app-toggle
          [checked]="location.enabled"
          (checkedChange)="toggled.emit($event)"
        ></app-toggle>
      </div>
    </div>
  `
})
export class LocationCardComponent {
  @Input({ required: true }) location!: Location;
  @Output() toggled = new EventEmitter<boolean>();

  get icon(): string {
    return SCRAPER_ICONS[this.location.scraper_type] ?? '📍';
  }
}
