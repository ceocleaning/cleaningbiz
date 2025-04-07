"""
Local development settings to override production settings
"""

# Disable SSL/HTTPS settings for local development
SECURE_PROXY_SSL_HEADER = None
SECURE_SSL_REDIRECT = False
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
