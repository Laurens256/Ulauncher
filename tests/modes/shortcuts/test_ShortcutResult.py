import pytest
from ulauncher.modes.shortcuts.ShortcutResult import ShortcutResult
from ulauncher.api.shared.query import Query


class TestShortcutResult:
    @pytest.fixture(autouse=True)
    def OpenAction(self, mocker):
        return mocker.patch("ulauncher.modes.shortcuts.ShortcutResult.OpenAction")

    @pytest.fixture(autouse=True)
    def run_script(self, mocker):
        return mocker.patch("ulauncher.modes.shortcuts.ShortcutResult.run_script")

    @pytest.fixture
    def item(self):
        return ShortcutResult(
            "kw", "name", "https://site/?q=%s", "icon_path", is_default_search=True, run_without_argument=False
        )

    def test_keyword(self, item):
        assert item.keyword == "kw"

    def test_name(self, item):
        assert item.name == "name"

    def test_get_description(self, item):
        assert item.get_description(Query("kw test")) == "https://site/?q=test"
        assert item.get_description(Query("keyword test")) == "https://site/?q=..."
        assert item.get_description(Query("goo")) == "https://site/?q=..."

    def test_icon(self, item):
        assert isinstance(item.icon, str)

    def test_on_activation(self, item, OpenAction):
        result = item.on_activation(Query("kw test"))
        OpenAction.assert_called_once_with("https://site/?q=test")
        assert not isinstance(result, str)

    def test_on_activation__default_search(self, item, OpenAction):
        item.is_default_search = True
        result = item.on_activation(Query("search query"))
        OpenAction.assert_called_once_with("https://site/?q=search query")
        assert not isinstance(result, str)

    def test_on_activation__run_without_arguments(self, item, OpenAction):
        item.run_without_argument = True
        result = item.on_activation(Query("kw"))
        # it doesn't replace %s if run_without_argument = True
        OpenAction.assert_called_once_with("https://site/?q=%s")
        assert not isinstance(result, str)

    def test_on_activation__misspelled_kw(self, item, OpenAction):
        assert item.on_activation(Query("keyword query")) == "kw "
        assert not OpenAction.called

    def test_on_activation__run_file(self, run_script):
        item = ShortcutResult("kw", "name", "/usr/bin/something/%s", "icon_path")
        item.on_activation(Query("kw query"))
        # Scripts should support both %s and arguments
        run_script.assert_called_once_with("/usr/bin/something/query", "query")
