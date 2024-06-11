import { Component, OnInit } from '@angular/core';
import { Observable } from 'rxjs';
import { Tenant } from '../models/tenant';
import { TenantsService } from '../tenants.service';
import { HttpClient, HttpHeaders } from '@angular/common/http';
// import { v4 as uuidv4 } from 'uuid';
declare global {
  interface Window {
    Checkout: any; // Define the Checkout property on the Window interface
  }
}
@Component({
  selector: 'app-list',
  templateUrl: './list.component.html',
  styleUrls: ['./list.component.scss'],
})
export class ListComponent implements OnInit {
  tenants$ = new Observable<Tenant[]>();
  tenantData: Tenant[] = [];
  newTenantData: any = [];
  isLoading: boolean = true;
  displayedColumns = [
    'tenantId',
    'tenantName',
    'tenantEmail',
    'tenantTier',
    'isActive',
    'tenantBalance',
    'addCredits',
  ];
  checkoutId: string | null = null;
  private checkout: any; // Assuming Checkout is loaded globally

  constructor(private tenantSvc: TenantsService, private http: HttpClient) {}

  ngOnInit(): void {
    this.tenantSvc.fetch().subscribe((data) => {
      this.tenantData = data;
      this.isLoading = false;
      console.log(data, 29);
    });
  }
  generateUniqueId(): string {
    return 'OrNo' + new Date().getTime() + 'Acumen';
  }
  postTenantData(tenantData: Tenant): Observable<any> {
    tenantData.tenantBalance += 50;
    const url = `${this.tenantSvc.baseUrl}/tenant/` + tenantData.tenantId; // Adjust the URL as needed
    console.log(url);
    console.log(tenantData);
    return this.http.put<any>(url, tenantData);
    // return
    // return this.http.post<any>(url, tenantData);
  }
  callApi(): void {
    const url = 'https://acumencompanylogin.onrender.com/api/auth-token';
    this.http
      .post(
        url,
        {},
        {
          headers: {
            'Content-Type': 'application/json',
          },
        }
      )
      .subscribe(
        (data: any) => {
          console.log('Access Token:', data.access_token);
          this.getCheckoutId(data.access_token);
          // Further processing can go here
        },
        (error) => {
          console.error('Error:', error);
        }
      );
  }
  getCheckoutId(accessToken: string): void {
    const url =
      'https://acumencompanylogin.onrender.com/api/create-checkout-id';

    const body = {
      accessToken: accessToken,
      amount: 1,
      merchantTransactionId: this.generateUniqueId(),
      currency: 'ZAR',
      forceDefaultMethod: true,
      entityId: '8ac7a4c88fc8ac63018fc92d2ce50163',
      nonce: 'UNQ00012345678',
      shopperResultUrl: 'https://kaleem99.github.io/BlazingGrill-UI/',
      defaultPaymentMethod: 'CARD',
    };

    this.http
      .post(url, body, {
        headers: new HttpHeaders({
          'Content-Type': 'application/json',
        }),
      })
      .subscribe(
        (data: any) => {
          console.log('Checkout ID:', data.checkoutId, data);
          // Add any further processing or UI updates here
          this.generateIframeSrcDoc(data.checkoutId);
        },
        (error) => {
          console.error('Error:', error);
        }
      );
  }
  generateIframeSrcDoc(checkoutId: string): void {
    this.checkout = window.Checkout.initiate({
      key: '8ac7a4c88fc8ac63018fc92d2ce50163',
      checkoutId: checkoutId,
      options: {
        theme: {
          brand: {
            primary: '#ff0000',
          },
          cards: {
            background: '#00ff00',
            backgroundHover: '#F3F3F4',
          },
        },
      },
      events: {
        onCompleted: (event: any) =>
          this.postTenantData(this.newTenantData).subscribe(
            (response) => {
              console.log('PUT request successful:', response);
              // Handle success, update UI, etc.
              console.log('Completed', event);
              this.newTenantData.tenantBalance += 20;
            },
            (error) => {
              console.error('Error in PUT request:', error);
              // Handle error, display error message, etc.
            }
          ),
        onCancelled: (event: any) => console.log('Cancelled:', event),
        onExpired: (event: any) => console.log('Expired:', event),
      },
    });

    this.checkout.render('#payment-form');
  }

  addCredits(element: Tenant): void {
    // Logic to add credits for the selected tenant
    console.log('Add credits for:', element);
    // element.tenantBalance += 50;
    console.log(this.generateUniqueId(), 50);
    this.callApi();
    this.newTenantData = element;
    // console.log(this.tenantSvc.tenantsApiUrl, this.tenantSvc.baseUrl, 100);
    // this.postTenantData(element).subscribe(
    //   (response) => {
    //     console.log('PUT request successful:', response);
    //     // Handle success, update UI, etc.
    //   },
    //   (error) => {
    //     console.error('Error in PUT request:', error);
    //     // Handle error, display error message, etc.
    //   }
    // );
    // You can call a service method here to add credits or update the tenant's balance
  }
}
