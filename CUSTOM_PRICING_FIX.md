# Custom Pricing Fix & Visual Indicators

## Issues Fixed

### **1. Custom Pricing Not Being Applied**
**Problem:** API returned `is_custom_pricing` but JavaScript checked for `has_custom_pricing`

**Solution:**
```javascript
// BEFORE (incorrect)
if (data.success && data.has_custom_pricing) {

// AFTER (correct)
if (data.success && data.pricing) {
  if (data.pricing.is_custom_pricing) {
```

### **2. No Visual Indicator for Special Rates**
**Problem:** Users couldn't tell if they were getting custom pricing

**Solution:** Added two visual indicators:
1. **Alert banner** in overview card header
2. **Badge** next to total price

---

## Visual Indicators Added

### **1. Special Rates Alert Banner**
**Location:** Top of Service Overview card

**Appearance:**
```
┌─────────────────────────────────────┐
│ ⭐ Special Rates Applied!           │
│ Welcome back, John! You're getting  │
│ your custom pricing.                │
└─────────────────────────────────────┘
```

**Code:**
```javascript
showSpecialRatesIndicator(customerName) {
  const overviewCard = document.querySelector('.cleaningbiz-overview-card .cleaningbiz-card-header');
  const indicator = document.createElement('div');
  indicator.id = 'special-rates-indicator';
  indicator.className = 'alert alert-success mt-2 mb-0';
  indicator.innerHTML = `
    <div class="d-flex align-items-center">
      <i class="fas fa-star me-2" style="color: #ffc107;"></i>
      <strong>Special Rates Applied!</strong>
    </div>
    <small class="d-block mt-1">Welcome back${customerName ? ', ' + customerName.split(' ')[0] : ''}! You're getting your custom pricing.</small>
  `;
  overviewCard.appendChild(indicator);
}
```

### **2. Special Rate Badge on Total**
**Location:** Next to total price

**Appearance:**
```
Total: $150.00 [⭐ Special Rate]
```

**Code:**
```javascript
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
```

---

## Debugging Enhancements

### **Console Logging Added**

**1. Customer Pricing Response:**
```javascript
console.log('Customer pricing response:', data);
```

**2. Price Calculation:**
```javascript
console.log('Calculating price with:', usingCustomPricing ? 'CUSTOM PRICING' : 'DEFAULT PRICING');
console.log('Pricing data:', prices);
console.log(`Base: $${prices.base_price}, Bedrooms: ${bedrooms} x $${bedroomPrice}, Bathrooms: ${bathrooms} x $${bathroomPrice}`);
```

**What to Check in Console:**
```
✅ Customer pricing response: {success: true, pricing: {...}}
✅ Calculating price with: CUSTOM PRICING
✅ Pricing data: {base_price: 50, bedroom_price: 15, ...}
✅ Base: $50, Bedrooms: 3 x $15, Bathrooms: 2 x $10
```

---

## API Response Structure

### **Correct Response from `/customer/api/pricing/{business_id}/customer/{customer_id}/`**

```json
{
  "success": true,
  "pricing": {
    "customer_id": "uuid",
    "customer_name": "John Doe",
    "is_custom_pricing": true,
    
    "base_price": 50.00,
    "bedroom_price": 15.00,
    "bathroom_price": 10.00,
    
    "sqft_multiplier_standard": 0.05,
    "sqft_multiplier_deep": 0.08,
    "sqft_multiplier_moveinout": 0.10,
    "sqft_multiplier_airbnb": 0.06,
    
    "addon_price_dishes": 15.00,
    "addon_price_laundry": 20.00,
    "addon_price_window": 25.00,
    "addon_price_pets": 15.00,
    "addon_price_fridge": 20.00,
    "addon_price_oven": 20.00,
    "addon_price_baseboard": 15.00,
    "addon_price_blinds": 20.00,
    
    "weekly_discount": 10.00,
    "biweekly_discount": 5.00,
    "monthly_discount": 15.00,
    
    "custom_addons": {
      "addon-uuid-1": {
        "id": "addon-uuid-1",
        "name": "Custom Addon Name",
        "price": 30.00,
        "default_price": 35.00,
        "is_custom": true
      }
    }
  }
}
```

---

## Testing Checklist

### **Test Scenario 1: Existing Customer with Custom Pricing**

1. ✅ Enter email of customer with active custom pricing
2. ✅ Click "Next" from Step 1
3. ✅ Check console: "Customer pricing response" logged
4. ✅ Check console: "Calculating price with: CUSTOM PRICING"
5. ✅ **Visual Check:** Green alert banner appears: "Special Rates Applied!"
6. ✅ **Visual Check:** Badge appears next to total: "⭐ Special Rate"
7. ✅ Verify prices match custom pricing (not default)
8. ✅ Change bedrooms/bathrooms - prices recalculate with custom rates
9. ✅ Add addons - custom addon prices used
10. ✅ Complete booking successfully

### **Test Scenario 2: New Customer (No Custom Pricing)**

1. ✅ Enter new email
2. ✅ Click "Next" from Step 1
3. ✅ Check console: "Calculating price with: DEFAULT PRICING"
4. ✅ **Visual Check:** NO alert banner
5. ✅ **Visual Check:** NO special rate badge
6. ✅ Verify prices match business default pricing
7. ✅ Complete booking successfully

### **Test Scenario 3: Existing Customer WITHOUT Custom Pricing**

1. ✅ Enter email of customer without custom pricing
2. ✅ Click "Next" from Step 1
3. ✅ Check console: "Calculating price with: DEFAULT PRICING"
4. ✅ **Visual Check:** NO alert banner
5. ✅ **Visual Check:** NO special rate badge
6. ✅ Verify prices match business default pricing

---

## Visual Design

### **Colors & Styling**

**Alert Banner:**
- Background: Success green (`alert-success`)
- Star icon: Gold (`#ffc107`)
- Font size: Small (`0.875rem`)
- Padding: Compact (`8px 12px`)

**Badge:**
- Background: Success green (`bg-success`)
- Font size: Extra small (`0.7rem`)
- Position: Next to total price
- Icon: Star (`fas fa-star`)

---

## Files Modified

1. ✅ `static/js/embeddable-booking-form.js`
   - Fixed `has_custom_pricing` → `is_custom_pricing`
   - Added `showSpecialRatesIndicator()` method
   - Added badge to total price
   - Added console logging for debugging
   - Improved price calculation with better fallbacks

2. ✅ `customer/check_customer_api.py`
   - Fixed `Business.objects.get(id=...)` → `Business.objects.get(businessId=...)`
   - Added debug print statement

---

## How It Works

### **Flow:**

```
User enters email → Click "Next"
    ↓
checkExistingCustomer() API call
    ↓
Customer found? → fetchCustomerPricing()
    ↓
Pricing received with is_custom_pricing: true
    ↓
showSpecialRatesIndicator() → Display alert banner
    ↓
calculatePrice() → Use custom pricing
    ↓
Update overview → Add badge to total
    ↓
User sees: "⭐ Special Rates Applied!" + "⭐ Special Rate" badge
```

---

## Benefits

1. ✅ **Clear Visual Feedback** - Users immediately know they're getting special pricing
2. ✅ **Personalized Welcome** - Uses customer's first name in greeting
3. ✅ **Prominent Display** - Alert banner catches attention
4. ✅ **Persistent Reminder** - Badge stays visible throughout booking
5. ✅ **Better UX** - Customers feel valued and recognized
6. ✅ **Debug-Friendly** - Console logs help troubleshoot issues

---

## Troubleshooting

### **If custom pricing not applying:**

1. Check console for: `"Customer pricing response:"`
2. Verify `is_custom_pricing: true` in response
3. Check: `"Calculating price with: CUSTOM PRICING"`
4. Verify pricing data has custom values
5. Check CustomerPricing model: `is_active = True`

### **If visual indicators not showing:**

1. Check: `data.pricing.is_custom_pricing === true`
2. Verify `.cleaningbiz-overview-card .cleaningbiz-card-header` exists
3. Check console for errors
4. Verify Bootstrap classes loaded

---

## Next Steps

- ✅ Test with real customer data
- ✅ Verify all pricing fields work correctly
- ✅ Test on different screen sizes
- ✅ Ensure indicators are mobile-responsive
