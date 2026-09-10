"""
factory_boy factories for building test fixtures without repeating
model instantiation boilerplate across test files (DRY in tests).
"""

import factory

from boxes.models import Box
from orders.models import Order, OrderItem
from products.models import Product


class ProductFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Product

    name = factory.Sequence(lambda n: f"Product {n}")
    sku = factory.Sequence(lambda n: f"SKU-{n:05d}")
    length_cm = "10.00"
    width_cm = "10.00"
    height_cm = "10.00"
    weight_kg = "1.000"
    is_active = True


class BoxFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Box

    name = factory.Sequence(lambda n: f"Box {n}")
    internal_length_cm = "30.00"
    internal_width_cm = "30.00"
    internal_height_cm = "30.00"
    max_weight_kg = "10.000"
    cost = "20.00"
    is_active = True


class OrderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Order

    reference = factory.Sequence(lambda n: f"ORD-{n:05d}")


class OrderItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OrderItem

    order = factory.SubFactory(OrderFactory)
    product = factory.SubFactory(ProductFactory)
    quantity = 1
