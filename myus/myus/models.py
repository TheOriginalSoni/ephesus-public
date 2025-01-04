from django.db import models

from django.contrib.auth.models import AbstractUser

from django.db.models import Subquery, OuterRef, Exists, Sum, Q

from django.core.validators import MinValueValidator

import django.urls as urls

from datetime import datetime, timezone

DEFAULT_GUESS_LIMIT = 20


class User(AbstractUser):
    display_name = models.CharField(max_length=500, blank=True, help_text="Optional.")
    discord_username = models.CharField(
        max_length=500,
        blank=True,
        help_text="Your Discord username and tag (e.g. example). Not currently used for anything, but might be used in Discord integrations if they are implemented, since it appears that many hunts in the target audience are run over Discord.",
    )
    bio = models.TextField(blank=True, help_text="Tell us about yourself. Optional.")
    creation_time = models.DateTimeField(auto_now_add=True)


class Hunt(models.Model):
    name = models.CharField(max_length=500)
    description = models.TextField(help_text="Description of the hunt.")
    creation_time = models.DateTimeField(auto_now_add=True)
    start_time = models.DateTimeField(
        blank=True,
        null=True,
        help_text="(Not implemented) Start time of the hunt. If empty, the hunt will never begin. For indefinitely open hunts, you can just set it to any time in the past.",
    )
    end_time = models.DateTimeField(
        blank=True,
        null=True,
        help_text="End date of the hunt. If <b>Archive after end date</b> is checked, hunt will be put in archive mode after this date.",
    )
    archive_after_end_date = models.BooleanField(
        default=False,
        help_text="Set hunt to archive mode after end date (teams can still be created and progress, but leaderboard is frozen and all puzzles are unlocked).",
    )
    organizers = models.ManyToManyField(User, related_name="organizing_hunts")
    invited_organizers = models.ManyToManyField(
        User, blank=True, related_name="invited_organizing_hunts"
    )
    progress_floor = models.IntegerField(
        default=0,
        help_text="A floor on the number of 'progress points' held by every team; their 'progress points' will be computed as the maximum of this quantity and the total number of progress points granted by puzzles they've solved. Expected usage is to increase this midhunt to gradually unlock puzzles for everybody.",
        validators=[MinValueValidator(0)],
    )
    member_limit = models.IntegerField(
        default=0,
        help_text="(Not implemented) The maximum number of members allowed per team; 0 means unlimited",
        validators=[MinValueValidator(0)],
    )
    guess_limit = models.IntegerField(
        default=DEFAULT_GUESS_LIMIT,
        help_text="The default number of guesses teams get on each puzzle; 0 means unlimited",
        validators=[MinValueValidator(0)],
    )

    class LeaderboardStyle(models.TextChoices):
        DEFAULT = "DEF", "Default (ordered by score, solve count, and last solve time)"
        HIDDEN = "HID", "Hidden (not displayed publicly)"
        SPEEDRUN = "SPD", "Speedrun (ordered by score and time to solve)"

    leaderboard_style = models.CharField(
        max_length=3, choices=LeaderboardStyle, default=LeaderboardStyle.DEFAULT
    )

    class SolutionStyle(models.TextChoices):
        VISIBLE = "VIS", "Solutions are always visible"
        HIDDEN = "HID", "Solutions are always hidden"
        AFTER_SOLVE = (
            "SOL",
            "Solution displayed after puzzle is solved (or when hunt is in archive mode)",
        )

    solution_style = models.CharField(
        max_length=3, choices=SolutionStyle, default=SolutionStyle.HIDDEN
    )

    slug = models.SlugField(help_text="A short, unique identifier for the hunt.")

    def is_archived(self):
        return (
            self.end_time is not None
            and self.archive_after_end_date
            and self.end_time < datetime.now(timezone.utc)
        )

    def public_puzzles(self):
        if self.is_archived():
            return self.puzzles
        else:
            return self.puzzles.filter(progress_threshold__lte=self.progress_floor)

    def __str__(self):
        return self.name


class Puzzle(models.Model):
    hunt = models.ForeignKey(Hunt, on_delete=models.CASCADE, related_name="puzzles")
    name = models.CharField(max_length=500)
    content = models.TextField(
        blank=True,
        help_text="The puzzle body. For most puzzles, we suggest just providing an external URL; however, you can put short text-only puzzles here, or include a small amount of flavortext or explanatory text with a URL.",
    )
    solution_url = models.CharField(
        max_length=500,
        blank=True,
        default="",
        verbose_name="Solution URL",
        help_text="URL of solution.",
    )
    answer = models.CharField(max_length=500)
    answer_response = models.CharField(
        max_length=500,
        default="",
        blank=True,
        help_text='Response to a correct answer. Default is "You have solved this puzzle!". Basic html and images allowed.',
    )
    points = models.IntegerField(
        default=1,
        help_text="How many points solving this puzzle earns.",
        validators=[MinValueValidator(0)],
    )
    order = models.IntegerField(
        default=0,
        help_text="Order in which this puzzle is displayed on the hunt page. Ties will be broken by puzzle name.",
    )
    progress_points = models.IntegerField(
        default=0,
        help_text="How many 'progress points' solving this puzzle earns. Progress points are only used to determine unlocking of puzzles.",
        validators=[MinValueValidator(0)],
    )
    progress_threshold = models.IntegerField(
        default=0,
        help_text="How many 'progress points' are necessary for a team to unlock this puzzle. Puzzles with progress threshold ≤ 0 are public.",
        validators=[MinValueValidator(0)],
    )
    slug = models.SlugField(help_text="A short, unique identifier for the puzzle.")

    def is_viewable_by(self, team):
        if team:
            progress = team.progress()
        else:
            progress = self.hunt.progress_floor

        return progress >= self.progress_threshold

    def __str__(self):
        return self.hunt.name + "_" + self.slug


class GuessResponse(models.Model):
    """Any special response to a particular answer guess.

    Common use cases include some kind of "Keep going!" message in
    response to answers that are close but incorrect, or some kind of
    acknowledgement for an intermediate cluephrase asking the teams
    to do something telling teams that they should in fact do that
    thing.
    """

    puzzle = models.ForeignKey(
        Puzzle, on_delete=models.CASCADE, related_name="guess_responses"
    )
    guess = models.CharField(max_length=500)
    response = models.CharField(max_length=500)

    class Meta:
        unique_together = ("puzzle", "guess")

    def __str__(self):
        return self.puzzle.name + "_" + self.guess


class Team(models.Model):
    # TODO: Should we have a team captain?
    name = models.CharField(max_length=500)
    hunt = models.ForeignKey(Hunt, on_delete=models.CASCADE, related_name="teams")
    members = models.ManyToManyField(
        User, blank=True, related_name="teams"
    )  # blank=True in case all members quit a team to join another one or something
    invited_members = models.ManyToManyField(
        User, blank=True, related_name="invited_teams"
    )
    creation_time = models.DateTimeField(auto_now_add=True)

    def progress(self):
        puzzles = self.hunt.puzzles
        team_progress = (
            puzzles.annotate(
                solved=Exists(
                    Guess.objects.filter(team=self, puzzle=OuterRef("pk"), correct=True)
                ),
            )
            .filter(solved=True)
            .aggregate(sum=Sum("progress_points"))["sum"]
        )
        if team_progress is None:
            team_progress = 0
        hunt_progress = self.hunt.progress_floor

        return max(team_progress, hunt_progress)

    def unlocked_puzzles(self):
        return self.hunt.puzzles.filter(progress_threshold__lte=self.progress())

    def unlocked_puzzles_with_solved(self):
        return self.unlocked_puzzles().annotate(
            correct_guess=Subquery(
                Guess.objects.filter(
                    team=self, puzzle=OuterRef("pk"), correct=True
                ).values("guess")
            ),
        )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                name="unique_team_name_per_hunt", fields=["name", "hunt"]
            ),
        ]

    def __str__(self):
        return self.hunt.name + "_" + self.name


class Guess(models.Model):
    guess = models.CharField(max_length=500)
    team = models.ForeignKey(Team, related_name="guesses", on_delete=models.CASCADE)
    user = models.ForeignKey(
        User, related_name="guesses", on_delete=models.SET_NULL, null=True
    )  # Not a source of truth because users could move around teams, but maybe useful for auditing
    puzzle = models.ForeignKey(Puzzle, related_name="guesses", on_delete=models.CASCADE)
    correct = models.BooleanField()
    response = models.CharField(max_length=500)
    time = models.DateTimeField(auto_now_add=True)
    counts_as_guess = models.BooleanField()  # for partial confirmations...

    class Meta:
        constraints = [
            models.UniqueConstraint(
                name="unique_correct_guess_team_puzzle",
                fields=["team", "puzzle"],
                condition=Q(correct=True),
            )
        ]

    def __str__(self):
        return self.team.name + "_" + self.puzzle.name + "_" + self.guess


class ExtraGuessGrant(models.Model):
    "Extra guesses granted to a particular team."

    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    puzzle = models.ForeignKey(Puzzle, on_delete=models.CASCADE)
    extra_guesses = (
        models.IntegerField()
    )  # I guess you *could* want to take guesses away...

    class Meta:
        constraints = [
            models.UniqueConstraint(
                name="unique_team_puzzle_grant", fields=["team", "puzzle"]
            ),
        ]

    def __str__(self):
        return self.team.name + "_" + self.puzzle.name
