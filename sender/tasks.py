# from celery import shared_task
# from django.utils import timezone
# from datetime import timedelta
# from django.conf import settings
#
#
# @shared_task
# def update_task_status():
#     now = timezone.now()
#     expired_tasks = Task.objects.filter(
#         deadline__lt=now, status__in=["created", "in_progress"]
#     )
#     updated_count = 0
#     for task in expired_tasks:
#         task.status = "expired"
#         task.save()
#         updated_count += 1
#     return f"Updated {updated_count} tasks"
