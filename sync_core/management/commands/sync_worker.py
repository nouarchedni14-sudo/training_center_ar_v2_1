from django.core.management.base import BaseCommand, CommandError

from sync_core.worker import run_sync_loop, run_sync_once, validate_worker_ready


class Command(BaseCommand):
    help = "يرسل تغييرات SyncOutbox، يستقبل SyncInbox، ويطبق الأحداث حسب سياسة التعارضات."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="تنفيذ دورة واحدة فقط ثم الخروج.")
        parser.add_argument("--loop", action="store_true", help="التشغيل المستمر داخل نفس العملية.")
        parser.add_argument("--interval", type=int, default=None, help="الفاصل بالثواني عند استعمال --loop.")
        parser.add_argument("--push-only", action="store_true", help="إرسال فقط دون استقبال أو تطبيق.")
        parser.add_argument("--pull-only", action="store_true", help="استقبال فقط دون إرسال، ثم تطبيق ما تم استقباله إلا إذا استعملت --no-apply.")
        parser.add_argument("--no-apply", action="store_true", help="لا تطبق أحداث SyncInbox على الجداول المحلية.")
        parser.add_argument("--apply-only", action="store_true", help="تطبيق أحداث SyncInbox الموجودة محليًا فقط دون اتصال بالخادم المركزي.")
        parser.add_argument("--force", action="store_true", help="تجاوز CENTRAL_SYNC_ENABLED/SYNC_WORKER_ENABLED للاختبار فقط.")
        parser.add_argument("--check", action="store_true", help="فحص الإعدادات فقط دون إرسال أو استقبال.")

    def handle(self, *args, **options):
        force = bool(options["force"])
        apply = not bool(options["no_apply"])

        if options["push_only"] and options["pull_only"]:
            raise CommandError("لا يمكن استعمال --push-only و --pull-only معًا.")
        if options["apply_only"] and (options["push_only"] or options["pull_only"]):
            raise CommandError("لا تستعمل --apply-only مع --push-only أو --pull-only.")

        if options["apply_only"]:
            try:
                from sync_core.worker import apply_inbox_events
                result = apply_inbox_events()
                self.stdout.write(self.style.SUCCESS("تم تطبيق أحداث SyncInbox."))
                self.stdout.write(str(result))
                return
            except Exception as exc:
                raise CommandError(str(exc)) from exc

        push = not options["pull_only"]
        pull = not options["push_only"]
        if options["push_only"]:
            apply = False

        try:
            identity = validate_worker_ready(force=force)
            if options["check"]:
                self.stdout.write(self.style.SUCCESS("إعدادات عامل المزامنة صحيحة."))
                self.stdout.write(f"OFFICE_ID={identity.office_id}")
                self.stdout.write(f"SERVER_ID={identity.server_id}")
                self.stdout.write(f"CENTRAL_URL={identity.central_url}")
                self.stdout.write(f"APPLY_INBOX={apply}")
                return

            if options["loop"] and not options["once"]:
                self.stdout.write("بدء عامل المزامنة المستمر...")
                run_sync_loop(interval=options["interval"], push=push, pull=pull, apply=apply, force=force, stdout=self.stdout)
                return

            result = run_sync_once(push=push, pull=pull, apply=apply, force=force)
            self.stdout.write(self.style.SUCCESS("تمت دورة المزامنة."))
            self.stdout.write(str(result))
        except Exception as exc:
            raise CommandError(str(exc)) from exc
