# proxy pool
本项目实现了一个通用爬虫代理池，主要特性如下：
- 通过付费代理API获得代理地址
- 使用Redis保存代理地址和状态信息
- 循环检测代理池中的代理地址有效性，使用一个0-100的分数指标来评估所有代理的可用状态
- 使用Flask构建web接口，随机输出高可用的代理地址，实现负载均衡
- 充分利用python的协程和多进程特性，提高代理池维护效率


1 环境依赖
---

Redis / aiohttp / requests / redis-py / Flask



2 模块架构
---

**2.1 存储模块**
- 负责代理池的存储
- 要求数据去重
- 要求动态实时地处理每个代理
    - 因此我们采用Redis的Sorted Set作为存储框架

**2.2 获取模块**
- 代理池系统的入口
- 负责捕获待检测和存储的代理ip，把结果传递给存储模块

**2.3 检测模块**
- 负责定时检测数据库中的代理
- 负责标识数据库中代理的可用状态
    - 为代理的可用性打分
    - 检测后，若代理可用，标记为满分，若代理不可用，则其分数-1，当分数过低时，将其从代理池中移除
- 检测模块只与存储模块沟通

**2.4 接口模块**
- 代理池系统的出口
- 负责提供一个Web API接口，爬虫应用通过访问接口即可获得代理
- 要求均匀地提供可用接口，实现负载均衡



3 模块分析
---

**3.1 存储模块**

- 使用[[Redis的有序集合]](https://www.runoob.com/redis/redis-sorted-sets.html)作为数据结构
    - 作用1：去重
    - 作用2：使代理根据可用性（分值）进行排序
- 当代理被检测为可用时，设其分值为100，每次检测为不可用时，其状态分值-1，当一个分值减至0时，从数据库中移除
- 新代理初始分值为10

```
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
        self.db = redis.StrictRedis(host=host, port=port, password=password, decode_responses=True)  # 建立Redis连接, decode_response=True意味着用纯str存取信息

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

    def decresse(self, proxy):
        """
        代理可用状态分-1，若分数低于最小值，则移除该代理信息
        :param proxy: 代理
        :return: 修改后的代理分数
        """
        score = self.db.zscore(REDIS_KEY, proxy)
        if score and score > MIN_SCORE:
            # print('Proxy:', proxy, '; Current Score:', score, ' -1')
            return self.db.zincrby(REDIS_KEY, -1, proxy)  # 有序集合中对指定成员的分数加上增量
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

```

**3.2 获取模块**

```
from db import RedisClient
import requests
import time

POOL_UPPER_THRESHOLD = 10000  # 数据库中的代理容量上限
PROXY_GETTER_URL = 'http://xxxxxxxxx'

class Getter:
    def __init__(self):
        self.redis = RedisClient()  # 初始化数据库连接

    def get_proxies(self):
        """
        获取代理（每次运行取10个proxy，用时1秒）
        :return: 代理列表
        """
        proxies = set()  # 返回的代理列表，元素格式要求：'xxx,xxx,xxx,xxx:xxxx'
        for i in range(1):  # 由于本人使用的付费代理大概5秒给一个新ip，所以不需要频繁请求
            r = requests.get(PROXY_GETTER_URL)
            # print(r.text)
            if 'false' in r.text:  # 判断是否出错
                raise Warning(r.text)
            else:
                proxy = r.text.split()[0]  # 格式清理：按空格分割
                proxies.add(proxy)
            # time.sleep(0.1)  # 控制每秒访问次数
        return list(proxies)

    def is_over_threshold(self, upper=POOL_UPPER_THRESHOLD):
        """
        判断是否达到了代理池限制
        """
        if self.redis.count() >= upper:
            return True
        else:
            return False

    def run(self):
        # print('获取器开始执行')
        if not self.is_over_threshold():
            proxies = self.get_proxies()
            for proxy in proxies:
                self.redis.add(proxy)

```

**3.3 检测模块**

关于异步IO，可参考[廖雪峰-python异步与协程](https://www.liaoxuefeng.com/wiki/1016959663602400/1017959540289152)

```
import asyncio  # asyncio可以实现单线程并发IO操作
import aiohttp  # asyncio实现了TCP、UDP、SSL等协议，aiohttp则是基于asyncio实现的HTTP框架
import time
import sys

try:
    from aiohttp import ClientError
except:
    from aiohttp import ClientProxyConnectionError as ProxyConnectionError
from db import RedisClient  # 这里注意检查引用

VALID_STATUS_CODES = [200]
TEST_URL = 'http://www.baidu.com'  # 用来测试响应的网址
BATCH_TEST_SIZE = 50  # 同一时间协程测试的代理数量


class Checker(object):
    def __init__(self):  # 建立数据库连接
        self.redis = RedisClient()

    async def test_single_proxy(self, proxy):
        """
        测试单个代理
        :param proxy: 代理地址
        :return:
        """
        conn = aiohttp.TCPConnector(verify_ssl=False)
        async with aiohttp.ClientSession(connector=conn) as session:  # 类似文件处理中的with open.. as...
            try:
                if isinstance(proxy, bytes):  # 编码格式校验
                    proxy = proxy.decode('utf-8')
                real_proxy = 'http://' + proxy  # 补上http头
                print('正在测试', proxy)
                async with session.get(TEST_URL, proxy=real_proxy, timeout=10,
                                       allow_redirects=False) as response:  # 异步请求
                    if response.status in VALID_STATUS_CODES:  # 如果代理可用
                        self.redis.max(proxy)  # 更新该代理的状态分值
                        print('代理可用', proxy)
                    else:
                        self.redis.decrease(proxy)  # 否则扣分
                        print('请求响应码不合法 ', response.status, 'IP', proxy)
            except (ClientError, asyncio.TimeoutError,
                    AttributeError):  # 其他各种错误，统统扣分
                self.redis.decrease(proxy)
                print('代理请求失败', proxy)

    def run(self):
        """
        测试主函数，执行时将把代理池中的代理全部检测一遍
        :return:
        """
        print('测试器开始运行')
        try:
            count = self.redis.count()
            print('当前剩余', count, '个代理')
            for i in range(0, count, BATCH_TEST_SIZE):
                start = i
                stop = min(i + BATCH_TEST_SIZE, count) - 1  # 防止末尾溢出
                print('正在测试第', start + 1, '-', stop + 1, '个代理')
                test_proxies = self.redis.batch(start, stop)  # 根据索引批量获取代理
                loop = asyncio.get_event_loop()  # 初始化事件轮询
                tasks = [self.test_single_proxy(proxy) for proxy in test_proxies]  # 列表解析，元素为函数
                loop.run_until_complete(asyncio.wait(tasks))
                sys.stdout.flush()
                time.sleep(1)
        except Exception as e:
            print('测试器发生错误', e.args)

```

**3.4 接口模块**
```
from flask import Flask, g  # g 保存的是当前请求的全局变量，不同的请求会有不同的全局变量，通过不同的thread id区别

from db import RedisClient

__all__ = ['app']
app = Flask(__name__)  # flask应用初始化


def get_conn():
    if not hasattr(g, 'redis'):  # hasattr() 函数用于判断对象是否包含对应的属性
        g.redis = RedisClient()
    return g.redis


@app.route('/')  # 主页
def index():
    return '<h2>Welcome to Proxy Pool System</h2>'


@app.route('/random')  # 获取随机代理
def get_proxy():
    """
    Get a proxy
    :return: 随机代理
    """
    conn = get_conn()
    return conn.random()


@app.route('/count')  # 获取代理池总量
def get_counts():
    """
    Get the count of proxies
    :return: 代理池总量
    """
    conn = get_conn()
    return str(conn.count())


if __name__ == '__main__':
    app.run()
```

**3.5 调度模块**

```

# 检查周期
TESTER_CYCLE = 1
# 获取周期
GETTER_CYCLE = 1
# 三个开关
TESTER_ENABLED = True
GETTER_ENABLED = True
API_ENABLED = True

import time
from multiprocessing import Process
from webAPI import app
from getter import Getter
from check import Checker
from db import RedisClient


class Scheduler:
    def schedule_checker(self, cycle=TESTER_CYCLE):
        """
        定时检测代理
        """
        checker = Checker()
        while True:
            # print('检测器开始运行')
            checker.run()
            time.sleep(cycle)

    def schedule_getter(self, cycle=GETTER_CYCLE):
        """
        定时获取代理
        """
        getter = Getter()
        while True:
            # print('开始获取代理')
            getter.run()
            time.sleep(cycle)

    def schedule_api(self):
        """
        开启API
        """
        app.run()

    def run(self):
        print('代理池开始运行')

        if GETTER_ENABLED:
            getter_process = Process(target=self.schedule_getter)
            getter_process.start()

        if TESTER_ENABLED:
            tester_process = Process(target=self.schedule_checker)
            tester_process.start()

        if API_ENABLED:
            api_process = Process(target=self.schedule_api)
            api_process.start()
```
