from autoqa.security import host_resolves_public, same_origin, validate_target_url


def test_blocks_private_targets_by_default():
    for url in ["http://127.0.0.1:8000", "http://10.0.0.1", "http://169.254.169.254"]:
        try:
            validate_target_url(url, allow_private=False)
            assert False, f"Expected private target to be blocked: {url}"
        except ValueError:
            pass


def test_allows_private_when_explicitly_enabled():
    assert validate_target_url("http://127.0.0.1:8000/demo", allow_private=True) == "http://127.0.0.1:8000/demo"


def test_public_literal_and_private_literal_resolution():
    assert host_resolves_public("8.8.8.8", 443)
    assert not host_resolves_public("127.0.0.1", 80)


def test_same_origin_normalizes_default_ports():
    assert same_origin("https://example.com/a", "https://example.com/b")
    assert same_origin("https://example.com/a", "https://example.com:443/b")
    assert not same_origin("https://example.com", "http://example.com")
