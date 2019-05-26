import sys
sys.path.append("../")
import check

"""__init__"""
c = check.Checker()
print("__init__测试：", c.redis is not None)

"""run"""
c.run()
