from apps.catalog.models import Product

from . import client

BATCH = 50


def refresh_product_embeddings(queryset=None) -> int:
    qs = (queryset if queryset is not None else Product.objects.all()).select_related("category").prefetch_related(
        "part_numbers__brand", "fitments__vehicle_model"
    )
    products = list(qs)
    for i in range(0, len(products), BATCH):
        chunk = products[i : i + BATCH]
        vectors = client.embed([p.embedding_text() for p in chunk], task="embed_products")
        for product, vector in zip(chunk, vectors):
            product.embedding = vector
        Product.objects.bulk_update(chunk, ["embedding"])
    return len(products)
