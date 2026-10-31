"""Translatable status and error texts from the device layer.

The device layer has no Qt dependency, so it cannot translate on its own. Messages are
created as :class:`Text`: a plain ``str`` holding the English text, which also keeps the
English template (with ``%1``, ``%2`` placeholders) and its arguments. The GUI translates
the template and fills in the arguments (see ``linto.gui.i18n.localize``).
"""

from __future__ import annotations


class Text(str):
    """English message text that remembers its template for later translation."""

    template: str
    args: tuple[str, ...]

    def __new__(cls, template: str, *args: object) -> "Text":
        str_args = tuple(str(a) for a in args)
        obj = super().__new__(cls, fill_placeholders(template, str_args))
        obj.template = template
        obj.args = str_args
        return obj


def fill_placeholders(template: str, args: tuple[str, ...]) -> str:
    """Replace %1, %2, ... with the given arguments (highest number first)."""
    text = template
    for i in range(len(args), 0, -1):
        text = text.replace(f"%{i}", args[i - 1])
    return text
