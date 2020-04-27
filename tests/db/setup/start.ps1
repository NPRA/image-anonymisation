$container_name = "oracle_test_database"
docker rm $container_name
docker run -e ORACLE_PWD=password -p 1521:1521 --name $container_name  oracle/database:18.4.0-xe