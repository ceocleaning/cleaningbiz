
import logging
import rollbar

# Get the logger instance
logger = logging.getLogger(__name__)

def log_message(level, message, extra_data=None):
    extra_data = extra_data or {}
    try:
        if level == 'debug':
            rollbar.report_message(message, 'debug', extra_data=extra_data)
        elif level == 'info':
            rollbar.report_message(message, 'info', extra_data=extra_data)
        elif level == 'warning':
            rollbar.report_message(message, 'warning', extra_data=extra_data)
        elif level == 'error':
            rollbar.report_message(message, 'error', extra_data=extra_data)
        elif level == 'critical':
            rollbar.report_message(message, 'critical', extra_data=extra_data)
    except Exception as e:
        # Fallback to standard logging if Rollbar fails
        logger.error(f"Failed to send log to Rollbar: {e}")
        fallback_logger = logging.getLogger('fallback')
        if level == 'debug':
            fallback_logger.debug(message, extra=extra_data)
        elif level == 'info':
            fallback_logger.info(message, extra=extra_data)
        elif level == 'warning':
            fallback_logger.warning(message, extra=extra_data)
        elif level == 'error':
            fallback_logger.error(message, extra=extra_data)
        elif level == 'critical':
            fallback_logger.critical(message, extra=extra_data)
