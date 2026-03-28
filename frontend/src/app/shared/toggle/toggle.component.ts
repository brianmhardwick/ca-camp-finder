import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-toggle',
  standalone: true,
  imports: [CommonModule],
  template: `
    <button
      type="button"
      role="switch"
      [attr.aria-checked]="checked"
      (click)="toggle()"
      [class]="checked
        ? 'relative inline-flex h-6 w-11 items-center rounded-full bg-ocean-600 transition-colors focus:outline-none focus:ring-2 focus:ring-ocean-500 focus:ring-offset-2'
        : 'relative inline-flex h-6 w-11 items-center rounded-full bg-slate-200 transition-colors focus:outline-none focus:ring-2 focus:ring-ocean-500 focus:ring-offset-2'"
    >
      <span
        [class]="checked
          ? 'inline-block h-4 w-4 translate-x-6 transform rounded-full bg-white shadow transition-transform'
          : 'inline-block h-4 w-4 translate-x-1 transform rounded-full bg-white shadow transition-transform'"
      ></span>
    </button>
  `
})
export class ToggleComponent {
  @Input() checked = false;
  @Output() checkedChange = new EventEmitter<boolean>();

  toggle() {
    this.checkedChange.emit(!this.checked);
  }
}
