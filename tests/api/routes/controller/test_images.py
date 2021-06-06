#!/usr/bin/env python
#
# Copyright (C) 2021 GNS3 Technologies Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import pytest
import hashlib

from fastapi import FastAPI, status
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


@pytest.fixture
def iou_32_bit_image(tmpdir) -> str:
    """
    Create a fake IOU image on disk
    """

    path = os.path.join(tmpdir, "iou_32bit.bin")
    with open(path, "wb+") as f:
        f.write(b'\x7fELF\x01\x01\x01')
    return path


@pytest.fixture
def iou_64_bit_image(tmpdir) -> str:
    """
    Create a fake IOU image on disk
    """

    path = os.path.join(tmpdir, "iou_64bit.bin")
    with open(path, "wb+") as f:
        f.write(b'\x7fELF\x02\x01\x01')
    return path


@pytest.fixture
def ios_image(tmpdir) -> str:
    """
    Create a fake IOS image on disk
    """

    path = os.path.join(tmpdir, "ios.bin")
    with open(path, "wb+") as f:
        f.write(b'\x7fELF\x01\x02\x01')
    return path


@pytest.fixture
def qcow2_image(tmpdir) -> str:
    """
    Create a fake Qemu qcow2 image on disk
    """

    path = os.path.join(tmpdir, "image.qcow2")
    with open(path, "wb+") as f:
        f.write(b'QFI\xfb')
    return path


@pytest.fixture
def invalid_image(tmpdir) -> str:
    """
    Create a fake invalid image on disk
    """

    path = os.path.join(tmpdir, "invalid_image.bin")
    with open(path, "wb+") as f:
        f.write(b'\x01\x01\x01\x01')
    return path


@pytest.fixture
def empty_image(tmpdir) -> str:
    """
    Create a fake empty image on disk
    """

    path = os.path.join(tmpdir, "empty_image.bin")
    with open(path, "wb+") as f:
        f.write(b'')
    return path


class TestImageRoutes:

    @pytest.mark.parametrize(
        "image_type, fixture_name, valid_request",
        (
            ("iou", "iou_32_bit_image", True),
            ("iou", "iou_64_bit_image", True),
            ("iou", "invalid_image", False),
            ("ios", "ios_image", True),
            ("ios", "invalid_image", False),
            ("qemu", "qcow2_image", True),
            ("qemu", "empty_image", False),
            ("wrong_type", "qcow2_image", False),
        ),
    )
    async def test_upload_image(
            self,
            app: FastAPI,
            client: AsyncClient,
            images_dir: str,
            image_type: str,
            fixture_name: str,
            valid_request: bool,
            request
    ) -> None:

        image_path = request.getfixturevalue(fixture_name)
        image_name = os.path.basename(image_path)
        image_checksum = hashlib.md5()
        with open(image_path, "rb") as f:
            image_data = f.read()
        image_checksum.update(image_data)

        response = await client.post(
            app.url_path_for("upload_image", image_name=image_name),
            params={"image_type": image_type},
            content=image_data)

        if valid_request:
            assert response.status_code == status.HTTP_201_CREATED
            assert response.json()["filename"] == image_name
            assert response.json()["checksum"] == image_checksum.hexdigest()
            assert os.path.exists(os.path.join(images_dir, image_type.upper(), image_name))
        else:
            assert response.status_code != status.HTTP_201_CREATED

    async def test_image_list(self, app: FastAPI, client: AsyncClient) -> None:

        response = await client.get(app.url_path_for("get_images"))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 4  # 4 valid images uploaded before

    async def test_image_get(self, app: FastAPI, client: AsyncClient, qcow2_image: str) -> None:

        image_name = os.path.basename(qcow2_image)
        response = await client.get(app.url_path_for("get_image", image_name=image_name))
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["filename"] == image_name

    async def test_same_image_cannot_be_uploaded(self, app: FastAPI, client: AsyncClient, qcow2_image: str) -> None:

        image_name = os.path.basename(qcow2_image)
        with open(qcow2_image, "rb") as f:
            image_data = f.read()
        response = await client.post(
            app.url_path_for("upload_image", image_name=image_name),
            params={"image_type": "qemu"},
            content=image_data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_image_delete(self, app: FastAPI, client: AsyncClient, images_dir: str, qcow2_image: str) -> None:

        image_name = os.path.basename(qcow2_image)
        response = await client.delete(app.url_path_for("delete_image", image_name=image_name))
        assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_not_found_image(self, app: FastAPI, client: AsyncClient, qcow2_image: str) -> None:

        image_name = os.path.basename(qcow2_image)
        response = await client.get(app.url_path_for("get_image", image_name=image_name))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_image_deleted_on_disk(self, app: FastAPI, client: AsyncClient, images_dir: str, qcow2_image: str) -> None:

        image_name = os.path.basename(qcow2_image)
        with open(qcow2_image, "rb") as f:
            image_data = f.read()
        response = await client.post(
            app.url_path_for("upload_image", image_name=image_name),
            params={"image_type": "qemu"},
            content=image_data)
        assert response.status_code == status.HTTP_201_CREATED

        response = await client.delete(app.url_path_for("delete_image", image_name=image_name))
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not os.path.exists(os.path.join(images_dir, "QEMU", image_name))
