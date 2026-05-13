def is_placeholder_value(value):
    if value is None:
        return True

    normalized = str(value).strip()
    if not normalized:
        return True

    lowered = normalized.lower()
    placeholder_terms = (
        "your_",
        "example",
        "changeme",
        "change-me",
        "replace_me",
        "replace-me",
        "test_key",
        "dummy",
        "placeholder",
    )
    return any(term in lowered for term in placeholder_terms)


def has_configured_value(value):
    return not is_placeholder_value(value)
