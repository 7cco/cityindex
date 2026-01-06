from django.db import models
from django.core.validators import MinValueValidator
from django.db.models import Avg, F

class Locality(models.Model):
    city = models.CharField(
        max_length=150,
        verbose_name="Название города",
    )
    region = models.CharField(
        max_length=100,
        verbose_name="Субъект РФ",
    )
    population = models.PositiveIntegerField(
        verbose_name="Население",
        validators=[MinValueValidator(1)],
    )
    oktmo_code = models.CharField(
        max_length=11,
        unique=True,
        verbose_name="Код ОКТМО",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Участвует в рейтинге",
        help_text="Поле для отладки, исключение 'некорректных городов'"
    )

    class Meta:
        verbose_name = "Город"
        verbose_name_plural = "Города"
        ordering = ['-population']

    def __str__(self):
        return f"{self.city} ({self.region})"
    

    def calculate_inv_index(self):
        eco = self.economics.order_by('-year').first()
        if not eco:
            return 0.0
        eco_score = min(eco.ndfl_per_capita / eco.ndfl_median(self.region), 1.5)    
        unemployment = eco.unemployment_rate or 5.0
        demo_score = max(0, 1 - unemployment / 100)    
        infra_score = 0.0
        if hasattr(self, 'infrastructure'):
            infra_score = self.infrastructure.infra_score(self.region)        
        return min(0.5 * eco_score + 0.3 * demo_score + 0.2 * infra_score, 1.0)

class EconomicData(models.Model):
    locality = models.ForeignKey(
        Locality,
        on_delete=models.CASCADE,
        related_name='economics',
        verbose_name="Город"
    )
    year = models.PositiveSmallIntegerField(
        verbose_name="Год данных",
    )
    ndfl_total = models.BigIntegerField(
        verbose_name="НДФЛ всего (руб.)",
    )
    unemployment_rate = models.FloatField(
        null=True,
        blank=True,
        verbose_name="Безработица (%)",
    )

    class Meta:
        verbose_name = "Экономические данные"
        verbose_name_plural = "Экономические данные"
        unique_together = ['locality', 'year']
        ordering = ['-year']

    def __str__(self):
        return f"{self.locality.city} ({self.year} г.)"

    @property
    def ndfl_per_capita(self):
        """Расчёт НДФЛ на душу населения"""
        if self.locality.population > 0:
            return self.ndfl_total / self.locality.population
        return 0

    @property
    def ndfl_per_capita_display(self):
        return f"{self.ndfl_per_capita:,.0f} ₽".replace(",", " ")
    
    def ndfl_median(self,region_name):
        ndfl_agg=EconomicData.objects.filter(
            locality__region=region_name,
            locality__is_active=True).aggregate(
                avg_ndfl=Avg('ndfl_total'),
                avg_pop=Avg('locality__population')
            )
        return ndfl_agg['avg_ndfl']/ndfl_agg['avg_pop']

class InfrastructureData(models.Model):
    locality = models.OneToOneField(
        Locality,
        on_delete=models.CASCADE,
        related_name='infrastructure',
        verbose_name="Город"
    )
    schools = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Школы",
    )
    gas_stations = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="АЗС",
    )
    bus_stops = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Остановки ОТ",
    )

    class Meta:
        verbose_name = "Инфраструктура"
        verbose_name_plural = "Инфраструктура"

    def __str__(self):
        return f"Инфраструктура: {self.locality.city}"
    
    @classmethod
    def infra_median(cls,region_name):
        qs=cls.objects.filter(
            locality__region=region_name,
            locality__is_active=True
        ).annotate(
            schools_per_1k=F('schools')*1000/F('locality__population'),
            gas_per_1k=F('gas_stations')*1000/F('locality__population'),
            bus_per_1k=F('bus_stops')*1000/F('locality__population')
        )
        agg=qs.aggregate(
            avg_schools=Avg('schools_per_1k'),
            avg_gas=Avg('gas_per_1k'),
            avg_bus=Avg('bus_per_1k')
            )
        
        return{
            'schools_per_1k': agg['avg_schools'] or 0.4,
            'gas_stations_per_1k': agg['avg_gas'] or 0.1,
            'bus_stops_per_1k': agg['avg_bus'] or 2
        }

    def infra_score(self,region_name):
        regional_medians=self.infra_median(region_name)
        pop_k=max(self.locality.population/1000,1)

        ratios={'schools':self.schools/pop_k/regional_medians['schools_per_1k'],
                'gas_stations':self.gas_stations/pop_k/regional_medians['gas_stations_per_1k'],
                'bus_stops':self.bus_stops/pop_k/regional_medians['bus_stops_per_1k']
                }
        
        weights={'schools':0.4,'gas_stations':0.3,'bus_stops':0.3}
        score=0
        for key in ratios:
            ratio=min(ratios[key],1.5)
            score+=ratio*weights[key]
        
        return min(score,1.0)