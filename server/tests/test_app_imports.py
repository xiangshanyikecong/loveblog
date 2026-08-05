# Love Journal - a private journal + blog + real-time interaction platform for couples.
# Copyright (C) 2026 Love Journal Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Import smoke test — guards against import-time failures in the FastAPI app.

The whole app (every router + every route object) is built at import time. A
route that declares a no-body status code (204 / 304 / 1xx) together with a
truthy ``response_model`` trips an assertion *when the route is registered*,
which crashes app startup before a single request is served.

A real example this guards against: ``@router.delete(..., status_code=204)`` on
a handler annotated ``-> None`` inside a module that uses
``from __future__ import annotations``. The stringized ``"None"`` annotation is
evaluated by FastAPI to ``NoneType`` (a truthy response_model), so the route
fails to register and the process exits on boot.

Importing the app here turns that whole class of bug into a fast, dependency
-light unit test that a CI run (or a quick local ``pytest``) catches.

Run directly without pytest:  ``python tests/test_app_imports.py``
"""
from __future__ import annotations


def _iter_concrete_routes(routes):
    """Flatten FastAPI's lazy included-router wrappers across versions."""
    for route in routes:
        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            yield from _iter_concrete_routes(original_router.routes)
        else:
            yield route


def test_app_imports_and_builds() -> None:
    from fastapi import FastAPI

    from app.main import app

    assert isinstance(app, FastAPI)

    # A representative slice of routes must be present — guards against a router
    # silently failing to register (which would also be an import-time problem).
    paths = set(app.openapi()["paths"])
    assert "/v1/cottage/wishes/{wid}" in paths
    assert "/v1/cottage/watch/sources/{wsid}" in paths
    assert "/v1/cottage/watch/state" in paths


def test_no_body_status_routes_have_no_response_model() -> None:
    """No 204/304/1xx route may carry a response model.

    If the app imported at all this already holds (FastAPI would have raised on
    registration), but the explicit scan gives a precise, actionable message if
    a future change reintroduces the pattern.
    """
    from fastapi.routing import APIRoute

    from app.main import app

    no_body_status = {204, 304} | set(range(100, 200))
    offenders = [
        route.path
        for route in _iter_concrete_routes(app.routes)
        if isinstance(route, APIRoute)
        and route.status_code in no_body_status
        and route.response_model is not None
    ]
    assert not offenders, f"no-body status routes must not set a response_model: {offenders}"


if __name__ == "__main__":
    test_app_imports_and_builds()
    test_no_body_status_routes_have_no_response_model()
    print("ok: app imports and all no-body routes are clean")
