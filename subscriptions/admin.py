from django.contrib import admin
from .models import Plan, Subscription, NotifiedAlert


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'stripe_price_id', 'price')

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'status', 'stripe_subscription_id', 'current_period_end')
    list_filter = ('status', 'plan')
    search_fields = ('user__username', 'stripe_customer_id', 'stripe_subscription_id')

@admin.register(NotifiedAlert)
class NotifiedAlertAdmin(admin.ModelAdmin):
    list_display = ('user', 'nws_alert_id', 'saved_location', 'sent_at')
    list_filter = ('user',)
    search_fields = ('user__username', 'nws_alert_id')
    readonly_fields = ('sent_at',)
