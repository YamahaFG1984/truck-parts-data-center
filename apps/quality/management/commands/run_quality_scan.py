from django.core.management import BaseCommand

from apps.quality.scan import run_scan


class Command(BaseCommand):
    help = "Run all data quality rules and refresh completeness scores"

    def handle(self, *args, **opts):
        result = run_scan()
        self.stdout.write(f"Scanned {result['products']} products, found {result['issues']} issues")
