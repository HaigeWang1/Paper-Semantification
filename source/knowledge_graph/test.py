from main import Neo4jConnection

class HelloWorldExample:

    def __init__(self, uri):
        self.neo4j_connection = Neo4jConnection(uri, "neo4j", "password")
        self.neo4j_connection.connect()


    def print_greeting(self, message):
        with self.neo4j_connection._driver.session() as session:
            greeting = session.execute_write(self._create_and_return_greeting, message)
            print(greeting)

    @staticmethod
    def _create_and_return_greeting(tx, message):
        result = tx.run("CREATE (a:Greeting) "
                        "SET a.message = $message "
                        "RETURN a.message + ', from node ' + id(a)", message=message)
        return result.single()[0]


if __name__ == "__main__":
    # This test is to check if the connection to the Neo4j database is successful
    # If the connection is successful, a node with the message "hello, world!" will be created in the Neo4j database
    greeter = HelloWorldExample("bolt://localhost:7687")
    greeter.print_greeting("hello, world!")