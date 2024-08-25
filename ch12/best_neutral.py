''' 演示如何计算具有最佳预期收益的跨式/宽跨式策略 '''

from chain_reader import ChainReader, read_option_chain

def compute_probabilities(chain, current_price):

    # 初始化信念
    beliefs = {}
    for strike in chain:
        if strike < current_price:
            price = chain[strike]['P']['ask_price']
            beliefs[strike + price] = 0.0  # 对于OTM看跌期权，信念初始化为0
        elif strike > current_price:
            price = chain[strike]['C']['ask_price']
            beliefs[strike - price] = 0.0  # 对于OTM看涨期权，信念初始化为0

    # 更新概率
    prob_len = len(beliefs)
    prob_keys = list(beliefs.keys())
    for i, strike in enumerate(chain):

        # 处理OTM看跌期权
        if strike < current_price:
            size = chain[strike]['P']['ask_size']
            for j in range(i, prob_len):
                beliefs[prob_keys[j]] += size  # 累加看跌期权的数量

        # 处理OTM看涨期权
        elif strike > current_price:
            size = chain[strike]['C']['ask_size']
            for j in range(0, i):
                beliefs[prob_keys[j]] += size  # 累加看涨期权的数量

    # 将信念替换为概率
    total = sum(list(beliefs.values()))
    for key in beliefs:
        beliefs[key] /= total  # 归一化概率
    return beliefs

def best_neutral(probs, chain, spreads):

    profits = []
    max_profit = -1000.0  # 初始化最大利润为一个很小的值
    max_index = -1
    for i, spread in enumerate(spreads):

        # 行权价格和期权溢价
        K1 = spread[0]
        K2 = spread[1]
        P1 = chain[K1]['P']['ask_price']  # 看跌期权的溢价
        P2 = chain[K2]['C']['ask_price']  # 看涨期权的溢价

        # 遍历概率
        profit = 0.0
        for j, belief in enumerate(probs):

            if belief < K1:
                profit += ((K1 - belief) - (P1 + P2)) * probs[belief]/(P1 + P2)  # 计算利润
            elif belief > K2:
                profit += ((belief - K2) - (P1 + P2)) * probs[belief]/(P1 + P2)  # 计算利润
            else:
                profit += -(P1 + P2) * probs[belief]/(P1 + P2)  # 计算利润

        # 检查具有最大利润的跨式/宽跨式策略
        profits.append(profit)
        if profit > max_profit:
            max_profit = profit
            max_index = i

    return max_profit, max_index

def main():

    # 创建客户端并连接到TWS
    client = ChainReader('127.0.0.1', 7497, 0)
    chain, atm_price = read_option_chain(client, 'IBM')
    client.disconnect()

    # 计算不同价格下的概率
    probs = compute_probabilities(chain, atm_price)

    # 为期权链创建跨式/宽跨式策略
    strikes = list(chain.keys())
    rev = strikes[::-1]
    atm_index = strikes.index(atm_price)
    spreads = []
    for i in range(0, atm_index-1):
        spreads.append([strikes[atm_index-i], strikes[atm_index+i]])  # 创建跨式/宽跨式策略

    # Find the best spread
    max_profit, max_index = best_spread(probs, chain, spreads)
    print('Best return: {} for {}'.format(max_profit, spreads[max_index]))

if __name__ == '__main__':
    main()