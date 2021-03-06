import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { SessionService } from '../session/session.service';

import { Vimeo } from '../model/vimeo.model';

import * as moment from 'moment';

import { ClipboardModule } from 'ngx-clipboard';
import { ToasterService } from 'angular5-toaster/dist/src/toaster.service';
import { ToasterConfig } from 'angular5-toaster/dist/src/toaster-config';
import { RecordService } from '../record.service';

@Component({
  selector: 'app-session-close',
  templateUrl: './session-close.component.html',
  styleUrls: ['./session-close.component.css']
})
export class SessionCloseComponent implements OnInit {

  activatedHelp: boolean = false;
  sessionId: string;
  binaryData = null;
  vimeouser: string = undefined;
  vimeopassword: string = undefined;
  formatedDate: string = 'undefined';
  editorLink: string = undefined;
  recordLink: string = undefined;

  currentSession: {concert: string, band: string, date:number, is_public: boolean, location: string, vimeo: Vimeo} = undefined;
  public toasterconfig: ToasterConfig = new ToasterConfig({animation: 'fade'});

  isImageLoading: boolean = false;
  imageToShow: any;

  constructor(
    private route: ActivatedRoute,
    private sessionSrv: SessionService,
    private router: Router,
    private toasterService: ToasterService,
    private recordSrv: RecordService) { }

  createImageFromBlob(image: Blob) {
     const reader = new FileReader();
     reader.addEventListener('load', () => {
        this.imageToShow = reader.result;
     }, false);

     if (image) {
        reader.readAsDataURL(image);
     }
  }

  setHelpStatus() {
    this.activatedHelp = !this.activatedHelp;
  }

  ngOnInit() {
    this.sessionId = this.route.snapshot.params['id'];
    // console.log('this.sessionId::', this.sessionId);

    this.sessionSrv.getSessionById(this.sessionId)
      .subscribe(
        (response) => {
          console.log(response);
          this.currentSession = response.json();

          const dateOk = new Date(this.currentSession.date);
          const niceDate = moment(dateOk).locale('es').format('L');

          this.formatedDate = niceDate;
          this.editorLink = this.currentSession['edition_url'];
          this.recordLink = this.currentSession['record_url'];

          this.toasterService.pop('success', 'Crear sessió', 'Sessió creada correctament');
        }
      );

    this.sessionSrv.getLogoById(this.sessionId)
      .subscribe(
        (response) => {
          this.binaryData = response.blob();
          this.createImageFromBlob(this.binaryData);
        }
      );
  }

  goToMasterCamera() {
    window.open(
      this.currentSession['master_url'],
      '_blank'
    );
  }

  onCloseSession() {
    this.sessionSrv.closeSession(this.sessionId)
      .subscribe(
        (response) => {
          console.log('close session', response);
          this.router.navigate(['/session']);
        }
      )
  }

  onCopyToClipboard() {
    this.toasterService.pop('info', 'Enllaç creat', 'l\'Enllaç s\'ha copiat al portaretalls');
  }

  onCopyRecordLinkToClipboard() {
    this.toasterService.pop('info', 'Enllaç creat', 'l\'Enllaç s\'ha copiat al portaretalls');
  }

}
