import sqlite3, logging, typing as ty

logger = logging.getLogger(__name__)


class utility:
    @classmethod
    def connectDB(self) -> tuple:
        cnxn = sqlite3.connect("./volume/db.sqlite3")

        def dict_factory(cursor, row):
            d = {}
            for idx, col in enumerate(cursor.description):
                d[col[0]] = row[idx]
            return d

        cnxn.row_factory = dict_factory
        cursor = cnxn.cursor()
        return cnxn, cursor

    @classmethod
    def runSQL(cls, query: str, param: ty.Optional[list] = None) -> ty.Optional[list]:
        cnxn, cursor = cls.connectDB()

        try:
            if param is None:
                cursor.execute(query)
            else:
                cursor.execute(query, param)

            SQLresult = cursor.fetchall()
            cnxn.commit()
            cursor.close()
            cnxn.close()
            return SQLresult if len(SQLresult) > 0 else None

        except Exception as e:
            cnxn.rollback()
            cursor.close()
            cnxn.close()
            raise ValueError(e)
