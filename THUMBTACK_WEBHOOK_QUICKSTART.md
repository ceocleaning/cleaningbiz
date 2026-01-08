# Thumbtack Webhook Integration - Quick Reference

## 📋 Summary

I've successfully implemented a complete webhook management system for Thumbtack integration in your Django application. This allows you to receive real-time notifications when events occur on Thumbtack (like new messages).

## 🎯 What Was Created

### 1. **Backend Functions** (`accounts/thumbtack_views.py`)

- ✅ `create_thumbtack_webhook()` - Create a new webhook
- ✅ `list_thumbtack_webhooks()` - List all webhooks
- ✅ `update_thumbtack_webhook()` - Update webhook settings
- ✅ `delete_thumbtack_webhook()` - Delete a webhook
- ✅ `webhook_receiver()` - Receive and process webhook events

### 2. **API Endpoints** (`accounts/urls.py`)

- ✅ `POST /accounts/thumbtack/webhooks/create/` - Create webhook
- ✅ `GET /accounts/thumbtack/webhooks/list/` - List webhooks
- ✅ `PUT /accounts/thumbtack/webhooks/<id>/update/` - Update webhook
- ✅ `DELETE /accounts/thumbtack/webhooks/<id>/delete/` - Delete webhook
- ✅ `POST /accounts/thumbtack/webhook/receiver/` - Receive events (public)

### 3. **User Interface** (`templates/accounts/thumbtack/webhooks.html`)

- ✅ Beautiful, modern UI for webhook management
- ✅ Create webhooks with form validation
- ✅ View all existing webhooks
- ✅ Enable/disable webhooks with one click
- ✅ Delete webhooks with confirmation
- ✅ Real-time updates and alerts

### 4. **Documentation**

- ✅ `THUMBTACK_WEBHOOK_GUIDE.md` - Comprehensive guide
- ✅ `test_thumbtack_webhook.py` - Test script
- ✅ `THUMBTACK_WEBHOOK_QUICKSTART.md` - This file

## 🚀 Quick Start

### Step 1: Access the Webhook Management Page

Navigate to: `http://localhost:8000/accounts/thumbtack/webhooks/`

Or add a link in your Thumbtack dashboard:

```html
<a href="{% url 'accounts:thumbtack_webhooks_page' %}">Manage Webhooks</a>
```

### Step 2: Create Your First Webhook

**Using the UI:**

1. Go to the webhook management page
2. Fill in the form:
   - **Webhook URL**: `https://yourdomain.com/accounts/thumbtack/webhook/receiver/`
   - **Event Types**: Select `MessageCreatedV4`
   - **Enable**: Check the box
   - **Authentication**: (Optional but recommended)
     - Username: `webhook_user_123`
     - Password: `secure_password_456`
3. Click "Create Webhook"

**Using API (cURL):**

```bash
curl -X POST http://localhost:8000/accounts/thumbtack/webhooks/create/ \
  -H "Content-Type: application/json" \
  -H "Cookie: sessionid=YOUR_SESSION_ID" \
  -d '{
    "webhookURL": "https://yourdomain.com/accounts/thumbtack/webhook/receiver/",
    "eventTypes": ["MessageCreatedV4"],
    "enabled": true,
    "auth": {
      "username": "webhook_user",
      "password": "secure_password"
    }
  }'
```

**Using Python:**

```python
from accounts.thumbtack_views import create_thumbtack_webhook

result = create_thumbtack_webhook(
    access_token='your_access_token',
    webhook_url='https://yourdomain.com/accounts/thumbtack/webhook/receiver/',
    event_types=['MessageCreatedV4'],
    enabled=True,
    auth_username='webhook_user',
    auth_password='secure_password'
)

if result['success']:
    webhook_id = result['data']['webhookID']
    print(f"Webhook created: {webhook_id}")
```

### Step 3: Test the Webhook Receiver

**Using the test script:**

```bash
python test_thumbtack_webhook.py
```

**Using cURL:**

```bash
curl -X POST http://localhost:8000/accounts/thumbtack/webhook/receiver/ \
  -H "Content-Type: application/json" \
  -d '{
    "eventType": "MessageCreatedV4",
    "eventID": "evt_123",
    "userID": "user_456",
    "message": {
      "messageID": "msg_789",
      "conversationID": "conv_012",
      "content": "Test message"
    }
  }'
```

## 📝 Common Use Cases

### 1. Auto-Save Messages to Database

Edit `webhook_receiver()` in `thumbtack_views.py`:

```python
if event_type == 'MessageCreatedV4':
    from leads.models import ThumbtackMessage

    message_data = payload.get('message', {})
    ThumbtackMessage.objects.create(
        message_id=message_data.get('messageID'),
        conversation_id=message_data.get('conversationID'),
        sender_id=message_data.get('senderID'),
        content=message_data.get('content'),
        user_id=user_id
    )
```

### 2. Send Email Notifications

```python
if event_type == 'MessageCreatedV4':
    from django.core.mail import send_mail

    message_data = payload.get('message', {})
    send_mail(
        'New Thumbtack Message',
        f'You received: {message_data.get("content")}',
        'noreply@yourdomain.com',
        ['admin@yourdomain.com'],
    )
```

### 3. Trigger Auto-Response

```python
if event_type == 'MessageCreatedV4':
    # Send automatic reply
    conversation_id = payload.get('message', {}).get('conversationID')
    # Call Thumbtack API to send response
    send_thumbtack_message(
        conversation_id=conversation_id,
        message="Thank you! We'll respond shortly."
    )
```

## 🔐 Security Best Practices

1. **Always use HTTPS** for webhook URLs in production
2. **Enable webhook authentication** with strong credentials
3. **Verify webhook signatures** (if Thumbtack provides them)
4. **Log all webhook events** for auditing
5. **Rate limit** the webhook receiver endpoint
6. **Validate payload structure** before processing

## 🧪 Testing

### Test Locally

1. Start your Django server:

   ```bash
   python manage.py runserver
   ```

2. Run the test script:

   ```bash
   python test_thumbtack_webhook.py
   ```

3. Or use the UI at: `http://localhost:8000/accounts/thumbtack/webhooks/`

### Test in Production

1. Deploy your application
2. Update webhook URL to your production domain
3. Use ngrok for testing before deployment:
   ```bash
   ngrok http 8000
   ```
   Then use the ngrok URL as your webhook URL

## 📊 Monitoring

### Check Webhook Status

```python
from accounts.thumbtack_views import list_thumbtack_webhooks

result = list_thumbtack_webhooks(access_token)
if result['success']:
    for webhook in result['data']['webhooks']:
        print(f"Webhook {webhook['webhookID']}: {webhook['enabled']}")
```

### View Webhook Logs

Check your server logs for webhook events:

```bash
tail -f logs/django.log | grep "Received Thumbtack webhook"
```

## 🛠️ Troubleshooting

### Webhook Not Receiving Events

1. ✅ Verify webhook is enabled
2. ✅ Check webhook URL is publicly accessible
3. ✅ Ensure HTTPS is used (not HTTP)
4. ✅ Verify event types are correct
5. ✅ Check server logs for errors

### Authentication Errors

1. ✅ Verify credentials match those provided during creation
2. ✅ Check authentication header format
3. ✅ Ensure credentials are not expired

### Processing Errors

1. ✅ Check server logs for exceptions
2. ✅ Verify payload structure
3. ✅ Test with sample payloads locally
4. ✅ Ensure database connections work

## 📚 Additional Resources

- **Full Documentation**: `THUMBTACK_WEBHOOK_GUIDE.md`
- **Test Script**: `test_thumbtack_webhook.py`
- **Code**: `accounts/thumbtack_views.py`
- **UI Template**: `templates/accounts/thumbtack/webhooks.html`

## 🎉 Next Steps

1. **Customize the webhook receiver** to handle your specific business logic
2. **Add more event types** as Thumbtack adds support for them
3. **Implement webhook retry logic** for failed processing
4. **Add webhook analytics** to track event volumes
5. **Set up monitoring** and alerts for webhook failures

## 💡 Tips

- Store webhook IDs in your database for easy management
- Implement idempotency using event IDs to prevent duplicate processing
- Use background tasks (Celery) for heavy processing
- Keep webhook responses fast (< 5 seconds)
- Log all events for debugging and compliance

---

**Need Help?** Check the full documentation in `THUMBTACK_WEBHOOK_GUIDE.md` or review the code in `accounts/thumbtack_views.py`.
