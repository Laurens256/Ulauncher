from __future__ import annotations

import json
import logging
import time
from functools import lru_cache

from gi.repository import Gdk, Gio, GLib, Gtk, Keybinder  # type: ignore[attr-defined]

from ulauncher.api.shared.query import Query
from ulauncher.config import APP_ID, DBUS_PATH, FIRST_RUN, PATHS
from ulauncher.modes.extensions.ExtensionRunner import ExtensionRunner
from ulauncher.modes.extensions.ExtensionServer import ExtensionServer
from ulauncher.ui.AppIndicator import AppIndicator
from ulauncher.ui.windows.PreferencesWindow import PreferencesWindow
from ulauncher.ui.windows.UlauncherWindow import UlauncherWindow
from ulauncher.utils.environment import IS_X11
from ulauncher.utils.launch_detached import launch_detached
from ulauncher.utils.Settings import Settings

logger = logging.getLogger()


class UlauncherApp(Gtk.Application, AppIndicator):
    """
    Main Ulauncher application (singleton)
    """

    # Gtk.Applications check if the app is already registered and if so,
    # new instances sends the signals to the registered one
    # So all methods except __init__ runs on the main app
    _query = ""
    window: UlauncherWindow | None = None
    preferences: PreferencesWindow | None = None
    _current_accel_name = None

    @classmethod
    @lru_cache(maxsize=None)
    def get_instance(cls):
        return cls()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE, **kwargs)
        self.connect("startup", self.setup)  # runs only once on the main instance

    @property
    def query(self) -> Query:
        return Query(self._query)

    @query.setter
    def query(self, value: str):
        self._query = value.lstrip()
        if self.window:
            self.window.input.set_text(self._query)
            self.window.input.set_position(-1)

    def do_startup(self):
        Gtk.Application.do_startup(self)
        Gio.ActionMap.add_action_entries(self, [("set-query", self.activate_query, "s")])

    def do_activate(self, *_args, **_kwargs):
        self.show_launcher()

    def do_command_line(self, *args, **_kwargs):
        # We need to use "--no-window" from the unique CLI invocation here,
        # Can't use config.get_options(), because that's the daemon's initial cli arguments
        if "--no-window" not in args[0].get_arguments():
            self.activate()

        return 0

    def setup(self, _):
        settings = Settings.load()
        self.hold()  # Keep the app running even without a window

        if settings.show_indicator_icon:
            self.toggle_appindicator(True)

        if IS_X11:
            # bind hotkey
            Keybinder.init()
            # bind in the main thread
            GLib.idle_add(self.bind_hotkey, settings.hotkey_show_app)

        ExtensionServer.get_instance().start()
        time.sleep(0.01)
        ExtensionRunner.get_instance().run_all()

        with open(f"{PATHS.APPLICATION}/dbus.xml") as file:
            xml = file.read()
            (actions,) = Gio.DBusNodeInfo.new_for_xml(xml).interfaces
            self.get_dbus_connection().register_object(DBUS_PATH, actions, self.dbus_method_listener)

    def bind_hotkey(self, accel_name):
        if not IS_X11 or self._current_accel_name == accel_name:
            return

        if self._current_accel_name:
            Keybinder.unbind(self._current_accel_name)
            self._current_accel_name = None

        logger.info("Trying to bind app hotkey: %s", accel_name)
        Keybinder.bind(accel_name, lambda _: self.show_launcher())
        self._current_accel_name = accel_name
        if FIRST_RUN:
            display_name = Gtk.accelerator_get_label(*Gtk.accelerator_parse(accel_name))
            self.show_notification(f"Hotkey is set to {display_name}", "hotkey_first_run")

    def show_launcher(self):
        if not self.window:
            self.window = UlauncherWindow(application=self)
        self.window.show()

    def show_preferences(self, page=None):
        self.window.hide()

        if self.preferences:
            self.preferences.present(page)
        else:
            self.preferences = PreferencesWindow(application=self)
            self.preferences.show(page)

    def show_notification(self, text, id=None):
        notification = Gio.Notification.new("Ulauncher")
        notification.set_body(text)
        self.send_notification(id, notification)

    def activate_query(self, _action, variant, *_):
        self.activate()
        self.query = variant.get_string()

    def dbus_method_listener(self, *_args):
        method, [raw_data], invocation, *_ = _args[4:]
        if method == "RunAction":
            try:
                data = json.loads(raw_data)
                action = data.get("action", None)
                if action == "open":
                    value = data.get("value")
                    logger.debug('Opening "%s"', value)
                    launch_detached(["xdg-open", value])
                if action == "copy":
                    value = data.get("value")
                    logger.debug('Copying "%s"', value)
                    clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
                    clipboard.set_text(value, -1)
                    clipboard.store()
            except Exception as e:
                logger.exception('Error "%s" parsing JSON message "%s"', e, data)
        else:
            logger.warning("Unknown dbus method '%s'", method)
        invocation.return_value()
