from backend.services.rate_limiter import RateLimiter, normalize_linkedin_settings


def test_zero_linkedin_settings_disable_limits_and_operating_hours(tmp_path):
    limiter = RateLimiter(tmp_path / "rate-limits.sqlite3")
    settings = normalize_linkedin_settings({
        "hourly_limit": 0,
        "daily_limit": 0,
        "min_delay_seconds": 0,
        "max_delay_seconds": 0,
        "operating_hours_start": 0,
        "operating_hours_end": 0,
    })

    allowed, reason = limiter.check_rate_limit("linkedin:1", settings)

    assert allowed is True
    assert reason == "OK"


def test_reset_clears_an_account_scoped_linkedin_usage(tmp_path):
    limiter = RateLimiter(tmp_path / "rate-limits.sqlite3")
    settings = normalize_linkedin_settings({
        "hourly_limit": 1,
        "daily_limit": 1,
        "min_delay_seconds": 0,
        "max_delay_seconds": 0,
        "operating_hours_start": 0,
        "operating_hours_end": 0,
    })
    limiter.log_request("linkedin:1")
    limiter.increment_daily_count("linkedin:1")

    assert limiter.check_rate_limit("linkedin:1", settings)[0] is False
    limiter.reset("linkedin:1")
    assert limiter.check_rate_limit("linkedin:1", settings)[0] is True
