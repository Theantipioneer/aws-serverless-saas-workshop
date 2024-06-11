/*
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */
import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable, from, pipe } from 'rxjs';
import { environment } from 'src/environments/environment';
import { Auth } from 'aws-amplify';
import { Tenant } from './models/tenant';
import { CognitoUserSession } from 'amazon-cognito-identity-js';

import { Component, OnInit } from '@angular/core';

import { map } from 'rxjs/operators';

@Injectable({
  providedIn: 'root',
})
export class TenantsService {
  accessToken$: Observable<string> | undefined;
  session$: Observable<CognitoUserSession> | undefined;

  constructor(private http: HttpClient) {}
  baseUrl = `${environment.apiUrl}`;
  tenantsApiUrl = `${this.baseUrl}/tenants`;
  registrationApiUrl = `${this.baseUrl}/registration`;

  // TODO strongly-type these anys as tenants once we dial in what the tenant call should return
  fetch(): Observable<Tenant[]> {
    console.log(from(Auth.currentSession()), 23);
    console.log(this, 24);
    console.log(this.http.get<Tenant[]>(this.tenantsApiUrl));
    this.session$ = from(Auth.currentSession());

    this.accessToken$ = this.session$.pipe(
      map((sesh) => {
        console.log(sesh.getAccessToken().getJwtToken(), 11111);
        return sesh.getAccessToken().getJwtToken();
      })
    );
    // console.log(this.accessToken$, 2000, this.session$, 11);
    // console.log(Auth.currentSession());
    from(Auth.currentSession().then((data) => console.log(data)));
    return this.http.get<Tenant[]>(this.tenantsApiUrl);
  }

  post(tenant: Tenant): Observable<Tenant[]> {
    return this.http.post<Tenant[]>(this.registrationApiUrl, tenant);
  }
}
