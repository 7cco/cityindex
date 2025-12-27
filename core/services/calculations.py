from django.db.models import Avg, F
from core.models import Locality, InfrastructureData

def calculate_infra_score(self, regional_medians):
        """
        Расчёт инфраструктурного балла (0.0 - 1.0)
        regional_medians: словарь с медианами по региону
        """
        # Нормируем на 1 тыс. жителей
        pop_k = max(self.locality.population / 1000, 1)
        
        ratios = {
            'schools': self.schools / pop_k / regional_medians['schools_per_1k'],
            'gas_stations': self.gas_stations / pop_k / regional_medians['gas_stations_per_1k'],
            'bus_stops': self.bus_stops / pop_k / regional_medians['bus_stops_per_1k']
        }
        
        # Веса компонентов
        weights = {
            'schools': 0.3,
            'gas_stations': 0.4,
            'bus_stops': 0.3
        }
        
        score = 0
        for key in ratios:
            # Ограничиваем на 1.5х медианы
            ratio = min(ratios[key], 1.5)
            score += ratio * weights[key]
        
        return min(score, 1.0)