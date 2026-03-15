import os
import sys

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 打印当前目录和模板路径
print(f"当前工作目录: {os.getcwd()}")
print(f"模板文件夹路径: {os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'templates')}")
print(f"模板文件夹是否存在: {os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'templates'))}")

# 导入并运行应用
from app.app import app

if __name__ == '__main__':
    # 明确设置模板文件夹路径
    app.template_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'templates')
    print(f"设置的模板文件夹路径: {app.template_folder}")
    # 运行应用
    app.run(debug=True, host='0.0.0.0', port=5001)
