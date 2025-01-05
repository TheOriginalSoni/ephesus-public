from functools import wraps
from typing import Optional

from django import urls
from django.contrib.auth.decorators import login_required
from django.db.models import OuterRef, Sum, Subquery, Count, Q, F, DurationField, Max
from django.db.models.functions import Coalesce, Greatest
from django.http import Http404, JsonResponse
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import PermissionDenied
from datetime import timedelta

import django.urls as urls
import django.forms as forms

from .forms import (
    GuessForm,
    NewHuntForm,
    EditHuntForm,
    InviteMemberForm,
    PuzzleForm,
    RegisterForm,
    TeamForm,
    MarkdownTextarea,
)
from .models import Hunt, Team, Puzzle, Guess, ExtraGuessGrant, GuessResponse


def index(request):
    # user = request.user
    hunts = Hunt.objects.all()
    return render(
        request,
        "index.html",
        {
            "hunts": hunts,
        },
    )


def register(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect(urls.reverse("login"))
        else:
            return render(request, "register.html", {"form": form})
    else:
        form = RegisterForm()
        return render(request, "register.html", {"form": form})


@login_required
def new_hunt(request):
    if request.method == "POST":
        form = NewHuntForm(request.POST)
        if form.is_valid():
            hunt = form.save()

            # needs save before we can do many-to-many stuff
            hunt.organizers.add(request.user)

            return redirect(urls.reverse("view_hunt", args=[hunt.pk, hunt.slug]))
    else:
        form = NewHuntForm()

    return render(
        request,
        "new_hunt.html",
        {
            "form": form,
        },
    )


def get_team(user, hunt):
    if user.is_anonymous:
        return None

    try:
        return Team.objects.get(hunt=hunt, members=user)
    except Team.DoesNotExist:
        return None
    # bad if MultipleObjectsReturned


def redirect_from_hunt_id_to_hunt_id_and_slug(view_func):
    """Redirect from a URL with a hunt ID to a URL with a hunt ID and a slug

    Also redirect from a URL with a hunt ID and the wrong slug to the correct slug
    """

    @wraps(view_func)
    def wrapper(request, hunt_id: int, *args, slug: Optional[str] = None, **kwargs):
        hunt = get_object_or_404(Hunt, id=hunt_id)

        if hunt.slug != slug:
            view_name = urls.resolve(request.path_info).url_name
            return redirect(view_name, hunt.id, hunt.slug)

        return view_func(request, hunt_id, slug, *args, **kwargs)

    return wrapper


def force_url_to_include_both_hunt_and_puzzle_slugs(view_func):
    """Redirect from a URL missing a hunt or puzzle slug to one that includes them

    Also redirect from a URL where the ID doesn't match the slug to the correct URL
    """

    @wraps(view_func)
    def wrapper(
        request,
        hunt_id: int,
        puzzle_id: int,
        *args,
        hunt_slug: Optional[str] = None,
        puzzle_slug: Optional[str] = None,
        **kwargs
    ):
        hunt = get_object_or_404(Hunt, id=hunt_id)
        puzzle = get_object_or_404(Puzzle, hunt=hunt, id=puzzle_id)

        if hunt.slug != hunt_slug or puzzle.slug != puzzle_slug:
            view_name = urls.resolve(request.path_info).url_name
            return redirect(
                view_name,
                hunt_id=hunt.id,
                hunt_slug=hunt.slug,
                puzzle_id=puzzle.id,
                puzzle_slug=puzzle.slug,
            )

        return view_func(
            request,
            *args,
            hunt_id=hunt_id,
            hunt_slug=hunt_slug,
            puzzle_id=puzzle_id,
            puzzle_slug=puzzle_slug,
            **kwargs
        )

    return wrapper


@redirect_from_hunt_id_to_hunt_id_and_slug
def view_hunt(request, hunt_id: int, slug: Optional[str] = None):
    user = request.user
    hunt = get_object_or_404(Hunt, id=hunt_id)
    team = get_team(user, hunt)
    is_organizer = user.is_authenticated and hunt.organizers.filter(id=user.id).exists()

    if is_organizer:
        puzzles = hunt.puzzles.all()
    elif team:
        puzzles = team.unlocked_puzzles_with_solved()
    else:
        puzzles = hunt.public_puzzles()

    puzzles = puzzles.annotate(
        solve_count=Count("guesses", filter=Q(guesses__correct=True)),
        guess_count=Count("guesses"),
    )

    return render(
        request,
        "view_hunt.html",
        {
            "hunt": hunt,
            "team": team,
            "puzzles": puzzles.order_by("order"),
            "is_organizer": is_organizer,
        },
    )


@redirect_from_hunt_id_to_hunt_id_and_slug
def leaderboard(request, hunt_id: int, slug: Optional[str] = None):
    user = request.user
    hunt = get_object_or_404(Hunt, id=hunt_id)
    team = get_team(user, hunt)
    is_organizer = user.is_authenticated and hunt.organizers.filter(id=user.id).exists()

    if hunt.leaderboard_style == Hunt.LeaderboardStyle.HIDDEN and not is_organizer:
        raise Http404()

    # for the sake of simplicity, assume teams won't end up with two correct guesses for a puzzle
    if hunt.is_archived():
        correct_guess_Q = Q(guesses__correct=True, guesses__time__lte=hunt.end_time)
        teams = hunt.teams.filter(creation_time__lte=hunt.end_time)
    else:
        correct_guess_Q = Q(guesses__correct=True)
        teams = hunt.teams

    teams = teams.annotate(
        score=Coalesce(Sum("guesses__puzzle__points", filter=correct_guess_Q), 0),
        solve_count=Count("guesses", filter=correct_guess_Q),
        last_solve=Max(
            "guesses__time",
            filter=correct_guess_Q
            & (
                Q(guesses__puzzle__points__gt=0)
                | Q(guesses__puzzle__progress_points__gt=0)
            ),
        ),
        created_or_start=Greatest(F("creation_time"), hunt.start_time),
        solve_time=Greatest(
            Coalesce(F("last_solve"), F("created_or_start")) - F("created_or_start"),
            timedelta(seconds=0),
            output_field=DurationField(),
        ),
    )

    if hunt.leaderboard_style == Hunt.LeaderboardStyle.SPEEDRUN:
        teams = teams.order_by("-score", "solve_time", "last_solve")
    else:
        teams = teams.order_by("-score", "-solve_count", "last_solve")

    return render(
        request,
        "leaderboard.html",
        {
            "hunt": hunt,
            "team": team,
            "teams": teams,
            "is_organizer": is_organizer,
        },
    )


def normalize_answer(answer):
    return "".join(c for c in answer if c.isalnum()).upper()


@force_url_to_include_both_hunt_and_puzzle_slugs
def view_puzzle(
    request,
    hunt_id: int,
    puzzle_id: int,
    hunt_slug: Optional[str] = None,
    puzzle_slug: Optional[str] = None,
):
    user = request.user
    hunt = get_object_or_404(Hunt, id=hunt_id)
    puzzle = get_object_or_404(Puzzle, hunt=hunt, id=puzzle_id)
    team = get_team(user, hunt)

    is_organizer = user.is_authenticated and hunt.organizers.filter(id=user.id).exists()

    if not is_organizer and not puzzle.is_viewable_by(team):
        raise Http404("Puzzle is not viewable by team (or the public)")

    if team:
        solved = Guess.objects.filter(puzzle=puzzle, team=team, correct=True).exists()

        guess_limit = hunt.guess_limit
        guesses_limited = bool(guess_limit)

        if guesses_limited:
            try:
                grant = ExtraGuessGrant.objects.get(team=team, puzzle=puzzle)
                guess_limit += grant.extra_guesses
            except ExtraGuessGrant.DoesNotExist:
                pass

            guesses_remaining = (
                guess_limit
                - Guess.objects.filter(
                    puzzle=puzzle, team=team, counts_as_guess=True
                ).count()
            )
            guesses_at_limit = guesses_remaining <= 0
        else:
            # hunt doesn't limit guesses
            guesses_remaining = 0
            guesses_at_limit = False
    else:
        solved = False
        guesses_limited = None
        guesses_remaining = 0
        guesses_at_limit = False

    if request.method == "POST":
        guess_form = GuessForm(request.POST)

        if solved:
            error = "You have already solved the puzzle!"
        elif not guesses_at_limit and guess_form.is_valid():
            guess_text = normalize_answer(guess_form.cleaned_data["guess"])
            if Guess.objects.filter(
                guess=guess_text, team=team, puzzle=puzzle
            ).exists():
                guess_form.add_error("guess", "You have already guessed that answer!")
            else:
                guess_responses = puzzle.guess_responses.all()
                response = ""
                counts_as_guess = True
                for gr in guess_responses:
                    if guess_text == normalize_answer(gr.guess):
                        response = gr.response
                        counts_as_guess = False
                guess = Guess(
                    guess=guess_text,
                    team=team,
                    user=user,
                    puzzle=puzzle,
                    response=response,
                    counts_as_guess=counts_as_guess,
                    correct=(guess_text == normalize_answer(puzzle.answer)),
                )
                guess.save()

                if guess.correct:
                    solved = True

                return redirect(urls.reverse("view_puzzle", args=[hunt_id, puzzle_id]))
    else:
        guess_form = GuessForm()

    show_solution = False
    if puzzle.solution_url != "":
        if (
            hunt.solution_style == Hunt.SolutionStyle.VISIBLE
            or is_organizer
            or (hunt.solution_style == Hunt.SolutionStyle.AFTER_SOLVE and solved)
            or (
                hunt.solution_style == Hunt.SolutionStyle.AFTER_SOLVE
                and hunt.is_archived()
            )
        ):
            show_solution = True

    return render(
        request,
        "view_puzzle.html",
        {
            "hunt": hunt,
            "team": team,
            "puzzle": puzzle,
            "solved": solved,
            "show_solution": show_solution,
            "guesses_limited": guesses_limited,
            "guesses_remaining": guesses_remaining,
            "guesses_at_limit": guesses_at_limit,
            "guesses": Guess.objects.filter(team=team, puzzle=puzzle).order_by("time"),
            "guess_form": guess_form,
            "is_organizer": is_organizer,
        },
    )


@force_url_to_include_both_hunt_and_puzzle_slugs
def view_puzzle_log(
    request,
    hunt_id: int,
    puzzle_id: int,
    hunt_slug: Optional[str] = None,
    puzzle_slug: Optional[str] = None,
):
    user = request.user
    hunt = get_object_or_404(Hunt, id=hunt_id)
    puzzle = get_object_or_404(Puzzle, hunt=hunt, id=puzzle_id)

    is_organizer = user.is_authenticated and hunt.organizers.filter(id=user.id).exists()

    if not is_organizer:
        raise Http404("Puzzle stats are only viewable by organizers")

    return render(
        request,
        "view_puzzle_log.html",
        {
            "hunt": hunt,
            "puzzle": puzzle,
            "guesses": Guess.objects.filter(puzzle=puzzle).order_by("time"),
        },
    )


@login_required
@redirect_from_hunt_id_to_hunt_id_and_slug
def my_team(request, hunt_id: int, slug: Optional[str] = None):
    user = request.user
    hunt = get_object_or_404(Hunt, id=hunt_id)
    team = get_team(user, hunt)
    error = None

    create_team_form = TeamForm()
    invite_member_form = InviteMemberForm()

    if request.method == "POST":
        if "create_team" in request.POST:
            create_team_form = TeamForm(request.POST)
            if team:
                create_team_form.add_error(None, "You are already in a team!")
            else:
                if create_team_form.is_valid():
                    team = create_team_form.save(commit=False)
                    team.hunt = hunt
                    team.save()
                    team.members.add(user)

                    return redirect(urls.reverse("my_team", args=[hunt_id]))
        elif "invite_member" in request.POST:
            invite_member_form = InviteMemberForm(request.POST)
            if not team:
                invite_member_form.add_error(
                    None, "You are not in a team, so you can't invite anybody!"
                )
            else:
                if invite_member_form.is_valid():
                    user_to_invite = invite_member_form.cleaned_data["user"]
                    if hunt.organizers.filter(id=user_to_invite.id).exists():
                        invite_member_form.add_error(
                            "username", "That user is an organizer!"
                        )
                    elif team.members.filter(id=user_to_invite.id).exists():
                        invite_member_form.add_error(
                            "username", "That user is already in the team!"
                        )
                    elif team.invited_members.filter(id=user_to_invite.id).exists():
                        invite_member_form.add_error(
                            "username", "That user has already been invited!"
                        )
                    else:
                        team.invited_members.add(user_to_invite)

                        return redirect(urls.reverse("my_team", args=[hunt_id]))
        elif "accept_invite" in request.POST:
            if team:
                error = (
                    "You are already in a team, so you can't accept any invitations!"
                )
            else:
                try:
                    inviting_team = Team.objects.get(id=request.POST["accept_invite"])
                    if inviting_team.invited_members.filter(id=user.id).exists():
                        inviting_team.members.add(user)
                        inviting_team.invited_members.remove(user)

                        return redirect(urls.reverse("my_team", args=[hunt_id]))
                    else:
                        error = "You don't have an invitation to that team!"
                except Team.DoesNotExist:
                    error = "You are not in a team, so you can't invite anybody!"

    return render(
        request,
        "my_team.html",
        {
            "hunt": hunt,
            "team": team,
            "error": error,
            "create_team_form": create_team_form,
            "invite_member_form": invite_member_form,
            "inviting_teams": (
                Team.objects.filter(hunt=hunt, invited_members=user)
                if user.is_authenticated
                else []
            ),
            "is_organizer": not user.is_anonymous
            and hunt.organizers.filter(id=user.id).exists(),
        },
    )


class GuessResponseForm(forms.ModelForm):
    class Meta:
        model = GuessResponse
        fields = ["guess", "response"]


@redirect_from_hunt_id_to_hunt_id_and_slug
@login_required
def new_puzzle(request, hunt_id: int, slug: Optional[str] = None):
    PuzzleFormSet = forms.inlineformset_factory(
        Puzzle, GuessResponse, form=GuessResponseForm, extra=1, can_delete=True
    )
    user = request.user
    hunt = get_object_or_404(Hunt, id=hunt_id)

    if not hunt.organizers.filter(id=user.id).exists():
        return HttpResponse(status=403)

    if request.method == "POST":
        form = PuzzleForm(request.POST)
        formset = PuzzleFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            puzzle = form.save(commit=False)
            puzzle.hunt = hunt
            puzzle.save()

            formset.instance = puzzle
            formset.save()

            return redirect(urls.reverse("view_puzzle", args=[hunt.id, puzzle.id]))
    else:
        form = PuzzleForm()
        formset = PuzzleFormSet()

    return render(
        request,
        "new_puzzle.html",
        {
            "hunt": hunt,
            "form": form,
            "formset": formset,
        },
    )


@force_url_to_include_both_hunt_and_puzzle_slugs
@login_required
def edit_puzzle(
    request,
    hunt_id: int,
    puzzle_id: int,
    hunt_slug: Optional[str] = None,
    puzzle_slug: Optional[str] = None,
):
    PuzzleFormSet = forms.inlineformset_factory(
        Puzzle, GuessResponse, form=GuessResponseForm, extra=1, can_delete=True
    )
    user = request.user
    hunt = get_object_or_404(Hunt, id=hunt_id)
    puzzle = get_object_or_404(Puzzle, hunt=hunt, id=puzzle_id)
    if not hunt.organizers.filter(id=user.id).exists():
        return HttpResponse(status=403)

    if request.method == "POST":
        form = PuzzleForm(request.POST, instance=puzzle)
        formset = PuzzleFormSet(request.POST, instance=puzzle)
        if form.is_valid() and formset.is_valid():
            puzzle = form.save()
            formset = formset.save()
            if request.POST.get("submit", "") == "Submit":
                return redirect(urls.reverse("view_puzzle", args=[hunt.id, puzzle.id]))
            else:
                return redirect(urls.reverse("edit_puzzle", args=[hunt.id, puzzle.id]))
    else:
        form = PuzzleForm(instance=puzzle)
        formset = PuzzleFormSet(instance=puzzle)
    return render(
        request,
        "edit_puzzle.html",
        {
            "hunt": hunt,
            "puzzle": puzzle,
            "form": form,
            "formset": formset,
        },
    )


@login_required
@redirect_from_hunt_id_to_hunt_id_and_slug
def edit_hunt(
    request,
    hunt_id: int,
    slug: Optional[str] = None,
):
    user = request.user
    hunt = get_object_or_404(Hunt, id=hunt_id)
    if not hunt.organizers.filter(id=user.id).exists():
        raise PermissionDenied

    if request.method == "POST":
        form = EditHuntForm(request.POST, instance=hunt)
        if form.is_valid():
            hunt = form.save()
            return redirect(urls.reverse("view_hunt", args=[hunt.pk, hunt.slug]))
    else:
        form = EditHuntForm(instance=hunt)

    return render(
        request,
        "edit_hunt.html",
        {
            "form": form,
            "hunt": hunt,
        },
    )


@csrf_exempt
def preview_markdown(request):
    if request.method == "POST":
        output = render_to_string(
            "preview_markdown.html", {"input": request.body.decode("utf-8")}
        )
        return JsonResponse(
            {
                "success": True,
                "output": output,
            }
        )
    return JsonResponse(
        {
            "success": False,
            "error": "No markdown input received",
        }
    )
