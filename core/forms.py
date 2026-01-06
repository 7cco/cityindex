from django import forms
from .models import Locality

class CityFilterForm(forms.Form):
    region = forms.ChoiceField(
        choices=[],
        required=False,
        label="Регион",
        widget=forms.Select(attrs={"class": "form-select"})
    )
    population_min = forms.IntegerField(
        required=False,
        label="Население от",
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "1000"})
    )
    population_max = forms.IntegerField(
        required=False,
        label="Население до",
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "100000"})
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
class ComprasionForm(forms.Form):
    cities=forms.ModelMultipleChoiceField(
        queryset=Locality.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        label="DO 5 gorodov",
        required=True
    )

    def clean_cities(self):
        cities=self.cleaned_data["cities"]
        if len(cities)>5:
            raise forms.ValidationError("Do 5")
        if len(cities)<2:
            raise forms.ValidationError("min 2")
        return cities