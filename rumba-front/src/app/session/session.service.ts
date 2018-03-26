import { Injectable } from "@angular/core";
import { Http } from "@angular/http";
import { HttpClient } from '@angular/common/http';

import { AppConfig } from '../app-config';

@Injectable()
export class SessionService {

  url: string;

  constructor(private http: Http, private httpClient: HttpClient) {}

  startSession(session: any) {
    this.url = AppConfig.START_SESSON;
    return this.http.post(AppConfig.API_ENDPOINT + this.url, session);
  }

  closeSession (id: string) {
    return this.http.put(AppConfig.API_ENDPOINT + '/sessions/' + id + '/stop', {});
  }

  getSessionById (id: string) {
    return this.http.get(AppConfig.API_ENDPOINT + '/sessions/' + id);
  }

  uploadLogo (id: string, selectedFile: File) {
    const fd = new FormData();
    fd.append('image', selectedFile, selectedFile.name);
    return this.httpClient.post(AppConfig.API_ENDPOINT + '/sessions/' + id + '/logo', fd)
  }

}
