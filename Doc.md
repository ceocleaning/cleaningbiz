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

## Main Application
- `GET /` - Home page
  - Displays dashboard with key metrics



