# Endpoints Documentation

## Authentication and User Management
- `GET /account/login/` - User login page
  - Displays the login form for existing users to authenticate
  - Handles user credentials validation and session creation

- `GET /account/register/` - New user registration
  - Provides a registration form for new users
  - Collects essential user information and creates a new user account

- `GET /account/logout/` - User logout
  - Terminates the current user session
  - Redirects to the login page

- `GET /account/profile/` - View user profile
  - Displays user's personal information
  - Shows account settings and preferences

- `POST /account/profile/update/` - Update user profile information
  - Allows users to modify their personal details
  - Updates stored user information in the database

- `POST /account/profile/change-password/` - Change user password
  - Provides interface for password change
  - Validates old password and updates to new password

- `POST /account/profile/update-credentials/` - Update user credentials
  - Updates authentication credentials
  - Manages API keys and access tokens

### Business Management
- `POST /account/register-business/` - Register a new business
  - Creates a new business profile
  - Required before accessing booking features
  - Collects business details like name, address, and contact information

- `POST /account/business/edit/` - Edit business information
  - Modifies existing business details
  - Updates business profile information

- `POST /account/business/settings/edit/` - Edit business settings
  - Configures business-specific settings
  - Manages operational preferences and defaults

### Business Add-ons and Integrations
- `POST /account/custom-addon/add/` - Add a custom add-on
  - Creates new service add-ons for bookings
  - Defines pricing and description for additional services

- `POST /account/custom-addon/<int:addon_id>/edit/` - Edit specific custom add-on
  - Modifies existing add-on details
  - Updates pricing or description of services

- `DELETE /account/custom-addon/<int:addon_id>/delete/` - Delete specific custom add-on
  - Removes an add-on from the system
  - Updates related bookings accordingly

- `POST /account/business/credentials/edit/` - Edit business credentials
  - Manages API keys and integration credentials
  - Updates authentication tokens for third-party services

- `POST /account/business/credentials/generate-secret/` - Generate new secret key
  - Creates new API secret key
  - Used for webhook authentication and API access

- `POST /account/business/integrations/add/` - Add new integration
  - Connects third-party services
  - Sets up webhook endpoints and API configurations

- `POST /account/business/integrations/<int:pk>/edit/` - Edit specific integration
  - Modifies integration settings
  - Updates API endpoints and credentials

- `DELETE /account/business/integrations/<int:pk>/delete/` - Delete specific integration
  - Removes third-party service integration
  - Cleans up associated credentials and settings

### SMTP Configuration
- `GET /account/smtp-config/` - View and manage SMTP configuration
  - Displays form for viewing and adding SMTP settings
  - Shows existing SMTP configuration if available
  - Handles AJAX requests for saving configuration

- `POST /account/smtp-config/` - Save SMTP configuration
  - Creates or updates SMTP settings for the business
  - Supports both traditional form submission and AJAX requests
  - Returns JSON response for AJAX requests

- `POST /account/smtp-config/delete/` - Delete SMTP configuration
  - Removes SMTP configuration for the business
  - Supports AJAX requests with confirmation
  - Returns JSON response for AJAX requests

- `POST /account/test-email-settings/` - Test SMTP configuration
  - Sends a test email using the configured SMTP settings
  - Requires AJAX request with XMLHttpRequest header
  - Returns JSON response with success/failure status and message

## Bookings Management
- `GET /booking/` - View all bookings
  - Displays list of all bookings for the business
  - Shows pending and completed booking counts
  - Provides booking management interface

- `POST /booking/create/` - Create new booking
  - Creates a new service booking
  - Collects customer details, service type, and scheduling information
  - Handles add-ons and special requirements

- `GET /booking/detail/<str:bookingId>/` - View specific booking details
  - Shows comprehensive booking information
  - Displays customer details, services, and status

- `POST /booking/edit/<str:bookingId>/` - Edit specific booking
  - Modifies booking details
  - Updates schedule, services, or customer information

- `POST /booking/mark-completed/<str:bookingId>/` - Mark booking as completed
  - Updates booking status to completed
  - Triggers related workflows (e.g., invoice generation)

- `DELETE /booking/delete/<str:bookingId>/` - Delete specific booking
  - Removes booking from the system
  - Handles related record cleanup

### Invoice Management
- `GET /booking/invoices/` - View all invoices
  - Lists all invoices for the business
  - Shows payment status and due amounts

- `POST /booking/invoices/create/<str:bookingId>/` - Create invoice for specific booking
  - Generates new invoice from booking details
  - Calculates total amount including services and add-ons

- `GET /booking/invoices/detail/<str:invoiceId>/` - View specific invoice details
  - Displays comprehensive invoice information
  - Shows line items, totals, and payment status

- `POST /booking/invoices/edit/<str:invoiceId>/` - Edit specific invoice
  - Modifies invoice details
  - Updates amounts, line items, or payment terms

- `DELETE /booking/invoices/delete/<str:invoiceId>/` - Delete specific invoice
  - Removes invoice from the system
  - Updates related booking records

- `POST /booking/invoices/mark-paid/<str:invoiceId>/` - Mark invoice as paid
  - Updates invoice payment status
  - Records payment details and date

- `GET /booking/invoices/<str:invoiceId>/preview/` - Preview specific invoice
  - Displays formatted invoice preview
  - Shows how invoice will appear to customers

- `GET /booking/invoices/<str:invoiceId>/generate-pdf/` - Generate PDF for specific invoice
  - Creates downloadable PDF invoice
  - Includes business branding and all invoice details

## Lead Management
- `GET /leads/` - View all leads
  - Displays list of all business leads
  - Shows lead status and priority

- `POST /leads/create/` - Create new lead
  - Records new business opportunity
  - Captures potential customer information

- `GET /leads/<str:leadId>/` - View specific lead details
  - Shows comprehensive lead information
  - Displays contact details and interaction history

- `POST /leads/<str:leadId>/update/` - Update specific lead
  - Modifies lead information
  - Updates status and follow-up details

- `DELETE /leads/<str:leadId>/delete/` - Delete specific lead
  - Removes lead from the system
  - Cleans up related records

## Webhook Endpoints
- `POST /webhook/<str:secretKey>/` - Handle Retell webhook
  - Processes incoming Retell API Data
  - Updates system based on external events
  - Requires valid secret key for authentication

- `POST /thumbtack-webhook/` - Handle Thumbtack webhook
  - Processes Thumbtack platform Data
  - Updates leads from Thumbtack

## Cleaner Management
- `GET /cleaners/` - View all cleaners
  - Displays list of all cleaners for the business
  - Shows availability status and contact information

- `POST /cleaners/create/` - Create new cleaner
  - Adds a new cleaner to the business
  - Collects name, email, and phone number

- `GET /cleaners/<int:pk>/` - View specific cleaner details
  - Shows comprehensive cleaner information
  - Displays availability schedule and assigned bookings

- `POST /cleaners/<int:pk>/update/` - Update specific cleaner
  - Modifies cleaner information
  - Updates contact details and availability status

- `DELETE /cleaners/<int:pk>/delete/` - Delete specific cleaner
  - Removes cleaner from the system
  - Updates related booking assignments

### Cleaner Availability Management
- `GET /cleaners/<int:cleaner_id>/availability/` - View cleaner availability
  - Displays weekly recurring schedule and specific date exceptions
  - Shows working hours and off days

- `POST /cleaners/<int:cleaner_id>/availability/add/` - Add availability slot
  - Creates new availability entry for a cleaner
  - Supports both weekly recurring and specific date availability

- `POST /cleaners/<int:cleaner_id>/availability/<int:pk>/update/` - Update availability slot
  - Modifies existing availability entry
  - Updates time slots or off day status

- `DELETE /cleaners/<int:cleaner_id>/availability/<int:pk>/delete/` - Delete availability slot
  - Removes specific availability entry
  - Updates cleaner's schedule

## Custom Add-ons Management
- `GET /account/custom-addons/` - View all custom add-ons
  - Lists all custom add-ons for the business
  - Shows pricing and descriptions

- `POST /account/custom-addons/create/` - Create new custom add-on
  - Adds a new custom service add-on
  - Sets pricing and generates data name for system integration

- `POST /account/custom-addons/<int:pk>/update/` - Update custom add-on
  - Modifies existing add-on details
  - Updates pricing and description

- `DELETE /account/custom-addons/<int:pk>/delete/` - Delete custom add-on
  - Removes custom add-on from the system
  - Updates related booking options

## Availability Checker
- `GET /booking/availability/check/` - Check cleaner availability
  - Verifies availability of cleaners for a specific date and time
  - Returns available cleaners based on their schedules
  - Considers both weekly recurring availability and specific date exceptions

- `POST /booking/assign-cleaner/<str:bookingId>/` - Assign cleaner to booking
  - Assigns an available cleaner to a specific booking
  - Validates cleaner availability before assignment
  - Updates booking with cleaner information

## Business Settings
- `GET /account/business/settings/` - View business settings
  - Displays pricing configuration for services
  - Shows tax rates and deposit fees

- `POST /account/business/settings/update/` - Update business settings
  - Modifies pricing structure for services
  - Updates add-on pricing and square footage multipliers
  - Sets tax rates and deposit fees

## API Integrations
- `GET /account/business/integrations/` - View all integrations
  - Lists all third-party service integrations
  - Shows connection status and configuration details

- `POST /account/business/integrations/add/` - Add new integration
  - Connects a new third-party service
  - Configures API keys and webhook URLs

- `POST /account/business/integrations/<int:pk>/update/` - Update integration
  - Modifies existing integration configuration
  - Updates API keys and webhook settings

- `DELETE /account/business/integrations/<int:pk>/delete/` - Delete integration
  - Removes third-party service integration
  - Cleans up associated credentials

### API Credentials Management
- `GET /account/business/credentials/` - View API credentials
  - Displays API keys and webhook URLs
  - Shows integration connection details

- `POST /account/business/credentials/update/` - Update API credentials
  - Modifies API keys for third-party services
  - Updates webhook URLs and connection settings

- `POST /account/business/credentials/generate-secret/` - Generate new secret key
  - Creates a new unique secret key for webhook authentication
  - Updates webhook URLs with the new secret key

## Main Application
- `GET /` - Home page
  - Displays dashboard with key metrics
