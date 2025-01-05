from django.urls import path, re_path
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeView,
    PasswordChangeDoneView,
)
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("login", LoginView.as_view(template_name="login.html"), name="login"),
    path("logout", LogoutView.as_view(template_name="logout.html"), name="logout"),
    path(
        "change-password",
        PasswordChangeView.as_view(template_name="change-password.html"),
        name="password_change",
    ),
    path(
        "change-password/done",
        PasswordChangeDoneView.as_view(template_name="change-password-done.html"),
        name="password_change_done",
    ),
    path("register", views.register, name="register"),
    path("new", views.new_hunt, name="new_hunt"),
    path("hunt/<int:hunt_id>/edit", views.edit_hunt, name="edit_hunt"),
    path("hunt/<int:hunt_id>-<slug:slug>/edit", views.edit_hunt, name="edit_hunt"),
    path("hunt/<int:hunt_id>", views.view_hunt, name="view_hunt"),
    path("hunt/<int:hunt_id>-<slug:slug>", views.view_hunt, name="view_hunt"),
    path("hunt/<int:hunt_id>/team", views.my_team, name="my_team"),
    path("hunt/<int:hunt_id>-<slug:slug>/team", views.my_team, name="my_team"),
    path("hunt/<int:hunt_id>/new", views.new_puzzle, name="new_puzzle"),
    path("hunt/<int:hunt_id>-<slug:slug>/new", views.new_puzzle, name="new_puzzle"),
    path("hunt/<int:hunt_id>/leaderboard", views.leaderboard, name="leaderboard"),
    path(
        "hunt/<int:hunt_id>-<slug:slug>/leaderboard",
        views.leaderboard,
        name="leaderboard",
    ),
    # The regex is complicated; it's saying A) the literal "/hunt/", B) a hunt_id made of digits, C) optionally a hyphen and then a hunt slug (made of letters, digits, hyphens, or underscores), D) the literal "/puzzle/", E) a puzzle_id made up of digits, F) optionally a hyphen and then a puzzle slug
    re_path(
        r"^hunt/(?P<hunt_id>\d+)(?:-(?P<hunt_slug>[-\w]+))?/puzzle/(?P<puzzle_id>\d+)(?:-(?P<puzzle_slug>[-\w]+))?$",
        views.view_puzzle,
        name="view_puzzle",
    ),
    re_path(
        r"^hunt/(?P<hunt_id>\d+)(?:-(?P<hunt_slug>[-\w]+))?/puzzle/(?P<puzzle_id>\d+)(?:-(?P<puzzle_slug>[-\w]+))?/edit$",
        views.edit_puzzle,
        name="edit_puzzle",
    ),
    re_path(
        r"^hunt/(?P<hunt_id>\d+)(?:-(?P<hunt_slug>[-\w]+))?/puzzle/(?P<puzzle_id>\d+)(?:-(?P<puzzle_slug>[-\w]+))?/log$",
        views.view_puzzle_log,
        name="view_puzzle_log",
    ),
    path("preview_markdown", views.preview_markdown, name="preview_markdown"),
]
