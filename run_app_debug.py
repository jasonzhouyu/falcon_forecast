import os
import sys

# 打印当前环境信息
print(f"Python版本: {sys.version}")
print(f"当前工作目录: {os.getcwd()}")
print(f"脚本所在目录: {os.path.dirname(os.path.abspath(__file__))}")

# 构建模板文件夹路径
template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'templates')
print(f"模板文件夹路径: {template_dir}")
print(f"模板文件夹是否存在: {os.path.exists(template_dir)}")

# 检查模板文件是否存在
for file in ['index.html', 'result.html', 'error.html']:
    file_path = os.path.join(template_dir, file)
    print(f"{file} 是否存在: {os.path.exists(file_path)}")

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入Flask和其他模块
try:
    from flask import Flask, render_template
    print("Flask导入成功")
except ImportError as e:
    print(f"Flask导入失败: {e}")
    sys.exit(1)

# 创建Flask应用
app = Flask(__name__)

# 明确设置模板文件夹路径
app.template_folder = template_dir
print(f"设置的模板文件夹路径: {app.template_folder}")

# 导入应用模块
try:
    from app.app import index, predict
    print("应用模块导入成功")
except ImportError as e:
    print(f"应用模块导入失败: {e}")
    sys.exit(1)

# 注册路由
app.route('/')(index)
app.route('/predict', methods=['POST'])(predict)

# 运行应用
if __name__ == '__main__':
    print("启动应用...")
    app.run(debug=True, host='0.0.0.0', port=5001)
