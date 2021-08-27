import sqlite3
from datetime import datetime
import logging


class utility:
    def __connectDB():
        cnxn = sqlite3.connect("./db.sqlite3")
        cursor = cnxn.cursor()
        return cnxn, cursor

    @classmethod
    def runSQL(cls, query: str, param=None, rtn=False):
        cnxn, cursor = cls.__connectDB()

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

    def strptime(strtime: str, timeIncluded=True):
        return (
            datetime.strptime(strtime, "%Y-%m-%d %H:%M:%S")
            if timeIncluded == True
            else datetime.strptime(strtime, "%Y-%m-%d")
        )

    def strftime(dt: datetime, timeIncluded=True):
        return (
            datetime.strftime(dt, "%Y-%m-%d %H:%M:%S")
            if timeIncluded == True
            else datetime.strftime(dt, "%Y-%m-%d")
        )

    def print(text: str):
        print(text)
        logging.debug(text)
