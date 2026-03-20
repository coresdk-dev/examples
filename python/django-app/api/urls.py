"""URL configuration for the CoreSDK django-app example."""
from django.urls import path
from api import views

urlpatterns = [
    path("healthz",                views.healthz,          name="healthz"),
    path("me",                     views.me,               name="me"),
    path("products",               views.products,         name="products"),
    path("products/<int:pk>",      views.product_detail,   name="product-detail"),
    path("policy/check",           views.policy_check,     name="policy-check"),
]
