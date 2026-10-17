import playbook_shared


def test_package_imports_and_exposes_version():
    assert isinstance(playbook_shared.__version__, str)
    assert playbook_shared.__version__
