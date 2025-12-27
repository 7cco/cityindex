from django.contrib import admin
from .models import Locality, EconomicData, InfrastructureData


@admin.register(Locality)
class LocalityAdmin(admin.ModelAdmin):
    list_display = ('city', 'region', 'population', 'oktmo_code')
    search_fields = ('city', 'region')
    list_filter = ('region',)

@admin.register(EconomicData)
class EconomicDataAdmin(admin.ModelAdmin):
    list_display = ('locality', 'year', 'ndfl_total', 'unemployment_rate')
    search_fields = ('locality__city', 'locality__region')
    list_filter = ('year', 'locality__region')

@admin.register(InfrastructureData)
class InfrastructureDataAdmin(admin.ModelAdmin):
    list_display = ('locality', 'schools', 'gas_stations', 'bus_stops')
    search_fields = ('locality__city',)
    list_filter = ('locality__region',)