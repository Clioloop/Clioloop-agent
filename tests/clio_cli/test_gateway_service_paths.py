from unittest.mock import patch


def test_service_path_skips_nonexistent_node_modules(tmp_path):
    """Service PATH should not include node_modules/.bin if it doesn't exist."""
    from clio_cli.gateway import _build_service_path_dirs
    with patch("clio_cli.gateway.get_clio_home", return_value=tmp_path / ".clio"):
        dirs = _build_service_path_dirs(project_root=tmp_path)
    node_modules_bin = str(tmp_path / "node_modules" / ".bin")
    assert node_modules_bin not in dirs


def test_service_path_includes_node_modules_when_present(tmp_path):
    """Service PATH should include node_modules/.bin when it exists."""
    nm_bin = tmp_path / "node_modules" / ".bin"
    nm_bin.mkdir(parents=True)
    from clio_cli.gateway import _build_service_path_dirs
    with patch("clio_cli.gateway.get_clio_home", return_value=tmp_path / ".clio"):
        dirs = _build_service_path_dirs(project_root=tmp_path)
    assert str(nm_bin) in dirs


def test_service_path_includes_clio_home_node_modules(tmp_path):
    """Service PATH should include ~/.clio/node_modules/.bin when it exists."""
    clio_nm = tmp_path / ".clio" / "node_modules" / ".bin"
    clio_nm.mkdir(parents=True)
    from clio_cli.gateway import _build_service_path_dirs
    with patch("clio_cli.gateway.get_clio_home", return_value=tmp_path / ".clio"):
        dirs = _build_service_path_dirs(project_root=tmp_path)
    assert str(clio_nm) in dirs
