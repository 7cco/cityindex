from django.db import models
from django.core.validators import MinValueValidator

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