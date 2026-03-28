import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MonitorTabComponent } from './features/monitor-tab/monitor-tab.component';
import { LogsTabComponent } from './features/logs-tab/logs-tab.component';

type Tab = 'monitor' | 'logs';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, MonitorTabComponent, LogsTabComponent],
  template: `
    <div class="min-h-screen bg-slate-50">
      <!-- Top nav -->
      <header class="bg-white border-b border-slate-200 sticky top-0 z-40">
        <div class="max-w-2xl mx-auto px-4">
          <div class="flex items-center justify-between h-14">
            <div class="flex items-center gap-2">
              <span class="text-xl">🏕</span>
              <span class="font-bold text-slate-900 text-lg tracking-tight">CA Camp Finder</span>
            </div>
            <!-- Tabs -->
            <nav class="flex">
              <button
                *ngFor="let t of tabs"
                (click)="activeTab = t.id"
                [class]="activeTab === t.id
                  ? 'px-4 h-14 text-sm font-semibold text-ocean-600 border-b-2 border-ocean-600'
                  : 'px-4 h-14 text-sm font-medium text-slate-500 hover:text-slate-700 border-b-2 border-transparent'">
                {{ t.label }}
              </button>
            </nav>
          </div>
        </div>
      </header>

      <!-- Tab content -->
      <main class="max-w-2xl mx-auto px-4 py-6">
        <app-monitor-tab *ngIf="activeTab === 'monitor'"></app-monitor-tab>
        <app-logs-tab *ngIf="activeTab === 'logs'"></app-logs-tab>
      </main>
    </div>
  `
})
export class AppComponent {
  activeTab: Tab = 'monitor';
  tabs = [
    { id: 'monitor' as Tab, label: 'Monitor' },
    { id: 'logs' as Tab, label: 'History' },
  ];
}
