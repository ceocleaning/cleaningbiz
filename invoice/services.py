from decimal import Decimal
from django.db import transaction


class TipService:
    """
    Service class for handling tip-related operations.
    Follows the service pattern to keep business logic separate from views and models.
    """
    
    @staticmethod
    def calculate_percentage_tip(amount, percentage):
        """
        Calculate tip amount based on a percentage of the invoice amount.
        
        Args:
            amount (Decimal): The invoice amount
            percentage (int): The tip percentage (e.g., 10, 15, 20)
            
        Returns:
            Decimal: The calculated tip amount
        """
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
        
        return (amount * Decimal(percentage) / Decimal(100)).quantize(Decimal('0.01'))
    
    @staticmethod
    def validate_tip_amount(tip_amount, invoice_amount):
        """
        Validate that the tip amount is reasonable.
        
        Args:
            tip_amount (Decimal): The tip amount to validate
            invoice_amount (Decimal): The invoice amount for reference
            
        Returns:
            tuple: (is_valid, error_message)
        """
        if not isinstance(tip_amount, Decimal):
            tip_amount = Decimal(str(tip_amount))
            
        if tip_amount < 0:
            return False, "Tip amount cannot be negative"
        
        # Optional: Add maximum tip validation if needed
        # For example, prevent tips larger than 100% of the invoice
        if tip_amount > invoice_amount:
            print(f"Tip amount {tip_amount} cannot exceed invoice amount {invoice_amount}")
            return False, "Tip amount cannot exceed the invoice amount"
            
        return True, None
    
    @staticmethod
    @transaction.atomic
    def add_tip_to_booking(booking, tip_amount):
        """
        Add a tip to a booking and update related invoice.
        Uses transaction to ensure data consistency.
        
        Args:
            booking: The booking object
            tip_amount (Decimal): The tip amount
            
        Returns:
            tuple: (booking, invoice) - The updated booking and invoice objects
        """
        if not isinstance(tip_amount, Decimal):
            tip_amount = Decimal(str(tip_amount))
        
        # Update booking tip
        booking.tip = tip_amount
        booking.save(update_fields=['tip'])
        
        # Update invoice if it exists
        if hasattr(booking, 'invoice'):
            invoice = booking.invoice
            # Add tip to the invoice amount
            invoice.amount = invoice.amount + tip_amount
            invoice.save(update_fields=['amount'])
            return booking, invoice
        
        return booking, None
    
    @staticmethod
    def get_suggested_tip_amounts(invoice_amount):
        """
        Get suggested tip amounts based on the invoice amount.
        
        Args:
            invoice_amount (Decimal): The invoice amount
            
        Returns:
            dict: Suggested tip amounts and percentages
        """
        if not isinstance(invoice_amount, Decimal):
            invoice_amount = Decimal(str(invoice_amount))
            
        # Calculate percentage-based suggestions
        tip_10_percent = TipService.calculate_percentage_tip(invoice_amount, 10)
        tip_15_percent = TipService.calculate_percentage_tip(invoice_amount, 15)
        tip_20_percent = TipService.calculate_percentage_tip(invoice_amount, 20)
        
        # Fixed amount suggestions
        fixed_suggestions = [
            Decimal('5.00'),
            Decimal('10.00'),
            Decimal('20.00')
        ]
        
        return {
            'percentage_based': {
                '10%': tip_10_percent,
                '15%': tip_15_percent,
                '20%': tip_20_percent
            },
            'fixed_amounts': fixed_suggestions
        }
