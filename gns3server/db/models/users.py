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

from sqlalchemy import Boolean, Column, String, event

from .base import BaseTable, generate_uuid, GUID
from gns3server.services import auth_service

import logging

log = logging.getLogger(__name__)


class User(BaseTable):

    __tablename__ = "users"

    user_id = Column(GUID, primary_key=True, default=generate_uuid)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    full_name = Column(String)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    is_superadmin = Column(Boolean, default=False)

@event.listens_for(User.__table__, 'after_create')
def create_default_super_admin(target, connection, **kw):

    hashed_password = auth_service.hash_password("admin")
    stmt = target.insert().values(
        username="admin",
        full_name="Super Administrator",
        hashed_password=hashed_password,
        is_superadmin=True
    )
    connection.execute(stmt)
    connection.commit()
    log.info("Default super admin account added")