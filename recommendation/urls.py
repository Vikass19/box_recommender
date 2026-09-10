from django.urls import path

from recommendation.views import RecommendBoxView

urlpatterns = [
    path("recommend-box/", RecommendBoxView.as_view(), name="recommend-box"),
]
