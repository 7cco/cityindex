from django.shortcuts import render,redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from core.models import Locality
from .forms import CityFilterForm, ComparisonForm
from django.contrib import messages
import plotly.graph_objects as go
from django.contrib.auth.decorators import login_required
import csv
from django.http import HttpResponse


def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)  # Автоматический вход после регистрации
            return redirect('home')
    else:
        form = UserCreationForm()
    return render(request, 'core/register.html', {'form': form})

def home_view(request):
    cities = Locality.objects.filter(is_active=True).select_related('infrastructure')
    total_index = 0
    top_cities_list = []
    
    for city in cities:
        index = city.calculate_inv_index()
        total_index += index
        top_cities_list.append((city, index))
    
    top_cities_list.sort(key=lambda x: x[1], reverse=True)
    top_cities = [city for city, _ in top_cities_list[:5]]
    
    avg_index = total_index / len(cities)
    context = {
    'cities_count': len(cities),
    'regions_count': cities.values('region').distinct().count(),
    'avg_index': avg_index,
    'top_cities_with_index': top_cities_list[:5]
    }
    return render(request, 'core/home.html', context)

def main_view(request):
    form = CityFilterForm(request.GET or None)
    cities_queryset = Locality.objects.filter(is_active=True).select_related('infrastructure')

    if form.is_valid():
        if form.cleaned_data['region']:
            cities_queryset = cities_queryset.filter(region=form.cleaned_data['region'])
        if form.cleaned_data['population_min']:
            cities_queryset = cities_queryset.filter(population__gte=form.cleaned_data['population_min'])
        if form.cleaned_data['population_max']:
            cities_queryset = cities_queryset.filter(population__lte=form.cleaned_data['population_max'])

    # Рассчитываем индекс и сортируем
    cities_with_index = []
    for city in cities_queryset:
        index = city.calculate_inv_index()
        city.cached_index = index
        cities_with_index.append((city, index))

    cities_with_index.sort(key=lambda x: x[1], reverse=True)
    all_cities = [city for city, _ in cities_with_index]
    top_20 = all_cities[:20]

    return render(request, 'core/main.html', {
        'form': form,
        'top_20': top_20,
        'all_cities': all_cities,'show_full': request.GET.get('show') == 'all',
    })

def compare_cities(request):
    if request.method == "POST":
        form=ComparisonForm(request.POST, user=request.user)
        if form.is_valid():
            cities = form.cleaned_data['cities']
            categories = ['Экономика','Безработица','Инфраструктура']
            fig=go.Figure()

            for city in cities:
                eco = city.economics.order_by('-year').first()
                if not eco:
                    continue

                eco_score = min(eco.ndfl_per_capita / eco.ndfl_median(city.region), 1)    
                demo_score = 1 - eco.unemployment_rate / 100
                if hasattr(city, 'infrastructure'):
                    infra_score = city.infrastructure.infra_score(city.region)  

                fig.add_trace(go.Bar(
                    name = city.city,
                    x = categories,
                    y = [eco_score,demo_score, infra_score],
                    text = [f"{eco_score:.2f}",f"{demo_score:.2f}",f"{infra_score:.2f}"],
                    textposition = 'auto'
                ))
            fig.update_layout(
                title = "Сравнение компонентов инвестиционного индекса",
                barmode = 'group',
                yaxis = dict(range=[0, 1.5], title="Балл"),
                xaxis = dict(title="Компоненты индекса")
            )

            chart_html = fig.to_html(
                full_html = False,
                include_plotlyjs = 'cdn',
                config = {'displayModebar': False}
            )

            return render(request, 'core/compare.html',{
                'cities': cities,
                'chart_html': chart_html,
            })
        else:
            messages.error(request,"Error: " + "; ".join(form.errors['cities']))
            return redirect('main')
    
    return redirect('main')

@login_required
def export_cities_csv(request):
    # Создаём HTTP-ответ с типом content-type для CSV
    response = HttpResponse(content_type = 'text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="gorodindex_cities.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Город', 'Регион', 'Население', 'ОКТМО',
        'НДФЛ(тыс ₽)', 'Безработица (%)', 'Инвестиционный индекс'
    ])
    
    cities = Locality.objects.filter(is_active=True).select_related(
        'infrastructure'
    ).prefetch_related('economics')
    
    for city in cities:
        # Берём последние экономические данные
        eco = city.economics.order_by('-year').first()
        ndfl = eco.ndfl_total
        unemployment = eco.unemployment_rate
        index = city.calculate_inv_index()
        
        writer.writerow([
            city.city,
            city.region,
            city.population,
            city.oktmo_code,
            f"{ndfl:.0f}",
            unemployment,
            f"{index:.2f}"
        ])
    
    return response