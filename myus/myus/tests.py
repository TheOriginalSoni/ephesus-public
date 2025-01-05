from datetime import datetime, timezone, timedelta
from http import HTTPStatus

from django.urls import reverse
from django.test import TestCase, override_settings

from myus.forms import NewHuntForm
from myus.models import Hunt, Puzzle, User, Team, Guess


class TestViewHunt(TestCase):
    """Test the view_hunt endpoint

    The tests related to the handling of URLs with IDs and slugs should be taken as
    general tests for the redirect_from_hunt_id_to_hunt_id_and_slug decorator
    """

    def setUp(self):
        self.hunt = Hunt.objects.create(name="Test Hunt", slug="test-hunt")
        self.view_name = "view_hunt"

    def test_view_hunt_with_id_and_slug_success(self):
        """Visiting the view_hunt endpoint with both ID and slug in the URL displays the requested page"""
        res = self.client.get(
            reverse(self.view_name, args=[self.hunt.id, self.hunt.slug])
        )
        self.assertEqual(res.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(res, "view_hunt.html")

    def test_view_hunt_with_id_only_redirects_to_id_and_slug(self):
        """Visiting the view_hunt endpoint with only ID in the URL redirects to the URL with ID and slug"""
        res = self.client.get(reverse(self.view_name, args=[self.hunt.id]))
        self.assertRedirects(
            res, reverse(self.view_name, args=[self.hunt.id, self.hunt.slug])
        )

    def test_view_hunt_with_id_and_wrong_slug_redirects_to_id_and_correct_slug(self):
        """Visiting the view_hunt endpoint with ID and the wrong slug in URL redirects to URL with ID and correct slug"""
        res = self.client.get(
            reverse(self.view_name, args=[self.hunt.id, "the-wrong-slug"])
        )
        self.assertRedirects(
            res, reverse(self.view_name, args=[self.hunt.id, self.hunt.slug])
        )


class TestViewPuzzle(TestCase):
    """Test the view_puzzle endpoint

    The tests related to the handling of URLs with IDs and slugs should be taken as general tests for the force_url_to_include_both_hunt_and_puzzle_slugs decorator
    """

    def setUp(self):
        self.hunt = Hunt.objects.create(name="Test Hunt", slug="test-hunt")
        self.puzzle = Puzzle.objects.create(
            name="Test Puzzle", slug="test-puzzle", hunt=self.hunt
        )
        self.view_name = "view_puzzle"
        self.correct_url = reverse(
            self.view_name,
            args=[self.hunt.id, self.hunt.slug, self.puzzle.id, self.puzzle.slug],
        )

    def test_view_puzzle_with_ids_and_slugs_success(self):
        """Visiting the view_puzzle endpoint with hunt and puzzle IDs and slug in the URL displays the requested page"""
        res = self.client.get(self.correct_url)
        self.assertEqual(res.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(res, "view_puzzle.html")

    def test_view_puzzle_with_no_hunt_slug_redirects_to_full_url(self):
        """Visiting the view_puzzle endpoint with no hunt_slug in the URL redirects to the full URL"""
        res = self.client.get(
            reverse(
                self.view_name, args=[self.hunt.id, self.puzzle.id, self.puzzle.slug]
            )
        )
        self.assertRedirects(res, self.correct_url)

    def test_view_puzzle_with_no_puzzle_slug_redirects_to_full_url(self):
        """Visiting the view_puzzle endpoint with no puzzle_slug in the URL redirects to the full URL"""
        res = self.client.get(
            reverse(self.view_name, args=[self.hunt.id, self.hunt.slug, self.puzzle.id])
        )
        self.assertRedirects(res, self.correct_url)

    def test_view_puzzle_with_no_hunt_or_puzzle_slug_redirects_to_full_url(self):
        """Visiting the view_puzzle endpoint with no hunt_slug or puzzle_slug in the URL redirects to the full URL"""
        res = self.client.get(
            reverse(self.view_name, args=[self.hunt.id, self.puzzle.id])
        )
        self.assertRedirects(res, self.correct_url)

    def test_view_puzzle_with_ids_and_wrong_slugs_redirects_to_ids_and_correct_slugs(
            self,
    ):
        """Visiting the view_puzzle endpoint with IDs and the wrong slugs in URL redirects to URL with IDs and correct slugs"""
        res = self.client.get(
            reverse(
                self.view_name,
                args=[
                    self.hunt.id,
                    "wrong-hunt-slug",
                    self.puzzle.id,
                    "wrong-puzzle-slug",
                ],
            )
        )
        self.assertRedirects(res, self.correct_url)


class TestNewHuntForm(TestCase):
    """Test the NewHuntForm"""

    def setUp(self):
        self.shared_test_data = {
            "name": "Test Hunt",
            "slug": "test",
            "member_limit": 0,
            "guess_limit": 20,
            "solution_style": Hunt.SolutionStyle.HIDDEN,
            "leaderboard_style": Hunt.LeaderboardStyle.DEFAULT,
        }

    def test_hunt_form_accepts_start_time_in_iso_format(self):
        """The NewHuntForm accepts the start_time field in ISO format (YYYY-MM-DDTHH:MM:SS)"""
        test_data = self.shared_test_data.copy()
        start_time = datetime(2024, 3, 15, 1, 2, tzinfo=timezone.utc)
        test_data["start_time"] = start_time.isoformat()
        form = NewHuntForm(data=test_data)
        self.assertTrue(form.is_valid(), msg=form.errors)
        hunt = form.save()
        self.assertEqual(hunt.start_time, start_time)

    def test_hunt_form_accepts_start_time_without_seconds(self):
        """The NewHuntForm accepts the start_time field without seconds specified

        The out-of-the-box datetime-local input appears to provide data in this format
        """
        test_data = self.shared_test_data.copy()
        start_time = datetime(2024, 3, 15, 1, 2, tzinfo=timezone.utc)
        test_data["start_time"] = start_time.strftime("%Y-%m-%dT%H:%M")
        form = NewHuntForm(data=test_data)
        self.assertTrue(form.is_valid(), msg=form.errors)
        hunt = form.save()
        self.assertEqual(hunt.start_time, start_time)

    def test_hunt_form_start_time_uses_datetime_local_input(self):
        """The NewHuntForm uses a datetime-local input for the start_time field"""
        form = NewHuntForm(data=self.shared_test_data)
        start_time_field = form.fields["start_time"]
        self.assertEqual(start_time_field.widget.input_type, "datetime-local")

    def test_hunt_form_accepts_end_time_in_iso_format(self):
        """The NewHuntForm accepts the end_time field in ISO format (YYYY-MM-DDTHH:MM:SS)"""
        test_data = self.shared_test_data.copy()
        end_time = datetime(2024, 3, 15, 1, 2, tzinfo=timezone.utc)
        test_data["end_time"] = end_time.isoformat()
        form = NewHuntForm(data=test_data)
        self.assertTrue(form.is_valid(), msg=form.errors)
        hunt = form.save()
        self.assertEqual(hunt.end_time, end_time)

    def test_hunt_form_accepts_end_time_without_seconds(self):
        """The NewHuntForm accepts the end_time field without seconds specified

        The out-of-the-box datetime-local input appears to provide data in this format
        """
        test_data = self.shared_test_data.copy()
        end_time = datetime(2024, 3, 15, 1, 2, tzinfo=timezone.utc)
        test_data["end_time"] = end_time.strftime("%Y-%m-%dT%H:%M")
        form = NewHuntForm(data=test_data)
        self.assertTrue(form.is_valid(), msg=form.errors)
        hunt = form.save()
        self.assertEqual(hunt.end_time, end_time)

    def test_hunt_form_end_time_displays_datetime_local_widget(self):
        """The NewHuntForm uses a datetime-local input for the end_time field"""
        form = NewHuntForm(data=self.shared_test_data)
        end_time_field = form.fields["end_time"]
        self.assertEqual(end_time_field.widget.input_type, "datetime-local")


class TestArchiveMode(TestCase):
    """Test archive mode"""

    def setUp(self):
        curr_time = datetime.now(timezone.utc)
        self.archived_hunt = Hunt.objects.create(
            name="Archived Hunt",
            slug="archived-hunt",
            end_time=curr_time - timedelta(minutes=15),
            leaderboard_style=Hunt.LeaderboardStyle.DEFAULT,
            solution_style=Hunt.SolutionStyle.AFTER_SOLVE,
            archive_after_end_date=True,
        )
        self.archive_solved_puzzle = Puzzle.objects.create(
            name="Test Puzzle",
            slug="test-puzzle",
            hunt=self.archived_hunt,
            progress_threshold=0,
            points=20,
            solution_url="https://google.com",
        )
        self.archive_locked_puzzle = Puzzle.objects.create(
            name="Test Locked Puzzle",
            hunt=self.archived_hunt,
            progress_threshold=10,
            slug="locked-puzzle",
        )

        self.teams = []
        for name, create_time, guess_time in [
            ("Archived Team", -40, -30),
            ("Late Guess", -40, -10),
            ("Late Creation", -10, -5),
        ]:
            team = Team.objects.create(name=name, hunt=self.archived_hunt)
            team.creation_time = curr_time + timedelta(minutes=create_time)
            team.save()

            guess = Guess.objects.create(
                team=team,
                puzzle=self.archive_solved_puzzle,
                counts_as_guess=True,
                correct=True,
            )
            guess.time = curr_time + timedelta(minutes=guess_time)
            guess.save()
            self.teams.append(team)

        self.active_hunt = Hunt.objects.create(
            name="Active Hunt 1",
            slug="active-hunt-1",
            end_time=curr_time + timedelta(minutes=15),
            archive_after_end_date=True,
        )

    def test_is_archive(self):
        self.assertEqual(self.archived_hunt.is_archived(), True)
        self.assertEqual(self.active_hunt.is_archived(), False)

    def test_puzzle_visibility(self):
        # all puzzles are public in an archived hunt
        self.assertEqual(self.archived_hunt.public_puzzles().count(), 2)
        res = self.client.get(
            reverse(
                "view_puzzle",
                args=[
                    self.archived_hunt.id,
                    self.archived_hunt.slug,
                    self.archive_locked_puzzle.id,
                    self.archive_locked_puzzle.slug,
                ],
            )
        )
        self.assertContains(
            res, "<h1>Puzzle: Test Locked Puzzle </h1>", status_code=200
        )
        # team-visible in an archived hunt is still the same
        self.assertEqual(self.teams[0].unlocked_puzzles().count(), 1)

    def test_leaderboard(self):
        res = self.client.get(
            reverse(
                "leaderboard", args=[self.archived_hunt.id, self.archived_hunt.slug]
            )
        )

        # solves before the end time should count on leaderboard
        self.assertContains(
            res, "<td>Archived Team</td><td>20</td><td>1</td>", html=True
        )
        # solves after the end time don't count
        self.assertContains(res, "<td>Late Guess</td><td>0</td><td>0</td>", html=True)
        # teams created after the hunt end don't appear
        self.assertNotContains(res, "Late Creation", html=True)

    def test_solution_visibility(self):
        res = self.client.get(
            reverse(
                "view_puzzle",
                args=[
                    self.archived_hunt.id,
                    self.archived_hunt.slug,
                    self.archive_solved_puzzle.id,
                    self.archive_solved_puzzle.slug,
                ],
            )
        )

        # non-hidden solutions are visible after archiving
        self.assertContains(res, '<a href="https://google.com">Solution</a>', html=True)

    @override_settings(APPEND_SLASH=True)
    def test_append_slash_redirect(self):
        """URLs without trailing slashes should be redirected to their counterparts with trailing slashes"""
        url_without_slash = reverse("view_hunt", args=[self.hunt.id, self.hunt.slug])
        if url_without_slash[-1] == '/':
            url_without_slash = url_without_slash[:-1]
        url_with_slash = url_without_slash + '/'

        res = self.client.get(url_without_slash)
        self.assertRedirects(res, url_with_slash, status_code=HTTPStatus.MOVED_PERMANENTLY)

        # Repeat for view_puzzle
        url_without_slash = reverse(
            "view_puzzle",
            args=[self.hunt.id, self.hunt.slug, self.puzzle.id, self.puzzle.slug],
        )
        if url_without_slash[-1] == '/':
            url_without_slash = url_without_slash[:-1]
        url_with_slash = url_without_slash + '/'

        res = self.client.get(url_without_slash)
        self.assertRedirects(res, url_with_slash, status_code=HTTPStatus.MOVED_PERMANENTLY)