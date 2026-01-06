from django.shortcuts import render,redirect
from core.models import Locality
from .forms import CityFilterForm, ComprasionForm
from django.contrib import messages


def home_view(request):
    context = {
        'title': 'ГородИндекс',
        'message': 'Сервис оценки инвестиционного потенциала малых городов РФ'
    }
    return render(request, 'core/home.html', context)

def main_view(request):
    # Создаём форму на основе GET-параметров
    form = CityFilterForm(request.GET or None)
    cities = Locality.objects.filter(is_active=True).select_related('infrastructure')
    
    # Применяем фильтры, если форма валидна
    if form.is_valid():
        if form.cleaned_data['region']:
            cities = cities.filter(region=form.cleaned_data['region'])
        if form.cleaned_data['population_min']:
            cities = cities.filter(population__gte=form.cleaned_data['population_min'])
        if form.cleaned_data['population_max']:
            cities = cities.filter(population__lte=form.cleaned_data['population_max'])
    
    for city in cities:
        city._cached_index = city.calculate_inv_index()
    
    return render(request, 'core/main.html', {
        'form': form,
        'cities': cities
    })

def compare_cities(request):
    if request.method=="POST":
        form=ComprasionForm(request.POST)
        if form.is_valid():
            cities=form.cleaned_data['cities']
            categories=['Economics','Demography','Infrasrtucture']
            plot_data=[]

            for city in cities:
                eco=city.economics.order_by('-year').first()
                if not eco:
                    continue

                eco_score = min(eco.ndfl_per_capita / eco.ndfl_median(city.region), 1.5)    
                unemployment = eco.unemployment_rate
                demo_score = max(0, 1 - unemployment / 100)    
                if hasattr(city, 'infrastructure'):
                    infra_score = city.infrastructure.infra_score(city.region)  
                pop_k = city.population/1000
                infra = getattr(city, 'infrastructure', None)
                plot_data.append({
                    'city':city.city,
                    'score': [eco_score,demo_score, infra_score],
                    'ndfl_pc':eco.ndfl_per_capita,
                    'unemployment':eco.unemployment_rate,
                    'schools_per_1k':infra.schools/pop_k,
                    'gas_per_1k':infra.gas_stations/pop_k,
                    'bus_per_1k':infra.bus_stops/pop_k,
                    'index':city.calculate_inv_index()
                })

            return render(request, 'core/compare.html',{
                'cities':cities,
                'plot_data':plot_data,
                'categories': categories
            })
        else:
            messages.error(request,"Error: " + "; ".join(form.errors['cities']))
            return redirect('main')
    
    return redirect('main')