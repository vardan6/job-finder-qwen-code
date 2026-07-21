from pathlib import Path
import re


TEMPLATE_PATH = Path(__file__).parents[1] / "frontend" / "templates" / "settings" / "llm.html"


def test_every_provider_template_option_has_a_template_definition():
    template = TEMPLATE_PATH.read_text()
    provider_select = re.search(
        r'<select id="provider-template".*?</select>', template, flags=re.DOTALL
    ).group(0)
    option_values = re.findall(r'<option value="([a-z0-9_]+)">', provider_select)
    template_keys = re.findall(r'^    ([a-z0-9_]+): \{', template, flags=re.MULTILINE)

    assert set(option_values) <= set(template_keys)


def test_provider_template_application_does_not_require_structured_clone():
    template = TEMPLATE_PATH.read_text()

    assert "structuredClone(" not in template
