from rest_framework.response import Response
from rest_framework.decorators import api_view
from datetime import datetime, timedelta
import pytz
from rest_framework.views import csrf_exempt
import dateparser
from django.utils import timezone
from .utils import generateAppoitnmentId, sendInvoicetoClient, sendEmailtoClientInvoice

from bookings.models import Booking

  
   
    


