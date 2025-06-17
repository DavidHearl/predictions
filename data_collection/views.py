from django.shortcuts import render, get_object_or_404, redirect
from .models import *
from .forms import *
from django.core.paginator import Paginator


def home(request):
    return render(request, "data_collection/home.html")


def players(request):
    query = request.GET.get("q", "")
    players_qs = Player.objects.all()
    if query:
        players_qs = players_qs.filter(name__icontains=query)
    total_count = Player.objects.count()
    filtered_count = players_qs.count()
    paginator = Paginator(players_qs, 200)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(
        request,
        "data_collection/players.html",
        {
            "players": page_obj.object_list,
            "page_obj": page_obj,
            "query": query,
            "total_count": total_count,
            "filtered_count": filtered_count,
        },
    )


def player_detail(request, pk):
    player = get_object_or_404(Player, pk=pk)
    return render(request, "data_collection/player_detail.html", {"player": player})


def player_edit(request, pk):
    player = get_object_or_404(Player, pk=pk)
    if request.method == "POST":
        form = PlayerForm(request.POST, instance=player)
        if form.is_valid():
            form.save()
            return redirect("player_detail", pk=player.pk)
    else:
        form = PlayerForm(instance=player)
    return render(request, "data_collection/player_edit.html", {"form": form, "player": player})