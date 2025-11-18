from django.shortcuts import render, get_object_or_404, redirect
from django.conf import settings
from django.contrib.auth.decorators import login_required
from ohq.models import Account, Queue, AccountEntry, QueueHistory
from ohq.forms import EditAccountForm, CreateQueueForm 

from django.urls import reverse_lazy, reverse
from allauth.account.views import EmailView
from allauth.account.forms import AddEmailForm
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount

from django.http import JsonResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.db.models import Q
import json
from ohq.forms import EditAccountForm
from datetime import datetime
from urllib.parse import urlencode

def index(request):
    print('/index')
    return render(request, 'ohq/home.html', {})

@login_required
def queue_list_action(request):
    print('/queue_list_action')
    _create_debug_queues()
    context = dict()
    account = get_object_or_404(Account, user=request.user)
    context['DEBUG'] = settings.DEBUG
    context['account'] = account 
    context['error'] = request.GET.get('error', None)
    return render(request, 'ohq/home.html', context)

@login_required
def queue_action(request, id):
    print('/queue_action')
    context = dict()
    account = get_object_or_404(Account, user=request.user)
    try:
        queue = Queue.objects.get(id=id)
    except Queue.DoesNotExist:
        # TODO: include some sort of error popup
        url = reverse('queue-list') 
        query_params = urlencode({'error': f"Queue {id} does not exist"})  # Add the error message as query param
        redirect_url = f"{url}?{query_params}"
        return redirect(redirect_url)
    
    # Check if user is staff for this queue or a site admin
    is_staff = queue.allowedStaff.filter(id=account.id).exists() or account.isAdmin or request.user.is_superuser
    
    context['queue'] = queue 
    context['queueID'] = queue.id
    context['queue_name'] = queue.queueName
    context['is_open'] = queue.isOpen
    context['description'] = queue.description
    context['DEBUG'] = settings.DEBUG
    context['is_staff'] = is_staff
    context['is_admin'] = account.isAdmin or request.user.is_superuser
    context['account'] = account 

    # keep track of user's recently viewed queues
    try:
        qh_old = QueueHistory.objects.get(account = account, queue = queue)
        qh_old.delete()
    except QueueHistory.DoesNotExist:
        pass
    qh = QueueHistory()
    qh.lastUsedTime = datetime.now()
    qh.account = account
    qh.queue = queue
    qh.save()
    return render(request, 'ohq/student-queue.html', context)

# Configuring settings for a queue
@login_required
def queue_settings_action(request, id):
    print('/queue_settings_action')
    
    queue = get_object_or_404(Queue, id=id)
    account = get_object_or_404(Account, user=request.user)

    # Authorization: Only site admins or superusers can access this page
    if not (account.isAdmin or request.user.is_superuser):
        return redirect('queue', id=id) # Redirect non-authorized

    if request.method == 'POST':
        if 'action_delete_queue' in request.POST:
            queue.delete()
            # Redirect to the homepage (queue list) after deletion.
            return redirect('queue-list')

    # Query for current staff to display
    current_staff = queue.allowedStaff.all().order_by('nickname')

    context = {
        'queue': queue,
        'current_staff': current_staff, 
        'DEBUG': settings.DEBUG,
        'account': account,
    }
    return render(request, 'ohq/queue-settings.html', context)

# --- Queue Creation View ---
@login_required
def queue_create_action(request):
    print('/queue_create_action')
    account = get_object_or_404(Account, user=request.user)

    # Authorization: Only site admins or superusers can create queues
    if not (account.isAdmin or request.user.is_superuser):
        return redirect('queue-list') # Redirect non-authorized

    if request.method == 'POST':
        form = CreateQueueForm(request.POST)
        if form.is_valid():
            new_queue = form.save()
            # Automatically add the creator as staff
            new_queue.allowedStaff.add(account)
            # Redirect to the new queue's settings page
            return redirect('queue-settings', id=new_queue.id)
    else:
        # GET request, show an empty form
        form = CreateQueueForm()

    context = {
        'form': form,
        'account': account,
        'DEBUG': settings.DEBUG,
    }
    return render(request, 'ohq/queue-create.html', context)


# --- User Control Panel View ---
@login_required
def user_control_panel(request):
    print('/user_control_panel')
    account = get_object_or_404(Account, user=request.user)
    error = ''

    # Handle nickname form submission
    if request.method == "POST" and 'action_save_nickname' in request.POST:
        form = EditAccountForm(request.POST, instance=account)
        if form.is_valid():
            form.save()
            return redirect('user-control-panel')
        else:
            form = EditAccountForm(instance=account)
            error = "Nickname must be non-empty"
    else:
        form = EditAccountForm(instance=account)

    # Get email data from allauth
    emailaddresses = EmailAddress.objects.filter(user=request.user)
    email_add_form = AddEmailForm(user=request.user)
    
    is_social_account = SocialAccount.objects.filter(user=request.user).exists()

    context = {
        'account': account,
        'form': form, # For the nickname form
        'emailaddresses': emailaddresses, # For allauth email list
        'email_add_form': email_add_form, # For allauth add email form
        'is_social_account': is_social_account, 
        'DEBUG': settings.DEBUG,
        'error': error,
    }
    return render(request, 'ohq/user_control_panel.html', context)

class CustomEmailView(EmailView):
    # Override the success_url to redirect back to our control panel
    success_url = reverse_lazy('user-control-panel')

# --- API View for User Search ---
@login_required
def user_search_api(request, id):
    print('/api_search_users')
    
    # Authorization
    account = get_object_or_404(Account, user=request.user)
    if not (account.isAdmin or request.user.is_superuser):
        return HttpResponseForbidden(json.dumps({'error': 'Not authorized.'}), content_type='application/json')
    
    queue = get_object_or_404(Queue, id=id)
    query_str = request.GET.get('q', '')

    if not query_str:
        return JsonResponse([], safe=False) # Return empty list if no query

    # Find accounts matching query that are NOT already staff
    results = Account.objects.filter(
        Q(nickname__icontains=query_str) | Q(email__icontains=query_str)
    ).exclude(
        staff__id=queue.id
    ).values(
        'id', 'nickname', 'email', 'isAdmin' 
    )[:10] # Limit to 10 results

    return JsonResponse(list(results), safe=False)

# --- API View for Managing Staff ---
@login_required
def manage_queue_staff_api(request, id):
    print('/api_manage_staff')
    
    # Authorization
    account = get_object_or_404(Account, user=request.user)
    if not (account.isAdmin or request.user.is_superuser):
        return HttpResponseForbidden(json.dumps({'error': 'Not authorized.'}), content_type='application/json')

    if request.method != 'POST':
        return HttpResponseBadRequest(json.dumps({'error': 'Must use POST.'}), content_type='application/json')

    try:
        data = json.loads(request.body)
        action = data.get('action')
        account_id_to_manage = data.get('account_id')
        
        if not action or not account_id_to_manage:
            raise ValueError('Missing action or account_id')

        queue = get_object_or_404(Queue, id=id)
        account_to_manage = get_object_or_404(Account, id=account_id_to_manage)

        if action == 'add':
            queue.allowedStaff.add(account_to_manage)
        elif action == 'remove':
            queue.allowedStaff.remove(account_to_manage)
        elif action == 'toggle_admin':
            is_admin = data.get('is_admin')
            if is_admin is None:
                raise ValueError('Missing is_admin status')
            
            account_to_manage.isAdmin = is_admin
            account_to_manage.save()
        else:
            raise ValueError('Invalid action')

        return JsonResponse({'status': 'ok'})

    except Exception as e:
        return HttpResponseBadRequest(json.dumps({'error': str(e)}), content_type='application/json')

# --- START: Site Admin Views ---
@login_required
def site_settings_action(request):
    print('/site_settings_action')
    account = get_object_or_404(Account, user=request.user)

    # Authorization: Only site admins or superusers can access this page
    if not (account.isAdmin or request.user.is_superuser):
        return redirect('queue-list') # Redirect non-authorized

    # GET request
    current_admins = Account.objects.filter(isAdmin=True).order_by('nickname')

    context = {
        'account': account,
        'current_admins': current_admins,
        'DEBUG': settings.DEBUG,
    }
    return render(request, 'ohq/site-settings.html', context)


@login_required
def site_search_api(request):
    print('/api_site_search_users')
    
    # Authorization
    account = get_object_or_404(Account, user=request.user)
    if not (account.isAdmin or request.user.is_superuser):
        return HttpResponseForbidden(json.dumps({'error': 'Not authorized.'}), content_type='application/json')
    
    query_str = request.GET.get('q', '')

    if not query_str:
        return JsonResponse([], safe=False) # Return empty list if no query

    # Find accounts matching query that are NOT already admins
    results = Account.objects.filter(
        Q(nickname__icontains=query_str) | Q(email__icontains=query_str)
    ).exclude(
        isAdmin=True
    ).values(
        'id', 'nickname', 'email'
    )[:10] # Limit to 10 results

    return JsonResponse(list(results), safe=False)


@login_required
def manage_site_admin_api(request):
    print('/api_manage_site_admin')
    
    # Authorization
    account = get_object_or_404(Account, user=request.user)
    if not (account.isAdmin or request.user.is_superuser):
        return HttpResponseForbidden(json.dumps({'error': 'Not authorized.'}), content_type='application/json')

    if request.method != 'POST':
        return HttpResponseBadRequest(json.dumps({'error': 'Must use POST.'}), content_type='application/json')

    try:
        data = json.loads(request.body)
        action = data.get('action')
        account_id_to_manage = data.get('account_id')
        
        if not action or not account_id_to_manage:
            raise ValueError('Missing action or account_id')

        account_to_manage = get_object_or_404(Account, id=account_id_to_manage)

        if action == 'add':
            account_to_manage.isAdmin = True
        elif action == 'remove':
            account_to_manage.isAdmin = False
        else:
            raise ValueError('Invalid action')
        
        account_to_manage.save()
        return JsonResponse({'status': 'ok'})

    except Exception as e:
        return HttpResponseBadRequest(json.dumps({'error': str(e)}), content_type='application/json')

def _create_debug_queues():
    # objects already exist. creating debug entry is unnecessary
    if len(Queue.objects.all()) > 0:
        return False
    queue = Queue()
    queue.queueName = "17-437"
    queue.courseNumber = '17437'
    queue.description = "This is a test queue with a very very very very very very long description"
    queue.save()

    queue2 = Queue()
    queue2.queueName = "Foundations of Software Engineering"
    queue2.courseNumber = '17313'
    queue2.description = "See Piazza for OH rules"
    queue2.save()
    
    queue3 = Queue()
    queue3.queueName = "15112"
    queue3.courseNumber = '15112'
    queue3.save()

    queue4 = Queue()
    queue4.queueName = "Distributed Systems"
    queue4.courseNumber = '15440'
    queue4.save()
