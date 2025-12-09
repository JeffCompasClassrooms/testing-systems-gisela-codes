import http.client
import json
import os
import pytest
import shutil
import subprocess
import sys
import time
import urllib


from squirrel_db import SquirrelDB

todo = pytest.mark.skip(reason='todo: pending spec')

def describe_squirrel_server():

    @pytest.fixture(autouse=True)  # auto use means this is used in EVERY describe function.
    def setup_and_cleanup_database():
        # setup the database
        if os.path.isfile('squirrel_db.db'):
            os.remove('squirrel_db.db')
        
        # figure out how to copy the empty db to the one the squirrel server will actually use.
        if os.path.isfile('empty_squirrel_db.db'):
            shutil.copy('empty_squirrel_db.db', 'squirrel_db.db')
       
        yield

    @pytest.fixture(autouse=True, scope='session')
    def start_and_stop_server():
        # Always start the custom squirrel server (not http.server)
        server_process = subprocess.Popen([sys.executable, 'squirrel_server.py'])
        
        # Wait for server to start
        time.sleep(2)
        
        # Verify server started successfully
        max_retries = 5
        for i in range(max_retries):
            try:
                conn = http.client.HTTPConnection('localhost:8080', timeout=1)
                conn.request("GET", "/squirrels")
                response = conn.getresponse()
                conn.close()
                break
            except:
                if i < max_retries - 1:
                    time.sleep(1)
                else:
                    server_process.kill()
                    raise Exception("Server failed to start")
        
        yield
        
        # stop the server process
        server_process.terminate()
        server_process.wait()
        print("Server stopped.")

    # you can use http_client or you can use requests. 
    # or you could decide that you don't want to do a fixture for this.
    # notice that this fixture is only passed in where we want it. Here it
    # is used just to clean up the url.
    @pytest.fixture
    def http_client():
        conn = http.client.HTTPConnection('localhost:8080')
        return conn

    # a fixture to create a fake squirrel? You write your own!
    @pytest.fixture
    def request_body():
        return urllib.parse.urlencode({ 'name': 'Sam', 'size': 'large' })

    # a fixture to construct the headers? Yes please!
    @pytest.fixture
    def request_headers():
        return { 'Content-Type': 'application/x-www-form-urlencoded' }

    # a fixture that returns the instance of the DB...
    @pytest.fixture
    def db():
        return SquirrelDB()

    
    # you are going to make lots of squirrels... 
    @pytest.fixture
    def make_a_squirrel(db):
        db.createSquirrel("Fred", "small")

    # ok, here go the tests...
    def describe_get_squirrels():

        # just checking to see that it returns 200 is valuable, but very incomplete.
        def it_returns_200_status_code(http_client):
            http_client.request("GET", "/squirrels")
            response = http_client.getresponse()
            http_client.close()

            assert response.status == 200

        # yes, you need to test that it returns the correct content type. 
        # Probably EVERY type of request should return the right content type, shouldn't it? (hint)
        def it_returns_json_content_type_header(http_client):
            http_client.request("GET", "/squirrels")
            response = http_client.getresponse()
            http_client.close()

            assert response.getheader('Content-Type') == "application/json"

        # empty
        def it_returns_empty_json_array(http_client):
            http_client.request("GET", "/squirrels")
            response = http_client.getresponse()
            response_body = response.read()
            http_client.close()

            # assert response_body == b'[]'
            assert json.loads(response_body) == []

        # one
        def it_returns_json_array_with_one_squirrel(http_client, make_a_squirrel):
            http_client.request("GET", "/squirrels")
            response = http_client.getresponse()
            response_body = response.read()
            http_client.close()

            expected = [ {'id': 1, 'name': 'Fred', 'size': 'small' } ]

            assert json.loads(response_body) == expected




    def describe_post_squirrels():

        @pytest.fixture
        def incomplete_request_body():
            return urllib.parse.urlencode({'name': 'Sam'})

        def it_returns_400_for_incomplete_post(http_client, incomplete_request_body, request_headers):
            http_client.request("POST", "/squirrels", body=incomplete_request_body, headers=request_headers)
            response = http_client.getresponse()
            http_client.close()

            assert response.status == 400
            
        def it_creates_a_new_squirrel_in_the_database(http_client, request_body, request_headers, db):
            http_client.request("POST", "/squirrels", body=request_body, headers=request_headers)
            response = http_client.getresponse()
            response_body = response.read()
            http_client.close()

            assert response.status == 201
            # assert response.getheader('Content-Type') == "application/json"
    
            squirrels = db.getSquirrels()
            assert len(squirrels) == 1
            assert squirrels[0]['name'] == 'Sam'
            assert squirrels[0]['size'] == 'large'
        
    def describe_put_squirrels():

        def it_returns_204_and_updates_an_existing_squirrel(http_client, make_a_squirrel, request_headers, db):
            update_body = urllib.parse.urlencode({'name': 'Chip', 'size': 'large'})

            http_client.request("PUT", "/squirrels/1", body=update_body, headers=request_headers)
            response = http_client.getresponse()
            response_body = response.read()
            http_client.close()

            assert response.status == 204

            squirrels = db.getSquirrels()
            assert len(squirrels) == 1
            assert squirrels[0]['id'] == 1
            assert squirrels[0]['name'] == 'Chip'
            assert squirrels[0]['size'] == 'large'

        def it_returns_404_when_updating_a_missing_squirrel(http_client, request_headers, db):
            update_body = urllib.parse.urlencode({'name': 'Chip', 'size': 'large'})
            http_client.request("PUT", "/squirrels/1", body=update_body, headers=request_headers)
            response = http_client.getresponse()
            response_body = response.read()
            http_client.close()

            assert response.status == 404
            squirrels = db.getSquirrels()
            assert squirrels == []


    def describe_delete_squirrels():

        def it_returns_204_and_deletes_an_existing_squirrel(http_client, make_a_squirrel, db):

            squirrels_before = db.getSquirrels()
            assert len(squirrels_before) == 1

            http_client.request("DELETE", "/squirrels/1")
            response = http_client.getresponse()
            response_body = response.read()
            http_client.close()

            assert response.status == 204

            squirrels_after = db.getSquirrels()
            assert len(squirrels_after) == 0

        def it_returns_404_when_deleting_a_missing_squirrel(http_client, db):

            http_client.request("DELETE", "/squirrels/1")
            response = http_client.getresponse()
            response_body = response.read()
            http_client.close()

            assert response.status == 404

            squirrels = db.getSquirrels()
            assert squirrels == []
