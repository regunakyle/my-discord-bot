import sqlite3
from datetime import datetime
import logging
import typing as ty


class utility:
    @classmethod
    def connectDB(self) -> tuple:
        cnxn = sqlite3.connect("./volume/db.sqlite3")
        cursor = cnxn.cursor()
        return cnxn, cursor

    @classmethod
    def runSQL(
        cls, query: str, param: ty.Optional[list] = None, rtn: bool = False
    ) -> ty.Optional[list]:
        cnxn, cursor = cls.connectDB()

        try:
            if param is None:
                cursor.execute(query)
            else:
                cursor.execute(query, param)
        except Exception as e:
            cursor.close()
            cnxn.close()
            raise ValueError(e)

        if rtn == True:
            columns = [column[0] for column in cursor.description]
            results = []
            SQLresult = cursor.fetchall()
            if len(SQLresult) > 0:
                for row in SQLresult:
                    results.append(dict(zip(columns, row)))
            else:
                results = None
            cnxn.commit()
            cursor.close()
            cnxn.close()
            return results

        cnxn.commit()
        cursor.close()
        cnxn.close()

    @staticmethod
    def strptime(strtime: str, timeIncluded: bool = True) -> datetime:
        return (
            datetime.strptime(strtime, "%Y-%m-%d %H:%M:%S")
            if timeIncluded == True
            else datetime.strptime(strtime, "%Y-%m-%d")
        )

    @staticmethod
    def strftime(dt: datetime, timeIncluded: bool = True) -> str:
        return (
            datetime.strftime(dt, "%Y-%m-%d %H:%M:%S")
            if timeIncluded == True
            else datetime.strftime(dt, "%Y-%m-%d")
        )

    @staticmethod
    def print(text: ty.Any) -> None:
        print(text)
        logging.debug(text)
