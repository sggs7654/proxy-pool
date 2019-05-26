import sys
sys.path.append("../")
import db
import redis

r = redis.StrictRedis(host='localhost', port=6379, decode_responses=True)  # 创建用于测试的数据库连接

"""__init__"""
client = db.RedisClient()  # 加载目标测试模块
print("__init__测试：", client.db is not None)

"""add"""
test_proxy = "000.000.000.000:1111"
if r.zscore(db.REDIS_KEY, test_proxy) is not None:  # 检查测试痕迹
    r.zrem(db.REDIS_KEY, test_proxy)
print("add测试1", client.add(test_proxy) is 1)  # 正常添加
print("add测试2", client.add(test_proxy) is None)  # 重复添加
r.zrem(db.REDIS_KEY, test_proxy)  # 清理测试痕迹

"""random, batch"""
test_proxies = {"000.000.000.000:1111": 10, "000.000.000.000:2222": 100, "000.000.000.000:3333": 100}
for proxy in test_proxies.keys():  # 检查测试痕迹
    if r.zscore(db.REDIS_KEY, proxy) is not None:
        r.zrem(db.REDIS_KEY, proxy)
r.zadd(db.REDIS_KEY, test_proxies)  # 添加测试代理
result = set()
for i in range(20):  # 多次测试
    result.add(client.random())
print("random测试1：", "000.000.000.000:1111" not in result)
print("random测试2: ", len(result) is not 1)
print("batch测试：", client.batch(0, 2))
for proxy in test_proxies.keys():  # 清理测试痕迹
    if r.zscore(db.REDIS_KEY, proxy) is not None:
        r.zrem(db.REDIS_KEY, proxy)

"""decrease"""
test_proxy = "000.000.000.000:1111"
if r.zscore(db.REDIS_KEY, test_proxy) is not None:  # 检查测试痕迹
    r.zrem(db.REDIS_KEY, test_proxy)
r.zadd(db.REDIS_KEY, {test_proxy: 1})  # 添加测试数据
print("decrease测试1：", client.decrease(test_proxy) == 0)
print("decrease测试2：", client.decrease(test_proxy) is 1)
if r.zscore(db.REDIS_KEY, test_proxy) is not None:  # 清理测试痕迹
    r.zrem(db.REDIS_KEY, test_proxy)

"""exists, max, count, all"""
test_proxy = "000.000.000.000:1111"
if r.zscore(db.REDIS_KEY, test_proxy) is not None:  # 检查测试痕迹
    r.zrem(db.REDIS_KEY, test_proxy)
print("exists测试1：", client.exists(test_proxy) is False)
r.zadd(db.REDIS_KEY, {test_proxy: 10})  # 添加测试数据
print("exists测试2：", client.exists(test_proxy) is True)
client.max(test_proxy)
print("max测试：", r.zscore(db.REDIS_KEY, test_proxy) == db.MAX_SCORE)
print("count测试：", client.count())
print("all测试：", client.all())
if r.zscore(db.REDIS_KEY, test_proxy) is not None:  # 清理测试痕迹
    r.zrem(db.REDIS_KEY, test_proxy)

print("【db模块测试结束】")

