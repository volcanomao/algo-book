''' Demonstrates how an application can request the current time '''
from datetime import datetime
from threading import Thread
import time

from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.utils import iswrapper

class SimpleClient(EWrapper, EClient):
    ''' Serves as the client and the wrapper '''

    def __init__(self, addr, port, client_id):
        EClient. __init__(self, self)

        # Connect to TWS
        self.connect(addr, port, client_id)

        # Launch the client thread
        thread = Thread(target=self.run)
        thread.start()

    @iswrapper
    def currentTime(self, cur_time):
        t = datetime.fromtimestamp(cur_time)
        print('Current time: {}'.format(t))

    @iswrapper
    def error(self, req_id, code, msg):
        print('Error {}: {}'.format(code, msg))

def main():

    # Create the client and connect to TWS
    client = SimpleClient('127.0.0.1', 7497, 0)

    # Request the current time
    client.reqCurrentTime()

    # Sleep while the request is processed
    time.sleep(0.5)

    # Disconnect from TWS
    client.disconnect()

if __name__ == '__main__':
    main()

