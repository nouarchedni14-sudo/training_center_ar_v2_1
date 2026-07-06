from django.core.management.base import BaseCommand

from sync_core.models import CentralUpdateRelease, CentralUpdateCheckLog


class Command(BaseCommand):
    help = "عرض حالة التحديثات المركزية وفحوصات المكاتب."

    def handle(self, *args, **options):
        self.stdout.write("Central updates:")
        for item in CentralUpdateRelease.objects.order_by("-published_at", "-created_at")[:20]:
            target = "ALL" if item.rollout_all_offices else ",".join(item.allowed_office_ids or [])
            self.stdout.write(f"- {item.version} active={item.is_active} required={item.is_required} type={item.update_type} channel={item.channel} target={target}")
        self.stdout.write("")
        self.stdout.write("Recent update checks:")
        for check in CentralUpdateCheckLog.objects.order_by("-created_at")[:20]:
            self.stdout.write(f"- {check.created_at:%Y-%m-%d %H:%M} {check.office_id} current={check.current_version or '-'} offered={check.offered_version or '-'} has_update={check.has_update}")
