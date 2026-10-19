from celery import shared_task
import africastalking
from django.conf import settings

@shared_task
def send_status_update_sms(phone_number, ref_number, new_status):
    """
    Sends an SMS notification via Africa's Talking API when a request status changes.
    """
    africastalking.initialize(settings.AT_USERNAME, settings.AT_API_KEY)
    sms = africastalking.SMS
    message = f"Murang'a e-Citizen: Your request {ref_number} status has been updated to '{new_status}'."
    
    try:
        response = sms.send(message, [phone_number])
        return response
    except Exception as e:
        print(f"SMS delivery error: {e}")
        return None