from db import RedisClient
import requests
import time

POOL_UPPER_THRESHOLD = 10000  # 数据库中的代理容量上限
# 时长优先
PROXY_GETTER_URL = 'http://dynamic.goubanjia.com/dynamic/get/76321e8eafa2628ae577bfcdb522b4b5.html?sep=4&random=true'
# 速度优先
# PROXY_GETTER_URL = 'http://dynamic.goubanjia.com/dynamic/get/76321e8eafa2628ae577bfcdb522b4b5.html?sep=4'
# 此代理获取地址每秒访问不可超过10次，每个代理最长有效期为1min


class Getter:
    def __init__(self):
        self.redis = RedisClient()  # 初始化数据库连接

    def get_proxies(self):
        """
        获取代理（每次运行取10个proxy，用时1秒）
        :return: 代理列表
        """
        proxies = set()  # 返回的代理列表，元素格式要求：'xxx,xxx,xxx,xxx:xxxx'
        for i in range(1):  # 由于付费代理大概5秒给一个新ip，所以不需要频繁请求
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
        """
        每秒run一次
        :return:
        """
        if not self.is_over_threshold():
            proxies = self.get_proxies()
            # print('获取器运行，得到', len(proxies), '个代理地址')
            for proxy in proxies:
                self.redis.add(proxy)
