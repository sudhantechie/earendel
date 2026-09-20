#
# This file is licensed under the Affero General Public License (AGPL) version 3.
#
# Copyright (C) 2025 New Vector, Ltd
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# See the GNU Affero General Public License for more details:
# <https://www.gnu.org/licenses/agpl_3.0.html>.
#
#


from typing import TYPE_CHECKING, cast

from earendel.api.auth.mas import MasDelegatedAuth
from earendel.api.errors import EarendelError
from earendel.http.server import DirectServeJsonResource

if TYPE_CHECKING:
    from earendel.app.generic_worker import GenericWorkerStore
    from earendel.http.site import EarendelRequest
    from earendel.server import HomeServer


class MasBaseResource(DirectServeJsonResource):
    def __init__(self, hs: "HomeServer"):
        auth = hs.get_auth()
        assert isinstance(auth, MasDelegatedAuth)

        self._is_request_from_mas = auth.is_request_using_the_shared_secret

        DirectServeJsonResource.__init__(self, extract_context=True)
        self.store = cast("GenericWorkerStore", hs.get_datastores().main)
        self.hostname = hs.hostname

    def assert_request_is_from_mas(self, request: "EarendelRequest") -> None:
        """Assert that the request is coming from MAS itself, not a regular user.

        Throws a 403 if the request is not coming from MAS.
        """
        if not self._is_request_from_mas(request):
            raise EarendelError(403, "This endpoint must only be called by MAS")
