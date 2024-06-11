import { Component, OnInit } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { TenantsService } from '../../tenants/tenants.service';
import { Tenant } from '../../tenants/models/tenant';
import { Observable } from 'rxjs';
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
  transactionForm: FormGroup;
  tenants$ = new Observable<Tenant[]>();
  private checkout: any; // Assuming Checkout is loaded globally

  categories: string[] = [
    'Groceries',
    'Bills',
    'Entertainment',
    'Travel',
    'Other',
  ];

  constructor(private fb: FormBuilder, private tenantSvc: TenantsService) {
    this.transactionForm = this.fb.group({
      id: ['', Validators.required],
      date: ['', Validators.required],
      description: ['', Validators.required],
      amount: ['', [Validators.required, Validators.min(0)]],
    });
  }
  // constructor(private tenantSvc: TenantsService) {}

  ngOnInit(): void {
    // this.tenantSvc.fetch().subscribe((data) => {
    //   // this.tenantData = data;
    //   // this.isLoading = false;
    //   console.log(data);
    // });
    // console.log(this.transactionForm, 1000);
    // console.log(this.tenants$, 99);
    // this.checkout = window.Checkout.initiate({
    //   key: '8ac7a4c88fc8ac63018fc92d2ce50163',
    //   checkoutId: '4873f5d4596342358661add497741f36',
    //   options: {
    //     theme: {
    //       brand: {
    //         primary: '#ff0000',
    //       },
    //       cards: {
    //         background: '#00ff00',
    //         backgroundHover: '#F3F3F4',
    //       },
    //     },
    //   },
    //   events: {
    //     onCompleted: (event: any) => console.log('Completed:', event),
    //     onCancelled: (event: any) => console.log('Cancelled:', event),
    //     onExpired: (event: any) => console.log('Expired:', event),
    //   },
    // });

    // this.checkout.render('#payment-form');
  }

  onSubmit(): void {
    if (this.transactionForm.valid) {
      const newTransaction = this.transactionForm.value;
      console.log('New Transaction:', newTransaction);
      // Add logic to handle the new transaction, e.g., adding it to the transactions array.
    }
  }
}
