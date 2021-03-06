import logging
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import ProgrammingError
from alembic import command
from alembic.config import Config
from sqlparse import parsestream

from os.path import join

log = logging.getLogger(__name__)

# Python 2/3 compatibility
try:
    stringtype = unicode
except NameError:
    stringtype = str


def execute(engine, file_path):
    with open(file_path) as f:
        for parsed_statement in parsestream(f):
            statement = stringtype(parsed_statement).strip()
            if statement == '':
                continue
            if log is not None:
                log.info("Running: {statement}".format(statement=statement))
            try:
                engine.execute(statement)
            except ProgrammingError as e:
                if log is not None:
                    log.warning(e.message)
                else:
                    raise e


class DatabaseManager(object):
    def __init__(self, engine, sql_dir, alembic_path, orm_base, version='head'):
        """

        :param engine: Database connection engine
        :type engine: sqlalchemy.engine.Engine
        :param sql_dir: Path to directory containing all SQL scripts
        :type sql_dir: string
        :param alembic_path: Path to Alembic folder
        :param alembic_path: string
        :param orm_base: Base sqlalchemy class, for metadata access
        :type orm_base: sqlalchemy.ext.declarative.DeclarativeMeta
        :param version: Current database version (for Alembic)
        :type version: string
        """
        self.engine = engine
        self.sql_dir = sql_dir
        self.alembic_version = version
        self.orm_base = orm_base
        self.alembic_path = alembic_path

    def current_version(self):
        """
        Display Alembic current version
        """
        command.current(self.alembic_config())

    def upgrade_database(self):
        command.upgrade(self.alembic_config(), self.alembic_version)

    def alembic_config(self):
        config = join(self.alembic_path, 'alembic.ini')
        versions = join(self.alembic_path, 'versions')
        script_location = self.alembic_path

        alembic_cfg = Config(config)
        alembic_cfg.set_section_option('alembic', 'version_locations', versions)
        alembic_cfg.set_section_option('alembic', 'script_location', script_location)
        alembic_cfg.set_section_option('alembic', 'sqlalchemy.url', str(self.engine.url))

        return alembic_cfg

    def initialise_database(self, primary_files, secondary_files, pg_functions=[], pg_triggers=[]):
        """

        :param primary_files: SQL files to execute in first pass, before object creation
        :type primary_files: list of string
        :param secondary_files: SQL files to execute in second pass, after object creation
        :type secondary_files: list of string
        :type pg_functions: list
        :type pg_triggers: list
        """
        session = sessionmaker(bind=self.engine)()
        session.connection().connection.set_isolation_level(0)
        for sql_file in primary_files:
            execute(session, join(self.sql_dir, sql_file))
        self.orm_base.metadata.create_all(self.engine)
        for pg_func in pg_functions:
            self.engine.execute(pg_func)
        for pg_trigger in pg_triggers:
            self.engine.execute(pg_trigger)
        command.stamp(self.alembic_config(), self.alembic_version)
        for sql_file in secondary_files:
            execute(session, join(self.sql_dir, sql_file))

    def execute_scripts(self, sql_filenames):
        """

        :param sql_filenames: Names of SQL files to execute, in order
        :type sql_filenames: list of string
        """
        session = sessionmaker(bind=self.engine)()
        session.connection().connection.set_isolation_level(0)
        for sql_file in sql_filenames:
            execute(session, join(self.sql_dir, sql_file))
