from django.shortcuts import render,redirect
from core.models import Locality
from .forms import CityFilterForm, ComprasionForm
from django.contrib import messages
import plotly.graph_objects as go


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
            fig=go.Figure()

            for city in cities:
                eco=city.economics.order_by('-year').first()
                if not eco:
                    continue

                eco_score = min(eco.ndfl_per_capita / eco.ndfl_median(city.region), 1)    
                demo_score = max(0, 1 - eco.unemployment_rate / 100)    
                if hasattr(city, 'infrastructure'):
                    infra_score = city.infrastructure.infra_score(city.region)  

                fig.add_trace(go.Bar(
                    name=city.city,
                    x=categories,
                    y=[eco_score,demo_score, infra_score],
                    text=[f"{eco_score:.2f}",f"{demo_score:.2f}",f"{infra_score:.2f}"],
                    textposition='auto'
                ))
            fig.update_layout(
                title="Compare components of inv index",
                barmode='group',
                yaxis=dict(range=[0, 1.5], title="Score"),
                xaxis=dict(title="Components of index")
            )

            chart_html = fig.to_html(
                full_html=False,
                include_plotlyjs='cdn',
                config={'displayModebar': False}
            )

            return render(request, 'core/compare.html',{
                'cities':cities,
                'chart_html': chart_html,
            })
        else:
            messages.error(request,"Error: " + "; ".join(form.errors['cities']))
            return redirect('main')
    
    return redirect('main')