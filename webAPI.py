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
