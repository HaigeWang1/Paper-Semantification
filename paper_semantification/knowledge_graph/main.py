from neo4j import GraphDatabase

# Neo4j database connection
class Neo4jConnection:
    def __init__(self, uri, user = None, password = None):
        self._uri = uri
        self._user = user
        self._password = password
        self._driver = None

    def close(self):
        if self._driver is not None:
            self._driver.close()

    def connect(self):
        self._driver = GraphDatabase.driver(self._uri, auth=(self._user, self._password))

    def query(self, query, parameters=None, db=None):
        assert self._driver is not None, "Driver not initialized!"
        session = self._driver.session(database=db) if db is not None else self._driver.session()
        result = list(session.run(query, parameters))
        session.close()
        return result