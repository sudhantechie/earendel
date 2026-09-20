#
# This file is licensed under the Affero General Public License (AGPL) version 3.
#
# Copyright 2022 The Matrix.org Foundation C.I.C.
# Copyright (C) 2023 New Vector, Ltd
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# See the GNU Affero General Public License for more details:
# <https://www.gnu.org/licenses/agpl-3.0.html>.
#
# Originally licensed under the Apache License, Version 2.0:
# <http://www.apache.org/licenses/LICENSE-2.0>.
#
# [This file includes modifications made by New Vector Limited]
#
#

import json
import os
import urllib.parse
from hashlib import blake2b
from importlib.metadata import Distribution, PackageNotFoundError

import earendel
from earendel.earendel_rust import get_rust_file_digest


def check_rust_lib_up_to_date() -> None:
    """For editable installs check if the rust library is outdated and needs to
    be rebuilt.
    """

    # Get the location of the editable install.
    earendel_root = get_earendel_source_directory()
    if earendel_root is None:
        return None

    # Get the hash of all Rust source files
    rust_path = os.path.join(earendel_root, "rust")
    if not os.path.exists(rust_path):
        return None

    hash = _hash_rust_files_in_directory(earendel_root)

    if hash != get_rust_file_digest():
        raise Exception("Rust module outdated. Please rebuild using `poetry install`")


def _hash_rust_files_in_directory(earendel_root: str) -> str:
    """Get the hash of all files in a directory (recursively)"""

    src_directory = os.path.abspath(os.path.join(earendel_root, "rust", "src"))

    paths = []

    dirs = [src_directory]
    while dirs:
        dir = dirs.pop()
        with os.scandir(dir) as d:
            for entry in d:
                if entry.is_dir():
                    dirs.append(entry.path)
                else:
                    paths.append(entry.path)

    # Manually add Cargo.toml's, Cargo.lock and build.rs to the hash, since
    # changes to these files should also invalidate the built module.
    paths.append(os.path.join(earendel_root, "rust", "Cargo.toml"))
    paths.append(os.path.join(earendel_root, "rust", "build.rs"))
    paths.append(os.path.join(earendel_root, "Cargo.lock"))
    paths.append(os.path.join(earendel_root, "Cargo.toml"))

    # We sort to make sure that we get a consistent and well-defined ordering.
    paths.sort()

    hasher = blake2b()

    for path in paths:
        with open(path, "rb") as f:
            hasher.update(f.read())

    return hasher.hexdigest()


def get_earendel_source_directory() -> str | None:
    """Try and find the source directory of earendel for editable installs (like
    those used in development).

    Returns None if not an editable install (or otherwise can't find the source
    directory).
    """

    # Try and find the installed matrix-earendel package.
    try:
        package = Distribution.from_name("matrix-earendel")
    except PackageNotFoundError:
        # The package is not found, so it's not installed and so must be being
        # pulled out from a local directory (usually the current one).
        earendel_dir = os.path.dirname(earendel.__file__)
        earendel_root = os.path.abspath(os.path.join(earendel_dir, ".."))

        # Double check we've not gone into site-packages...
        if os.path.basename(earendel_root) == "site-packages":
            return None

        # ... and it looks like the root of a python project.
        if not os.path.exists("pyproject.toml"):
            return None

        return earendel_root

    # Read the `direct_url.json` metadata for the package. This won't exist for
    # packages installed via a repository/etc.
    # c.f. https://packaging.python.org/en/latest/specifications/direct-url/
    direct_url_json = package.read_text("direct_url.json")
    if direct_url_json is None:
        # No direct url metadata. Check if this is an egg-info install.
        #
        # An egg-info install is when there exists a `matrix_earendel.egg-info`
        # directory alongside the source tree, containing the package metadata.
        # This allows discovering packages in the current directory, without
        # installing them properly to the environment wide `site-packages`
        # directory.
        #
        # When searching for a package, Python will look for `.egg-info` files
        # in the current working directory before looking in `site-packages`.
        # This means that when running Earendel (or the tests) from the source
        # tree Python will pick up the earendel package from the egg-info
        # install.
        #
        # Poetry will create an egg-info install when running `poetry install`.
        #
        # The combination of the above means that it is very common for
        # developers (e.g. running tests) to encounter egg-info installs.
        #
        # In this case we can find the source tree by looking for the
        # `matrix_earendel.egg-info/PKG-INFO` file, and going up two directories
        # from there.

        metadata_path = package.locate_file("matrix_earendel.egg-info/PKG-INFO")
        if not os.path.exists(str(metadata_path)):
            # Not an egg-info install.
            return None

        # `metadata_path` points to the egg-info/PKG-INFO file, so go up two
        # directories to get the root of the source tree.
        source_dir = metadata_path.parent.parent
        return os.fspath(source_dir)

    # c.f. https://packaging.python.org/en/latest/specifications/direct-url/ for
    # the format
    direct_url_dict: dict = json.loads(direct_url_json)

    # `url` must exist as a key, and point to where we fetched the repo from.
    project_url = urllib.parse.urlparse(direct_url_dict["url"])

    # If its not a local file then we must have built the rust libs either a)
    # after we downloaded the package, or b) we built the download wheel.
    if project_url.scheme != "file":
        return None

    # And finally if its not an editable install then the files can't have
    # changed since we installed the package.
    if not direct_url_dict.get("dir_info", {}).get("editable", False):
        return None

    return project_url.path
