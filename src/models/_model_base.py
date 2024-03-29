import uuid

from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass

from ._guid import GUID


class ModelBase(MappedAsDataclass, DeclarativeBase):
    type_annotation_map = {
        uuid.UUID: GUID,
    }
