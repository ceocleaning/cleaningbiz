
def get_email_template(booking, to, when):
    business = booking.business
    cleaner = None
    if to == 'cleaner':
        cleaner = booking.cleaner

    cleaner_or_business = cleaner.name if cleaner else business.businessName
    name = cleaner.name if cleaner else booking.firstName + ' ' + booking.lastName
    email_template = f"""
            <!DOCTYPE html>
            <html>
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>Booking Reminder</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
                        .header {{ background-color: #4a90e2; color: white; padding: 20px; text-align: center; }}
                        .content {{ padding: 20px; background-color: #f9f9f9; }}
                        .details {{ margin: 20px 0; }}
                        .details table {{ width: 100%; border-collapse: collapse; }}
                        .details table td {{ padding: 8px; border-bottom: 1px solid #ddd; }}
                        .details table td:first-child {{ font-weight: bold; width: 40%; }}
                        .tips {{ background-color: #e8f4fb; padding: 15px; border-radius: 5px; margin-top: 20px; }}
                        .footer {{ margin-top: 20px; text-align: center; font-size: 12px; color: #777; }}
                    </style>
                </head>
                <body>
                    <div class="header">
                        <h1>Your Cleaning Service Is {when}</h1>
                    </div>
                    <div class="content">
                        <p>Hello {name},</p>
                        <p>This is a friendly reminder that your cleaning service with {cleaner_or_business} is scheduled for {when}.</p>
                        
                        <div class="details">
                            <h3>Booking Details:</h3>
                            <table>
                                <tr>
                                    <td>Service:</td>
                                    <td>{booking.get_serviceType_display()}</td>
                                </tr>
                                <tr>
                                    <td>Date:</td>
                                    <td>{booking.cleaningDate.strftime('%A, %B %d, %Y')}</td>
                                </tr>
                                <tr>
                                    <td>Time:</td>
                                    <td>{booking.startTime.strftime('%I:%M %p')} - {booking.endTime.strftime('%I:%M %p')}</td>
                                </tr>
                                <tr>
                                    <td>Address:</td>
                                    <td>{booking.address1}</td>
                                </tr>
                            </table>
                        </div>
                        
                        <div class="tips">
                            <h3>Preparation Tips:</h3>
                            <ul>
                                <li>Please ensure access to your property is available at the scheduled time</li>
                                <li>Clear any personal items that may obstruct cleaning</li>
                                <li>Secure pets in a safe area if necessary</li>
                            </ul>
                        </div>
                        
                        <p>If you need to reschedule or have any questions, please contact us as soon as possible at {business.phone or business.user.email}.</p>
                    </div>
                    <div class="footer">
                        <p>This is an automated message from {business.businessName}.</p>
                    </div>
                </body>
            </html>
            """
    
    return email_template