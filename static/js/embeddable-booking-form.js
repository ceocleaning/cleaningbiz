/**
 * Embeddable Booking Form JavaScript
 * This script creates and manages an embeddable booking form that can be added to any website
 */

class CleaningBizBookingForm {
  constructor(options = {}) {
    this.options = {
      businessId: null,
      targetElement: null,
      apiBaseUrl: 'https://cleaningbizai.com',
      onSuccess: null,
      onError: null,
      redirectToInvoice: true, // Whether to redirect to invoice page after successful booking
      ...options
    };

    if (!this.options.businessId) {
      console.error('Business ID is required');
      return;
    }

    if (!this.options.targetElement) {
      console.error('Target element is required');
      return;
    }

    this.businessData = null;
    this.formElement = null;
    this.customerId = null;
    this.customerPricing = null;
    this.appliedCoupon = null;
    this.couponDiscountAmount = 0;
    this.init();
  }

  async init() {
    try {
      // Fetch business data and pricing
      await this.fetchBusinessData();
      
      // Create and render the form
      this.renderForm();
      
      // Wait for the next frame to ensure DOM elements are available
      setTimeout(() => {
        // Set up event listeners
        this.setupEventListeners();
        
        // Initialize the form with default values
        this.initializeFormValues();
      }, 0);
    } catch (error) {
      console.error('Error initializing booking form:', error);
      if (this.options.onError) {
        this.options.onError(error);
      }
    }
  }
  
  initializeFormValues() {
    // Set default values for form fields if needed
    const serviceTypeEl = document.getElementById('serviceType');
    if (serviceTypeEl && !serviceTypeEl.value) {
      // Select the first option if none is selected
      if (serviceTypeEl.options.length > 0) {
        serviceTypeEl.selectedIndex = 0;
      }
    }
    
    // Initialize calculations
    this.calculatePrice();
    this.updateOverview();
  }

  async fetchBusinessData() {
    try {
      const response = await fetch(`${this.options.apiBaseUrl}/customer/api/booking/${this.options.businessId}/`);
      
      if (!response.ok) {
        throw new Error(`Failed to fetch business data: ${response.status}`);
      }
      
      this.businessData = await response.json();
      return this.businessData;
    } catch (error) {
      console.error('Error fetching business data:', error);
      throw error;
    }
  }

  async checkExistingCustomer() {
    const emailInput = document.getElementById('email');
    if (!emailInput || !emailInput.value) {
      return;
    }

    try {
      const response = await fetch(`${this.options.apiBaseUrl}/customer/api/check-customer/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email: emailInput.value,
          business_id: this.options.businessId
        })
      });

      if (response.ok) {
        const data = await response.json();
        console.log('Check customer response:', data);
        
        if (data.customer_id) {
          this.customerId = data.customer_id;
          
          // Auto-fill customer information if available
          if (data.customer_info) {
            this.autoFillCustomerInfo(data.customer_info);
          }
          
          // Fetch custom pricing for this customer
          await this.fetchCustomerPricing();
        } else {
          this.customerId = null;
          this.customerPricing = null;
        }
      }
    } catch (error) {
      console.error('Error checking existing customer:', error);
      // Continue without custom pricing
      this.customerId = null;
      this.customerPricing = null;
    }
  }

  autoFillCustomerInfo(customerInfo) {
    console.log('Auto-filling customer info:', customerInfo);
    
    // Fill Step 1 fields (if not already filled)
    this.safeSetValue('firstName', customerInfo.first_name);
    this.safeSetValue('lastName', customerInfo.last_name);
    this.safeSetValue('phoneNumber', customerInfo.phone_number);
    this.safeSetValue('countryCode', customerInfo.country_code);
    
    // Fill Step 2 (Address) fields
    this.safeSetValue('address', customerInfo.address);
    this.safeSetValue('city', customerInfo.city);
    this.safeSetValue('stateOrProvince', customerInfo.state);
    this.safeSetValue('zipCode', customerInfo.zip_code);
    
    // Show a notification that info was auto-filled
    if (customerInfo.address) {
      this.showAutoFillNotification();
    }
  }

  showAutoFillNotification() {
    // Show a temporary notification
    const step1 = document.getElementById('step1');
    if (step1) {
      // Remove existing notification if any
      const existingNotif = document.getElementById('autofill-notification');
      if (existingNotif) {
        existingNotif.remove();
      }
      
      const notification = document.createElement('div');
      notification.id = 'autofill-notification';
      notification.className = 'alert alert-info mt-3';
      notification.style.cssText = 'animation: fadeIn 0.3s ease-in;';
      notification.innerHTML = `
        <div class="d-flex align-items-center">
          <i class="fas fa-info-circle me-2"></i>
          <span>We've pre-filled your information. Please review and update if needed.</span>
        </div>
      `;
      step1.appendChild(notification);
      
      // Remove notification after 5 seconds
      setTimeout(() => {
        if (notification && notification.parentNode) {
          notification.style.animation = 'fadeOut 0.3s ease-out';
          setTimeout(() => notification.remove(), 300);
        }
      }, 5000);
    }
  }

  async fetchCustomerPricing() {
    if (!this.customerId) {
      return;
    }

    try {
      const response = await fetch(`${this.options.apiBaseUrl}/customer/api/pricing/${this.options.businessId}/customer/${this.customerId}/`);

      if (response.ok) {
        const data = await response.json();
        console.log('Customer pricing response:', data);
        
        if (data.success && data.pricing) {
          this.customerPricing = data.pricing;
          
          // Show special rates indicator if custom pricing is active
          if (data.pricing.is_custom_pricing) {
            this.showSpecialRatesIndicator(data.pricing.customer_name);
          }
          
          // Recalculate prices with custom pricing
          this.calculatePrice();
          this.updateOverview();
        }
      }
    } catch (error) {
      console.error('Error fetching customer pricing:', error);
      // Continue with default pricing
      this.customerPricing = null;
    }
  }

  showSpecialRatesIndicator(customerName) {
    // Add special rates badge to the overview card
    const overviewCard = document.querySelector('.cleaningbiz-overview-card .cleaningbiz-card-header');
    if (overviewCard) {
      // Remove existing indicator if any
      const existingIndicator = document.getElementById('special-rates-indicator');
      if (existingIndicator) {
        existingIndicator.remove();
      }
      
      // Create new indicator
      const indicator = document.createElement('div');
      indicator.id = 'special-rates-indicator';
      indicator.className = 'alert alert-success mt-2 mb-0';
      indicator.style.cssText = 'padding: 8px 12px; font-size: 0.875rem; border-radius: 6px;';
      indicator.innerHTML = `
        <div class="d-flex align-items-center">
          <i class="fas fa-star me-2" style="color: #ffc107;"></i>
          <strong>Special Rates Applied!</strong>
        </div>
        <small class="d-block mt-1">Welcome back${customerName ? ', ' + customerName.split(' ')[0] : ''}! You're getting your custom pricing.</small>
      `;
      overviewCard.appendChild(indicator);
    }
  }

  renderForm() {
    const targetElement = document.querySelector(this.options.targetElement);
    if (!targetElement) {
      console.error(`Target element not found: ${this.options.targetElement}`);
      return;
    }

    // Create form container
    this.formElement = document.createElement('div');
    this.formElement.className = 'cleaningbiz-booking-form';
    
    // Add Bootstrap CSS if not already present
    if (!document.querySelector('link[href*="bootstrap"]')) {
      const bootstrapCss = document.createElement('link');
      bootstrapCss.rel = 'stylesheet';
      bootstrapCss.href = 'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css';
      document.head.appendChild(bootstrapCss);
    }
    
    // Add Font Awesome if not already present
    if (!document.querySelector('link[href*="font-awesome"]')) {
      const fontAwesomeCss = document.createElement('link');
      fontAwesomeCss.rel = 'stylesheet';
      fontAwesomeCss.href = 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css';
      document.head.appendChild(fontAwesomeCss);
    }
    
    // Add custom CSS
    const styleElement = document.createElement('style');
    styleElement.textContent = `
      .cleaningbiz-booking-form {
        font-family: 'Arial', sans-serif;
        max-width: 1200px;
        margin: 0 auto;
      }
      
      .cleaningbiz-card {
        border-radius: 8px;
        box-shadow: 0 0 10px rgba(0,0,0,0.1);
        margin-bottom: 20px;
      }
      
      .cleaningbiz-card-header {
        background-color: #f8f9fa;
        padding: 15px 20px;
        border-bottom: 1px solid #dee2e6;
        border-radius: 8px 8px 0 0;
      }
      
      .cleaningbiz-card-body {
        padding: 20px;
      }
      
      .cleaningbiz-progress {
        height: 8px;
        margin-bottom: 10px;
      }
      
      .cleaningbiz-step-indicator {
        font-size: 14px;
        color: #6c757d;
        transition: all 0.3s ease;
      }
      
      .cleaningbiz-step-indicator.active {
        color: #3498db;
        font-weight: 500;
      }
      
      .cleaningbiz-step-indicator.completed {
        color: #2ecc71;
      }
      
      .cleaningbiz-form-step {
        display: none;
      }
      
      .cleaningbiz-form-step.active {
        display: block;
      }
      
      .cleaningbiz-form-section {
        margin-bottom: 20px;
      }
      
      .cleaningbiz-form-section h5 {
        margin-bottom: 15px;
        color: #2c3e50;
      }
      
      .cleaningbiz-form-group {
        margin-bottom: 15px;
      }
      
      .cleaningbiz-form-group label {
        display: block;
        margin-bottom: 5px;
        font-weight: 500;
      }
      
      .cleaningbiz-form-control {
        width: 100%;
        padding: 8px 12px;
        border: 1px solid #ced4da;
        border-radius: 4px;
        font-size: 16px;
        transition: border-color 0.15s ease-in-out, box-shadow 0.15s ease-in-out;
      }
      
      .cleaningbiz-form-control:focus {
        border-color: #3498db;
        outline: 0;
        box-shadow: 0 0 0 0.25rem rgba(52, 152, 219, 0.25);
      }
      
      .cleaningbiz-form-control.is-invalid {
        border-color: #dc3545;
      }
      
      .cleaningbiz-invalid-feedback {
        display: none;
        width: 100%;
        margin-top: 0.25rem;
        font-size: 0.875em;
        color: #dc3545;
      }
      
      .cleaningbiz-form-control.is-invalid + .cleaningbiz-invalid-feedback {
        display: block;
      }
      
      .cleaningbiz-addon-item {
        display: flex;
        align-items: center;
        margin-bottom: 10px;
        padding: 10px;
        border-radius: 4px;
        background-color: #f8f9fa;
      }
      
      .cleaningbiz-addon-item label {
        margin-right: 10px;
        margin-bottom: 0;
        flex-grow: 1;
      }
      
      .cleaningbiz-addon-item input {
        width: 70px;
      }
      
      .cleaningbiz-price-summary {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 4px;
      }
      
      .cleaningbiz-price-row {
        display: flex;
        justify-content: space-between;
        margin-bottom: 8px;
      }
      
      .cleaningbiz-price-total {
        font-weight: bold;
        font-size: 18px;
        border-top: 1px solid #dee2e6;
        padding-top: 10px;
        margin-top: 10px;
      }
      
      .cleaningbiz-btn {
        display: inline-block;
        font-weight: 400;
        text-align: center;
        white-space: nowrap;
        vertical-align: middle;
        user-select: none;
        border: 1px solid transparent;
        padding: 0.375rem 0.75rem;
        font-size: 1rem;
        line-height: 1.5;
        border-radius: 0.25rem;
        transition: color 0.15s ease-in-out, background-color 0.15s ease-in-out, border-color 0.15s ease-in-out, box-shadow 0.15s ease-in-out;
        cursor: pointer;
      }
      
      .cleaningbiz-btn-primary {
        color: #fff;
        background-color: #3498db;
        border-color: #3498db;
      }
      
      .cleaningbiz-btn-primary:hover {
        background-color: #2980b9;
        border-color: #2980b9;
      }
      
      .cleaningbiz-btn-secondary {
        color: #fff;
        background-color: #6c757d;
        border-color: #6c757d;
      }
      
      .cleaningbiz-btn-secondary:hover {
        background-color: #5a6268;
        border-color: #5a6268;
      }
      
      .cleaningbiz-overview-card {
        position: sticky;
        top: 20px;
      }
      
      .cleaningbiz-overview-section {
        margin-bottom: 15px;
      }
      
      .cleaningbiz-overview-section h6 {
        color: #6c757d;
        margin-bottom: 10px;
      }
      
      .cleaningbiz-overview-item {
        display: flex;
        justify-content: space-between;
        margin-bottom: 5px;
      }
      
      .cleaningbiz-success-message {
        background-color: #d4edda;
        color: #155724;
        padding: 15px;
        border-radius: 4px;
        margin-top: 20px;
      }
      
      .cleaningbiz-error-message {
        background-color: #f8d7da;
        color: #721c24;
        padding: 15px;
        border-radius: 4px;
        margin-top: 20px;
      }
      
      @media (max-width: 768px) {
        .cleaningbiz-overview-card {
          position: static;
        }
      }
    `;
    
    document.head.appendChild(styleElement);
    
    // Form HTML with two-column layout and multi-step form
    this.formElement.innerHTML = `
      <div class="row">
        <!-- Left Column - Booking Form -->
        <div class="col-lg-8">
          <div class="cleaningbiz-card">
            <div class="cleaningbiz-card-header">
              <h2 class="px-3 py-3"><i class="fas fa-calendar-plus me-2"></i>Book a Cleaning with ${this.businessData.business.businessName}</h2>
              
              <!-- Progress Bar -->
              <div class="px-3">
                <div class="progress cleaningbiz-progress">
                  <div id="form-progress" class="progress-bar" role="progressbar" style="width: 20%;" aria-valuenow="20" aria-valuemin="0" aria-valuemax="100">20%</div>
                </div>
                <div class="d-flex justify-content-between mt-2">
                  <span class="cleaningbiz-step-indicator active" id="step1-indicator">Customer</span>
                  <span class="cleaningbiz-step-indicator" id="step2-indicator">Address</span>
                  <span class="cleaningbiz-step-indicator" id="step3-indicator">Service</span>
                  <span class="cleaningbiz-step-indicator" id="step4-indicator">Property</span>
                  <span class="cleaningbiz-step-indicator" id="step5-indicator">Add-ons</span>
                </div>
              </div>
            </div>
            
            <div class="cleaningbiz-card-body px-4 py-4">
              <form id="cleaningbiz-booking-form">
                <input type="hidden" id="subtotal" name="subtotal" value="0">
                <input type="hidden" id="tax" name="tax" value="0">
                <input type="hidden" id="totalAmount" name="totalAmount" value="0">
                <input type="hidden" id="appliedDiscountPercent" name="appliedDiscountPercent" value="0">
                <input type="hidden" id="discountAmount" name="discountAmount" value="0">
                
                <!-- Coupon Hidden Fields -->
                <input type="hidden" id="appliedCouponCode" name="appliedCouponCode" value="">
                <input type="hidden" id="couponDiscountAmount" name="couponDiscountAmount" value="0">
                
                <!-- Step 1: Customer Information -->
                <div class="cleaningbiz-form-step active" id="step1">
                  <h5 class="mb-4"><i class="fas fa-user me-2"></i>Customer Information</h5>
                  
                  <div class="row">
                    <div class="col-md-6 mb-3">
                      <label for="firstName" class="form-label">First Name</label>
                      <input type="text" class="form-control cleaningbiz-form-control" id="firstName" name="firstName" required>
                      <div class="cleaningbiz-invalid-feedback">Please enter your first name.</div>
                    </div>
                    <div class="col-md-6 mb-3">
                      <label for="lastName" class="form-label">Last Name</label>
                      <input type="text" class="form-control cleaningbiz-form-control" id="lastName" name="lastName" required>
                      <div class="cleaningbiz-invalid-feedback">Please enter your last name.</div>
                    </div>
                  </div>
                  
                  <div class="row">
                    <div class="col-md-6 mb-3">
                      <label for="email" class="form-label">Email</label>
                      <input type="email" class="form-control cleaningbiz-form-control" id="email" name="email" placeholder="john.doe@example.com" required>
                      <div class="cleaningbiz-invalid-feedback">Please enter a valid email address.</div>
                    </div>
                    <div class="col-md-6 mb-3">
                      <label for="phoneNumber" class="form-label">Phone Number</label>
                      <div class="d-flex">
                        <div class="input-group me-2" style="width: 150px;">
                          <span class="input-group-text">+</span>
                          <select class="form-select cleaningbiz-form-control" id="countryCode" name="countryCode">
                            <option value="1" selected>1 (US/CA)</option>
                            <option value="44">44 (UK)</option>
                            <option value="49">49 (DE)</option>
                            <option value="61">61 (AU)</option>
                            <option value="86">86 (CN)</option>
                            <option value="91">91 (IN)</option>
                            <option value="92">92 (PK)</option>
                          </select>
                        </div>
                        <input type="tel" 
                               class="form-control cleaningbiz-form-control" 
                               id="phoneNumber" 
                               name="phoneNumber" 
                               placeholder="555 123 4567"
                               pattern="^[0-9]{3}[ -]?[0-9]{3}[ -]?[0-9]{4}$"
                               title="Format: Area code and phone number (e.g., 555 123 4567)"
                               required>
                      </div>
                      <small class="form-text text-muted">Select country code and enter your phone number</small>
                      <div class="cleaningbiz-invalid-feedback">Please enter a valid phone number.</div>
                    </div>
                  </div>
                  
                  <div class="d-flex justify-content-end mt-4">
                    <button type="button" class="btn cleaningbiz-btn cleaningbiz-btn-primary next-step">Next <i class="fas fa-arrow-right ms-2"></i></button>
                  </div>
                </div>
                
                <!-- Step 2: Address Information -->
                <div class="cleaningbiz-form-step" id="step2">
                  <h5 class="mb-4"><i class="fas fa-map-marker-alt me-2"></i>Address Information</h5>
                  <div class="row">
                    <div class="col-md-12 mb-3">
                      <label for="address" class="form-label">Address</label>
                      <input type="text" class="form-control cleaningbiz-form-control" id="address" name="address" placeholder="123 Main Street" required>
                      <div class="cleaningbiz-invalid-feedback">Please enter your address.</div>
                    </div>
                  </div>
                  
                  <div class="row">
                    <div class="col-md-4 mb-3">
                      <label for="city" class="form-label">City</label>
                      <input type="text" class="form-control cleaningbiz-form-control" id="city" name="city" placeholder="New York" required>
                      <div class="cleaningbiz-invalid-feedback">Please enter your city.</div>
                    </div>
                    <div class="col-md-4 mb-3">
                      <label for="stateOrProvince" class="form-label">State/Province</label>
                      <input type="text" class="form-control cleaningbiz-form-control" id="stateOrProvince" name="stateOrProvince" placeholder="NY" required>
                      <div class="cleaningbiz-invalid-feedback">Please enter your state or province.</div>
                    </div>
                    <div class="col-md-4 mb-3">
                      <label for="zipCode" class="form-label">ZIP Code</label>
                      <input type="text" class="form-control cleaningbiz-form-control" id="zipCode" name="zipCode" placeholder="10001" required>
                      <div class="cleaningbiz-invalid-feedback">Please enter your ZIP code.</div>
                    </div>
                  </div>
                  
                  <div class="d-flex justify-content-between mt-4">
                    <button type="button" class="btn cleaningbiz-btn cleaningbiz-btn-secondary prev-step"><i class="fas fa-arrow-left me-2"></i> Previous</button>
                    <button type="button" class="btn cleaningbiz-btn cleaningbiz-btn-primary next-step">Next <i class="fas fa-arrow-right ms-2"></i></button>
                  </div>
                </div>
                
                <!-- Step 3: Service Details -->
                <div class="cleaningbiz-form-step" id="step3">
                  <h5 class="mb-4"><i class="fas fa-broom me-2"></i>Service Details</h5>
                  <div class="row">
                    <div class="col-md-6 mb-3">
                      <label for="cleaningDate" class="form-label">Cleaning Date</label>
                      <input type="date" class="form-control cleaningbiz-form-control" id="cleaningDate" name="cleaningDate" required min="${new Date().toISOString().split('T')[0]}">
                      <div class="cleaningbiz-invalid-feedback">Please select a date.</div>
                    </div>
                    <div class="col-md-6 mb-3">
                      <label for="startTime" class="form-label">Start Time</label>
                      <select class="form-control form-select cleaningbiz-form-control" id="startTime" name="startTime" required>
                        <option value="">Select Time</option>
                        <option value="06:00">6:00 AM</option>
                        <option value="07:00">7:00 AM</option>
                        <option value="08:00">8:00 AM</option>
                        <option value="09:00">9:00 AM</option>
                        <option value="10:00">10:00 AM</option>
                        <option value="11:00">11:00 AM</option>
                        <option value="12:00">12:00 PM</option>
                        <option value="13:00">1:00 PM</option>
                        <option value="14:00">2:00 PM</option>
                        <option value="15:00">3:00 PM</option>
                        <option value="16:00">4:00 PM</option>
                        <option value="17:00">5:00 PM</option>
                        <option value="18:00">6:00 PM</option>
                      </select>
                      <div class="cleaningbiz-invalid-feedback">Please select a time.</div>
                    </div>
                    
                    <!-- Availability Checking UI -->
                    <div class="col-12">
                      <div id="availability-alert" style="display: none;" class="alert mt-2">
                        <div id="availability-message"></div>
                      </div>
                      
                      <!-- Alternative slots suggestion -->
                      <div id="alternative-slots" style="display: none;" class="mt-3">
                        <h6 class="mb-2">Alternative Available Slots:</h6>
                        <div id="alt-slots-list" class="d-flex flex-wrap gap-2 mb-3"></div>
                      </div>
                    </div>
                    
                    <div class="col-md-6 mb-3">
                      <label for="serviceType" class="form-label">Service Type</label>
                      <select class="form-control form-select cleaningbiz-form-control" name="serviceType" id="serviceType" required>
                        <option value="" disabled>Select a service type</option>
                        ${this.renderServiceTypeOptions()}
                      </select>
                      <div class="cleaningbiz-invalid-feedback">Please select a service type.</div>
                    </div>
                    <div class="col-md-6 mb-3">
                      <label for="recurring" class="form-label">Recurring Service</label>
                      <select class="form-control form-select cleaningbiz-form-control" name="recurring" id="recurring">
                        <option value="" disabled>Select frequency</option>
                        <option value="one-time" selected>One Time</option>
                        <option value="weekly">Weekly</option>
                        <option value="biweekly">Bi-weekly</option>
                        <option value="monthly">Monthly</option>
                      </select>
                      <div class="cleaningbiz-invalid-feedback">Please select a frequency.</div>
                    </div>
                  </div>
                  
                  <div class="d-flex justify-content-between mt-4">
                    <button type="button" class="btn cleaningbiz-btn cleaningbiz-btn-secondary prev-step"><i class="fas fa-arrow-left me-2"></i> Previous</button>
                    <button type="button" class="btn cleaningbiz-btn cleaningbiz-btn-primary next-step">Next <i class="fas fa-arrow-right ms-2"></i></button>
                  </div>
                </div>
                
                <!-- Step 4: Property Details -->
                <div class="cleaningbiz-form-step" id="step4">
                  <h5 class="mb-4"><i class="fas fa-home me-2"></i>Property Details</h5>
                  <div class="row">
                    <div class="col-md-4 mb-3">
                      <label for="bedrooms" class="form-label">Number of Bedrooms</label>
                      <input type="number" class="form-control cleaningbiz-form-control property-input" id="bedrooms" name="bedrooms" min="0" placeholder="2" required>
                      <div class="cleaningbiz-invalid-feedback">Please enter the number of bedrooms.</div>
                    </div>
                    <div class="col-md-4 mb-3">
                      <label for="bathrooms" class="form-label">Number of Bathrooms</label>
                      <input type="number" class="form-control cleaningbiz-form-control property-input" id="bathrooms" name="bathrooms" min="0" placeholder="1" required>
                      <div class="cleaningbiz-invalid-feedback">Please enter the number of bathrooms.</div>
                    </div>
                    <div class="col-md-4 mb-3">
                      <label for="squareFeet" class="form-label">Square Footage</label>
                      <input type="number" class="form-control cleaningbiz-form-control property-input" id="squareFeet" name="squareFeet" min="100" placeholder="1000" required>
                      <div class="cleaningbiz-invalid-feedback">Please enter the square footage.</div>
                    </div>
                  </div>
                  
                  <div class="d-flex justify-content-between mt-4">
                    <button type="button" class="btn cleaningbiz-btn cleaningbiz-btn-secondary prev-step"><i class="fas fa-arrow-left me-2"></i> Previous</button>
                    <button type="button" class="btn cleaningbiz-btn cleaningbiz-btn-primary next-step">Next <i class="fas fa-arrow-right ms-2"></i></button>
                  </div>
                </div>
                
                <!-- Step 5: Add-on Services -->
                <div class="cleaningbiz-form-step" id="step5">
                  <h5 class="mb-4"><i class="fas fa-plus me-2"></i>Add-on Services</h5>
                  
                  <!-- Standard Add-ons -->
                  <div class="row" id="standard-addons">
                    ${this.renderStandardAddons()}
                  </div>
                  
                  <!-- Custom Add-ons -->
                  <div class="row" id="custom-addons">
                    ${this.renderCustomAddons()}
                  </div>
                  
                  <!-- Access Information -->
                  <h6 class="mb-3 mt-4"><i class="fas fa-key me-2"></i>Access Information</h6>
                  <div class="mb-3">
                    <label class="form-label">Will someone be home during the cleaning?</label>
                    <div class="form-check">
                      <input class="form-check-input" type="radio" id="someoneHomeYes" name="willSomeoneBeHome" value="yes" checked>
                      <label class="form-check-label" for="someoneHomeYes">
                        Yes, someone will be home
                      </label>
                    </div>
                    <div class="form-check">
                      <input class="form-check-input" type="radio" id="someoneHomeNo" name="willSomeoneBeHome" value="no">
                      <label class="form-check-label" for="someoneHomeNo">
                        I will hide the keys
                      </label>
                    </div>
                  </div>
                  <div class="mb-3" id="keyLocationContainer" style="display: none;">
                    <label for="keyLocation" class="form-label">Where will the keys be hidden? <span class="text-danger">*</span></label>
                    <input type="text" class="form-control cleaningbiz-form-control" id="keyLocation" name="keyLocation" placeholder="e.g., Under the mat, Code: 1234, etc.">
                    <small class="form-text text-muted">Please provide the key code or location where the key is hidden</small>
                  </div>
                  
                  <!-- Additional Information -->
                  <h6 class="mb-3 mt-4"><i class="fas fa-info-circle me-2"></i>Special Requests</h6>
                  <div class="mb-3">
                    <textarea class="form-control cleaningbiz-form-control" id="otherRequests" name="otherRequests" rows="3" placeholder="Any special requests or notes?"></textarea>
                  </div>
                  
                  <div class="d-flex justify-content-between mt-4">
                    <button type="button" class="btn cleaningbiz-btn cleaningbiz-btn-secondary prev-step"><i class="fas fa-arrow-left me-2"></i> Previous</button>
                    <button type="submit" class="btn cleaningbiz-btn cleaningbiz-btn-primary" id="submitBookingBtn">
                      <i class="fas fa-check me-2"></i>Submit Booking
                    </button>
                  </div>
                </div>
                
                <div id="form-messages"></div>
              </form>
            </div>
          </div>
        </div>
        
        <!-- Right Column - Booking Summary -->
        <div class="col-lg-4">
          <div class="cleaningbiz-card cleaningbiz-overview-card">
            <div class="cleaningbiz-card-header">
              <h5 class="mb-0"><i class="fas fa-receipt me-2"></i>Service Overview</h5>
            </div>
            <div class="cleaningbiz-card-body">
              <!-- Business Info -->
              <div class="cleaningbiz-overview-section mb-4">
                <h6 class="text-muted mb-3">Selected Business</h6>
                <div class="d-flex align-items-center mb-2">
                  <div class="flex-shrink-0">
                    <div class="bg-light rounded-circle p-2">
                      <i class="fas fa-building text-primary"></i>
                    </div>
                  </div>
                  <div class="ms-3">
                    <h6 class="mb-0">${this.businessData.business.businessName}</h6>
                    <p class="text-muted small mb-0">${this.businessData.business.address}</p>
                  </div>
                </div>
              </div>
              
              <!-- Service Details -->
              <div class="cleaningbiz-overview-section mb-4">
                <h6 class="text-muted mb-3">Service Details</h6>
                <div class="mb-2">
                  <div class="d-flex justify-content-between">
                    <span>Service Type:</span>
                    <span class="fw-medium" id="overview-service">-</span>
                  </div>
                </div>
                <div class="mb-2">
                  <div class="d-flex justify-content-between">
                    <span>Date & Time:</span>
                    <span class="fw-medium" id="overview-datetime">-</span>
                  </div>
                </div>
                <div class="mb-2">
                  <div class="d-flex justify-content-between">
                    <span>Bedrooms:</span>
                    <span class="fw-medium" id="overview-bedrooms">-</span>
                  </div>
                </div>
                <div class="mb-2">
                  <div class="d-flex justify-content-between">
                    <span>Bathrooms:</span>
                    <span class="fw-medium" id="overview-bathrooms">-</span>
                  </div>
                </div>
                <div class="mb-2">
                  <div class="d-flex justify-content-between">
                    <span>Square Feet:</span>
                    <span class="fw-medium" id="overview-squarefeet">-</span>
                  </div>
                </div>
              </div>
              
              <!-- Add-ons Summary -->
              <div class="cleaningbiz-overview-section mb-4">
                <h6 class="text-muted mb-3">Add-ons</h6>
                <div id="overview-addons-list">
                  <p class="text-muted small">No add-ons selected</p>
                </div>
              </div>
              
              <!-- Coupon Code Section -->
              <div class="cleaningbiz-coupon-section mb-3 p-3" style="background-color: #f8f9fa; border-radius: 8px;">
                <h6 class="mb-3"><i class="fas fa-ticket-alt me-2"></i>Have a Coupon?</h6>
                <div class="input-group mb-2">
                  <input type="text" class="form-control text-uppercase" id="couponCode" 
                         placeholder="Enter coupon code" maxlength="50" style="text-transform: uppercase;">
                  <button class="btn btn-outline-primary" type="button" id="applyCouponBtn">
                    Apply
                  </button>
                </div>
                <div id="coupon-message" class="small mt-2" style="display: none;"></div>
              </div>
              
              <!-- Pricing Summary -->
              <div class="cleaningbiz-price-summary">
                <h6 class="mb-3">Price Summary</h6>
                <div class="cleaningbiz-price-row">
                  <span>Base Price:</span>
                  <span class="fw-medium">$<span id="overview-base-price">0.00</span></span>
                </div>
                <div class="cleaningbiz-price-row">
                  <span>Add-ons:</span>
                  <span class="fw-medium">$<span id="overview-addons-price">0.00</span></span>
                </div>
                <div class="cleaningbiz-price-row">
                  <span>Subtotal:</span>
                  <span class="fw-medium">$<span id="overview-subtotal">0.00</span></span>
                </div>
                <div id="discount-row" class="cleaningbiz-price-row text-success" style="display: none;">
                  <span>Discount (<span id="overview-discount-percent">0</span>%):</span>
                  <span class="fw-medium">-$<span id="overview-discount">0.00</span></span>
                </div>
                <div id="coupon-discount-row" class="cleaningbiz-price-row text-success" style="display: none;">
                  <span>Coupon (<span id="overview-coupon-code"></span>):</span>
                  <span class="fw-medium">-$<span id="overview-coupon-discount">0.00</span></span>
                </div>
                <div class="cleaningbiz-price-row">
                  <span>Tax (<span id="tax-percentage">${this.businessData.prices.tax_percent || this.businessData.prices.taxPercent || this.businessData.prices.tax || 0}</span>%):</span>
                  <span class="fw-medium">$<span id="overview-tax">0.00</span></span>
                </div>
                <div class="cleaningbiz-price-row cleaningbiz-price-total">
                  <span class="fw-bold">Total:</span>
                  <span class="fw-bold text-primary">$<span id="overview-total">0.00</span></span>
                </div>
                
                <!-- Terms and Submit Button -->
                <div class="mt-4">
                  <div class="form-check mb-3">
                    <input class="form-check-input" type="checkbox" id="termsCheck" required>
                    <label class="form-check-label small" for="termsCheck">
                      I agree to the <a href="#" class="text-decoration-none">Terms of Service</a> and <a href="#" class="text-decoration-none">Privacy Policy</a>
                    </label>
                  </div>
                  <button type="submit" class="btn cleaningbiz-btn cleaningbiz-btn-primary w-100" id="rightColumnSubmitBtn" form="cleaningbiz-booking-form">
                    <i class="fas fa-check me-2"></i>Confirm Booking
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
    
    targetElement.appendChild(this.formElement);
  }

  renderServiceTypeOptions() {
    const prices = this.businessData.prices;
    let options = '';
    
    if (prices.sqftMultiplierStandard > 0) {
      options += '<option value="standard">Standard Cleaning</option>';
    }
    if (prices.sqftMultiplierDeep > 0) {
      options += '<option value="deep">Deep Cleaning</option>';
    }
    if (prices.sqftMultiplierMoveinout > 0) {
      options += '<option value="moveinout">Move In/Out Cleaning</option>';
    }
    if (prices.sqftMultiplierAirbnb > 0) {
      options += '<option value="airbnb">Airbnb Cleaning</option>';
    }
    
    return options || '<option value="standard">Standard Cleaning</option>';
  }

  renderStandardAddons() {
    const prices = this.businessData.prices;
    let addonsHtml = '';
    
    const addons = [
      { id: 'addonDishes', name: 'Dishes', price: prices.addonPriceDishes },
      { id: 'addonLaundryLoads', name: 'Laundry Loads', price: prices.addonPriceLaundry },
      { id: 'addonWindowCleaning', name: 'Window Cleaning', price: prices.addonPriceWindow },
      { id: 'addonPetsCleaning', name: 'Pets Cleaning', price: prices.addonPricePets },
      { id: 'addonFridgeCleaning', name: 'Fridge Cleaning', price: prices.addonPriceFridge },
      { id: 'addonOvenCleaning', name: 'Oven Cleaning', price: prices.addonPriceOven },
      { id: 'addonBaseboard', name: 'Baseboard', price: prices.addonPriceBaseboard },
      { id: 'addonBlinds', name: 'Blinds', price: prices.addonPriceBlinds }
    ];
    
    // Group addons into pairs for the grid layout
    for (let i = 0; i < addons.length; i += 2) {
      if (addons[i] && addons[i].price > 0) {
        addonsHtml += '<div class="col-md-6 mb-3">';
        addonsHtml += `
          <div class="cleaningbiz-addon-item">
            <label for="${addons[i].id}">${addons[i].name} <small class="text-muted">($${addons[i].price.toFixed(2)} each)</small></label>
            <input type="number" class="form-control cleaningbiz-form-control" id="${addons[i].id}" name="${addons[i].id}" min="0" value="0" data-price="${addons[i].price}">
          </div>
        `;
        addonsHtml += '</div>';
      }
      
      if (addons[i+1] && addons[i+1].price > 0) {
        addonsHtml += '<div class="col-md-6 mb-3">';
        addonsHtml += `
          <div class="cleaningbiz-addon-item">
            <label for="${addons[i+1].id}">${addons[i+1].name} <small class="text-muted">($${addons[i+1].price.toFixed(2)} each)</small></label>
            <input type="number" class="form-control cleaningbiz-form-control" id="${addons[i+1].id}" name="${addons[i+1].id}" min="0" value="0" data-price="${addons[i+1].price}">
          </div>
        `;
        addonsHtml += '</div>';
      }
    }
    
    return addonsHtml || '<div class="col-12"><p class="text-muted">No standard add-ons available</p></div>';
  }

  renderCustomAddons() {
    const customAddons = this.businessData.customAddons || [];
    let addonsHtml = '';
    
    if (customAddons.length > 0) {
      addonsHtml += '<h6 class="mb-3 mt-4"><i class="fas fa-star me-2"></i>Custom Add-ons</h6>';
      
      // Group custom addons into pairs for the grid layout
      for (let i = 0; i < customAddons.length; i += 2) {
        if (customAddons[i]) {
          addonsHtml += '<div class="col-md-6 mb-3">';
          addonsHtml += `
            <div class="cleaningbiz-addon-item">
              <label for="custom_addon_qty_${customAddons[i].id}">${customAddons[i].addonName} <small class="text-muted">($${customAddons[i].addonPrice.toFixed(2)} each)</small></label>
              <input type="number" class="form-control cleaningbiz-form-control" id="custom_addon_qty_${customAddons[i].id}" name="custom_addon_qty_${customAddons[i].id}" min="0" value="0" data-price="${customAddons[i].addonPrice}">
            </div>
          `;
          addonsHtml += '</div>';
        }
        
        if (customAddons[i+1]) {
          addonsHtml += '<div class="col-md-6 mb-3">';
          addonsHtml += `
            <div class="cleaningbiz-addon-item">
              <label for="custom_addon_qty_${customAddons[i+1].id}">${customAddons[i+1].addonName} <small class="text-muted">($${customAddons[i+1].addonPrice.toFixed(2)} each)</small></label>
              <input type="number" class="form-control cleaningbiz-form-control" id="custom_addon_qty_${customAddons[i+1].id}" name="custom_addon_qty_${customAddons[i+1].id}" min="0" value="0" data-price="${customAddons[i+1].addonPrice}">
            </div>
          `;
          addonsHtml += '</div>';
        }
      }
    }
    
    return addonsHtml;
  }

  setupEventListeners() {
    const form = document.getElementById('cleaningbiz-booking-form');
    
    // Multi-step form navigation
    this.setupMultiStepForm();
    
    // Add event listeners for price calculation
    const priceInputs = [
      'bedrooms', 'bathrooms', 'squareFeet', 'serviceType', 'recurring',
      'addonDishes', 'addonLaundryLoads', 'addonWindowCleaning',
      'addonPetsCleaning', 'addonFridgeCleaning', 'addonOvenCleaning',
      'addonBaseboard', 'addonBlinds'
    ];
    
    priceInputs.forEach(inputId => {
      const element = document.getElementById(inputId);
      if (element) {
        element.addEventListener('change', () => this.calculatePrice());
        element.addEventListener('input', () => this.calculatePrice());
      }
    });
    
    // Add event listeners for custom addons
    const customAddons = this.businessData.customAddons || [];
    customAddons.forEach(addon => {
      const element = document.getElementById(`custom_addon_qty_${addon.id}`);
      if (element) {
        element.addEventListener('change', () => this.calculatePrice());
        element.addEventListener('input', () => this.calculatePrice());
      }
    });
    
    // Date and time inputs for overview update and availability check
    const dateInput = document.getElementById('cleaningDate');
    const timeInput = document.getElementById('startTime');
    if (dateInput && timeInput) {
      dateInput.addEventListener('change', () => {
        this.updateOverview();
        if (dateInput.value && timeInput.value) {
          this.checkAvailability(dateInput.value, timeInput.value);
        }
      });
      
      timeInput.addEventListener('change', () => {
        this.updateOverview();
        if (dateInput.value && timeInput.value) {
          this.checkAvailability(dateInput.value, timeInput.value);
        }
      });
    }
    
    // Access information toggle
    const someoneHomeYes = document.getElementById('someoneHomeYes');
    const someoneHomeNo = document.getElementById('someoneHomeNo');
    const keyLocationContainer = document.getElementById('keyLocationContainer');
    const keyLocationInput = document.getElementById('keyLocation');
    
    const toggleKeyLocation = () => {
      if (someoneHomeNo && someoneHomeNo.checked) {
        keyLocationContainer.style.display = 'block';
        keyLocationInput.required = true;
      } else {
        keyLocationContainer.style.display = 'none';
        keyLocationInput.required = false;
        keyLocationInput.value = '';
      }
    };
    
    if (someoneHomeYes && someoneHomeNo) {
      someoneHomeYes.addEventListener('change', toggleKeyLocation);
      someoneHomeNo.addEventListener('change', toggleKeyLocation);
    }
    
    // Phone number formatting
    const phoneInput = document.getElementById('phoneNumber');
    if (phoneInput) {
      phoneInput.addEventListener('input', function(e) {
        // Remove all non-digit characters
        let value = this.value.replace(/\D/g, '');
        
        // Format with spaces (North American format: XXX XXX XXXX)
        if (value.length > 0) {
          // Area code (first 3 digits)
          let formattedNumber = value.substring(0, 3);
          
          // First part of local number (next 3 digits)
          if (value.length > 3) {
            formattedNumber += ' ' + value.substring(3, 6);
          }
          
          // Second part of local number (next 4 digits)
          if (value.length > 6) {
            formattedNumber += ' ' + value.substring(6, 10);
          }
          
          this.value = formattedNumber;
        }
      });
    }
    
    // Coupon code functionality
    const couponCodeInput = document.getElementById('couponCode');
    const applyCouponBtn = document.getElementById('applyCouponBtn');
    const couponMessage = document.getElementById('coupon-message');
    
    if (couponCodeInput) {
      // Auto-uppercase coupon code
      couponCodeInput.addEventListener('input', function() {
        this.value = this.value.toUpperCase();
      });
    }
    
    if (applyCouponBtn) {
      applyCouponBtn.addEventListener('click', async () => {
        const couponCode = couponCodeInput?.value?.trim();
        
        if (!couponCode) {
          this.showCouponMessage('Please enter a coupon code', 'error');
          return;
        }
        
        // Show loading state
        applyCouponBtn.disabled = true;
        applyCouponBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Validating...';
        
        // Validate coupon
        const result = await this.validateCoupon(couponCode);
        
        // Reset button
        applyCouponBtn.disabled = false;
        applyCouponBtn.innerHTML = 'Apply';
        
        if (result.success) {
          // Show success message
          this.showCouponMessage(result.message + ' - ' + result.coupon.description, 'success');
          
          // Disable input and change button to remove
          couponCodeInput.disabled = true;
          applyCouponBtn.innerHTML = '<i class="fas fa-times"></i>';
          applyCouponBtn.onclick = () => {
            this.removeCoupon();
            couponCodeInput.value = '';
            couponCodeInput.disabled = false;
            applyCouponBtn.innerHTML = 'Apply';
            applyCouponBtn.onclick = null;
            if (couponMessage) couponMessage.style.display = 'none';
          };
        } else {
          // Show error message
          this.showCouponMessage(result.message, 'error');
        }
      });
    }
    
    // Form submission from both buttons
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      if (this.validateForm()) {
        this.submitForm();
      }
    });
    
    const rightColumnSubmitBtn = document.getElementById('rightColumnSubmitBtn');
    if (rightColumnSubmitBtn) {
      rightColumnSubmitBtn.addEventListener('click', (e) => {
        e.preventDefault();
        if (this.validateForm()) {
          this.submitForm();
        } else {
          // Show the step with errors
          const formSteps = document.querySelectorAll('.cleaningbiz-form-step');
          for (let i = 0; i < formSteps.length; i++) {
            const step = formSteps[i];
            const requiredFields = step.querySelectorAll('[required]');
            let hasError = false;
            
            requiredFields.forEach(field => {
              if (!field.value) {
                hasError = true;
              }
            });
            
            if (hasError) {
              this.goToStep(i);
              break;
            }
          }
        }
      });
    }
    
    // Terms checkbox validation
    const termsCheck = document.getElementById('termsCheck');
    if (termsCheck) {
      termsCheck.addEventListener('change', function() {
        const submitBtn = document.getElementById('rightColumnSubmitBtn');
        if (submitBtn) {
          submitBtn.disabled = !this.checked;
        }
      });
      
      // Initialize button state
      const submitBtn = document.getElementById('rightColumnSubmitBtn');
      if (submitBtn) {
        submitBtn.disabled = !termsCheck.checked;
      }
    }
    
    // No need for initial calculations here, they're now in initializeFormValues()
  }
  
  setupMultiStepForm() {
    // Get form elements
    const formSteps = document.querySelectorAll('.cleaningbiz-form-step');
    const nextButtons = document.querySelectorAll('.next-step');
    const prevButtons = document.querySelectorAll('.prev-step');
    const progressBar = document.getElementById('form-progress');
    const stepIndicators = document.querySelectorAll('.cleaningbiz-step-indicator');
    
    // Current step tracker
    this.currentStep = 0;
    
    // Next button click handler
    nextButtons.forEach((button, index) => {
      button.addEventListener('click', async () => {
        if (this.validateStep(this.currentStep)) {
          // If moving from step 1 (customer info), check for existing customer
          if (this.currentStep === 0) {
            await this.checkExistingCustomer();
          }
          this.goToStep(this.currentStep + 1);
        }
      });
    });
    
    // Previous button click handler
    prevButtons.forEach(button => {
      button.addEventListener('click', () => {
        this.goToStep(this.currentStep - 1);
      });
    });
  }
  
  goToStep(stepIndex) {
    const formSteps = document.querySelectorAll('.cleaningbiz-form-step');
    const stepIndicators = document.querySelectorAll('.cleaningbiz-step-indicator');
    const progressBar = document.getElementById('form-progress');
    
    // Validate step index
    if (stepIndex < 0 || stepIndex >= formSteps.length) {
      return;
    }
    
    // Hide current step
    formSteps[this.currentStep].classList.remove('active');
    
    // Show new step
    this.currentStep = stepIndex;
    formSteps[this.currentStep].classList.add('active');
    
    // Update progress bar
    const progress = ((this.currentStep + 1) / formSteps.length) * 100;
    progressBar.style.width = progress + '%';
    progressBar.setAttribute('aria-valuenow', progress);
    progressBar.textContent = Math.round(progress) + '%';
    
    // Update step indicators
    stepIndicators.forEach((indicator, index) => {
      if (index === this.currentStep) {
        indicator.classList.add('active');
        indicator.classList.remove('completed');
      } else if (index < this.currentStep) {
        indicator.classList.add('completed');
        indicator.classList.remove('active');
      } else {
        indicator.classList.remove('active', 'completed');
      }
    });
    
    // Scroll to top of form
    const formContainer = document.querySelector('.cleaningbiz-card-body');
    if (formContainer) {
      formContainer.scrollTop = 0;
    }
  }
  
  validateStep(stepIndex) {
    const formSteps = document.querySelectorAll('.cleaningbiz-form-step');
    const currentStepEl = formSteps[stepIndex];
    const requiredFields = currentStepEl.querySelectorAll('[required]');
    let isValid = true;
    
    requiredFields.forEach(field => {
      if (!field.value) {
        isValid = false;
        field.classList.add('is-invalid');
      } else {
        field.classList.remove('is-invalid');
      }
    });
    
    return isValid;
  }
  
  validateForm() {
    const formSteps = document.querySelectorAll('.cleaningbiz-form-step');
    let isValid = true;
    
    // Validate all steps
    for (let i = 0; i < formSteps.length; i++) {
      const step = formSteps[i];
      const requiredFields = step.querySelectorAll('[required]');
      
      requiredFields.forEach(field => {
        if (!field.value) {
          isValid = false;
          field.classList.add('is-invalid');
        } else {
          field.classList.remove('is-invalid');
        }
      });
    }
    
    // Validate terms checkbox
    const termsCheck = document.getElementById('termsCheck');
    if (termsCheck && !termsCheck.checked) {
      isValid = false;
      termsCheck.classList.add('is-invalid');
    } else if (termsCheck) {
      termsCheck.classList.remove('is-invalid');
    }
    
    return isValid;
  }

  calculatePrice() {
    // Use custom pricing if available, otherwise use business default pricing
    const prices = this.customerPricing || this.businessData.prices;
    const usingCustomPricing = !!this.customerPricing;
    
    console.log('Calculating price with:', usingCustomPricing ? 'CUSTOM PRICING' : 'DEFAULT PRICING');
    console.log('Pricing data:', prices);
    
    const serviceTypeEl = document.getElementById('serviceType');
    if (!serviceTypeEl) return; // Exit if elements don't exist yet
    
    const serviceType = serviceTypeEl.value;
    const bedroomsEl = document.getElementById('bedrooms');
    const bathroomsEl = document.getElementById('bathrooms');
    const squareFeetEl = document.getElementById('squareFeet');
    
    if (!bedroomsEl || !bathroomsEl || !squareFeetEl) return;
    
    const bedrooms = parseInt(bedroomsEl.value) || 0;
    const bathrooms = parseInt(bathroomsEl.value) || 0;
    const squareFeet = parseInt(squareFeetEl.value) || 0;
    
    // Calculate base price
    let basePrice = prices.base_price || 0;
    const bedroomPrice = prices.bedroom_price || prices.bedrooms || 0;
    const bathroomPrice = prices.bathroom_price || prices.bathrooms || 0;
    
    basePrice += bedrooms * bedroomPrice;
    basePrice += bathrooms * bathroomPrice;
    
    console.log(`Base: $${prices.base_price}, Bedrooms: ${bedrooms} x $${bedroomPrice}, Bathrooms: ${bathrooms} x $${bathroomPrice}`);
    
    // Apply square feet multiplier based on service type
    let sqftMultiplier = 0;
    let serviceTypeName = 'Standard Cleaning';
    switch (serviceType) {
      case 'standard':
        sqftMultiplier = prices.sqft_multiplier_standard || prices.sqftMultiplierStandard;
        serviceTypeName = 'Standard Cleaning';
        break;
      case 'deep':
        sqftMultiplier = prices.sqft_multiplier_deep || prices.sqftMultiplierDeep;
        serviceTypeName = 'Deep Cleaning';
        break;
      case 'moveinout':
        sqftMultiplier = prices.sqft_multiplier_moveinout || prices.sqftMultiplierMoveinout;
        serviceTypeName = 'Move In/Out Cleaning';
        break;
      case 'airbnb':
        sqftMultiplier = prices.sqft_multiplier_airbnb || prices.sqftMultiplierAirbnb;
        serviceTypeName = 'Airbnb Cleaning';
        break;
    }
    
    basePrice += squareFeet * sqftMultiplier;
    
    // Calculate addons price
    let addonsPrice = 0;
    
    // Standard addons - support both custom and default pricing formats
    const standardAddons = [
      { id: 'addonDishes', name: 'Dishes', price: prices.addon_price_dishes || prices.addonPriceDishes },
      { id: 'addonLaundryLoads', name: 'Laundry Loads', price: prices.addon_price_laundry || prices.addonPriceLaundry },
      { id: 'addonWindowCleaning', name: 'Window Cleaning', price: prices.addon_price_window || prices.addonPriceWindow },
      { id: 'addonPetsCleaning', name: 'Pets Cleaning', price: prices.addon_price_pets || prices.addonPricePets },
      { id: 'addonFridgeCleaning', name: 'Fridge Cleaning', price: prices.addon_price_fridge || prices.addonPriceFridge },
      { id: 'addonOvenCleaning', name: 'Oven Cleaning', price: prices.addon_price_oven || prices.addonPriceOven },
      { id: 'addonBaseboard', name: 'Baseboard', price: prices.addon_price_baseboard || prices.addonPriceBaseboard },
      { id: 'addonBlinds', name: 'Blinds', price: prices.addon_price_blinds || prices.addonPriceBlinds }
    ];
    
    // Clear addons list in overview
    const addonsList = document.getElementById('overview-addons-list');
    if (!addonsList) return; // Exit if element doesn't exist
    
    addonsList.innerHTML = '';
    
    let hasAddons = false;
    
    // Process standard addons
    standardAddons.forEach(addon => {
      const element = document.getElementById(addon.id);
      if (element) {
        const quantity = parseInt(element.value) || 0;
        if (quantity > 0) {
          hasAddons = true;
          addonsPrice += quantity * addon.price;
          
          // Add to overview
          const addonItem = document.createElement('div');
          addonItem.className = 'd-flex justify-content-between mb-1';
          addonItem.innerHTML = `
            <span class="small">${addon.name} (${quantity})</span>
            <span class="small">$${(quantity * addon.price).toFixed(2)}</span>
          `;
          addonsList.appendChild(addonItem);
        }
      }
    });
    
    // Custom addons
    const customAddons = this.businessData.customAddons || [];
    customAddons.forEach(addon => {
      const element = document.getElementById(`custom_addon_qty_${addon.id}`);
      if (element) {
        const quantity = parseInt(element.value) || 0;
        if (quantity > 0) {
          hasAddons = true;
          // Check if custom pricing has a price for this addon
          let addonPrice = addon.addonPrice;
          if (this.customerPricing && this.customerPricing.custom_addons && this.customerPricing.custom_addons[addon.id]) {
            addonPrice = this.customerPricing.custom_addons[addon.id].price;
          }
          addonsPrice += quantity * addonPrice;
          
          // Add to overview
          const addonItem = document.createElement('div');
          addonItem.className = 'd-flex justify-content-between mb-1';
          addonItem.innerHTML = `
            <span class="small">${addon.addonName} (${quantity})</span>
            <span class="small">$${(quantity * addonPrice).toFixed(2)}</span>
          `;
          addonsList.appendChild(addonItem);
        }
      }
    });
    
    // If no addons selected, show message
    if (!hasAddons) {
      addonsList.innerHTML = '<p class="text-muted small">No add-ons selected</p>';
    }
    
    // Calculate subtotal before discount and coupon
    let subtotalBeforeDiscount = basePrice + addonsPrice;
    
    // Calculate discount based on recurring option
    const recurringTypeEl = document.getElementById('recurring');
    let discountPercent = 0;
    
    if (recurringTypeEl) {
      const recurringType = recurringTypeEl.value;
      if (recurringType === 'weekly') {
        discountPercent = prices.weekly_discount || prices.weeklyDiscount || 0;
      } else if (recurringType === 'biweekly') {
        discountPercent = prices.biweekly_discount || prices.biweeklyDiscount || 0;
      } else if (recurringType === 'monthly') {
        discountPercent = prices.monthly_discount || prices.monthlyDiscount || 0;
      }
    }
    
    const discountAmount = subtotalBeforeDiscount * (discountPercent / 100);
    let subtotal = subtotalBeforeDiscount - discountAmount;
    
    // Apply coupon discount if available
    const couponDiscount = this.couponDiscountAmount || 0;
    subtotal = subtotal - couponDiscount;
    
    // Calculate tax on discounted subtotal
    const taxPercent = prices.tax_percent || prices.taxPercent || prices.tax || 0;
    const taxRate = taxPercent / 100;
    const taxAmount = subtotal * taxRate;
    const total = subtotal + taxAmount;
    
    console.log(`Subtotal: $${subtotal}, Tax: ${taxPercent}%, Tax Amount: $${taxAmount}, Total: $${total}`);
    
    // Update the price display in the price summary section - with null checks
    this.safeSetTextContent('base-price', `$${basePrice.toFixed(2)}`);
    this.safeSetTextContent('addons-price', `$${addonsPrice.toFixed(2)}`);
    this.safeSetTextContent('subtotal', `$${subtotal.toFixed(2)}`);
    this.safeSetTextContent('tax-amount', `$${taxAmount.toFixed(2)}`);
    this.safeSetTextContent('total-price', `$${total.toFixed(2)}`);
    
    // Update the overview section - with null checks
    this.safeSetTextContent('overview-service', serviceTypeName);
    this.safeSetTextContent('overview-bedrooms', bedrooms);
    this.safeSetTextContent('overview-bathrooms', bathrooms);
    this.safeSetTextContent('overview-squarefeet', squareFeet + ' sq ft');
    
    // Update overview price summary - with null checks
    this.safeSetTextContent('overview-base-price', basePrice.toFixed(2));
    this.safeSetTextContent('overview-addons-price', addonsPrice.toFixed(2));
    this.safeSetTextContent('overview-subtotal', subtotalBeforeDiscount.toFixed(2));
    
    // Show/hide discount row
    const discountRow = document.getElementById('discount-row');
    if (discountPercent > 0) {
      if (discountRow) {
        discountRow.style.display = 'flex';
        this.safeSetTextContent('overview-discount-percent', discountPercent);
        this.safeSetTextContent('overview-discount', discountAmount.toFixed(2));
      }
    } else {
      if (discountRow) {
        discountRow.style.display = 'none';
      }
    }
    
    // Show/hide coupon discount row
    const couponDiscountRow = document.getElementById('coupon-discount-row');
    if (couponDiscount > 0 && this.appliedCoupon) {
      if (couponDiscountRow) {
        couponDiscountRow.style.display = 'flex';
        this.safeSetTextContent('overview-coupon-code', this.appliedCoupon.code);
        this.safeSetTextContent('overview-coupon-discount', couponDiscount.toFixed(2));
      }
    } else {
      if (couponDiscountRow) {
        couponDiscountRow.style.display = 'none';
      }
    }
    
    this.safeSetTextContent('overview-tax', taxAmount.toFixed(2));
    this.safeSetTextContent('overview-total', total.toFixed(2));
    
    // Add custom pricing badge to total if using custom pricing
    const totalElement = document.getElementById('overview-total');
    if (totalElement && this.customerPricing && this.customerPricing.is_custom_pricing) {
      const parentSpan = totalElement.parentElement;
      if (parentSpan && !parentSpan.querySelector('.custom-pricing-badge')) {
        const badge = document.createElement('span');
        badge.className = 'custom-pricing-badge badge bg-success ms-2';
        badge.style.cssText = 'font-size: 0.7rem; vertical-align: middle;';
        badge.innerHTML = '<i class="fas fa-star"></i> Special Rate';
        parentSpan.appendChild(badge);
      }
    }
    
    // Update hidden fields - with null checks
    this.safeSetValue('totalAmount', total.toFixed(2));
    this.safeSetValue('tax', taxAmount.toFixed(2));
    this.safeSetValue('appliedDiscountPercent', discountPercent.toFixed(2));
    this.safeSetValue('discountAmount', discountAmount.toFixed(2));
  }
  
  // Helper method to safely set text content with null check
  safeSetTextContent(elementId, value) {
    const element = document.getElementById(elementId);
    if (element) {
      element.textContent = value;
    }
  }
  
  // Helper method to safely set value with null check
  safeSetValue(elementId, value) {
    const element = document.getElementById(elementId);
    if (element) {
      element.value = value;
    }
  }
  
  updateOverview() {
    // Update date and time in overview
    const dateEl = document.getElementById('cleaningDate');
    const timeEl = document.getElementById('startTime');
    const overviewDatetimeEl = document.getElementById('overview-datetime');
    
    // Exit if elements don't exist yet
    if (!dateEl || !timeEl || !overviewDatetimeEl) return;
    
    const cleaningDate = dateEl.value;
    const startTime = timeEl.value;
    
    if (cleaningDate && startTime) {
      try {
        // Create a date object from the date and time
        const dateObj = new Date(`${cleaningDate}T${startTime}`);
        
        // Format the date and time
        const options = { 
          weekday: 'long', 
          year: 'numeric', 
          month: 'long', 
          day: 'numeric', 
          hour: 'numeric', 
          minute: 'numeric' 
        };
        
        const formattedDateTime = dateObj.toLocaleDateString('en-US', options);
        overviewDatetimeEl.textContent = formattedDateTime;
      } catch (error) {
        console.error('Error formatting date and time:', error);
        overviewDatetimeEl.textContent = `${cleaningDate} at ${this.formatTime(startTime)}`;
      }
    } else {
      overviewDatetimeEl.textContent = '-';
    }
  }
  
  formatTime(time24h) {
    // Convert 24-hour time format to 12-hour format
    if (!time24h) return '';
    
    const [hours, minutes] = time24h.split(':');
    const hour = parseInt(hours, 10);
    const ampm = hour >= 12 ? 'PM' : 'AM';
    const hour12 = hour % 12 || 12;
    
    return `${hour12}:${minutes} ${ampm}`;
  }
  
  async checkAvailability(date, time) {
    // Get UI elements
    const availabilityAlert = document.getElementById('availability-alert');
    const availabilityMessage = document.getElementById('availability-message');
    const alternativeSlots = document.getElementById('alternative-slots');
    const altSlotsList = document.getElementById('alt-slots-list');
    
    // Exit if elements don't exist
    if (!availabilityAlert || !availabilityMessage || !alternativeSlots || !altSlotsList) {
      console.error('Availability UI elements not found');
      return;
    }
    
    // Show loading state
    availabilityAlert.style.display = 'block';
    availabilityAlert.className = 'alert alert-info mt-2';
    availabilityMessage.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i> Checking availability...';
    
    try {
      // Get timezone from browser
      const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
      
      // Make API request
      const url = `${this.options.apiBaseUrl}/api/check-availability/?date=${date}&time=${time}&timezone=${encodeURIComponent(timezone)}&businessId=${this.options.businessId}`;
      
      const response = await fetch(url);
      const data = await response.json();
      
      if (data.available) {
        // Show success message
        availabilityAlert.className = 'alert alert-success mt-2';
        availabilityMessage.innerHTML = '<i class="fas fa-check-circle me-2"></i> This timeslot is available!';
        
        // Hide alternative slots
        alternativeSlots.style.display = 'none';
        
        // Hide the alert after 5 seconds
        setTimeout(() => {
          availabilityAlert.style.display = 'none';
        }, 5000);
      } else {
        // Show error message
        availabilityAlert.className = 'alert alert-danger mt-2';
        availabilityMessage.innerHTML = '<i class="fas fa-exclamation-triangle me-2"></i> This timeslot is not available.';
        
        // Show alternative slots if any
        if (data.alternative_slots && data.alternative_slots.length > 0) {
          alternativeSlots.style.display = 'block';
          altSlotsList.innerHTML = '';
          
          data.alternative_slots.forEach(slot => {
            // Parse the slot string to get date and time
            const slotParts = slot.split(' ');
            const slotDate = slotParts[0];
            const slotTime = slotParts[1] + ' ' + slotParts[2]; // e.g., "09:00 AM"
            
            // Create a button for each alternative slot
            const slotButton = document.createElement('button');
            slotButton.className = 'btn btn-outline-primary btn-sm me-2 mb-2';
            slotButton.innerHTML = `<i class="fas fa-calendar-check me-1"></i> ${slotTime} on ${this.formatDate(slotDate)}`;
            slotButton.type = 'button';
            slotButton.addEventListener('click', () => {
              // Set the form fields to this slot
              const dateInput = document.getElementById('cleaningDate');
              const timeInput = document.getElementById('startTime');
              
              if (dateInput && timeInput) {
                dateInput.value = slotDate;
                
                // Convert 12-hour format to 24-hour format for the select
                const timeValue = this.convert12to24(slotTime);
                timeInput.value = timeValue;
                
                // Trigger change events
                dateInput.dispatchEvent(new Event('change'));
                timeInput.dispatchEvent(new Event('change'));
              }
            });
            
            altSlotsList.appendChild(slotButton);
          });
        } else {
          alternativeSlots.style.display = 'none';
        }
      }
    } catch (error) {
      console.error('Error checking availability:', error);
      availabilityAlert.className = 'alert alert-warning mt-2';
      availabilityMessage.innerHTML = '<i class="fas fa-exclamation-circle me-2"></i> Could not check availability. Please try again.';
    }
  }
  
  formatDate(dateStr) {
    // Format date nicely (e.g., "Mon, Sep 10")
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
  }
  
  convert12to24(time12h) {
    // Convert 12-hour time format (e.g., "9:00 AM") to 24-hour format (e.g., "09:00")
    const [timePart, modifier] = time12h.split(' ');
    let [hours, minutes] = timePart.split(':');
    
    hours = parseInt(hours, 10);
    
    if (hours === 12) {
      hours = modifier === 'PM' ? 12 : 0;
    } else if (modifier === 'PM') {
      hours += 12;
    }
    
    return `${hours.toString().padStart(2, '0')}:${minutes}`;
  }

  async submitForm() {
    const form = document.getElementById('cleaningbiz-booking-form');
    const formData = new FormData(form);
    const formMessages = document.getElementById('form-messages');
    
    // Show loading state
    formMessages.innerHTML = `
      <div class="alert alert-info mt-3">
        <div class="d-flex align-items-center">
          <div class="spinner-border spinner-border-sm me-2" role="status">
            <span class="visually-hidden">Loading...</span>
          </div>
          <span>Processing your booking request...</span>
        </div>
      </div>
    `;
    
    // Disable submit buttons
    const submitBtn = document.getElementById('submitBookingBtn');
    const rightColumnSubmitBtn = document.getElementById('rightColumnSubmitBtn');
    if (submitBtn) submitBtn.disabled = true;
    if (rightColumnSubmitBtn) rightColumnSubmitBtn.disabled = true;
    
    // Convert FormData to JSON
    const data = {};
    formData.forEach((value, key) => {
      data[key] = value;
    });
    
    try {
      const response = await fetch(`${this.options.apiBaseUrl}/customer/api/booking/${this.options.businessId}/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
      });
      
      const result = await response.json();
      
      if (response.ok) {
        // Success
        const invoiceUrl = `${this.options.apiBaseUrl}/invoice/invoices/${result.invoiceId}/preview/`;
        
        console.log('Invoice URL:', invoiceUrl);
        
        if (this.options.redirectToInvoice) {
          // Redirect to invoice preview page
          window.location.href = invoiceUrl;
          return; // Exit early as we're redirecting
        } else {
          // Show success message with invoice link
          formMessages.innerHTML = `
            <div class="alert alert-success mt-3">
              <h5><i class="fas fa-check-circle me-2"></i>Booking Successful!</h5>
              <p>Your booking has been created successfully.</p>
              <p><strong>Booking ID:</strong> ${result.bookingId}</p>
              <p><strong>Invoice ID:</strong> ${result.invoiceId}</p>
              <p>
                <a href="${invoiceUrl}" target="_blank" class="btn btn-primary btn-sm">
                  <i class="fas fa-file-invoice me-1"></i> View Invoice
                </a>
              </p>
              <p>You will receive a confirmation email shortly.</p>
            </div>
          `;
          
          // Reset form and go to first step
          form.reset();
          this.goToStep(0);
          
          // Reset overview section
          this.safeSetTextContent('overview-service', '-');
          this.safeSetTextContent('overview-datetime', '-');
          this.safeSetTextContent('overview-bedrooms', '-');
          this.safeSetTextContent('overview-bathrooms', '-');
          this.safeSetTextContent('overview-squarefeet', '-');
          
          const addonsListEl = document.getElementById('overview-addons-list');
          if (addonsListEl) {
            addonsListEl.innerHTML = '<p class="text-muted small">No add-ons selected</p>';
          }
          
          this.safeSetTextContent('overview-base-price', '0.00');
          this.safeSetTextContent('overview-addons-price', '0.00');
          this.safeSetTextContent('overview-subtotal', '0.00');
          this.safeSetTextContent('overview-tax', '0.00');
          this.safeSetTextContent('overview-total', '0.00');
          
          // Scroll to top of form and to the success message
          const formContainer = document.querySelector('.cleaningbiz-card-body');
          if (formContainer) {
            formContainer.scrollTop = 0;
          }
          
          // Scroll the page to the success message
          formMessages.scrollIntoView({ behavior: 'smooth' });
        }
        
        // Call success callback if provided
        if (this.options.onSuccess) {
          this.options.onSuccess(result);
        }
      } else {
        // Error
        formMessages.innerHTML = `
          <div class="alert alert-danger mt-3">
            <h5><i class="fas fa-exclamation-triangle me-2"></i>Error</h5>
            <p>${result.error || 'An error occurred while processing your booking.'}</p>
          </div>
        `;
        
        // Call error callback if provided
        if (this.options.onError) {
          this.options.onError(result);
        }
      }
    } catch (error) {
      console.error('Error submitting form:', error);
      formMessages.innerHTML = `
        <div class="alert alert-danger mt-3">
          <h5><i class="fas fa-exclamation-triangle me-2"></i>Error</h5>
          <p>An unexpected error occurred. Please try again later.</p>
          <p class="small text-muted">Technical details: ${error.message}</p>
        </div>
      `;
      
      // Call error callback if provided
      if (this.options.onError) {
        this.options.onError(error);
      }
    } finally {
      // Re-enable submit buttons
      if (submitBtn) submitBtn.disabled = false;
      if (rightColumnSubmitBtn) rightColumnSubmitBtn.disabled = false;
    }
  }
  
  async validateCoupon(couponCode) {
    if (!couponCode || !couponCode.trim()) {
      return {
        success: false,
        message: 'Please enter a coupon code'
      };
    }
    
    try {
      const subtotalBeforeDiscount = (document.getElementById('overview-subtotal')?.textContent || '0').replace('$', '');
      const serviceType = document.getElementById('serviceType')?.value || 'standard';
      
      const response = await fetch(`${this.options.apiBaseUrl}/booking/api/validate-coupon/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          coupon_code: couponCode.trim().toUpperCase(),
          business_id: this.options.businessId,
          customer_id: this.customerId || '',
          booking_amount: parseFloat(subtotalBeforeDiscount),
          service_type: serviceType
        })
      });
      
      const data = await response.json();
      
      if (data.success) {
        this.appliedCoupon = data.coupon;
        this.couponDiscountAmount = data.coupon.discount_amount;
        
        // Update hidden fields
        this.safeSetValue('appliedCouponCode', data.coupon.code);
        this.safeSetValue('couponDiscountAmount', data.coupon.discount_amount);
        
        this.calculatePrice();
        return {
          success: true,
          message: data.message,
          coupon: data.coupon
        };
      } else {
        this.appliedCoupon = null;
        this.couponDiscountAmount = 0;
        
        // Clear hidden fields
        this.safeSetValue('appliedCouponCode', '');
        this.safeSetValue('couponDiscountAmount', '0');
        
        this.calculatePrice();
        return {
          success: false,
          message: data.message || 'Invalid coupon code'
        };
      }
    } catch (error) {
      console.error('Error validating coupon:', error);
      return {
        success: false,
        message: 'Error validating coupon. Please try again.'
      };
    }
  }
  
  removeCoupon() {
    this.appliedCoupon = null;
    this.couponDiscountAmount = 0;
    
    // Clear hidden fields
    this.safeSetValue('appliedCouponCode', '');
    this.safeSetValue('couponDiscountAmount', '0');
    
    this.calculatePrice();
  }
  
  showCouponMessage(message, type) {
    const couponMessage = document.getElementById('coupon-message');
    if (!couponMessage) return;
    
    const icon = type === 'success' ? '<i class="fas fa-check-circle me-1"></i>' : '<i class="fas fa-exclamation-circle me-1"></i>';
    couponMessage.innerHTML = icon + message;
    
    if (type === 'success') {
      couponMessage.className = 'alert alert-success mt-2 py-2 px-3 small';
    } else {
      couponMessage.className = 'alert alert-danger mt-2 py-2 px-3 small';
    }
    
    couponMessage.style.display = 'block';
    
    // Auto-hide error messages after 5 seconds
    if (type === 'error') {
      setTimeout(() => {
        couponMessage.style.display = 'none';
      }, 5000);
    }
  }
}

// Export the class
window.CleaningBizBookingForm = CleaningBizBookingForm;
