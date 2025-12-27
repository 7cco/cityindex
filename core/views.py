from django.shortcuts import render

def home_view(request):
    # Пока просто текст — позже заменим на данные из БД
    context = {
        'title': 'ГородИндекс',
        'message': 'Сервис оценки инвестиционного потенциала малых городов РФ'
    }
    return render(request, 'core/home.html', context)