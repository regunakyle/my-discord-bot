from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass


class ModelBase(MappedAsDataclass, DeclarativeBase):
    pass
