import sys
sys.path.append("../")
import getter

"""__init__"""
g = getter.Getter()
print("__init__测试：", g.redis is not None)

"""get_proxies"""
print("get_proxies测试：", g.get_proxies())

"""is_over_threshold"""
print("is_over_threshold测试：", g.is_over_threshold(upper=g.redis.count()) is True)
print("is_over_threshold测试：", g.is_over_threshold(upper=g.redis.count()+1) is False)

"""run"""
origin_num = g.redis.count()
g.run()
print("run测试：", g.redis.count() == origin_num + 1)
