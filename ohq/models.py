from django.contrib.auth.models import User # possibly unnecessary once we use Oauth?
from django.db import models

# Stores additional information about a user of the OHQ outside of 
# Django user class itself.
class Account(models.Model):
    isAdmin = models.BooleanField(default = False)
    email = models.EmailField(max_length = 25, blank = False) # andrew IDs are max 8 chars
    user = models.ForeignKey(User, default = None, on_delete = models.PROTECT, blank = False)
    nickname = models.CharField(max_length = 50, blank = True) # configurable in user settings

class Queue(models.Model):
    queueName = models.CharField(max_length = 50)
    courseNumber = models.CharField(max_length = 5, blank = False)
    description = models.CharField(max_length = 500, blank = True)
    isPublic = models.BooleanField(default = True)
    isOpen = models.BooleanField(default = False)
    freeze_timeout = models.IntegerField(default=600) # Frozen students will be placed back into the queue after this number of seconds
    
    allowedStaff = models.ManyToManyField(Account, related_name = 'staff')
    allowedStudents = models.ManyToManyField(Account, related_name = 'students')
    # field linking queues to who has pinned them
    pinnedQueues = models.ManyToManyField(Account, related_name = 'pinned')
    # field linking queues to who has hidden them
    hiddenQueues = models.ManyToManyField(Account, related_name = 'hidden')

    def get_staff(self):
        result = []
        all_entries = self.allowedStaff.all().order_by('-nickname')
        for entry in all_entries:
            entry_dict = {
                'id': entry.id,
                'nickname': entry.nickname,
                'email': entry.email,
            }
            result.append(entry_dict)
        return result
    
    def get_students(self):
        result = []
        all_entries = self.allowedStudents.all().order_by('-nickname')
        for entry in all_entries:
            entry_dict = {
                'id': entry.id,
                'nickname': entry.nickname,
                'email': entry.email,
            }
            result.append(entry_dict)
        return result
    
    @classmethod
    def get_queues(cls, account, orderBy='queueName'):
        pinned_list = []
        all_queues = []
        pinned = account.pinned.all()
        if orderBy == "recent":
            history = QueueHistory.objects.filter(account=account).order_by('-lastUsedTime')
            all_entries = [qh.queue for qh in history]
        else:
            all_entries = cls.objects.all().order_by(orderBy)
        for entry in all_entries:
            is_staff = entry.allowedStaff.filter(id=account.id).exists() or account.isAdmin or account.user.is_superuser
            if (not entry.isPublic and not (entry.allowedStudents.filter(id=account.id).exists()
                                            or is_staff)):
                continue
            entry_dict = {
                'id': entry.id,
                'name': entry.queueName,
                'number': entry.courseNumber[:2] + '-' + entry.courseNumber[2:],
                'description': entry.description,
                'status': entry.isOpen,
                'isPublic': entry.isPublic,
            }
            if entry in pinned:
                pinned_list.append(entry_dict)
            all_queues.append(entry_dict)
        return pinned_list, all_queues

    @classmethod
    def get_queues_from_search(cls, account, query):
        if query == '':
            return []
        all_queues = []
        # query either is prefix of queue name or course number
        # allow for people to search by course code with or without the -
        if len(query) <= 6 and query.replace('-', '').isdigit():
            query = query.replace('-', '')
        # allow for people to search by course code sans department
        if query.isdigit() and len(query) == 3:
            all_entries = cls.objects.filter(models.Q(queueName__istartswith=query) |
                                             models.Q(courseNumber__istartswith=query) |
                                             models.Q(courseNumber__iendswith=query)).order_by('queueName')
        else:
            all_entries = cls.objects.filter(models.Q(queueName__istartswith=query) |
                                             models.Q(courseNumber__istartswith=query)).order_by('queueName')
        for entry in all_entries:
            is_staff = entry.allowedStaff.filter(id=account.id).exists() or account.isAdmin or account.user.is_superuser
            if (not entry.isPublic and not (entry.allowedStudents.filter(id=account.id).exists()
                                            or is_staff)):
                continue
            entry_dict = {
                'id': entry.id,
                'name': entry.queueName,
                'number': entry.courseNumber[:2] + '-' + entry.courseNumber[2:],
                'description': entry.description,
                'status': entry.isOpen,
                'isPublic': entry.isPublic,
            }
            all_queues.append(entry_dict)
        return all_queues


# Class for students who have put themselves on the queue
class AccountEntry(models.Model):
    # Add choices for the new status field
    STATUS_WAITING = 'waiting'
    STATUS_HELPING = 'helping'
    STATUS_FROZEN = 'frozen'
    STATUS_CHOICES = [
        (STATUS_WAITING, 'Waiting'),
        (STATUS_HELPING, 'Being Helped'),
        (STATUS_FROZEN, 'Frozen'),
    ]

    joinTime = models.DateTimeField(blank = False)
    account = models.ForeignKey(Account, on_delete = models.PROTECT, blank = False)
    queue = models.ForeignKey(Queue, on_delete = models.CASCADE, blank = False) # <-- MODIFIED

    question = models.CharField(max_length=500, blank=True) # To store the student's question
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_WAITING)
    helping_staff = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, related_name='helping')
    freezeTime = models.DateTimeField(null=True, blank=True) # To store when the student was frozen

    @classmethod
    # expects that you do the error checking of whether queueID is valid earlier
    def get_all_students(cls, queueID):
        queue = Queue.objects.get(id = queueID)
        entries_list = []
        entries = AccountEntry.objects.filter(queue=queue).order_by('joinTime')
        for entry in entries:
            entry_dict = {
                'id': entry.id,
                'account_id': entry.account.id,
                'name': entry.account.nickname,
                'question': entry.question,
                'status': entry.status,
                'joinTime': entry.joinTime.isoformat(),
                'helping_staff_name': entry.helping_staff.nickname if entry.helping_staff else None,
                'freezeTime': entry.freezeTime.isoformat() if entry.freezeTime else None
            }
            entries_list.append(entry_dict)
        return entries_list
        

# Class for keeping track of when a queue has been last accessed by a user.
class QueueHistory(models.Model):
    lastUsedTime = models.DateTimeField(blank = False)
    account = models.ForeignKey(Account, blank = False, on_delete = models.PROTECT)
    queue = models.ForeignKey(Queue, blank = False, on_delete = models.CASCADE)