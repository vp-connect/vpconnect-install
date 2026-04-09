"""Оставшиеся ветки outputs (chmod, open_directory OSError)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from vpconnect_install.outputs import ArtifactBundle, open_directory_in_file_manager, write_secret_file


def test_open_directory_swallows_oserror(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    with patch("vpconnect_install.outputs.os.startfile", side_effect=OSError("x")):
        with patch("vpconnect_install.outputs.sys.platform", "win32"):
            open_directory_in_file_manager(tmp_path)


def test_operator_keypair_chmod_notimplemented(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from vpconnect_install.config import ProvisionConfig
    from vpconnect_install.outputs import prepare_artifact_dir

    real_chmod = Path.chmod

    def chmod_raise(self: Path, *a: object, **k: object) -> None:
        if self.name == "id_rsa":
            raise NotImplementedError()
        return real_chmod(self, *a, **k)

    monkeypatch.setattr(Path, "chmod", chmod_raise)
    cfg = ProvisionConfig(host="h", root_password="p", auto_setup=True)
    cfg.apply_auto_setup()
    bundle = prepare_artifact_dir(cfg, base=tmp_path)
    assert bundle.private_key_path and bundle.private_key_path.is_file()


def test_write_secret_file_chmod_notimplemented(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle = ArtifactBundle(root=tmp_path)
    real_chmod = Path.chmod

    def chmod_raise(self: Path, *a: object, **k: object) -> None:
        if self.suffix == ".txt" or self.name.endswith(".txt"):
            raise NotImplementedError()
        return real_chmod(self, *a, **k)

    monkeypatch.setattr(Path, "chmod", chmod_raise)
    p = write_secret_file(bundle, "sec.txt", "v")
    assert p.read_text(encoding="utf-8") == "v\n"
