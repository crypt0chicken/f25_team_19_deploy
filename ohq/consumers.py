from channels.generic.websocket import WebsocketConsumer
from asgiref.sync import async_to_sync
from django.contrib.auth.models import User
from ohq.models import Account, AccountEntry, Queue
from django.utils import timezone
import json


class QueueConsumer(WebsocketConsumer):
    group_name = 'ohq_queue_group'
    channel_name = 'ohq_queue_channel'

    user = None
    account = None
    queue = None

    def is_staff(self):
        if not self.account or not self.queue:
            return False
        return self.account.isAdmin or self.queue.allowedStaff.filter(id=self.account.id).exists()

    def connect(self):
        self.id = self.scope['url_route']['kwargs']['id']
        self.group_name = QueueConsumer.group_name + f'_{self.id}'
        async_to_sync(self.channel_layer.group_add)(
            self.group_name, self.channel_name
        )

        self.accept()

        if not self.scope["user"].is_authenticated:
            self.send_error(f'You must be logged in')
            self.close()
            return
        
        self.user = self.scope["user"]
        try:
            self.account = Account.objects.get(user = self.user)
        except Account.DoesNotExist:
            self.send_error('Your OHQ account does not exist.')
            self.close()
            return

        try:
            self.queue = Queue.objects.get(id=self.id)
        except Queue.DoesNotExist:
            self.send_error(f"queue {self.id} does not exist")
            self.close()
            return

        # if not self.scope["user"].email.endswith("@andrew.cmu.edu"):
        #     self.send_error(f'You must be logged with Andrew identity')
        #     self.close()
        #     return            

        self.broadcast_queue_state()
        
        # Send user their specific account ID
        self.send(text_data=json.dumps({
            'type': 'connection_established',
            'my_account_id': self.account.id
        }))

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)(
            self.group_name, self.channel_name
        )

    def receive(self, **kwargs):
        if 'text_data' not in kwargs:
            self.send_error('you must send text_data')
            return

        try:
            data = json.loads(kwargs['text_data'])
        except json.JSONDecodeError:
            self.send_error('invalid JSON sent to server')
            return

        if 'action' not in data:
            self.send_error('action property not sent in JSON')
            return

        action = data['action']

        match action:
        # STUDENT ACTIONS
            case 'ask-question':
                self.received_ask_question(data)
            case 'leave-queue':
                self.received_leave_queue(data)
            case 'unfreeze': 
                self.received_unfreeze(data)
        # COURSE STAFF ACTIONS
            case 'freeze':
                self.received_update_status(data, AccountEntry.STATUS_FROZEN)
            case 'help':
                self.received_update_status(data, AccountEntry.STATUS_HELPING)
            case 'finish-help':
                self.received_remove_entry(data)
            case 'toggle-queue':
                self.received_toggle_queue(data)
            case 'send-announcement': 
                self.received_send_announcement(data)
            case 'freeze-all': 
                self.received_freeze_all(data)
            case _:
                self.send_error(f'Invalid action property: "{action}"')

    # Currently only makes sure that isOpen status is up to date.
    def queue_update(self, event):
        if 'model_data' not in event: return
        model_data = event['model_data']
        if 'queue-status' in model_data:
            self.queue.isOpen = model_data['queue-status']
        if 'queue-publicity' in model_data:
            self.queue.isPublic = model_data['queue-publicity']
            if not self.queue.isPublic: # refresh entire queue
                self.queue = Queue.objects.get(id=self.queue.id)
                # check whether user should be redirected to home
                is_staff = self.queue.allowedStaff.filter(id=self.account.id).exists() or self.account.isAdmin or self.account.user.is_superuser
                if (not (self.queue.allowedStudents.filter(id=self.account.id).exists() or is_staff)):
                    self.send(text_data=json.dumps({'type': 'redirect-home', 
                                                    'message': "You do not have permission to access this queue."}))
                else:
                    # try to promote/demote user
                    self.send(text_data=json.dumps({'type': 'update-staff-status',
                                                    'isStaff': is_staff}))


    def queue_delete(self, event):
        self.send(text_data=json.dumps({'type': 'queue-deleted'}))

    def refresh_account_entries(self, event):
        self.broadcast_queue_state()

    def received_ask_question(self, data):
        if 'text' not in data:
            self.send_error('"text" property not sent in JSON')
            return
        
        if not self.queue.isOpen:
            self.send_error('The queue is closed. You cannot join at this time.')
            return

        # Check if user is already in this queue
        if AccountEntry.objects.filter(account=self.account, queue=self.queue).exists():
            self.send_error('You are already on this queue.')
            return

        AccountEntry.objects.create(
            joinTime=timezone.now(),
            account=self.account,
            queue=self.queue,
            question=data['text'],
            status=AccountEntry.STATUS_WAITING
        )
        
        self.broadcast_queue_state()

    def received_leave_queue(self, data):
        try:
            entry = AccountEntry.objects.get(account=self.account, queue=self.queue)
            entry.delete()
        except AccountEntry.DoesNotExist:
            # User wasn't on queue, no action needed
            pass
        
        self.broadcast_queue_state()

    def received_unfreeze(self, data):
        try:
            entry = AccountEntry.objects.get(account=self.account, queue=self.queue)
            if entry.status == AccountEntry.STATUS_FROZEN:
                entry.status = AccountEntry.STATUS_WAITING
                entry.freezeTime = None
                entry.save()
                self.broadcast_queue_state()
        except AccountEntry.DoesNotExist:
            self.send_error('You are not on this queue.')

    def received_toggle_queue(self, data):
        if not self.is_staff():
            return self.send_error('You are not authorized to toggle this queue; you must be queue staff.')
                
        self.queue.isOpen = not self.queue.isOpen
        self.queue.save()
        self.broadcast_queue_state()

    def received_update_status(self, data, new_status):
        if not self.is_staff():
            return self.send_error('You are not authorized to perform this action; you must be queue staff.')
        
        if 'entry_id' not in data:
            return self.send_error('"entry_id" not sent in JSON.')
        
        try:
            entry = AccountEntry.objects.get(id=data['entry_id'], queue=self.queue)
            entry.status = new_status
            
            if new_status == AccountEntry.STATUS_HELPING:
                entry.helping_staff = self.account
                entry.freezeTime = None # Unfreeze if they were frozen
            elif new_status == AccountEntry.STATUS_FROZEN:
                entry.helping_staff = None
                entry.freezeTime = timezone.now() # Set the freeze time
            else:
                entry.helping_staff = None # e.g. if set back to waiting
                entry.freezeTime = None # Unfreeze
                
            entry.save()
        except AccountEntry.DoesNotExist:
            return self.send_error('This entry does not exist in this queue.')
        
        self.broadcast_queue_state()

    def received_remove_entry(self, data):
        if not self.is_staff():
            return self.send_error('You are not authorized to perform this action; you must be queue staff.')
        
        if 'entry_id' not in data:
            return self.send_error('"entry_id" not sent in JSON.')
        
        try:
            entry = AccountEntry.objects.get(id=data['entry_id'], queue=self.queue)
            entry.delete()
        except AccountEntry.DoesNotExist:
            return self.send_error('This entry does not exist in this queue.')
        
        self.broadcast_queue_state()

    def received_send_announcement(self, data):
        if not self.is_staff():
            return self.send_error('You are not authorized to send an announcement; you must be queue staff.')
        
        if 'text' not in data or not data['text']:
            return self.send_error('Announcement text cannot be empty.')
        
        self.broadcast_announcement(data['text'])

    def received_freeze_all(self, data):
        if not self.is_staff():
            return self.send_error('You are not authorized to freeze the queue; you must be queue staff.')

        # Find all waiting students and freeze them
        # Set freezeTime to None to prevent auto-unfreezing
        AccountEntry.objects.filter(
            queue=self.queue,
            status=AccountEntry.STATUS_WAITING
        ).update(
            status=AccountEntry.STATUS_FROZEN,
            freezeTime=None # This prevents auto-unfreeze
        )
        
        self.broadcast_queue_state()

    def send_error(self, error_message):
        self.send(text_data=json.dumps({'error': error_message}))

    # This function will broadcast everything related to the queue state.
    def broadcast_queue_state(self):
        timeout_seconds = self.queue.freeze_timeout
        if timeout_seconds > 0: # Only run if auto-unfreeze is enabled
            cutoff_time = timezone.now() - timezone.timedelta(seconds=timeout_seconds)
            stale_entries = AccountEntry.objects.filter(
                queue=self.queue,
                status=AccountEntry.STATUS_FROZEN,
                freezeTime__lt=cutoff_time # Only select entries with a non-null freezeTime
            )
            # Update them back to 'waiting'
            stale_entries.update(status=AccountEntry.STATUS_WAITING, freezeTime=None)

        async_to_sync(self.channel_layer.group_send)(
            self.group_name,
            {
                'type': 'broadcast_event',
                'message': {
                    'queue-status': self.queue.isOpen,
                    'students': AccountEntry.get_all_students(self.id),
                    'queue_freeze_timeout': self.queue.freeze_timeout,
                },
            }
        )

    def broadcast_event(self, event):
        self.send(text_data=json.dumps(event['message']))

    def broadcast_announcement(self, announcement_text):
        async_to_sync(self.channel_layer.group_send)(
            self.group_name,
            {
                'type': 'announcement_event', # This type will be handled by announcement_event
                'message': {
                    'type': 'announcement', # This type will be read by the client
                    'message': announcement_text
                },
            }
        )

    # This handler is called when a message is received from the group
    # with type 'announcement_event'
    def announcement_event(self, event):
        # Send the message payload directly to the client
        self.send(text_data=json.dumps(event['message']))


class QueueListConsumer(WebsocketConsumer):
    group_name = 'ohq_queue_list_group'
    channel_name = 'ohq_queue_listchannel'

    def connect(self):
        self.group_name = QueueListConsumer.group_name
        async_to_sync(self.channel_layer.group_add)(
            self.group_name, self.channel_name
        )

        self.accept()

        if not self.scope["user"].is_authenticated:
            self.send_error(f'You must be logged in')
            self.close()
            return

        # if not self.scope["user"].email.endswith("@andrew.cmu.edu"):
        #     self.send_error(f'You must be logged with Andrew identity')
        #     self.close()
        #     return            

        self.user = self.scope["user"]
        try:
            self.account = Account.objects.get(user = self.user)
        except Account.DoesNotExist:
            self.send_error('Your OHQ account does not exist.')
            self.close()
            return

        self.last_sort_type = 'name' # what this user has their courses sorted by
        self.query = '' # current query, if any
        self.broadcast_queue_list_state()

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)(
            self.group_name, self.channel_name
        )

    def queue_add(self, event):
        # re-broadcast whatever the main queue list section view is like
        if len(self.query) == 0:
            print("self.last_sort_type")
            self.received_sort({'type': self.last_sort_type})
        else:
            self.received_search({"query": self.query})

        self.broadcast_pinned()

    # A queue has been deleted
    def queue_delete(self, event):
        print('dele')
        if 'queueID' not in event:
            return
        self.send(text_data=json.dumps({'type': 'queue-delete', 'queueID': event['queueID']}))

    def receive(self, **kwargs):
        if 'text_data' not in kwargs:
            self.send_error('you must send text_data')
            return

        try:
            data = json.loads(kwargs['text_data'])
        except json.JSONDecodeError:
            self.send_error('invalid JSON sent to server')
            return

        if 'action' not in data:
            self.send_error('action property not sent in JSON')
            return

        if 'userID' not in data or not data['userID'].isdigit():
            self.send_error('userID property not sent in JSON')
            return

        action = data['action']
        userID = int(data['userID'])
        
        if userID != self.user.id: 
            print(repr(userID), repr(self.user.id))
            return

        # i.e. searching, filters, sorting, pinning...
        match action:
            case "pin":
                self.received_pin_queue(data)
            case "search":
                self.received_search(data)
            case "sort":
                self.received_sort(data)
            case _:
                self.send_error(f'Invalid action property: "{action}"')

    def received_pin_queue(self, data):
        if 'queueID' not in data:
            return self.send_error("queueID not sent in JSON")
        queueID = data['queueID']
        try:
            queue = Queue.objects.get(id=queueID)
        except Queue.DoesNotExist:
            return self.send_error("queue does not exist")
        
        # toggle whether queue is pinned or not by user
        if self.account.pinned.filter(id=queueID).exists():
            self.account.pinned.remove(queue)
        else:
            self.account.pinned.add(queue)
        self.account.save()
        self.broadcast_pinned()

    def received_search(self, data):
        if 'query' not in data:
            return self.send_error("queueID not sent in JSON")
        query = data['query']
        self.query = query
        if query == '':
            self.received_sort({"type": self.last_sort_type})
        else: 
            self.broadcast_search(query)

    def received_sort(self, data):
        if 'type' not in data:
            return self.send_error("sort type not sent in JSON")
        match data['type']:
            case "name":
                self.last_sort_type = "name"
                _, queues = Queue.get_queues(self.account, orderBy="queueName")
                self.broadcast_sort(queues)
            case "number":
                self.last_sort_type = "number"
                _, queues = Queue.get_queues(self.account, orderBy="courseNumber")
                self.broadcast_sort(queues)
            case "recent":
                self.last_sort_type = "recent"
                _, queues = Queue.get_queues(self.account, orderBy="recent")
                self.broadcast_sort(queues)
            case "none":
                self.last_sort_type = "name"
                self.broadcast_queue_list_state()

    def send_error(self, error_message):
        self.send(text_data=json.dumps({'error': error_message}))

    def broadcast_sort(self, queues):
        async_to_sync(self.channel_layer.group_send)(
            self.group_name,
            {
                'type': 'broadcast_event',
                'message': {
                    'userID': str(self.user.id),
                    'queues': queues,
                },
            }
        )

    def broadcast_search(self, query):
        results = Queue.get_queues_from_search(self.account, query)
        async_to_sync(self.channel_layer.group_send)(
            self.group_name,
            {
                'type': 'broadcast_event',
                'message': {
                    'userID': str(self.user.id),
                    'queues': results,
                },
            }
        )

    def broadcast_pinned(self):
        pinned, _ = Queue.get_queues(self.account)
        async_to_sync(self.channel_layer.group_send)(
            self.group_name,
            {
                'type': 'broadcast_event',
                'message': {
                    'userID': str(self.user.id),
                    'pinned': pinned,
                },
            }
        )

    def broadcast_queue_list_state(self):
        pinned, all_queues = Queue.get_queues(self.account)
        async_to_sync(self.channel_layer.group_send)(
            self.group_name,
            {
                'type': 'broadcast_event',
                'message': {
                    'userID': str(self.user.id),
                    'pinned': pinned,
                    'queues': all_queues,
                },
            }
        )

    def broadcast_event(self, event):
        self.send(text_data=json.dumps(event['message']))