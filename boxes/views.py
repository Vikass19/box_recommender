from rest_framework import viewsets

from boxes.models import Box
from boxes.serializers import BoxSerializer


class BoxViewSet(viewsets.ModelViewSet):
    queryset = Box.objects.all()
    serializer_class = BoxSerializer
