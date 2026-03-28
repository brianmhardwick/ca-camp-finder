import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { AvailabilityLog } from '../models/log.model';
import { environment } from '../../../environments/environment';

@Injectable({ providedIn: 'root' })
export class LogsService {
  private http = inject(HttpClient);
  private base = environment.apiBase;

  getLogs(options: { location?: string; limit?: number; offset?: number } = {}): Observable<AvailabilityLog[]> {
    let params = new HttpParams();
    if (options.location) params = params.set('location', options.location);
    if (options.limit != null) params = params.set('limit', options.limit);
    if (options.offset != null) params = params.set('offset', options.offset);
    return this.http.get<AvailabilityLog[]>(`${this.base}/logs`, { params });
  }

  deleteLog(id: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/logs/${id}`);
  }
}
