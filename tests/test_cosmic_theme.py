"""Tests for the built-in Cosmic skin, the seasonal (holiday) layer and themed page rendering.

No Google auth or network needed: the app is imported with an isolated DATABASE_PATH and
exercised with FastAPI's TestClient (startup tasks are not run).
"""

import datetime as dt
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from config import theme  # noqa: E402
from config.buster_seasons import DEFAULT_WINDOWS, resolve_season  # noqa: E402
from config.skin_loader import (  # noqa: E402
    BUILTIN_SKINS_DIR, DEFAULT_SKIN, SUPPORTED_SKINS, SkinLoader, resolve_skin_name,
)

DS_DIR = ROOT / "src" / "static" / "ds"
SEASONS = ["none", "halloween", "thanksgiving", "winter", "newyear"]


# ---------------------------------------------------------------- built-in skin
def test_cosmic_is_a_builtin_skin(tmp_path):
    loader = SkinLoader(skins_dir=tmp_path / "personal")  # empty personal skins folder
    names = {s["name"]: s for s in loader.list_available_skins()}
    assert "cosmic" in names and names["cosmic"]["builtin"] is True
    assert names["cosmic"]["display_name"] == "Cosmic"

    skin = loader.load_skin("cosmic")
    assert skin is not None and skin.builtin
    assert skin.theme["design_system"] == "buster"
    assert skin.theme["companion"]["accent"] in ("cyan", "blue", "violet", "green", "amber", "magenta", "pink", "coral")
    css = skin.get_css_variables()
    # skin colour variables are mapped onto design-system tokens (with hex fallbacks)
    for key in ("--skin-primary", "--skin-accent", "--skin-bg-primary", "--skin-text-primary", "--skin-weather-border"):
        assert css[key].startswith("var(--") and ("#" in css[key] or "rgba" in css[key]), key
    data = skin.to_json()
    assert data["builtin"] is True and data["theme"]["companion"]["name"] == "Buster"
    assert data["quotes"]["greetings"]


def test_personal_cosmic_overrides_builtin_and_old_skins_are_hidden(tmp_path):
    personal = tmp_path / "skins"
    (personal / "roger").mkdir(parents=True)
    (personal / "roger" / "skin.yaml").write_text(yaml.safe_dump({"identity": {"display_name": "R0-GR"}}))
    (personal / "cosmic").mkdir()
    (personal / "cosmic" / "skin.yaml").write_text(yaml.safe_dump({"identity": {"display_name": "My Cosmic"}}))
    loader = SkinLoader(skins_dir=personal)
    names = {s["name"]: s for s in loader.list_available_skins()}
    assert list(names) == ["cosmic"]  # Cosmic is the only theme
    assert names["cosmic"]["display_name"] == "My Cosmic" and names["cosmic"]["builtin"] is False
    assert loader.load_skin("cosmic").builtin is False
    assert loader.load_skin("../etc").name == "cosmic"


@pytest.mark.parametrize("old", ["roger", "dracula", "alice", "jedi", "demon", "", None, "../etc"])
def test_removed_skins_resolve_to_cosmic(tmp_path, old):
    loader = SkinLoader(skins_dir=tmp_path / "personal")
    assert resolve_skin_name(old) == "cosmic"
    assert loader.load_skin(old).name == "cosmic"
    assert loader.set_active_skin(old) and loader.active_skin_name == "cosmic"
    assert loader.get_active_skin().name == "cosmic"


def test_default_skin_is_cosmic(tmp_path):
    assert DEFAULT_SKIN == "cosmic" and SUPPORTED_SKINS == ("cosmic",)
    assert SkinLoader(skins_dir=tmp_path / "p").get_active_skin().name == "cosmic"
    assert theme.UI_THEMES == ("cosmic",)


# ---------------------------------------------------------------- seasons
def test_default_calendar_matches_design_system_seasons_json():
    vendored = json.loads((DS_DIR / "seasons.json").read_text())["windows"]
    assert theme.default_windows() == vendored
    assert [dict(w) for w in DEFAULT_WINDOWS] == vendored
    upstream = Path("/Users/greglind/Projects/buildly/buster-design/dist/seasons.json")
    if upstream.exists():  # owner's machine: also compare with the design-system source
        assert json.loads(upstream.read_text())["windows"] == vendored


@pytest.mark.parametrize("md,expected", [
    ("10-14", ("none", "")),
    ("10-15", ("halloween", "")),
    ("10-31", ("halloween", "")),
    ("11-01", ("none", "")),
    ("11-15", ("thanksgiving", "")),
    ("12-01", ("winter", "")),
    ("12-25", ("winter", "")),
    ("12-26", ("winter", "")),
    ("12-27", ("winter", "newyear")),
    ("12-31", ("winter", "newyear")),
    ("01-02", ("winter", "newyear")),
    ("01-03", ("none", "")),
    ("07-04", ("none", "")),
])
def test_season_windows(md, expected):  # the shared calendar (matches the stream pages)
    for year in (2026, 2027, 2028):
        day = dt.date.fromisoformat(f"{year}-{md}")
        r = theme.resolve(today=day, windows=theme.default_windows())
        assert (r["season"], r["variant"]) == expected
        assert r["source"] == "calendar"


def test_every_day_matches_reference_implementation():
    windows = theme.default_windows()
    day = dt.date(2027, 1, 1)
    while day < dt.date(2029, 1, 1):  # includes a leap year
        r = theme.resolve(today=day, windows=windows)
        assert (r["season"], r["variant"]) == resolve_season(day, DEFAULT_WINDOWS)
        day += dt.timedelta(days=1)


def test_override_precedence():
    halloween_day = dt.date(2026, 10, 18)
    assert theme.resolve(today=halloween_day)["season"] == "halloween"
    r = theme.resolve(choice="winter", today=halloween_day)
    assert (r["season"], r["source"]) == ("winter", "user")
    r = theme.resolve(choice="winter", query="thanksgiving", today=halloween_day)
    assert (r["season"], r["source"]) == ("thanksgiving", "query")
    r = theme.resolve(choice="none", today=halloween_day)
    assert (r["season"], r["source"]) == ("none", "user")
    r = theme.resolve(query="newyear", today=halloween_day)
    assert (r["season"], r["variant"]) == ("winter", "newyear")
    r = theme.resolve(query="bogus", choice="auto", today=halloween_day)
    assert r["season"] == "halloween"
    r = theme.resolve(today=halloween_day, enabled=False)
    assert (r["season"], r["source"]) == ("none", "disabled")


def test_configurable_windows():
    cfg = theme.season_config({"seasons": {"windows": [
        {"season": "winter", "start": "11-15", "end": "02-01"},
        {"season": "halloween", "start": "13-01", "end": "10-31"},  # invalid -> ignored
    ]}})
    assert cfg["windows"] == [{"season": "winter", "start": "11-15", "end": "02-01"}]
    assert theme.resolve(today=dt.date(2026, 11, 20), windows=cfg["windows"])["season"] == "winter"
    assert theme.season_config({})["windows"] == theme.default_windows()
    assert theme.season_config({"seasons": {"enabled": False}})["enabled"] is False


def test_inject_theme_sets_html_attributes_and_calendar():
    page = '<!DOCTYPE html>\n<html lang="en" class="h-full">\n<head>\n    <!--DASH_THEME-->\n</head><body></body></html>'
    out = theme.inject_theme(page, {
        "ui": "family", "season": {"season": "winter", "variant": "newyear", "source": "query", "choice": "auto"},
        "windows": theme.default_windows(), "enabled": True, "skin": "cosmic",
    })
    assert ('<html lang="en" class="h-full" data-ui="family" data-theme="cosmic" data-season="winter" '
            'data-season-variant="newyear" data-season-lock>') in out
    assert 'id="buster-seasons"' in out and '"requestedSkin": "cosmic"' in out
    assert "<!--DASH_THEME-->" not in out
    assert theme.safe_name('cosmic"><script>') is None


# ---------------------------------------------------------------- pages render
@pytest.fixture(scope="module")
def client():
    tmp = tempfile.mkdtemp(prefix="dash-theme-test-")
    os.environ["DATABASE_PATH"] = str(Path(tmp) / "test.db")
    from fastapi.testclient import TestClient
    import main  # noqa: E402
    return TestClient(main.app)


@pytest.mark.parametrize("season", SEASONS)
def test_family_ui_renders_with_cosmic_and_each_season(client, season):
    r = client.get(f"/?ui=family&skin=cosmic&season={season}")
    assert r.status_code == 200
    expected = "winter" if season == "newyear" else season
    assert f'data-season="{expected}"' in r.text
    assert '"requestedSkin": "cosmic"' in r.text
    assert "/static/theme/dash-theme.js" in r.text and "/static/ds/tokens.css" in r.text


@pytest.mark.parametrize("season", SEASONS)
def test_modern_ui_renders_with_cosmic_and_each_season(client, season):
    r = client.get(f"/?ui=modern&theme=cosmic&season={season}")
    assert r.status_code == 200
    expected = "winter" if season == "newyear" else season
    assert f'data-season="{expected}"' in r.text
    assert '"requestedTheme": "cosmic"' in r.text and 'data-ui="modern"' in r.text


def test_static_theme_assets_are_served(client):
    for path in ("/static/ds/buster.js", "/static/ds/seasons-fx.js", "/static/ds/components.css",
                 "/static/theme/dash-theme.js", "/static/theme/dash-theme.css"):
        assert client.get(path).status_code == 200, path


def test_skins_api_lists_cosmic(client):
    data = client.get("/api/skins").json()
    assert "cosmic" in [s["name"] for s in data["skins"]]
    assert client.get("/api/skins/cosmic").json()["skin"]["theme"]["design_system"] == "buster"


def test_theme_api_saves_season_choice(client):
    assert client.post("/api/theme", json={"season": "bogus"}).status_code == 400
    r = client.post("/api/theme", json={"season": "thanksgiving"}).json()
    assert r["success"] and r["season"]["season"] == "thanksgiving"
    assert client.get("/api/theme").json()["season_choice"] == "thanksgiving"
    assert 'data-season="thanksgiving"' in client.get("/?ui=family").text
    assert 'data-season="winter"' in client.get("/?ui=family&season=winter").text  # ?season= still wins
    client.post("/api/theme", json={"season": "auto"})


@pytest.mark.parametrize("year,day", [(2026, 26), (2027, 25), (2028, 23)])
def test_thanksgiving_window_ends_on_thanksgiving_day(year, day):
    windows = theme.default_windows()
    on = theme.resolve(today=dt.date(year, 11, day), windows=windows)
    after = theme.resolve(today=dt.date(year, 11, day) + dt.timedelta(days=1), windows=windows)
    assert on["season"] == "thanksgiving" and after["season"] == "none"


# ---------------------------------------------------------------- cosmic only
def test_theme_layer_is_cosmic_only_and_migrates_stored_picks():
    js = (ROOT / "src" / "static" / "theme" / "dash-theme.js").read_text()
    css = (ROOT / "src" / "static" / "theme" / "dash-theme.css").read_text()
    # stored picks of removed skins/themes are rewritten to cosmic at load
    assert 'if (read("dashboard_skin") !== THEME) store("dashboard_skin", THEME);' in js
    assert 'if (read("dashboard_modern_theme") !== THEME) store("dashboard_modern_theme", THEME);' in js
    for gone in ('"classic"', "mountSeasonLite", "garlandSVG", "dash-skin-select", '["classic", "Classic"]'):
        assert gone not in js, gone
    assert 'data-theme="classic"' not in css


def test_family_template_has_no_theme_picker_or_theme_gating():
    html = (ROOT / "src" / "templates" / "dashboard_family.html").read_text()
    for gone in ('id="skin-select"', 'id="skin-select-header"', 'id="bg-select"', ".themes.includes",
                 "themes: [", "|| 'roger'", "/api/auth/microsoft/status", "/api/auth/proton/status", 'href="/trust"'):
        assert gone not in html, gone
    assert "switchSkin(COSMIC_SKIN, false)" in html


def test_pages_render_cosmic_without_picker(client):
    fam = client.get("/?ui=family&skin=roger").text
    assert 'data-theme="cosmic"' in fam and 'id="skin-select' not in fam
    mod = client.get("/?ui=modern&theme=classic").text
    assert 'data-theme="cosmic"' in mod and '"requestedTheme": null' in mod


def test_old_skin_requests_answer_with_cosmic(client):
    assert [s["name"] for s in client.get("/api/skins").json()["skins"]] == ["cosmic"]
    r = client.post("/api/skins/switch/roger").json()
    assert r["success"] and r["skin"]["name"] == "cosmic"
    assert client.get("/api/skins/active").json()["skin"]["name"] == "cosmic"


def test_email_link_opens_modern_email_section(client):
    r = client.get("/email", follow_redirects=False)
    assert r.status_code in (302, 307) and r.headers["location"] == "/?ui=modern&section=emails"


def test_garfield_history_pages_through_the_archive_sample(client):
    data = client.get("/api/comics/garfield/history?limit=20").json()
    assert data["success"] and len(data["comics"]) == 20
    dates = [c["date"] for c in data["comics"]]
    assert dates == sorted(dates) and all(c["image_url"] for c in data["comics"])
