import redis  # redis-py文档：https://pypi.org/project/redis/
from random import choice  # choice() 方法返回一个列表，元组或字符串的随机项

MAX_SCORE = 100
MIN_SCORE = 0
INITIAL_SCORE = 10
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_PASSWORD = None
REDIS_KEY = 'proxies'


class RedisClient(object):

    def __init__(self, host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD):
        """
        初始化
        :param host: Redis Address
        :param port: Redis Port
        :param password: Redis Password
        """
        # 建立Redis连接, decode_response=True意味着用纯str存取信息
        self.db = redis.StrictRedis(host=host, port=port, password=password, decode_responses=True)

    def add(self, proxy, score=INITIAL_SCORE):
        """
        添加新代理，并将其可用状态分设为初始分值
        :param proxy: 代理信息，格式一般为: “xx.xxx.xxx.xxx:xxxx” (ip:port)
        :param score: 代理的初始分值
        :return: 添加结果
        """
        if not self.db.zscore(REDIS_KEY, proxy):  # 避免proxy的重复添加
            return self.db.zadd(REDIS_KEY, {proxy: score})

    def random(self):
        # （这个函数可优化，考虑满分代理不存在时，优先返回高分代理）
        #   (返回满分代理时，可以考率在返回时把该代理分数减1~5，以实现负载均衡）
        """
        随机获取有效代理：先尝试获取满分代理，若满分代理不存在，则随机获取代理，若依然无结果则异常
        :return: 随机代理
        """
        result = self.db.zrangebyscore(REDIS_KEY, MAX_SCORE, MAX_SCORE)
        if len(result):
            return choice(result)
        else:
            result = self.db.zrangebyscore(REDIS_KEY, MIN_SCORE, MAX_SCORE)
            if len(result):
                return choice(result)
            else:
                raise RuntimeError("PoolEmptyError")

    def decrease(self, proxy):
        """
        代理可用状态分扣去一定值，若分数低于最小值，则移除该代理信息
        :param proxy: 代理
        :return: 修改后的代理分数
        """
        score = self.db.zscore(REDIS_KEY, proxy)
        if score and score > MIN_SCORE:
            # print('Proxy:', proxy, '; Current Score:', score, ' -1')
            return self.db.zincrby(REDIS_KEY, -20, proxy)  # 有序集合中对指定成员的分数加上增量
        else:
            # print('Proxy:', proxy, '; Current Score:', score, ' REMOVE')
            return self.db.zrem(REDIS_KEY, proxy)  # 移除有序集合中的一个或多个成员

    def exists(self, proxy):
        """
        判断该代理是否已存在于数据库中
        :param proxy:  代理
        :return: 是否存在
        """
        return self.db.zscore(REDIS_KEY, proxy) is not None

    def max(self, proxy):
        """
        将代理的可用状态分设为MAX_SCORE
        :param proxy:  代理
        :return: 操作结果
        """
        # print('Proxy:', proxy, 'is accessible, set score:', MAX_SCORE)
        return self.db.zadd(REDIS_KEY, {proxy: MAX_SCORE})

    def count(self):
        """
        获取数据库中的代理数量
        :return: 数量
        """
        return self.db.zcard(REDIS_KEY)

    def valid_count(self):
        """
        返回数据库中的满分代理数量
        :return:
        """
        return len(self.db.zrangebyscore(REDIS_KEY, MAX_SCORE, MAX_SCORE))

    def all(self):
        """
        获取数据库中的全部代理
        :return: 代理列表
        """
        return self.db.zrangebyscore(REDIS_KEY, MIN_SCORE, MAX_SCORE)

    def batch(self, start, stop):
        """
        批量获取
        :param start: 开始索引（物理索引）
        :param stop: 结束索引（物理索引）
        :return: 代理列表
        """
        return self.db.zrevrange(REDIS_KEY, start, stop)
