import stripe
import requests
from datetime import datetime
from decimal import Decimal
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .models import Settlement


@login_required
def payment_gateway_selection(request, settlement_id):
    """Allow user to select payment gateway for settlement payment."""
    settlement = get_object_or_404(Settlement, id=settlement_id)

    # Check permissions
    if not (settlement.exit_request.booking.tenant == request.user or
            settlement.exit_request.booking.property.landlord == request.user):
        messages.error(request, "You don't have permission to access this settlement.")
        return redirect('dashboard')

    if settlement.status != 'completed':
        messages.error(request, "Settlement must be completed before payment.")
        return redirect('early_exit_detail', settlement.exit_request.id)

    # Determine who needs to pay whom
    if settlement.net_payable_to_owner > 0:
        # Tenant owes money to owner
        payer = settlement.exit_request.booking.tenant
        payee = settlement.exit_request.booking.property.landlord
        amount = settlement.net_payable_to_owner
        description = f"Payment to landlord for settlement #{settlement.id}"
    elif settlement.net_refund_to_tenant > 0:
        # Owner owes refund to tenant
        payer = settlement.exit_request.booking.property.landlord
        payee = settlement.exit_request.booking.tenant
        amount = settlement.net_refund_to_tenant
        description = f"Refund from landlord for settlement #{settlement.id}"
    else:
        messages.info(request, "No payment is required for this settlement.")
        return redirect('early_exit_detail', settlement.exit_request.id)

    # Check if current user is the payer
    if request.user != payer:
        messages.error(request, "You are not the party responsible for payment.")
        return redirect('dashboard')

    context = {
        'settlement': settlement,
        'amount': amount,
        'description': description,
        'payer': payer,
        'payee': payee,
    }

    return render(request, 'listings/payment_gateway.html', context)


@login_required
@require_POST
def initiate_stripe_payment(request, settlement_id):
    """Initiate Stripe payment for settlement."""
    settlement = get_object_or_404(Settlement, id=settlement_id)

    # Validate permissions and settlement status
    if not (settlement.exit_request.booking.tenant == request.user or
            settlement.exit_request.booking.property.landlord == request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)

    if settlement.status != 'completed':
        return JsonResponse({'error': 'Settlement not completed'}, status=400)

    # Calculate amount to pay
    amount = settlement.net_payable_to_owner if settlement.net_payable_to_owner > 0 else settlement.net_refund_to_tenant
    if amount <= 0:
        return JsonResponse({'error': 'No payment required'}, status=400)

    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY

        # Create payment intent
        intent = stripe.PaymentIntent.create(
            amount=int(amount * 100),  # Convert to cents
            currency='npr',  # Nepalese Rupee
            metadata={
                'settlement_id': settlement.id,
                'booking_id': settlement.lease.id,
            },
            description=f'Settlement payment #{settlement.id}',
        )

        # Update settlement with payment info
        settlement.payment_gateway = 'stripe'
        settlement.payment_status = 'processing'
        settlement.payment_id = intent.id
        settlement.payment_amount = amount
        settlement.save()

        return JsonResponse({
            'client_secret': intent.client_secret,
            'payment_intent_id': intent.id,
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
def stripe_webhook(request):
    """Handle Stripe webhook for payment confirmation."""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return JsonResponse({'error': 'Invalid payload'}, status=400)
    except stripe.error.SignatureVerificationError:
        return JsonResponse({'error': 'Invalid signature'}, status=400)

    if event.type == 'payment_intent.succeeded':
        payment_intent = event.data.object
        settlement_id = payment_intent.metadata.get('settlement_id')

        if settlement_id:
            try:
                settlement = Settlement.objects.get(id=settlement_id)
                settlement.payment_status = 'completed'
                if isinstance(payment_intent.created, int):
                    settlement.payment_completed_at = timezone.make_aware(datetime.fromtimestamp(payment_intent.created))
                else:
                    settlement.payment_completed_at = payment_intent.created
                settlement.save()

                # Create notification for payee
                from users.models import Notification
                if settlement.net_payable_to_owner > 0:
                    # Tenant paid owner
                    recipient = settlement.exit_request.booking.property.landlord
                    title = "Payment Received"
                    message = f"You have received payment of Rs. {settlement.payment_amount} for settlement #{settlement.id}"
                else:
                    # Owner paid tenant
                    recipient = settlement.exit_request.booking.tenant
                    title = "Refund Received"
                    message = f"You have received a refund of Rs. {settlement.payment_amount} for settlement #{settlement.id}"

                Notification.objects.create(
                    recipient=recipient,
                    title=title,
                    message=message,
                    target_url=reverse('early_exit_detail', args=[settlement.exit_request.id])
                )

            except Settlement.DoesNotExist:
                pass

    return JsonResponse({'status': 'success'})


@login_required
def payment_success(request):
    """Handle successful payment return."""
    messages.success(request, "Payment completed successfully!")
    return redirect('dashboard')


@login_required
def payment_cancel(request):
    """Handle cancelled payment return."""
    messages.warning(request, "Payment was cancelled.")
    return redirect('dashboard')


# eSewa Integration (Nepal)
@login_required
@require_POST
def initiate_esewa_payment(request, settlement_id):
    """Initiate eSewa payment for settlement."""
    settlement = get_object_or_404(Settlement, id=settlement_id)

    # Validate permissions and settlement status
    if not (settlement.exit_request.booking.tenant == request.user or
            settlement.exit_request.booking.property.landlord == request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)

    if settlement.status != 'completed':
        return JsonResponse({'error': 'Settlement not completed'}, status=400)

    amount = settlement.net_payable_to_owner if settlement.net_payable_to_owner > 0 else settlement.net_refund_to_tenant
    if amount <= 0:
        return JsonResponse({'error': 'No payment required'}, status=400)

    # Update settlement
    settlement.payment_gateway = 'esewa'
    settlement.payment_status = 'processing'
    settlement.payment_amount = amount
    settlement.save()

    # eSewa payment URL construction
    esewa_url = "https://esewa.com.np/epay/main"
    params = {
        'amt': str(amount),
        'pdc': '0',  # Product delivery charge
        'psc': '0',  # Product service charge
        'txAmt': '0',  # Tax amount
        'tAmt': str(amount),  # Total amount
        'pid': f'settlement_{settlement.id}',
        'scd': settings.ESEWA_MERCHANT_ID,
        'su': request.build_absolute_uri(reverse('payment_success')),
        'fu': request.build_absolute_uri(reverse('payment_cancel')),
    }

    payment_url = esewa_url + '?' + '&'.join([f'{k}={v}' for k, v in params.items()])

    return JsonResponse({'payment_url': payment_url})


# Khalti Integration (Nepal)
@login_required
@require_POST
def initiate_khalti_payment(request, settlement_id):
    """Initiate Khalti payment for settlement."""
    settlement = get_object_or_404(Settlement, id=settlement_id)

    # Validate permissions and settlement status
    if not (settlement.exit_request.booking.tenant == request.user or
            settlement.exit_request.booking.property.landlord == request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)

    if settlement.status != 'completed':
        return JsonResponse({'error': 'Settlement not completed'}, status=400)

    amount = settlement.net_payable_to_owner if settlement.net_payable_to_owner > 0 else settlement.net_refund_to_tenant
    if amount <= 0:
        return JsonResponse({'error': 'No payment required'}, status=400)

    # Update settlement
    settlement.payment_gateway = 'khalti'
    settlement.payment_status = 'processing'
    settlement.payment_amount = amount
    settlement.save()

    # Khalti API call would go here
    # For now, return a placeholder response
    return JsonResponse({
        'message': 'Khalti integration placeholder - implement Khalti API call',
        'amount': str(amount),
        'settlement_id': settlement.id
    })