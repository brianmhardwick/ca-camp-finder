import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Location } from '../models/location.model';
import { environment } from '../../../environments/environment';

@Injectable({ providedIn: 'root' })
export class LocationsService {
  private http = inject(HttpClient);
  private base = environment.apiBase;

  getLocations(): Observable<Location[]> {
    return this.http.get<Location[]>(`${this.base}/locations`);
  }

  toggleLocation(slug: string, enabled: boolean): Observable<Location> {
    return this.http.patch<Location>(`${this.base}/locations/${slug}`, { enabled });
  }

  triggerCheckNow(): Observable<{ message: string }> {
    return this.http.post<{ message: string }>(`${this.base}/check/now`, {});
  }

  getHealth(): Observable<any> {
    return this.http.get(`${this.base}/health`);
  }

  sendTestNotification(): Observable<{ message: string }> {
    return this.http.post<{ message: string }>(`${this.base}/notify/test`, {});
  }
}
