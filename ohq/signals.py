from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Account, Queue
from .consumers import QueueConsumer, QueueListConsumer
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

@receiver(post_save, sender=User)
def create_or_update_ohq_account(sender, instance, created, **kwargs):
    """
    Automatically create or update an OHQ Account when a User is created or saved.
    This ensures an Account exists and the email is synced.
    """
    if created:
        # Create a new Account
        nickname = f"{instance.first_name} {instance.last_name}".title()
        if len(nickname) == 0:
            nickname = instance.username
        Account.objects.create(
            user=instance, 
            email=instance.email,
            nickname=nickname
        )
    else:
        # Update existing Account if email differs
        try:
            account = Account.objects.get(user=instance)
            if account.email != instance.email:
                account.email = instance.email
                account.save()
        except Account.DoesNotExist:
            # This handles a rare case where a User exists without an Account
            nickname = f"{instance.first_name} {instance.last_name}".title()
            if len(nickname) == 0:
                nickname = instance.username
            Account.objects.create(
                user=instance, 
                email=instance.email,
                nickname=nickname
            )

@receiver(post_save, sender=Queue)
def queue_updated(sender, instance, created, **kwargs):
    """
    Handles issue of those viewing a queue not immediately learning of
    queue being opened/closed or otherwise updated
    """
    channel_layer = get_channel_layer()

    if created:
        # trigger entire home page to refresh for everyone
        print("Queue created!")
        group_name = QueueListConsumer.group_name
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'queue_add',
            }
        )
    else:
        # inform those who are vieiwng the queue that the queue has been updated
        group_name = QueueConsumer.group_name + f'_{instance.id}'
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'queue_update',
                'model_data': {
                    'queue-status': instance.isOpen,
                }
            }
        )

@receiver(post_delete, sender=Queue)
def queue_deleted(sender, instance, **kwargs):
    """
    When a queue is deleted, anyone currently viewing that queue
    should be redirected to the home page
    """
    channel_layer = get_channel_layer()

    # inform those that are viewing the queue that the queue has been deleted
    group_name = QueueConsumer.group_name + f'_{instance.id}'
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            'type': 'queue_delete',
        }
    )

    # inform those on the home page that the queue has been deleted
    group_name = QueueListConsumer.group_name
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            'type': 'queue_delete',
            'queueID': instance.id,
        }
    )