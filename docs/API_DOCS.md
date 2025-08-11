# Webhook API Documentation: `Leads Webhook`

This document provides instructions for sending lead data to the `Leads Webhook`. This webhook processes incoming lead information, uses an AI model to structure the data, and then stores it in the system.

## Endpoint

*   **URL:** `https://cleaningbizai.com/lead/webhook/<secretKey>/`
*   **Method:** `POST`

### Path Parameters

*   `secretKey` (string, required): A unique API key to authenticate the request. This key is associated with a specific business account.

## Request Body

The request body must be a JSON object containing the lead's information. The webhook is designed to handle unstructured data, so you can send any relevant details. The AI model will extract the necessary fields.

### Example JSON Payload

```json
{
  "customer_name": "John Doe",
  "contact_email": "john.doe@example.com",
  "phone": "(555) 123-4567",
  "service_interest": "Deep cleaning for a 3-bedroom, 2-bathroom house.",
  "property_size": "Approx. 1500 sq ft",
  "preferred_date": "Next Friday afternoon",
  "notes": "Two cats in the house. Please use pet-friendly products."
}
```

## Responses

### Success Response

*   **Status Code:** `201 Created`
*   **Content:** A JSON object confirming that the lead was created, along with the lead's ID and the structured data that was extracted.

```json
{
  "message": "Lead created successfully",
  "lead_id": "12345abc-12ab-34cd-56ef-1234567890ab",
  "structured_data": {
    "name": "John Doe",
    "email": "john.doe@example.com",
    "phone_number": "(555) 123-4567",
    "bedrooms": 3,
    "bathrooms": 2,
    "squareFeet": 1500,
    "type_of_cleaning": "Deep cleaning",
    "notes": "Two cats in the house. Please use pet-friendly products.",
    "source": "API"
  }
}
```

### Error Responses

*   **Status Code:** `400 Bad Request`
    *   **Reason:** The request body is missing or not in a valid JSON format.
    *   **Content:**
        ```json
        {
          "error": "Invalid JSON data"
        }
        ```

*   **Status Code:** `401 Unauthorized`
    *   **Reason:** The provided `secretKey` is invalid or missing.
    *   **Content:**
        ```json
        {
          "message": "Secret Key Not Verified"
        }
        ```

*   **Status Code:** `405 Method Not Allowed`
    *   **Reason:** The request was made using a method other than `POST`.
    *   **Content:**
        ```json
        {
          "error": "Invalid request method"
        }
        ```
