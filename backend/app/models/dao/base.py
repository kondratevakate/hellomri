from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select
from sqlalchemy import update as sqlalchemy_update, delete as sqlalchemy_delete
from app.services.database import async_session_maker


class BaseDao:
    model = None

    @classmethod
    async def find_one_or_none_by_id(cls, id: int):
        """
        Asynchronously finds and returns one instance of the model by the specified criteria or None.

        Arguments:
            id: Criteria for filtering in the form of a record identifier.

        Returns:
            Model instance or None if nothing is found.
        """
        async with async_session_maker() as session:
            query = select(cls.model).filter_by(id=id)
            result = await session.execute(query)
            return result.scalar_one_or_none()
        

    @classmethod
    async def find_one_or_none(cls, **filter_by):
        """
        Asynchronously finds and returns one instance of the model by the specified criteria or None.

        Arguments:
            **filter_by: Criteria for filtering in the form of named parameters.

        Returns:
            Model instance or None if nothing is found.
        """
        async with async_session_maker() as session:
            query = select(cls.model).filter_by(**filter_by)
            result = await session.execute(query)
            return result.scalar_one_or_none()


    @classmethod
    async def find_all(cls, **filter_by):
        """
        Asynchronously finds and returns all instances of the model that match the specified criteria.

        Arguments:
            **filter_by: Criteria for filtering in the form of named parameters.

        Returns:
            List of model instances.
        """
        async with async_session_maker() as session:
            query = select(cls.model).filter_by(**filter_by)
            result = await session.execute(query)
            return result.scalars().all()


    @classmethod
    async def add(cls, **values):
        """
        Asynchronously creates a new model instance with the specified values.

        Arguments:
            **values: Named parameters for creating a new model instance.

        Returns:
            Created model instance.
        """
        async with async_session_maker() as session:
            async with session.begin():
                new_instance = cls.model(**values)
                session.add(new_instance)
                try:
                    await session.commit()
                except SQLAlchemyError as e:
                    await session.rollback()
                    raise e
                return new_instance


    @classmethod
    async def add_many(cls, instances: list[dict]):
        """
        Asynchronously creates multiple new model instances with the specified values.

        Arguments:
            instances: List of dictionaries, where each dictionary contains named parameters for creating a new
            model instance.

        Returns:
            List of created model instances.
        """
        async with async_session_maker() as session:
            async with session.begin():
                new_instances = [cls.model(**values) for values in instances]
                session.add_all(new_instances)
                try:
                    await session.commit()
                except SQLAlchemyError as e:
                    await session.rollback()
                    raise e
                return new_instances


    @classmethod
    async def update(cls, filter_by, **values):
        """
        Asynchronously updates model instances that match the filtering criteria specified in filter_by
        with new values specified in values.

        Arguments:
            filter_by: Criteria for filtering in the form of named parameters.
            **values: Named parameters for updating model instance values.

        Returns:
            Number of updated model instances.
        """
        async with async_session_maker() as session:
            async with session.begin():
                query = (
                    sqlalchemy_update(cls.model)
                    .where(*[getattr(cls.model, k) == v for k, v in filter_by.items()])
                    .values(**values)
                    .execution_options(synchronize_session="fetch")
                )
                result = await session.execute(query)
                try:
                    await session.commit()
                except SQLAlchemyError as e:
                    await session.rollback()
                    raise e
                return result.rowcount


    @classmethod
    async def delete(cls, delete_all: bool = False, **filter_by):
        """
        Asynchronously deletes model instances that match the filtering criteria specified in filter_by.

        Arguments:
            delete_all: If True, deletes all model instances without filtering.
            **filter_by: Criteria for filtering in the form of named parameters.

        Returns:
            Number of deleted model instances.
        """
        if delete_all is False:
            if not filter_by:
                raise ValueError("At least one parameter must be specified for deletion.")

        async with async_session_maker() as session:
            async with session.begin():
                query = sqlalchemy_delete(cls.model).filter_by(**filter_by)
                result = await session.execute(query)
                try:
                    await session.commit()
                except SQLAlchemyError as e:
                    await session.rollback()
                    raise e
                return result.rowcount