# -*- coding: utf-8 -*-
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

import uuid
import pydantic

from uuid import UUID
from fastapi.encoders import jsonable_encoder
from typing import List

from gns3server import schemas
from gns3server.db.repositories.templates import TemplatesRepository
from gns3server.controller import Controller
from gns3server.controller.controller_error import (
    ControllerBadRequestError,
    ControllerNotFoundError,
    ControllerForbiddenError
)

TEMPLATE_TYPE_TO_SHEMA = {
    "cloud": schemas.CloudTemplate,
    "ethernet_hub": schemas.EthernetHubTemplate,
    "ethernet_switch": schemas.EthernetSwitchTemplate,
    "docker": schemas.DockerTemplate,
    "dynamips": schemas.DynamipsTemplate,
    "vpcs": schemas.VPCSTemplate,
    "virtualbox": schemas.VirtualBoxTemplate,
    "vmware": schemas.VMwareTemplate,
    "iou": schemas.IOUTemplate,
    "qemu": schemas.QemuTemplate
}

DYNAMIPS_PLATFORM_TO_SHEMA = {
    "c7200": schemas.C7200DynamipsTemplate,
    "c3745": schemas.C3745DynamipsTemplate,
    "c3725": schemas.C3725DynamipsTemplate,
    "c3600": schemas.C3600DynamipsTemplate,
    "c2691": schemas.C2691DynamipsTemplate,
    "c2600": schemas.C2600DynamipsTemplate,
    "c1700": schemas.C1700DynamipsTemplate
}

# built-in templates have their compute_id set to None to tell clients to select a compute
BUILTIN_TEMPLATES = [
    {
        "template_id": uuid.uuid3(uuid.NAMESPACE_DNS, "cloud"),
        "template_type": "cloud",
        "name": "Cloud",
        "default_name_format": "Cloud{0}",
        "category": "guest",
        "symbol": ":/symbols/cloud.svg",
        "compute_id": None,
        "builtin": True
    },
    {
        "template_id": uuid.uuid3(uuid.NAMESPACE_DNS, "nat"),
        "template_type": "nat",
        "name": "NAT",
        "default_name_format": "NAT{0}",
        "category": "guest",
        "symbol": ":/symbols/cloud.svg",
        "compute_id": None,
        "builtin": True
    },
    {
        "template_id": uuid.uuid3(uuid.NAMESPACE_DNS, "vpcs"),
        "template_type": "vpcs",
        "name": "VPCS",
        "default_name_format": "PC{0}",
        "category": "guest",
        "symbol": ":/symbols/vpcs_guest.svg",
        "base_script_file": "vpcs_base_config.txt",
        "compute_id": None,
        "builtin": True
    },
    {
        "template_id": uuid.uuid3(uuid.NAMESPACE_DNS, "ethernet_switch"),
        "template_type": "ethernet_switch",
        "name": "Ethernet switch",
        "console_type": "none",
        "default_name_format": "Switch{0}",
        "category": "switch",
        "symbol": ":/symbols/ethernet_switch.svg",
        "compute_id": None,
        "builtin": True
    },
    {
        "template_id": uuid.uuid3(uuid.NAMESPACE_DNS, "ethernet_hub"),
        "template_type": "ethernet_hub",
        "name": "Ethernet hub",
        "default_name_format": "Hub{0}",
        "category": "switch",
        "symbol": ":/symbols/hub.svg",
        "compute_id": None,
        "builtin": True
    },
    {
        "template_id": uuid.uuid3(uuid.NAMESPACE_DNS, "frame_relay_switch"),
        "template_type": "frame_relay_switch",
        "name": "Frame Relay switch",
        "default_name_format": "FRSW{0}",
        "category": "switch",
        "symbol": ":/symbols/frame_relay_switch.svg",
        "compute_id": None,
        "builtin": True
    },
    {
        "template_id": uuid.uuid3(uuid.NAMESPACE_DNS, "atm_switch"),
        "template_type": "atm_switch",
        "name": "ATM switch",
        "default_name_format": "ATMSW{0}",
        "category": "switch",
        "symbol": ":/symbols/atm_switch.svg",
        "compute_id": None,
        "builtin": True
    },
]


class TemplatesService:

    def __init__(self, templates_repo: TemplatesRepository):

        self._templates_repo = templates_repo
        self._controller = Controller.instance()

    def get_builtin_template(self, template_id: UUID) -> dict:

        for builtin_template in BUILTIN_TEMPLATES:
            if builtin_template["template_id"] == template_id:
                return jsonable_encoder(builtin_template)

    async def get_templates(self) -> List[dict]:

        templates = []
        db_templates = await self._templates_repo.get_templates()
        for db_template in db_templates:
            templates.append(db_template.asjson())
        for builtin_template in BUILTIN_TEMPLATES:
            templates.append(jsonable_encoder(builtin_template))
        return templates

    async def create_template(self, template_data: schemas.TemplateCreate) -> dict:

        try:
            # get the default template settings
            template_settings = jsonable_encoder(template_data, exclude_unset=True)
            template_schema = TEMPLATE_TYPE_TO_SHEMA[template_data.template_type]
            template_settings_with_defaults = template_schema.parse_obj(template_settings)
            settings = template_settings_with_defaults.dict()
            if template_data.template_type == "dynamips":
                # special case for Dynamips to cover all platform types that contain specific settings
                dynamips_template_schema = DYNAMIPS_PLATFORM_TO_SHEMA[settings["platform"]]
                dynamips_template_settings_with_defaults = dynamips_template_schema.parse_obj(template_settings)
                settings = dynamips_template_settings_with_defaults.dict()
        except pydantic.ValidationError as e:
            raise ControllerBadRequestError(f"JSON schema error received while creating new template: {e}")
        db_template = await self._templates_repo.create_template(template_data.template_type, settings)
        template = db_template.asjson()
        self._controller.notification.controller_emit("template.created", template)
        return template

    async def get_template(self, template_id: UUID) -> dict:

        db_template = await self._templates_repo.get_template(template_id)
        if db_template:
            template = db_template.asjson()
        else:
            template = self.get_builtin_template(template_id)
        if not template:
            raise ControllerNotFoundError(f"Template '{template_id}' not found")
        return template

    async def update_template(self, template_id: UUID, template_data: schemas.TemplateUpdate) -> dict:

        if self.get_builtin_template(template_id):
            raise ControllerForbiddenError(f"Template '{template_id}' cannot be updated because it is built-in")
        template = await self._templates_repo.update_template(template_id, template_data)
        if not template:
            raise ControllerNotFoundError(f"Template '{template_id}' not found")
        template = template.asjson()
        self._controller.notification.controller_emit("template.updated", template)
        return template

    async def duplicate_template(self, template_id: UUID) -> dict:

        if self.get_builtin_template(template_id):
            raise ControllerForbiddenError(f"Template '{template_id}' cannot be duplicated because it is built-in")
        db_template = await self._templates_repo.duplicate_template(template_id)
        if not db_template:
            raise ControllerNotFoundError(f"Template '{template_id}' not found")
        template = db_template.asjson()
        self._controller.notification.controller_emit("template.created", template)
        return template

    async def delete_template(self, template_id: UUID) -> None:

        if self.get_builtin_template(template_id):
            raise ControllerForbiddenError(f"Template '{template_id}' cannot be deleted because it is built-in")
        if await self._templates_repo.delete_template(template_id):
            self._controller.notification.controller_emit("template.deleted", {"template_id": str(template_id)})
        else:
            raise ControllerNotFoundError(f"Template '{template_id}' not found")
