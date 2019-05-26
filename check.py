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
                # print('正在测试', proxy)
                async with session.get(TEST_URL, proxy=real_proxy, timeout=5,
                                       allow_redirects=False) as response:  # 异步请求
                    if response.status in VALID_STATUS_CODES:  # 如果代理可用
                        self.redis.max(proxy)  # 更新该代理的状态分值
                        # print('代理可用', proxy)
                    else:
                        self.redis.decrease(proxy)  # 否则扣分
                        # print('请求响应码不合法 ', response.status, 'IP', proxy)
            except (ClientError, asyncio.TimeoutError,
                    AttributeError):  # 其他各种错误，统统扣分
                self.redis.decrease(proxy)
                # print('代理请求失败', proxy)

    def run(self):
        """
        测试主函数，执行时将把代理池中的代理全部检测一遍
        :return:
        """
        # print('测试器开始运行')
        try:
            count = self.redis.count()
            v_count = self.redis.valid_count()
            print('当前代理池中包含', count, '个代理, 其中确认有效的有', v_count, '个')
            for i in range(0, count, BATCH_TEST_SIZE):
                start = i
                stop = min(i + BATCH_TEST_SIZE, count) - 1  # 防止末尾溢出
                # print('正在测试第', start + 1, '-', stop + 1, '个代理')
                test_proxies = self.redis.batch(start, stop)  # 根据索引批量获取代理
                loop = asyncio.get_event_loop()  # 初始化事件轮询
                tasks = [self.test_single_proxy(proxy) for proxy in test_proxies]  # 列表解析，元素为函数
                loop.run_until_complete(asyncio.wait(tasks))
                sys.stdout.flush()
                time.sleep(1)
        except Exception as e:
            print('测试器发生错误', e.args)
