from django.core.management import BaseCommand

from apps.ai.embeddings import refresh_product_embeddings
from apps.catalog.models import Product


class Command(BaseCommand):
    help = "Generate product embeddings for semantic search"

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="rebuild every product, not only missing ones")

    def handle(self, *args, **opts):
        qs = Product.objects.all() if opts["all"] else Product.objects.filter(embedding=None)
        self.stdout.write(f"Embedded {refresh_product_embeddings(qs)} products")
