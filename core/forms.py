from django import forms
from .models import Locality


GUEST_MAX_CITIES = 3
AUTH_USER_MAX_CITIES = 10
MIN_CITIES = 2


class CityFilterForm(forms.Form):
    region = forms.ChoiceField(
        choices = [],
        required = False,
        label = "Регион",
        widget = forms.Select(attrs={"class": "form-select"})
    )
    population_min = forms.IntegerField(
        required = False,
        label = "Население от",
        widget = forms.NumberInput(attrs={"class": "form-control", "placeholder": "1000"})
    )
    population_max = forms.IntegerField(
        required = False,
        label = "Население до",
        widget = forms.NumberInput(attrs={"class": "form-control", "placeholder": "100000"})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        regions = Locality.objects.values_list('region', flat=True).distinct()
        self.fields['region'].choices = [('', 'Любой регион')] + [(r, r) for r in regions]

    def clean(self):
        cleaned_data = super().clean()
        pop_min = cleaned_data.get('population_min')
        pop_max = cleaned_data.get('population_max')
        
        if pop_min and pop_max and pop_min > pop_max:
            raise forms.ValidationError("Минимальное население не может быть больше максимального")
        
        return cleaned_data
    

class ComparisonForm(forms.Form):
    cities = forms.ModelMultipleChoiceField(
        queryset=Locality.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        label="Города для сравнения",
        required=True
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_cities(self):
        cities = self.cleaned_data['cities']
        
        if self.user and self.user.is_authenticated:
            max_cities = AUTH_USER_MAX_CITIES
        else:
            max_cities = GUEST_MAX_CITIES
        
        if len(cities) < MIN_CITIES:
            raise forms.ValidationError("Выберите минимум 2 города для сравнения")
        if len(cities) > max_cities:
            raise forms.ValidationError(f"Можно выбрать не более {max_cities} городов!")
        
        return cities