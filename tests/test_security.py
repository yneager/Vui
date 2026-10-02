from autoqa.security import validate_target_url, same_origin


def test_blocks_private_targets_by_default():
    for url in ["http://127.0.0.1:8000", "http://10.0.0.1", "http://169.254.169.254"]:
        try:
            validate_target_url(url, allow_private=False)
            assert False, f"Expected private target to be blocked: {url}"
        except ValueError:
            pass


def test_allows_private_when_explicitly_enabled():
    assert validate_target_url("http://127.0.0.1:8000/demo", allow_private=True) == "http://127.0.0.1:8000/demo"


def test_same_origin_normalizes_default_ports():
    assert same_origin("https://example.com/a", "https://example.com/b")
    assert same_origin("https://example.com/a", "https://example.com:443/b")
    assert not same_origin("https://example.com", "http://example.com")
