from django.urls import path
from .views import OptimizeRouteView, IndexView

urlpatterns = [
    path('', IndexView.as_view(), name='index'),
    path('optimize/', OptimizeRouteView.as_view(), name='optimize_route'),
] 