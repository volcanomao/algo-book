''' 演示如何读取期权链 '''

from datetime import datetime
from threading import Thread, Event
import time
from queue import Queue

from ibapi.client import EClient, Contract
from ibapi.wrapper import EWrapper
from ibapi.utils import iswrapper

class ChainReader(EWrapper, EClient):
    ''' 作为客户端和包装器 '''

    def __init__(self, addr, port, client_id):
        EClient.__init__(self, self)

        # 初始化变量
        self.conid = 0
        self.current_price = 0.0
        self.expiration = ''
        self.expirations = []
        self.exchange = ''
        self.strikes = []
        self.atm_index = -1
        self.chain = {}

        # 线程相关
        self.data_ready = Event()
        self.data_queue = Queue()

        # 连接到TWS
        self.connect(addr, port, client_id)

        # 启动客户端线程
        thread = Thread(target=self.run)
        thread.start()

    @iswrapper
    def contractDetails(self, reqId, desc):
        ''' 获取合约ID '''
        self.conid = desc.contract.conId
        self.data_ready.set()

    @iswrapper
    def tickByTickMidPoint(self, reqId, time, midpoint):
        ''' 获取当前价格 '''
        self.current_price = midpoint
        self.data_ready.set()

    @iswrapper
    def securityDefinitionOptionParameter(self, reqId, exchange, underlyingConId, tradingClass, multiplier, expirations, strikes):
        ''' 提供行权价和到期日 '''

        # 保存到期日和行权价
        self.exchange = exchange
        self.expirations = expirations
        self.strikes = strikes
        #self.data_ready.set()

    @iswrapper
    def securityDefinitionOptionParameterEnd(self, reqId):
        ''' 接收行权价/到期日后处理数据 '''

        # 找到最接近当前价格的行权价
        self.strikes = sorted(self.strikes)
        min_dist = 99999.0
        for i, strike in enumerate(self.strikes):
            if strike - self.current_price < min_dist:
                min_dist = abs(strike - self.current_price)
                self.atm_index = i
        self.atm_price = self.strikes[self.atm_index]

        # 将行权价限制在平值期权周围的+7/-7范围内
        front = self.atm_index - 7
        back = len(self.strikes) - (self.atm_index + 7)
        if front > 0:
            del self.strikes[:front]
        if back > 0:
            del self.strikes[-(back-1):]

        # 找到一个刚好超过一个月的到期日
        self.expirations = sorted(self.expirations)
        current_date = datetime.now()        
        for date in self.expirations:
            exp_date = datetime.strptime(date, '%Y%m%d')
            interval = exp_date - current_date
            if interval.days > 21:
                self.expiration = date
                print('到期日: {}'.format(self.expiration))
                break
        self.data_ready.set()

    @iswrapper
    def tickPrice(self, req_id, field, price, attribs):
        ''' 提供期权的卖价/买价 '''

        if (field != 1 and field != 2) or price == -1.0:
            return        
        
        # 确定行权价和权利
        strike = self.strikes[(req_id - 3)//2]
        right = 'C' if req_id & 1 else 'P'

        # 更新期权链
        self.data_queue.put(('price', strike, right, field, price))

    @iswrapper
    def tickSize(self, req_id, field, size):
        ''' 提供期权的卖出量/买入量 '''

        if (field != 0 and field != 3) or size == 0:
            return
        
        # 确定行权价和权利
        strike = self.strikes[(req_id - 3)//2]
        right = 'C' if req_id & 1 else 'P'

        # 更新期权链
        self.data_queue.put(('size', strike, right, field, size))

    def error(self, reqId, code, msg):
        if code != 200:
            print('错误 {}: {}'.format(code, msg))

def read_option_chain(client, ticker):

    # 定义标的股票的合约
    contract = Contract()
    contract.symbol = ticker
    contract.secType = 'STK'
    contract.exchange = 'SMART'
    contract.currency = 'USD'
    client.reqContractDetails(0, contract)
    client.data_ready.wait()
    client.data_ready.clear()

    # 获取股票的当前价格
    client.reqTickByTickData(1, contract, "MidPoint", 1, True)
    client.data_ready.wait()
    client.data_ready.clear()

    # 请求行权价和到期日
    if client.conid:
        client.reqSecDefOptParams(2, ticker, '', 'STK', client.conid)
        client.data_ready.wait()
        client.data_ready.clear()
    else:
        print('获取合约标识符失败。')
        exit()    

    # 创建股票期权合约
    req_id = 3
    if client.strikes:
        for strike in client.strikes:        
            client.chain[strike] = {}
            for right in ['C', 'P']:

                # 添加到期权链
                client.chain[strike][right] = {}

                # 定义期权合约
                contract.secType = 'OPT'
                contract.right = right
                contract.strike = strike
                contract.exchange = client.exchange
                contract.lastTradeDateOrContractMonth = client.expiration

                # 请求期权数据
                client.reqMktData(req_id, contract, '100', False, False, [])
                req_id += 1
    else:
        print('访问行权价失败')
        exit()

    # 处理队列中的数据
    while not client.data_queue.empty():
        data_type, strike, right, field, value = client.data_queue.get()
        if data_type == 'price':
            if field == 1:
                client.chain[strike][right]['bid_price'] = value
            elif field == 2:
                client.chain[strike][right]['ask_price'] = value
        elif data_type == 'size':
            if field == 0:
                client.chain[strike][right]['bid_size'] = value
            elif field == 3:
                client.chain[strike][right]['ask_size'] = value

    # 移除空元素
    client.chain = {strike: data for strike, data in client.chain.items() if data['C'] and data['P']}
    return client.chain, client.atm_price

def main():

    # 创建客户端并连接到TWS
    client = ChainReader('127.0.0.1', 7497, 0)

    # 读取期权链
    chain, atm_price = read_option_chain(client, 'IBM')
    for strike in chain:
        print('{} 看跌期权: {}'.format(strike, chain[strike]['P']))
        print('{} 看涨期权: {}'.format(strike, chain[strike]['C']))

    # 断开与TWS的连接
    client.disconnect()

if __name__ == '__main__':
    main()