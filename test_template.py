import os
from flask import Flask, render_template

app = Flask(__name__)

# 打印当前目录和相关路径
print(f"当前工作目录: {os.getcwd()}")
print(f"当前文件目录: {os.path.dirname(os.path.abspath(__file__))}")

# 尝试设置模板文件夹路径
app.template_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'templates')
print(f"模板文件夹路径: {app.template_folder}")
print(f"模板文件夹是否存在: {os.path.exists(app.template_folder)}")
print(f"index.html是否存在: {os.path.exists(os.path.join(app.template_folder, 'index.html'))}")

# 测试渲染模板
try:
    with app.test_request_context():
        template = render_template('index.html')
        print("模板渲染成功!")
except Exception as e:
    print(f"模板渲染失败: {e}")
