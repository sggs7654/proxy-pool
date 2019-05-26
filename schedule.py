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