"""Tests for user-defined device profiles in ~/.config/linto/devices."""

import yaml

from linto.device import profile as profile_mod
from linto.device.profile import list_available_profiles, load_profile, user_devices_dir


def _write_profile(directory, model_id, name):
    bundled = yaml.safe_load((profile_mod._get_devices_dir() / "hpgl_generic.yaml").read_text(encoding="utf-8"))
    bundled["model_id"] = model_id
    bundled["name"] = name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{model_id}.yaml").write_text(yaml.safe_dump(bundled), encoding="utf-8")


def test_user_devices_dir_follows_xdg_config_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert user_devices_dir() == tmp_path / "linto" / "devices"


def test_user_profile_is_listed_and_loadable(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _write_profile(user_devices_dir(), "my_plotter", "My Plotter")

    names = {p.model_id: p.name for p in list_available_profiles()}
    assert names["my_plotter"] == "My Plotter"
    assert "mutoh_xp500" in names  # bundled profiles are still there
    assert load_profile("my_plotter").name == "My Plotter"


def test_user_profile_overrides_bundled(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _write_profile(user_devices_dir(), "hpgl_generic", "Generic (customized)")

    matches = [p for p in list_available_profiles() if p.model_id == "hpgl_generic"]
    assert len(matches) == 1
    assert matches[0].name == "Generic (customized)"
    assert load_profile("hpgl_generic").name == "Generic (customized)"


def test_invalid_user_profile_is_skipped(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    user_devices_dir().mkdir(parents=True)
    (user_devices_dir() / "broken.yaml").write_text("name: [unclosed", encoding="utf-8")

    profiles = list_available_profiles()
    assert len(profiles) >= 26
    assert "broken.yaml" in caplog.text
